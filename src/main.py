"""
src/main.py
-----------
Entry point — Gradio web interface for the Educational Recap pipeline.

Pipeline:
  1. data_processor  → load_transcript()  → TranscriptData
  2. llm_processor   → generate_recap()   → RecapScript
  3. tts_generator   → generate_audio()   → AudioResult + MP3

Run:
    python src/main.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import gradio as gr

from data_processor import load_transcript
from llm_processor  import generate_recap
from tts_generator  import generate_audio

logging.basicConfig(
    level  = logging.INFO,
    format = "%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

SAMPLE_PATH = Path("data/raw/sample_transcript.txt")


def run_pipeline(transcript_text: str, transcript_file, url_input: str,
                 voice_choice: str, lively_mode: bool):
    """
    Full pipeline: transcript → LLM recap → audio.
    Yields progress updates after each stage so the UI updates in real time.
    """

    gr.Info("🎙️ Your audio lesson is being prepared. Please be patient — this may take a minute.")

    # Resolve input source
    if transcript_file is not None:
        source = transcript_file.name
    elif url_input.strip():
        from data_processor import load_url
        yield "⏳ Stage 1 of 3 — Fetching article from URL...", "", "", "", None
        transcript = load_url(url_input.strip())
        if not transcript.is_valid:
            yield f"❌ Could not load URL: {transcript.error}", "", "", "", None
            return
        stage1_msg = (
            f"✅ Stage 1 complete — {transcript.word_count:,} words loaded\n"
            f"   Source: {url_input.strip()[:60]}\n\n"
            f"⏳ Stage 2 of 3 — Generating recap script with OpenAI..."
        )
        yield stage1_msg, "", "", "", None
        script = generate_recap(transcript, lively=lively_mode)
        if not script.is_valid:
            yield f"❌ Script generation failed: {script.error}", "", "", "", None
            return
        stage2_msg = (
            f"✅ Stage 1 complete — {transcript.word_count:,} words loaded\n\n"
            f"✅ Stage 2 complete — {len(script.key_points)} key points extracted\n\n"
            f"⏳ Stage 3 of 3 — Converting script to audio..."
        )
        yield stage2_msg, script.key_points_display(), script.quiz_display(), _format_script(script), None
        audio = generate_audio(script, voice=voice_choice)
        final_msg = (
            f"✅ Stage 1 complete — article fetched\n\n"
            f"✅ Stage 2 complete — {len(script.key_points)} key points extracted\n\n"
            f"✅ Stage 3 complete — Audio ready\n"
            f"   Duration: {audio.duration_estimate} | Provider: {audio.provider.upper()}\n\n"
            f"🎙️  Your recap podcast is ready!"
        ) if audio.success else (
            f"✅ Stages 1 and 2 complete\n⚠️  Audio failed: {audio.error}"
        )
        yield final_msg, script.key_points_display(), script.quiz_display(), _format_script(script), audio.file_path if audio.success else None
        return
    elif transcript_text.strip():
        source = transcript_text
    else:
        yield "❌ Please paste a transcript, upload a file, or enter a URL.", "", "", "", None
        return

    # Stage 1 — Load transcript
    yield "⏳ Stage 1 of 3 — Loading transcript...", "", "", "", None

    transcript = load_transcript(source)
    if not transcript.is_valid:
        yield f"❌ Could not load transcript: {transcript.error}", "", "", "", None
        return

    stage1_msg = (
        f"✅ Stage 1 complete — {transcript.word_count:,} words loaded\n"
        f"   Class: {transcript.class_name}\n\n"
        f"⏳ Stage 2 of 3 — Generating recap script with OpenAI..."
    )
    yield stage1_msg, "", "", "", None

    # Stage 2 — Generate recap script
    script = generate_recap(transcript, lively=lively_mode)
    if not script.is_valid:
        yield f"❌ Script generation failed: {script.error}", "", "", "", None
        return

    stage2_msg = (
        f"✅ Stage 1 complete — {transcript.word_count:,} words loaded\n"
        f"   Class: {transcript.class_name}\n\n"
        f"✅ Stage 2 complete — {len(script.key_points)} key points extracted\n\n"
        f"⏳ Stage 3 of 3 — Converting script to audio..."
    )
    yield (
        stage2_msg,
        script.key_points_display(),
        script.quiz_display(),
        _format_script(script),
        None,
    )

    # Stage 3 — Generate audio
    audio = generate_audio(script, voice=voice_choice)

    if not audio.success:
        final_msg = (
            f"✅ Stage 1 complete — {transcript.word_count:,} words loaded\n"
            f"   Class: {transcript.class_name}\n\n"
            f"✅ Stage 2 complete — {len(script.key_points)} key points extracted\n\n"
            f"⚠️  Stage 3 failed — {audio.error}\n"
            f"   Script is still available below."
        )
        yield (
            final_msg,
            script.key_points_display(),
            script.quiz_display(),
            _format_script(script),
            None,
        )
        return

    final_msg = (
        f"✅ Stage 1 complete — {transcript.word_count:,} words loaded\n"
        f"   Class: {transcript.class_name}\n\n"
        f"✅ Stage 2 complete — {len(script.key_points)} key points extracted\n\n"
        f"✅ Stage 3 complete — Audio ready\n"
        f"   Duration: {audio.duration_estimate} | Provider: {audio.provider.upper()}\n\n"
        f"🎙️  Your recap podcast is ready!"
    )
    yield (
        final_msg,
        script.key_points_display(),
        script.quiz_display(),
        _format_script(script),
        audio.file_path,
    )


def _format_script(script) -> str:
    """Format the recap script for display in the UI."""
    sections = []
    if script.intro:
        sections.append(f"── INTRO ──\n{script.intro}")
    if script.overview:
        sections.append(f"── OVERVIEW ──\n{script.overview}")
    if script.key_points:
        sections.append("── KEY POINTS ──\n" + "\n\n".join(script.key_points))
    if script.deeper_dive:
        sections.append(f"── DEEPER DIVE ──\n{script.deeper_dive}")
    if script.quiz_questions:
        sections.append("── SELF-TEST ──\n" + "\n".join(script.quiz_questions))
    if script.takeaway:
        sections.append(f"── TAKEAWAY ──\n{script.takeaway}")
    if script.outro:
        sections.append(f"── OUTRO ──\n{script.outro}")
    return "\n\n".join(sections)


def load_sample() -> str:
    if SAMPLE_PATH.exists():
        return SAMPLE_PATH.read_text(encoding="utf-8")
    return "Sample file not found. Add a transcript to data/raw/sample_transcript.txt"


def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title = "🎙️ Class Recap Podcast Generator",
    ) as demo:

        gr.Markdown("""
        # 🎙️ Class Recap Podcast Generator
        Upload a class transcript and get a spoken audio recap in under a minute.
        **Pipeline:** Transcript → OpenAI extracts key points → OpenAI TTS generates audio
        """)

        gr.Markdown("---")

        with gr.Row():

            # Left column — Input
            with gr.Column(scale=1):
                gr.Markdown("### 📥 Input")

                transcript_text = gr.Textbox(
                    label       = "Paste transcript",
                    placeholder = "Paste your class transcript here...",
                    lines       = 16,
                )

                with gr.Row():
                    sample_btn = gr.Button("📄 Load Sample", variant="secondary")
                    clear_btn  = gr.Button("🗑 Clear",        variant="secondary")

                gr.Markdown("**— or upload a file —**")

                transcript_file = gr.File(
                    label      = "Upload .txt or .pdf file",
                    file_types = [".txt", ".pdf"],
                )

                gr.Markdown("**— or enter a URL —**")

                url_input = gr.Textbox(
                    label       = "Article URL",
                    placeholder = "https://example.com/article",
                    lines       = 1,
                )

                gr.Markdown("**— podcast options —**")

                voice_choice = gr.Radio(
                    choices = ["Female", "Male"],
                    value   = "Female",
                    label   = "🎤 Voice",
                )

                lively_mode = gr.Checkbox(
                    label = "😄 Make it lively — add jokes and human touches",
                    value = False,
                )

                generate_btn = gr.Button(
                    "🎙️  Generate Recap Podcast",
                    variant = "primary",
                    size    = "lg",
                )

            # Right column — Output
            with gr.Column(scale=1):
                gr.Markdown("### 📤 Output")

                status_box = gr.Textbox(
                    label       = "Pipeline Status",
                    interactive = False,
                    lines       = 7,
                    placeholder = "Status updates will appear here...",
                )

                audio_out = gr.Audio(
                    label       = "🔊 Recap Podcast",
                    type        = "filepath",
                    interactive = False,
                )

                with gr.Tabs():
                    with gr.Tab("✅ Key Points"):
                        key_points_box = gr.Textbox(
                            label       = "Extracted key concepts",
                            lines       = 8,
                            interactive = False,
                            placeholder = "Key points appear here after generation...",
                        )
                    with gr.Tab("❓ Self-Test"):
                        quiz_box = gr.Textbox(
                            label       = "Test your understanding",
                            lines       = 5,
                            interactive = False,
                            placeholder = "Quiz questions appear here after generation...",
                        )
                    with gr.Tab("📄 Full Script"):
                        script_box = gr.Textbox(
                            label       = "Full narration script",
                            lines       = 18,
                            interactive = False,
                            placeholder = "Full script appears here after generation...",
                        )

        # Wire up buttons
        sample_btn.click(fn=load_sample, outputs=transcript_text)
        clear_btn.click(fn=lambda: ("", None, ""), outputs=[transcript_text, transcript_file, url_input])

        generate_btn.click(
            fn      = run_pipeline,
            inputs  = [transcript_text, transcript_file, url_input, voice_choice, lively_mode],
            outputs = [status_box, key_points_box, quiz_box, script_box, audio_out],
        )

        gr.Markdown("---")
        gr.Markdown("""
        **How it works:**
        `data_processor.py` → cleans transcript, strips timestamps, extracts metadata
        `llm_processor.py` → sends to OpenAI, extracts key points, builds structured script
        `tts_generator.py` → converts script to MP3 via OpenAI TTS or free gTTS fallback
        """)

    return demo


if __name__ == "__main__":
    ui = build_ui()
    ui.launch(
        server_name = "0.0.0.0",
        server_port = 7860,
        show_error  = True,
    )
