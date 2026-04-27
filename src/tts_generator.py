"""
src/tts_generator.py
--------------------
Stage 3 — Audio Generation

Converts a RecapScript into an MP3 file.

Provider hierarchy:
  1. OpenAI TTS  — best quality, requires OPENAI_API_KEY
  2. gTTS        — free fallback, no API key needed
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Voice mapping — Female and Male options
VOICE_MAP = {
    "Female": "nova",
    "Male":   "onyx",
}

_TTS_CHUNK_MAX = 4000


@dataclass
class AudioResult:
    success:           bool
    file_path:         Optional[str] = None
    provider:          str           = ""
    duration_estimate: str           = ""
    error:             Optional[str] = None

    def summary(self) -> str:
        if self.success:
            return (
                f"✅ Audio saved → {self.file_path} "
                f"({self.duration_estimate}, {self.provider.upper()})"
            )
        return f"❌ Audio failed: {self.error}"


def _chunk_text(text: str, max_chars: int = _TTS_CHUNK_MAX) -> list[str]:
    """Split text into chunks that respect sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    sentence_end = re.compile(r'(?<=[.!?])\s+')
    sentences    = sentence_end.split(text)

    chunks, current, current_len = [], [], 0
    for sent in sentences:
        if current_len + len(sent) + 1 > max_chars and current:
            chunks.append(" ".join(current))
            current, current_len = [sent], len(sent)
        else:
            current.append(sent)
            current_len += len(sent) + 1

    if current:
        chunks.append(" ".join(current))
    return chunks


def _estimate_duration(text: str) -> str:
    """Estimate audio duration at 140 words per minute."""
    words   = len(text.split())
    seconds = int((words / 140) * 60)
    return f"~{seconds // 60}m {seconds % 60}s"


def _safe_filename(text: str, max_len: int = 40) -> str:
    safe = re.sub(r"[^\w\s-]", "", text)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_len] or "recap"


def _generate_openai(text: str, output_path: Path, voice: str) -> None:
    """Generate MP3 via OpenAI TTS."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set.")

    client = OpenAI(api_key=api_key)
    chunks = _chunk_text(text)
    logger.info("OpenAI TTS: %d chunk(s), voice=%s", len(chunks), voice)

    all_bytes = bytearray()
    for i, chunk in enumerate(chunks):
        logger.info("  Chunk %d/%d (%d chars)", i + 1, len(chunks), len(chunk))
        response = client.audio.speech.create(
            model           = "tts-1",
            voice           = voice,
            input           = chunk,
            response_format = "mp3",
        )
        all_bytes.extend(response.content)
        if i < len(chunks) - 1:
            time.sleep(0.3)

    output_path.write_bytes(bytes(all_bytes))


def _generate_gtts(text: str, output_path: Path) -> None:
    """Generate MP3 via gTTS — free, no API key required."""
    try:
        from gtts import gTTS
    except ImportError:
        raise RuntimeError("gTTS not installed. Run: pip install gtts")
    logger.info("gTTS: generating audio")
    gTTS(text=text, lang="en", slow=False).save(str(output_path))


def generate_audio(script, voice: str = "Female", filename: Optional[str] = None) -> AudioResult:
    if not script.is_valid:
        return AudioResult(
            success = False,
            error   = script.error or "Invalid script.",
        )

    tts_text = script.to_tts_text()

    # ADD THESE LINES:
    max_words  = 2100  # 140 wpm × 15 mins
    word_count = len(tts_text.split())
    if word_count > max_words:
        tts_text = " ".join(tts_text.split()[:max_words])
        logger.warning("Script trimmed to 15 min limit (%d → %d words)", word_count, max_words)

    openai_voice = VOICE_MAP.get(voice, "nova")

    if not filename:
        filename = f"recap_{_safe_filename(script.class_name)}_{int(time.time())}"
    output_path = OUTPUT_DIR / f"{filename}.mp3"

    provider = "openai" if os.environ.get("OPENAI_API_KEY") else "gtts"
    duration = _estimate_duration(tts_text)

    try:
        if provider == "openai":
            _generate_openai(tts_text, output_path, voice=openai_voice)
        else:
            _generate_gtts(tts_text, output_path)

        result = AudioResult(
            success           = True,
            file_path         = str(output_path),
            provider          = provider,
            duration_estimate = duration,
        )
        logger.info(result.summary())
        return result

    except Exception as exc:
        logger.error("TTS failed: %s", exc)
        return AudioResult(success=False, provider=provider, error=str(exc))
