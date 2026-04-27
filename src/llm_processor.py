"""
src/llm_processor.py
--------------------
Stage 2 — Script Generation

3-call pipeline:
  Call 1 — Extract   : pull every topic, concept, and fact from the transcript
  Call 2 — Describe  : Feynman-layered explanation with theory + practice tracks
  Call 3 — Write     : produce the final word-for-word podcast script

Returns a RecapScript dataclass — the contract passed to tts_generator.py.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RecapScript:
    class_name:     str
    date:           str
    intro:          str           = ""
    overview:       str           = ""
    key_points:     list[str]     = field(default_factory=list)
    deeper_dive:    str           = ""
    quiz_questions: list[str]     = field(default_factory=list)
    takeaway:       str           = ""
    outro:          str           = ""
    full_script:    str           = ""
    error:          Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return bool(self.full_script.strip()) and self.error is None

    def to_tts_text(self) -> str:
        return self.full_script

    def key_points_display(self) -> str:
        if not self.key_points:
            return "No key points extracted."
        return "\n".join(f"{i}. {pt}" for i, pt in enumerate(self.key_points, 1))

    def quiz_display(self) -> str:
        if not self.quiz_questions:
            return ""
        return "\n".join(f"Q{i}: {q}" for i, q in enumerate(self.quiz_questions, 1))


# ---------------------------------------------------------------------------
# Shared system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert educational podcast host — a brilliant teaching assistant
who turns any lecture into a crisp, engaging audio review.

Your voice is:
- Warm and encouraging, like a study buddy who actually paid attention
- Direct and efficient — students are busy, no padding
- Concrete — always use examples, analogies, real-world connections
- Spoken — every sentence must sound natural out loud\
"""

_SYSTEM_PROMPT_LIVELY = """\
You are an expert educational podcast host — a brilliant, funny teaching assistant
who turns any lecture into a crisp, engaging, and entertaining audio review.

Your voice is:
- Warm, funny, and encouraging — like a study buddy who actually paid attention AND has great timing
- Direct and efficient — students are busy, but learning should be fun
- Concrete — always use examples, analogies, real-world connections
- Spoken — every sentence must sound natural out loud
- Lively — sprinkle in light jokes, witty asides, and relatable human moments
- Never cringe — keep humour clever and natural, never forced\
"""


# ---------------------------------------------------------------------------
# Call 1 — Extract
# ---------------------------------------------------------------------------

def _prompt_extract(transcript) -> str:
    return f"""\
You are reading a class transcript. Your job is ONLY to extract information — \
do not summarise, do not explain, do not skip anything.

CONTEXT:
- Course: {transcript.class_name}
- Instructor: {transcript.instructor}
- Length: {transcript.word_count:,} words

TRANSCRIPT:
{transcript.clean_text[:50000]}

---

List EVERY distinct topic, concept, term, tool, formula, and example mentioned \
in the transcript. Be exhaustive — nothing should be left out.

Format:
TOPIC: <n>
DETAIL: <one sentence of raw fact from the transcript>

Repeat for every single concept. Do not group. Do not summarise.\
"""


# ---------------------------------------------------------------------------
# Call 2 — Describe (Feynman layered, dual theory/practice tracks)
# ---------------------------------------------------------------------------

def _prompt_describe(extracted: str, transcript) -> str:
    return f"""\
Below is a raw extraction of every concept from a class transcript.

For each concept, produce a Feynman-layered explanation with both theory and \
practice tracks. This serves two audiences: students who missed the class and \
students reviewing for an exam.

EXTRACTED CONCEPTS:
{extracted}

---

Format each concept exactly as:

CONCEPT: <n>
SIMPLE: <explain it like the listener has no background — 2 sentences max>
UNIVERSITY: <build on the simple explanation with proper terminology and theory — 3 sentences>
EXPERT: <how a professional actually thinks about this concept — 1-2 sentences>
SCENARIO: <one concrete real-world situation where this concept applies>
TRAP: <what a student gets wrong about this in an exam or on the job — 1 sentence>

Cover every concept. Do not skip any.\
"""


# ---------------------------------------------------------------------------
# Call 3 — Write
# ---------------------------------------------------------------------------

def _prompt_write(described: str, transcript, lively: bool = False) -> str:
    lively_instruction = ""
    if lively:
        lively_instruction = """
TONE: Make this lively and fun. Include:
- 1-2 light jokes or witty observations naturally woven in
- Relatable asides (e.g. "Yes, this actually makes sense once you see it")
- Occasional informal language to keep it human
- Enthusiasm — this host genuinely loves this stuff
Keep humour clever and brief. Never forced.
"""

    return f"""\
You are writing a word-for-word podcast script for a spoken audio recap of a class.

Below are Feynman-layered descriptions of every concept from the class. Your job \
is to turn them into a natural, engaging podcast script that covers ALL of them. \
The script should serve both students who missed the class and those reviewing for \
an exam.
{lively_instruction}
DESCRIBED CONCEPTS:
{described}

---

OUTPUT FORMAT — produce each section with its label in square brackets.
Write ONLY the spoken words. No markdown, no bullet symbols.

[INTRO]
2 sentences. Open with energy. Name the course only. Do not mention the date or time.

[OVERVIEW]
2-3 sentences. Give a roadmap of everything covered today.

[KEY POINTS]
8 to 20 key concepts. Each on its own line.
Format: CONCEPT NAME: simple explanation anyone can follow. Why it matters in practice.

[DEEPER DIVE]
For each of the 3 most important concepts, cover all 5 layers:
1. Simple explanation anyone can follow
2. University-level explanation with proper terminology
3. How an expert actually thinks about it
4. A real-world scenario where it applies
5. The most common misunderstanding — what goes wrong in an exam or on the job

[QUIZ]
3 self-test questions that check real understanding. One per line.

[TAKEAWAY]
One sentence. The single most important lesson from everything covered.
Start with: "If you remember only one thing from today..."

[OUTRO]
2 sentences. Warm close.

---
Target: 15 minutes spoken (1200 to 1500 words).
Plain spoken English only. Cover every theme — do not omit any topic.\
"""


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_section(text: str, section: str) -> str:
    pattern = rf"\[{section}\](.*?)(?=\[[A-Z ]+\]|$)"
    match   = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_key_points(raw: str) -> list[str]:
    points = []
    for line in raw.split("\n"):
        line = line.strip().lstrip("•-–*0123456789.) ").strip()
        if len(line) > 10:
            points.append(line)
    return points


