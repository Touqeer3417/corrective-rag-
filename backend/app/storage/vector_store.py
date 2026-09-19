"""Qdrant vector store — Server OR Local mode (no server needed)."""

import uuid
from pathlib import Path
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk


logger = get_logger("storage.vector")


class VectorStore:
    """
    Qdrant vector store with ANN search.

    SMART:
    - First tries Qdrant server / Qdrant Cloud.
    - If local server is unavailable, falls back to embedded local Qdrant.
    - If QDRANT_URL is configured (production/cloud), connection failure
      raises an error instead of silently using ephemeral local storage.
    """

    def __init__(self):
        self.settings = get_settings()
        self.collection_name = self.settings.qdrant_collection
        self._dimension: Optional[int] = None

        # First try Qdrant server/cloud.
        # If no Qdrant URL is configured and local server is unavailable,
        # fall back to embedded local Qdrant.
        self.client = self._connect()

        # Check whether the configured collection already exists.
        self._init_collection()

    def _connect(self) -> QdrantClient:
        """Connect to Qdrant Cloud, server Qdrant, or embedded local Qdrant."""

        try:
            # ---------------------------------------------------------
            # Qdrant Cloud / URL-based connection
            # ---------------------------------------------------------
            if self.settings.qdrant_url:
                client = QdrantClient(
                    url=self.settings.qdrant_url,
                    api_key=self.settings.qdrant_api_key or None,
                    timeout=10,
                )

                target = self.settings.qdrant_url

            # ---------------------------------------------------------
            # Local/server Qdrant connection
            # ---------------------------------------------------------
            else:
                client = QdrantClient(
                    host=self.settings.qdrant_host,
                    port=self.settings.qdrant_port,
                    api_key=self.settings.qdrant_api_key or None,
                    timeout=10,
                )

                target = (
                    f"{self.settings.qdrant_host}:"
                    f"{self.settings.qdrant_port}"
                )

            # Test connection.
            client.get_collections()

            logger.info(f"Qdrant connected: {target}")

            return client

        except Exception as e:
            # ---------------------------------------------------------
            # IMPORTANT:
            # If QDRANT_URL is configured, it means we expect a real
            # production/cloud Qdrant instance.
            #
            # Do NOT silently fall back to local ephemeral storage.
            # ---------------------------------------------------------
            if self.settings.qdrant_url:
                raise RuntimeError(
                    f"Could not connect to Qdrant Cloud: {e}"
                ) from e

            # ---------------------------------------------------------
            # Local fallback
            # ---------------------------------------------------------
            logger.warning(
                "Qdrant server unavailable; "
                f"using local mode. Error: {e}"
            )

            local_path = (
                Path(self.settings.bm25_index_path).parent
                / "qdrant_local"
            )

            local_path.mkdir(
                parents=True,
                exist_ok=True,
            )

            client = QdrantClient(
                path=str(local_path)
            )

            logger.info(
                f"Qdrant LOCAL mode ON. Data: {local_path}"
            )

            return client

    def _init_collection(self) -> None:
        """Check whether the configured collection already exists."""

        try:
            collections = self.client.get_collections().collections

            exists = any(
                collection.name == self.collection_name
                for collection in collections
            )

            if exists:
                info = self.client.get_collection(
                    self.collection_name
                )

                self._dimension = (
                    info.config.params.vectors.size
                )

                logger.info(
                    f"Collection '{self.collection_name}' ready "
                    f"(dim={self._dimension}, "
                    f"total_vectors={self.count})"
                )

            else:
                logger.info(
                    f"Collection '{self.collection_name}' nahi milli. "
                    "Pehli upload pe ban jayegi."
                )

        except Exception as e:
            logger.warning(
                f"Collection check failed: {e}"
            )

    def _create_collection(self, dimension: int) -> None:
        """Create the Qdrant collection."""

        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                ),
            )

            self._dimension = dimension

            logger.info(
                f"Collection '{self.collection_name}' created "
                f"(dim={dimension})"
            )

        except Exception as e:
            logger.error(
                f"Collection create failed: {e}"
            )
            raise

    def upsert_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> None:
        """
        Insert or update document chunks and their embeddings in Qdrant.
        """

        if not chunks or not embeddings:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) != "
                f"embeddings ({len(embeddings)})"
            )

        dimension = len(embeddings[0])

        try:
            collections = self.client.get_collections().collections

            exists = any(
                collection.name == self.collection_name
                for collection in collections
            )

            # ---------------------------------------------------------
            # Create collection on first upload.
            # ---------------------------------------------------------
            if not exists:
                self._create_collection(dimension)

            # ---------------------------------------------------------
            # Recreate collection if embedding dimension changed.
            # Example:
            # 1536 -> 3072
            # ---------------------------------------------------------
            elif (
                self._dimension is not None
                and dimension != self._dimension
            ):
                logger.warning(
                    "Dimension badal gayi "
                    f"({self._dimension} -> {dimension}). "
                    "Collection dobara bana raha hun."
                )

                self.client.delete_collection(
                    self.collection_name
                )

                self._create_collection(
                    dimension
                )

            self._dimension = dimension

            points = []

            for chunk, embedding in zip(chunks, embeddings):
                if len(embedding) != dimension:
                    raise ValueError(
                        "Wrong dimension: "
                        f"expected {dimension}, "
                        f"got {len(embedding)}"
                    )

                # -----------------------------------------------------
                # Qdrant point IDs must be valid UUIDs or integers.
                #
                # Therefore:
                # - Generate a UUID for Qdrant's internal point ID.
                # - Store the application's original chunk_id
                #   inside the payload.
                # -----------------------------------------------------
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
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

                points.append(point)

            # ---------------------------------------------------------
            # Upload vectors to Qdrant.
            # ---------------------------------------------------------
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )

            logger.info(
                f"Upserted {len(points)} vectors to Qdrant"
            )

        except Exception as e:
            logger.error(
                f"Upsert failed: {e}"
            )
            raise

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """
        Search Qdrant for chunks similar to the query embedding.

        Args:
            query_embedding:
                Embedding vector generated from the user's query.

            top_k:
                Maximum number of vector results to return.

            document_ids:
                Optional list of document IDs.
                If provided, search only inside those documents.

        Returns:
            List of DocumentChunk objects ordered by similarity.
        """

        try:
            collections = self.client.get_collections().collections

            collection_exists = any(
                collection.name == self.collection_name
                for collection in collections
            )

            if not collection_exists:
                logger.warning(
                    f"Collection '{self.collection_name}' "
                    "does not exist"
                )
                return []

            # ---------------------------------------------------------
            # Optional document filtering
            # ---------------------------------------------------------
            query_filter = None

            if document_ids:
                query_filter = Filter(
                    should=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(
                                value=document_id
                            ),
                        )
                        for document_id in document_ids
                    ]
                )

            # ---------------------------------------------------------
            # Modern Qdrant query API
            # ---------------------------------------------------------
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

            results = response.points

            chunks: List[DocumentChunk] = []

            # ---------------------------------------------------------
            # Convert Qdrant results back into DocumentChunk objects.
            # ---------------------------------------------------------
            for scored_point in results:
                payload = scored_point.payload or {}

                chunk = DocumentChunk(
                    chunk_id=payload.get(
                        "chunk_id",
                        str(scored_point.id),
                    ),
                    document_id=payload.get(
                        "document_id",
                        "",
                    ),
                    document_name=payload.get(
                        "document_name",
                        "",
                    ),
                    file_type=payload.get(
                        "file_type",
                        "",
                    ),
                    page_number=payload.get(
                        "page_number"
                    ),
                    section=payload.get(
                        "section"
                    ),
                    text=payload.get(
                        "text",
                        "",
                    ),
                    metadata=(
                        payload.get(
                            "metadata",
                            {},
                        )
                        or {}
                    ),
                    score=(
                        float(scored_point.score)
                        if scored_point.score is not None
                        else 0.0
                    ),
                )

                chunks.append(chunk)

            logger.info(
                f"Qdrant search returned "
                f"{len(chunks)} results"
            )

            if chunks:
                logger.info(
                    "Top result: "
                    f"{chunks[0].document_name} "
                    f"(score={chunks[0].score:.3f})"
                )

            return chunks

        except Exception as e:
            logger.exception(
                f"Qdrant search failed: {e}"
            )
            return []

    def delete_by_document(
        self,
        document_id: str,
    ) -> int:
        """
        Delete all vectors belonging to a specific document.

        Returns:
            1 if deletion request was performed.
            0 if collection does not exist or deletion failed.
        """

        try:
            collections = self.client.get_collections().collections

            collection_exists = any(
                collection.name == self.collection_name
                for collection in collections
            )

            if not collection_exists:
                return 0

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(
                                value=document_id
                            ),
                        )
                    ]
                ),
                wait=True,
            )

            logger.info(
                f"Deleted vectors for document {document_id}"
            )

            return 1

        except Exception as e:
            logger.error(
                f"Delete failed: {e}"
            )
            return 0

    def clear(self) -> None:
        """Delete the entire Qdrant collection."""

        try:
            collections = self.client.get_collections().collections

            collection_exists = any(
                collection.name == self.collection_name
                for collection in collections
            )

            if collection_exists:
                self.client.delete_collection(
                    self.collection_name
                )

                logger.info(
                    f"Collection "
                    f"'{self.collection_name}' deleted"
                )

            self._dimension = None

        except Exception as e:
            logger.error(
                f"Clear failed: {e}"
            )

    @property
    def dimension(self) -> Optional[int]:
        """Return the current embedding dimension."""

        return self._dimension

    @property
    def count(self) -> int:
        """Return the number of vectors in the collection."""

        try:
            collections = self.client.get_collections().collections

            collection_exists = any(
                collection.name == self.collection_name
                for collection in collections
            )

            if not collection_exists:
                return 0

            result = self.client.count(
                collection_name=self.collection_name
            )

            return result.count

        except Exception as e:
            logger.warning(
                f"Count failed: {e}"
            )
            return 0


# -------------------------------------------------------------------------
# Singleton VectorStore instance
# -------------------------------------------------------------------------

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the singleton VectorStore instance."""

    global _vector_store

    if _vector_store is None:
        _vector_store = VectorStore()

    return _vector_store