"""
src/data_processor.py
---------------------
Stage 1 — Transcript Ingestion

Accepts a class transcript from:
  - Pasted text (string)
  - Uploaded .txt file (file path from Gradio)
  - Uploaded PDF file
  - Web article URL

Returns a TranscriptData dataclass — the contract passed to llm_processor.py.
"""

from __future__ import annotations

import re
import logging
import requests
from dataclasses import dataclass, field
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TranscriptData:
    raw_text:    str
    clean_text:  str
    class_name:  str        = "Unknown Class"
    date:        str        = ""
    instructor:  str        = ""
    word_count:  int        = 0
    segments:    list[dict] = field(default_factory=list)
    error:       Optional[str] = None

    def __post_init__(self):
        self.word_count = len(self.clean_text.split())

    @property
    def is_valid(self) -> bool:
        return bool(self.clean_text.strip()) and self.error is None

    def summary(self) -> str:
        parts = [self.class_name]
        if self.date:
            parts.append(self.date)
        parts.append(f"{self.word_count:,} words")
        parts.append(f"{len(self.segments)} segments")
        return " | ".join(parts)


_TIMESTAMP_RE  = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?\]")
_HEADER_RE     = re.compile(r"^TRANSCRIPT\s*[—\-]?\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_DATE_RE       = re.compile(r"^Date:\s*(.+)$",                re.MULTILINE | re.IGNORECASE)
_INSTRUCTOR_RE = re.compile(r"^Instructor:\s*(.+)$",          re.MULTILINE | re.IGNORECASE)


def _extract_metadata(text: str) -> dict:
    meta = {"class_name": "Unknown Class", "date": "", "instructor": ""}
    m = _HEADER_RE.search(text)
    if m:
        meta["class_name"] = m.group(1).split("|")[0].strip()
    m = _DATE_RE.search(text)
    if m:
        meta["date"] = m.group(1).strip()
    m = _INSTRUCTOR_RE.search(text)
    if m:
        meta["instructor"] = m.group(1).strip()
    return meta


def _parse_segments(text: str) -> list[dict]:
    segments = []
    matches  = list(_TIMESTAMP_RE.finditer(text))
    for i, match in enumerate(matches):
        time_str = match.group().strip("[]")
        start    = match.end()
        end      = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg_text = text[start:end].strip()
        if seg_text:
            segments.append({"time": time_str, "text": seg_text})
    return segments


def _clean_text(text: str) -> str:
    lines       = text.strip().split("\n")
    content     = []
    past_header = False
    for line in lines:
        s = line.strip()
        if not past_header:
            skip = (
                re.match(r"^TRANSCRIPT", s, re.IGNORECASE)
                or re.match(r"^Date:",       s, re.IGNORECASE)
                or re.match(r"^Instructor:", s, re.IGNORECASE)
                or s == ""
            )
            if skip:
                continue
            past_header = True
        cleaned = _TIMESTAMP_RE.sub("", line).strip()
        if cleaned:
            content.append(cleaned)
    result = " ".join(content)
    result = re.sub(r"\s{2,}", " ", result).strip()
    return result


def _is_pdf(file_path: str) -> bool:
    """Check if a file is a PDF by reading its first 4 magic bytes."""
    try:
        with open(file_path, "rb") as f:
            return f.read(4) == b"%PDF"
    except Exception:
        return False


def load_pdf(file_path: str) -> TranscriptData:
    """Extract text from a PDF file."""
    try:
        import PyPDF2
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages  = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)

        raw_text = "\n\n".join(pages)

        if not raw_text.strip():
            return TranscriptData(
                raw_text   = "",
                clean_text = "",
                error      = "No text found in PDF. It may be a scanned image — try copy-pasting the text instead."
            )

        meta     = _extract_metadata(raw_text)
        segments = _parse_segments(raw_text)
        clean    = _clean_text(raw_text)

        result = TranscriptData(
            raw_text   = raw_text,
            clean_text = clean,
            class_name = meta["class_name"],
            date       = meta["date"],
            instructor = meta["instructor"],
            segments   = segments,
        )
        logger.info("PDF loaded — %s", result.summary())
        return result

    except Exception as exc:
        return TranscriptData(
            raw_text   = "",
            clean_text = "",
            error      = f"PDF error: {exc}"
        )


def load_url(url: str) -> TranscriptData:
    """Scrape a web article and extract readable text."""
    try:
        headers  = {"User-Agent": "Mozilla/5.0 (compatible; PodcastStudioBot/1.0)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        article  = soup.find("article") or soup.find("main") or soup.body
        raw_text = article.get_text(separator="\n") if article else soup.get_text(separator="\n")
        title    = soup.title.string.strip() if soup.title else url

        if not raw_text.strip():
            return TranscriptData(
                raw_text   = "",
                clean_text = "",
                error      = "Could not extract text from that URL."
            )

        clean = _clean_text(raw_text)

        result = TranscriptData(
            raw_text   = raw_text,
            clean_text = clean,
            class_name = title[:80],
            date       = "",
            instructor = "",
            segments   = [],
        )
        logger.info("URL loaded — %s (%d words)", title[:50], result.word_count)
        return result

    except requests.exceptions.RequestException as exc:
        return TranscriptData(
            raw_text   = "",
            clean_text = "",
            error      = f"Could not fetch URL: {exc}"
        )


def load_transcript(source: str | Path) -> TranscriptData:
    """
    Load and clean a class transcript from a file path or raw string.
    Automatically detects PDF files by magic bytes.
    Returns TranscriptData ready for llm_processor.generate_recap()
    """
    source_str  = str(source)
    is_filepath = "\n" not in source_str and Path(source_str).exists()

    if is_filepath:
        # Detect PDF by extension OR magic bytes (handles Gradio temp files)
        if source_str.lower().endswith(".pdf") or _is_pdf(source_str):
            return load_pdf(source_str)

        logger.info("Loading from file: %s", source_str)
        try:
            raw_text = Path(source_str).read_text(encoding="utf-8")
        except Exception as exc:
            return TranscriptData(raw_text="", clean_text="",
                                  error=f"Cannot read file: {exc}")
    elif isinstance(source, str) and source.strip():
        logger.info("Loading from string (%d chars)", len(source))
        raw_text = source
    else:
        return TranscriptData(raw_text="", clean_text="",
                              error="No input provided.")

    if len(raw_text.strip()) < 100:
        return TranscriptData(
            raw_text=raw_text, clean_text="",
            error="Transcript too short. Paste the full class transcript."
        )

    meta     = _extract_metadata(raw_text)
    segments = _parse_segments(raw_text)
    clean    = _clean_text(raw_text)

    result = TranscriptData(
        raw_text   = raw_text,
        clean_text = clean,
        class_name = meta["class_name"],
        date       = meta["date"],
        instructor = meta["instructor"],
        segments   = segments,
    )
    logger.info("Loaded — %s", result.summary())
    return result
