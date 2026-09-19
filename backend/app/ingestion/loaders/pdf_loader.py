"""Memory-efficient PDF document loader using pdfplumber."""

from pathlib import Path
from typing import List, Tuple

import pdfplumber

from app.core.logging import get_logger
from app.core.exceptions import IngestionError


logger = get_logger("ingestion.pdf")


def load_pdf(file_path: str) -> Tuple[str, List[dict]]:
    """
    Load PDF and return extracted text with lightweight page metadata.

    Important:
    - Does NOT extract tables automatically.
    - Keeps metadata lightweight for large PDFs.
    - Suitable for low-memory production environments.
    """

    try:
        full_text_parts: List[str] = []
        pages_metadata: List[dict] = []

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            logger.info(
                f"Starting PDF extraction: {Path(file_path).name}, "
                f"{total_pages} pages"
            )

            for page_number, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""

                if text.strip():
                    full_text_parts.append(text)

                # Keep metadata very small.
                # Do NOT run page.extract_tables() here.
                pages_metadata.append(
                    {
                        "page_number": page_number,
                    }
                )

                if page_number % 10 == 0 or page_number == total_pages:
                    logger.info(
                        f"PDF extraction progress: "
                        f"{page_number}/{total_pages} pages"
                    )

        full_text = "\n\n".join(full_text_parts)

        logger.info(
            f"Loaded PDF: {Path(file_path).name}, "
            f"{total_pages} pages, "
            f"{len(full_text)} characters"
        )

        return full_text, pages_metadata

    except Exception as e:
        logger.exception(
            f"Failed to load PDF {file_path}: {e}"
        )

        raise IngestionError(
            f"Failed to load PDF {file_path}: {e}"
        ) from e