"""Document ingestion orchestration service."""
import shutil
import tempfile
from pathlib import Path
from typing import List

from app.config import get_settings
from app.core.logging import get_logger
from app.core.security import generate_secure_filename, validate_upload, validate_magic_bytes
from app.ingestion.parser import parse_document
from app.retrieval.embeddings import get_embedding_model
from app.retrieval.sparse import get_bm25_index
from app.schemas.document import DocumentChunk, DocumentUpload
from app.storage.document_store import get_document_store
from app.storage.file_store import get_file_store
from app.storage.vector_store import get_vector_store

logger = get_logger("services.ingestion")


class IngestionService:
    """Orchestrate document parsing, chunking, embedding, and indexing."""

    def __init__(self):
        self.doc_store = get_document_store()
        self.file_store = get_file_store()
        self.vector_store = get_vector_store()
        self.bm25 = get_bm25_index()
        self.embedder = get_embedding_model()

    async def ingest_document(
        self, file_path: str, original_filename: str, content_type: str
    ) -> DocumentUpload:
        """Full ingestion pipeline."""
        file_size = Path(file_path).stat().st_size
        ext = validate_upload(original_filename, file_size, content_type)

        secure_name = generate_secure_filename(original_filename)
        saved_path = self.file_store.save(file_path, secure_name)
        validate_magic_bytes(str(saved_path), ext)

        record = self.doc_store.create_document(
            filename=secure_name,
            original_name=original_filename,
            file_type=ext,
            file_size=file_size,
        )
        doc_id = record.document_id

        try:
            self.doc_store.update_status(doc_id, "processing")
            chunks, page_count = parse_document(
                str(saved_path), doc_id, original_filename, ext
            )

            if not chunks:
                raise ValueError("No text chunks extracted from document")

            texts = [chunk.text for chunk in chunks]
            embeddings = self.embedder.encode(texts)

            self.vector_store.upsert_chunks(chunks, embeddings)
            self.bm25.add_documents(chunks)

            self.doc_store.update_status(doc_id, "indexed", chunk_count=len(chunks))

            logger.info(f"Ingestion complete: {doc_id} ({len(chunks)} chunks)")
            return DocumentUpload(
                document_id=doc_id,
                filename=original_filename,
                file_type=ext,
                status="indexed",
                chunk_count=len(chunks),
                created_at=record.created_at,
            )

        except Exception as e:
            logger.error(f"Ingestion failed for {doc_id}: {e}")
            self.doc_store.update_status(doc_id, "error", message=str(e))
            self.file_store.delete(secure_name)
            raise


def get_ingestion_service() -> IngestionService:
    return IngestionService()
