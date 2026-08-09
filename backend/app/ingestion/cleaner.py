"""Text cleaning and normalization utilities."""
import re
from typing import List

from app.core.logging import get_logger

logger = get_logger("ingestion.cleaner")

# Regex patterns for cleaning
WHITESPACE_PATTERN = re.compile(r"\s+")
HEADER_FOOTER_PATTERN = re.compile(r"^(Page\s*\d+|\d+\s*of\s*\d+|Confidential|Draft|Internal Use Only)", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://\S+")
EMAIL_PATTERN = re.compile(r"\S+@\S+\.\S+")


def clean_text(text: str, aggressive: bool = False) -> str:
    """Clean and normalize extracted text.

    Args:
        text: Raw extracted text
        aggressive: If True, removes more formatting (use with caution)

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove null bytes
    text = text.replace("\x00", "")

    # Normalize whitespace (but preserve paragraph breaks)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        # Skip obvious headers/footers
        if HEADER_FOOTER_PATTERN.match(line) and len(line) < 50:
            continue
        # Normalize internal whitespace
        line = WHITESPACE_PATTERN.sub(" ", line)
        cleaned_lines.append(line)

    # Rejoin with proper paragraph breaks
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    if aggressive:
        # Remove URLs and emails only in aggressive mode
        text = URL_PATTERN.sub("[URL]", text)
        text = EMAIL_PATTERN.sub("[EMAIL]", text)

    return text.strip()


def normalize_for_embedding(text: str) -> str:
    """Normalize text specifically for embedding generation."""
    text = clean_text(text, aggressive=False)
    # Truncate extremely long lines (likely tables or data)
    lines = text.split("\n")
    normalized = []
    for line in lines:
        if len(line) > 1000:
            # Likely a table row or data dump, preserve but mark
            line = line[:1000] + "... [truncated]"
        normalized.append(line)
    return "\n".join(normalized)