def _parse_quiz(raw: str) -> list[str]:
    questions = []
    for line in raw.split("\n"):
        line = line.strip().lstrip("Q0123456789.: ").strip()
        if line.endswith("?") or len(line) > 20:
            questions.append(line)
    return questions[:3]


def _assemble_script(intro, overview, key_points, deeper_dive,
                     quiz_questions, takeaway, outro) -> str:
    parts = []
    if intro:
        parts.append(intro)
    if overview:
        parts.append(overview)
    if key_points:
        parts.append("Let's walk through the key concepts.")
        for point in key_points:
            parts.append(point)
    if deeper_dive:
        parts.append("Now let's go deeper on the most important ideas from today.")
        parts.append(deeper_dive)
    if quiz_questions:
        parts.append(
            "Before we wrap up, here are a few quick questions to test yourself. "
            "Pause and think about each one."
        )
        for q in quiz_questions:
            parts.append(q)
    if takeaway:
        parts.append(takeaway)
    if outro:
        parts.append(outro)
    return "\n\n".join(filter(None, parts))


def _parse_response(raw: str, transcript) -> RecapScript:
    intro          = _extract_section(raw, "INTRO")
    overview       = _extract_section(raw, "OVERVIEW")
    key_points     = _parse_key_points(_extract_section(raw, "KEY POINTS"))
    deeper_dive    = _extract_section(raw, "DEEPER DIVE")
    quiz_questions = _parse_quiz(_extract_section(raw, "QUIZ"))
    takeaway       = _extract_section(raw, "TAKEAWAY")
    outro          = _extract_section(raw, "OUTRO")

    full_script = _assemble_script(
        intro, overview, key_points, deeper_dive,
        quiz_questions, takeaway, outro
    )

    if not full_script.strip():
        full_script = raw

    return RecapScript(
        class_name     = transcript.class_name,
        date           = transcript.date,
        intro          = intro,
        overview       = overview,
        key_points     = key_points,
        deeper_dive    = deeper_dive,
        quiz_questions = quiz_questions,
        takeaway       = takeaway,
        outro          = outro,
        full_script    = full_script,
    )


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

def _call_openai(prompt: str, max_tokens: int = 4096, lively: bool = False) -> str:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set. Add it to your .env file.")
    client        = OpenAI(api_key=api_key)
    system_prompt = _SYSTEM_PROMPT_LIVELY if lively else _SYSTEM_PROMPT
    response      = client.chat.completions.create(
        model      = "gpt-4o-mini",
        max_tokens = max_tokens,
        messages   = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_recap(transcript, lively: bool = False) -> RecapScript:
    """
    3-call pipeline:
      1. Extract  — pull every concept from the transcript
      2. Describe — Feynman-layered explanation with theory + practice tracks
      3. Write    — produce the final podcast script
    lively: if True, adds jokes and human touches to the script
    """
    if not transcript.is_valid:
        return RecapScript(
            class_name = transcript.class_name,
            date       = transcript.date,
            error      = transcript.error or "Invalid transcript.",
        )

    logger.info(
        "Transcript length — %d chars / %d words",
        len(transcript.clean_text), transcript.word_count
    )
    logger.info("Starting 3-call pipeline for: %s (lively=%s)", transcript.class_name, lively)

    try:
        # Call 1 — Extract
        logger.info("Call 1 — Extracting concepts...")
        extracted = _call_openai(_prompt_extract(transcript), max_tokens=8192)
        logger.info("Extraction complete — %d chars", len(extracted))

        # Call 2 — Describe
        logger.info("Call 2 — Describing concepts (Feynman layers)...")
        described = _call_openai(_prompt_describe(extracted, transcript), max_tokens=8192)
        logger.info("Descriptions complete — %d chars", len(described))

        # Call 3 — Write
        logger.info("Call 3 — Writing podcast script (lively=%s)...", lively)
        raw_script = _call_openai(
            _prompt_write(described, transcript, lively=lively),
            max_tokens = 4096,
            lively     = lively,
        )
        logger.info("Script written — %d chars", len(raw_script))

        script = _parse_response(raw_script, transcript)
        logger.info(
            "Recap ready — %d key points, %d quiz questions, %d chars",
            len(script.key_points), len(script.quiz_questions), len(script.full_script)
        )
        return script

    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        return RecapScript(
            class_name = transcript.class_name,
            date       = transcript.date,
            error      = str(exc),
        )
