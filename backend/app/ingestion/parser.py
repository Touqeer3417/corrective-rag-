"""Document parser router - dispatches to appropriate loader."""
from pathlib import Path
from typing import List, Tuple

from app.core.logging import get_logger
from app.core.exceptions import IngestionError
from app.ingestion.loaders.pdf_loader import load_pdf
from app.ingestion.loaders.docx_loader import load_docx
from app.ingestion.loaders.txt_loader import load_txt, load_md
from app.ingestion.cleaner import clean_text
from app.ingestion.chunker import get_chunker
from app.schemas.document import DocumentChunk

logger = get_logger("ingestion.parser")


def parse_document(
    file_path: str,
    document_id: str,
    document_name: str,
    file_type: str,
) -> Tuple[List[DocumentChunk], int]:
    """Parse a document file into chunks with metadata.

    Returns:
        Tuple of (chunks, page_count)
    """
    file_path = str(Path(file_path).resolve())

    # Route to appropriate loader
    if file_type == "pdf":
        text, metadata = load_pdf(file_path)
        page_count = len(metadata)
    elif file_type == "docx":
        text, metadata = load_docx(file_path)
        page_count = len([m for m in metadata if not m.get("is_heading")])
    elif file_type == "txt":
        text, metadata = load_txt(file_path)
        page_count = 1
    elif file_type == "md":
        text, metadata = load_md(file_path)
        page_count = 1
    else:
        raise IngestionError(f"Unsupported file type: {file_type}")

    # Clean text
    cleaned_text = clean_text(text, aggressive=False)

    if not cleaned_text.strip():
        raise IngestionError(f"No extractable text found in {document_name}")

    # Chunk document
    chunker = get_chunker()
    chunks = chunker.chunk_document(
        text=cleaned_text,
        document_id=document_id,
        document_name=document_name,
        file_type=file_type,
        page_metadata=metadata,
    )

    logger.info(f"Parsed {document_name}: {page_count} pages, {len(chunks)} chunks")
    return chunks, page_count or 1
