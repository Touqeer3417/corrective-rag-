"""Qdrant vector store implementation."""
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk

logger = get_logger("storage.vector")

class VectorStore:
    """Qdrant-backed vector store with ANN search."""

    def __init__(self):
        self.settings = get_settings()
        try:
            self.client = QdrantClient(
                host=self.settings.qdrant_host,
                port=self.settings.qdrant_port,
                api_key=self.settings.qdrant_api_key or None,
            )
            self.collection_name = self.settings.qdrant_collection
            self._dimension: Optional[int] = None
            self._init_collection()
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    def _init_collection(self) -> None:
        """Check existing collection and get dimension."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if exists:
                info = self.client.get_collection(self.collection_name)
                self._dimension = info.config.params.vectors.size
                logger.info(
                    f"Connected to Qdrant collection '{self.collection_name}' "
                    f"(dim={self._dimension})"
                )
            else:
                logger.info(
                    f"Qdrant collection '{self.collection_name}' not found. "
                    f"Will create on first upsert."
                )
        except Exception as e:
            logger.warning(f"Could not check Qdrant collections: {e}")

    def _create_collection(self, dimension: int) -> None:
        """Create collection with given dimension."""
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
            self._dimension = dimension
            logger.info(
                f"Created Qdrant collection '{self.collection_name}' "
                f"with dimension {dimension}"
            )
        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {e}")
            raise

    def upsert_chunks(
        self, chunks: List[DocumentChunk], embeddings: List[List[float]]
    ) -> None:
        if not chunks or not embeddings:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) "
                f"must have same length"
            )

        dimension = len(embeddings[0])
        
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                self._create_collection(dimension)
            elif self._dimension is not None and dimension != self._dimension:
                logger.warning(
                    f"Dimension mismatch: existing={self._dimension}, new={dimension}. "
                    f"Recreating collection."
                )
                self.client.delete_collection(self.collection_name)
                self._create_collection(dimension)

            self._dimension = dimension

            points = []
            for chunk, emb in zip(chunks, embeddings):
                if len(emb) != dimension:
                    raise ValueError(
                        f"Inconsistent embedding dimension: expected {dimension}, "
                        f"got {len(emb)}"
                    )
                
                points.append(
                    PointStruct(
                        id=chunk.chunk_id,
                        vector=emb,
                        payload={
                            "chunk_id": chunk.chunk_id,
                            "document_id": chunk.document_id,
                            "document_name": chunk.document_name,
                            "file_type": chunk.file_type,
                            "page_number": chunk.page_number,
                            "section": chunk.section,
                            "text": chunk.text,
                            "metadata": chunk.metadata,
                        },
                    )
                )

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            logger.info(f"Upserted {len(points)} vectors to Qdrant")
        except Exception as e:
            logger.error(f"Failed to upsert chunks to Qdrant: {e}")
            raise

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                logger.warning("Qdrant collection does not exist, returning no results")
                return []

            query_filter = None
            if document_ids:
                # "should" = OR logic: document_id matches any of the given ids
                query_filter = Filter(
                    should=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=doc_id),
                        )
                        for doc_id in document_ids
                    ]
                )

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

            chunks = []
            for scored_point in results:
                payload = scored_point.payload or {}
                chunk = DocumentChunk(
                    chunk_id=payload.get("chunk_id", scored_point.id),
                    document_id=payload.get("document_id", ""),
                    document_name=payload.get("document_name", ""),
                    file_type=payload.get("file_type", ""),
                    page_number=payload.get("page_number"),
                    section=payload.get("section"),
                    text=payload.get("text", ""),
                    metadata=payload.get("metadata", {}) or {},
                    score=scored_point.score,
                )
                chunks.append(chunk)

            logger.info(f"Qdrant search returned {len(chunks)} results")
            return chunks
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []

    def delete_by_document(self, document_id: str) -> int:
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                return 0

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                ),
                wait=True,
            )
            logger.info(f"Deleted vectors for document {document_id} from Qdrant")
            return 1
        except Exception as e:
            logger.error(f"Failed to delete vectors from Qdrant: {e}")
            return 0

    def clear(self) -> None:
        try:
            collections = self.client.get_collections().collections
            if any(c.name == self.collection_name for c in collections):
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted Qdrant collection '{self.collection_name}'")
            self._dimension = None
        except Exception as e:
            logger.error(f"Failed to clear Qdrant collection: {e}")

    @property
    def dimension(self) -> Optional[int]:
        return self._dimension

    @property
    def count(self) -> int:
        try:
            collections = self.client.get_collections().collections
            if not any(c.name == self.collection_name for c in collections):
                return 0
            result = self.client.count(self.collection_name)
            return result.count
        except Exception as e:
            logger.warning(f"Could not get Qdrant count: {e}")
            return 0


_vector_store: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store