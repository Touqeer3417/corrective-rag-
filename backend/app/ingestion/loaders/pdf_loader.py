"""PDF document loader using pdfplumber."""
from pathlib import Path
from typing import List, Tuple

import pdfplumber

from app.core.logging import get_logger
from app.core.exceptions import IngestionError

logger = get_logger("ingestion.pdf")


def load_pdf(file_path: str) -> Tuple[str, List[dict]]:
    """Load PDF and return full text + page-level metadata.

    Returns:
        Tuple of (full_text, pages_metadata)
        pages_metadata: list of dicts with 'page_number', 'text', 'tables'
    """
    try:
        pages = []
        full_text_parts = []

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []

                page_meta = {
                    "page_number": i,
                    "text": text,
                    "tables": tables,
                    "width": page.width,
                    "height": page.height,
                }
                pages.append(page_meta)
                full_text_parts.append(text)

        full_text = "\n\n".join(full_text_parts)
        logger.info(f"Loaded PDF: {Path(file_path).name}, {len(pages)} pages")
        return full_text, pages

    except Exception as e:
        raise IngestionError(f"Failed to load PDF {file_path}: {e}")
