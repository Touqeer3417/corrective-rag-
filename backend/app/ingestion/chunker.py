"""Document chunking strategy with metadata preservation."""
import uuid
from typing import List, Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk

logger = get_logger("ingestion.chunker")


class RecursiveChunker:
    """Recursive character chunker with overlap and boundary preservation.

    Strategy:
    1. Split by paragraphs first (\n\n)
    2. If paragraph > chunk_size, split by lines (\n)
    3. If line > chunk_size, split by sentences (. )
    4. If sentence > chunk_size, split by words ( )
    5. Always preserve chunk overlap for context continuity
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " "]

    def _split_by_separator(self, text: str, separator: str) -> List[str]:
        """Split text by separator, keeping the separator with the preceding chunk."""
        if not separator:
            return list(text)
        parts = text.split(separator)
        result = []
        for i, part in enumerate(parts):
            if i < len(parts) - 1:
                result.append(part + separator)
            else:
                result.append(part)
        return [p for p in result if p.strip()]

    def _merge_chunks(self, chunks: List[str]) -> List[str]:
        """Merge small chunks up to chunk_size, respecting overlap."""
        if not chunks:
            return []

        merged = []
        current = chunks[0]

        for chunk in chunks[1:]:
            if len(current) + len(chunk) <= self.chunk_size:
                current += chunk
            else:
                merged.append(current.strip())
                # Apply overlap: take last N characters from current chunk
                overlap_text = current[-self.chunk_overlap:] if len(current) > self.chunk_overlap else current
                current = overlap_text + chunk

        if current.strip():
            merged.append(current.strip())

        return merged

    def _recursive_split(self, text: str, separator_idx: int = 0) -> List[str]:
        """Recursively split text using separators."""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        if separator_idx >= len(self.separators):
            # Final fallback: hard split at chunk_size
            chunks = []
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                chunk = text[i:i + self.chunk_size]
                if chunk.strip():
                    chunks.append(chunk.strip())
            return chunks

        separator = self.separators[separator_idx]
        parts = self._split_by_separator(text, separator)

        # If splitting didn't help, try next separator
        if len(parts) == 1 and len(parts[0]) > self.chunk_size:
            return self._recursive_split(text, separator_idx + 1)

        # Merge small parts
        merged = self._merge_chunks(parts)

        # Recursively split any chunks that are still too large
        result = []
        for chunk in merged:
            if len(chunk) > self.chunk_size:
                result.extend(self._recursive_split(chunk, separator_idx + 1))
            else:
                result.append(chunk)
        return result

    def chunk_document(
        self,
        text: str,
        document_id: str,
        document_name: str,
        file_type: str,
        page_metadata: Optional[List[dict]] = None,
    ) -> List[DocumentChunk]:
        """Chunk a document while preserving page/section metadata.

        Args:
            text: Full document text
            document_id: Unique document identifier
            document_name: Original filename
            file_type: File extension
            page_metadata: Optional list of page/element metadata from loaders
        """
        chunks = self._recursive_split(text)

        doc_chunks = []
        for i, chunk_text in enumerate(chunks):
            # Determine page number and section from metadata
            page_number = self._infer_page_number(chunk_text, page_metadata, i, len(chunks))
            section = self._infer_section(chunk_text, page_metadata, i)

            chunk = DocumentChunk(
                chunk_id=f"{document_id}_chunk_{i}",
                document_id=document_id,
                document_name=document_name,
                file_type=file_type,
                page_number=page_number,
                section=section,
                text=chunk_text,
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "char_count": len(chunk_text),
                },
            )
            doc_chunks.append(chunk)

        logger.info(f"Created {len(doc_chunks)} chunks for {document_name}")
        return doc_chunks

    def _infer_page_number(
        self,
        chunk_text: str,
        page_metadata: Optional[List[dict]],
        chunk_index: int,
        total_chunks: int,
    ) -> Optional[int]:
        """Infer page number from metadata or chunk position."""
        if not page_metadata:
            return 1

        # Simple proportional mapping for PDFs
        if len(page_metadata) > 1 and "page_number" in page_metadata[0]:
            ratio = chunk_index / max(total_chunks - 1, 1)
            page_idx = int(ratio * (len(page_metadata) - 1))
            return page_metadata[page_idx].get("page_number", page_idx + 1)

        return page_metadata[0].get("page_number", 1)

    def _infer_section(
        self,
        chunk_text: str,
        page_metadata: Optional[List[dict]],
        chunk_index: int,
    ) -> Optional[str]:
        """Infer section/heading from metadata."""
        if not page_metadata:
            return None

        # Look for preceding heading in metadata
        for meta in page_metadata:
            if meta.get("is_heading") and chunk_text.startswith(meta.get("text", "")[:50]):
                return meta.get("text", "")[:100]

        return None


def get_chunker() -> RecursiveChunker:
    settings = get_settings()
    return RecursiveChunker(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
