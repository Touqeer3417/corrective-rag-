"""Qdrant vector store — Server OR Local mode (no server needed)."""
import uuid  # ← YEH ADD KARO
from pathlib import Path
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
    """Qdrant vector store with ANN search.
    
    SMART: Pehle server dhundta hai (Docker/production).
    Agar server nahi mile -> LOCAL mode (embedded, no server needed).
    """

    def __init__(self):
        self.settings = get_settings()
        self.collection_name = self.settings.qdrant_collection
        self._dimension: Optional[int] = None
        
        # Pehle server try karo, nahi chal raha tu local mode
        self.client = self._connect()
        self._init_collection()

    def _connect(self) -> QdrantClient:
        """Server pehle, phir local fallback."""
        
        # --- Try 1: Qdrant Server (Docker) ---
        try:
            client = QdrantClient(
                host=self.settings.qdrant_host,
                port=self.settings.qdrant_port,
                api_key=self.settings.qdrant_api_key or None,
                timeout=3,
            )
            client.get_collections()  # Test connection
            logger.info(
                f"Qdrant SERVER connected: "
                f"{self.settings.qdrant_host}:{self.settings.qdrant_port}"
            )
            return client
        except Exception as e:
            logger.warning(
                f"Qdrant server nahi mila ({self.settings.qdrant_host}:"
                f"{self.settings.qdrant_port}). Local mode use kar raha hun. "
                f"Error: {e}"
            )

        # --- Try 2: Local Mode (NO SERVER NEEDED) ---
        local_path = Path(self.settings.bm25_index_path).parent / "qdrant_local"
        local_path.mkdir(parents=True, exist_ok=True)
        
        client = QdrantClient(path=str(local_path))
        logger.info(f"Qdrant LOCAL mode ON. Data: {local_path}")
        return client

    def _init_collection(self) -> None:
        """Check collection exists."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if exists:
                info = self.client.get_collection(self.collection_name)
                self._dimension = info.config.params.vectors.size
                logger.info(
                    f"Collection '{self.collection_name}' ready "
                    f"(dim={self._dimension}, total_vectors={self.count})"
                )
            else:
                logger.info(
                    f"Collection '{self.collection_name}' nahi milli. "
                    f"Pehli upload pe ban jayegi."
                )
        except Exception as e:
            logger.warning(f"Collection check failed: {e}")

    def _create_collection(self, dimension: int) -> None:
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
            self._dimension = dimension
            logger.info(
                f"Collection '{self.collection_name}' created (dim={dimension})"
            )
        except Exception as e:
            logger.error(f"Collection create failed: {e}")
            raise

    def upsert_chunks(
        self, chunks: List[DocumentChunk], embeddings: List[List[float]]
    ) -> None:
        if not chunks or not embeddings:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) != embeddings ({len(embeddings)})"
            )

        dimension = len(embeddings[0])
        
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                self._create_collection(dimension)
            elif self._dimension is not None and dimension != self._dimension:
                logger.warning(
                    f"Dimension badal gayi ({self._dimension} -> {dimension}). "
                    f"Collection dobara bana raha hun."
                )
                self.client.delete_collection(self.collection_name)
                self._create_collection(dimension)

            self._dimension = dimension

            points = []
            for chunk, emb in zip(chunks, embeddings):
                if len(emb) != dimension:
                    raise ValueError(
                        f"Wrong dimension: expected {dimension}, got {len(emb)}"
                    )
                
                # ← FIX: Qdrant ko valid UUID chahiye point ID ke liye
                # Asli chunk_id payload mein save hoti hai
                points.append(
                    PointStruct(
                        id=str(uuid.uuid4()),  # ← NAYA UUID for Qdrant
                        vector=emb,
                        payload={
                            "chunk_id": chunk.chunk_id,  # ← Asli ID yahan
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
            logger.error(f"Upsert failed: {e}")
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
                logger.warning("Collection nahi hai, kuch nahi mila")
                return []

            query_filter = None
            if document_ids:
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
            logger.error(f"Search failed: {e}")
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
            logger.info(f"Deleted vectors for document {document_id}")
            return 1
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0

    def clear(self) -> None:
        try:
            collections = self.client.get_collections().collections
            if any(c.name == self.collection_name for c in collections):
                self.client.delete_collection(self.collection_name)
                logger.info(f"Collection '{self.collection_name}' deleted")
            self._dimension = None
        except Exception as e:
            logger.error(f"Clear failed: {e}")

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
            logger.warning(f"Count failed: {e}")
            return 0


_vector_store: Optional[VectorStore] = None

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store