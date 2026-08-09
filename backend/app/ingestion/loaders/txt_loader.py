"""Plain text and markdown loaders."""
from pathlib import Path
from typing import Tuple

from app.core.logging import get_logger
from app.core.exceptions import IngestionError

logger = get_logger("ingestion.txt")


def load_txt(file_path: str) -> Tuple[str, list]:
    """Load plain text file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        logger.info(f"Loaded TXT: {Path(file_path).name}, {len(text)} chars")
        return text, [{"page_number": 1, "text": text}]
    except Exception as e:
        raise IngestionError(f"Failed to load TXT {file_path}: {e}")


def load_md(file_path: str) -> Tuple[str, list]:
    """Load markdown file (treated as text with structure hints)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        logger.info(f"Loaded MD: {Path(file_path).name}, {len(text)} chars")
        return text, [{"page_number": 1, "text": text}]
    except Exception as e:
        raise IngestionError(f"Failed to load MD {file_path}: {e}")
