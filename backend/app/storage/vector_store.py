"""Qdrant vector store with Cloud, server, and local fallback support."""

import uuid
from pathlib import Path
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk


logger = get_logger("storage.vector")

# Number of vectors sent to Qdrant in one request.
# Small batches are safer for low-memory production hosting.
QDRANT_BATCH_SIZE = 64

# Timeout for Qdrant Cloud/server operations.
QDRANT_TIMEOUT_SECONDS = 60


class VectorStore:
    """
    Qdrant vector store.

    Supports:
    - Qdrant Cloud through QDRANT_URL
    - Local/server Qdrant through QDRANT_HOST/QDRANT_PORT
    - Embedded Qdrant fallback for local development

    Large-document optimization:
    - Vectors are uploaded in small batches instead of one huge request.
    """

    def __init__(self):
        self.settings = get_settings()
        self.collection_name = self.settings.qdrant_collection

        self._dimension: Optional[int] = None

        self.client = self._connect()

        self._init_collection()

    # ======================================================================
    # Connection
    # ======================================================================

    def _connect(self) -> QdrantClient:
        """
        Connect to Qdrant.

        Priority:
        1. Qdrant Cloud / QDRANT_URL
        2. Qdrant server / host + port
        3. Embedded local Qdrant fallback
        """

        try:
            # --------------------------------------------------------------
            # Qdrant Cloud
            # --------------------------------------------------------------
            if self.settings.qdrant_url:
                client = QdrantClient(
                    url=self.settings.qdrant_url,
                    api_key=self.settings.qdrant_api_key or None,
                    timeout=QDRANT_TIMEOUT_SECONDS,
                )

                target = self.settings.qdrant_url

            # --------------------------------------------------------------
            # Qdrant server
            # --------------------------------------------------------------
            else:
                client = QdrantClient(
                    host=self.settings.qdrant_host,
                    port=self.settings.qdrant_port,
                    api_key=self.settings.qdrant_api_key or None,
                    timeout=QDRANT_TIMEOUT_SECONDS,
                )

                target = (
                    f"{self.settings.qdrant_host}:"
                    f"{self.settings.qdrant_port}"
                )

            # Test the connection.
            client.get_collections()

            logger.info(
                f"Qdrant connected successfully: {target}"
            )

            return client

        except Exception as e:
            # --------------------------------------------------------------
            # Production / Cloud
            # --------------------------------------------------------------
            # If QDRANT_URL is configured, we expect Qdrant Cloud.
            # Do not silently fall back to local ephemeral storage.
            # --------------------------------------------------------------
            if self.settings.qdrant_url:
                logger.exception(
                    f"Qdrant Cloud connection failed: {e}"
                )

                raise RuntimeError(
                    f"Could not connect to Qdrant Cloud: {e}"
                ) from e

            # --------------------------------------------------------------
            # Local development fallback
            # --------------------------------------------------------------
            logger.warning(
                "Qdrant server unavailable. "
                f"Switching to embedded local Qdrant. Error: {e}"
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
                f"Qdrant LOCAL mode enabled. "
                f"Storage path: {local_path}"
            )

            return client

    # ======================================================================
    # Collection helpers
    # ======================================================================

    def _collection_exists(self) -> bool:
        """Return True when the configured Qdrant collection exists."""

        collections = self.client.get_collections().collections

        return any(
            collection.name == self.collection_name
            for collection in collections
        )

    def _init_collection(self) -> None:
        """
        Check whether the configured collection already exists.

        Collection creation is delayed until the first document upload,
        because we need the embedding dimension first.
        """

        try:
            if not self._collection_exists():
                logger.info(
                    f"Collection '{self.collection_name}' "
                    "does not exist yet. "
                    "It will be created on the first upload."
                )
                return

            info = self.client.get_collection(
                self.collection_name
            )

            vectors_config = info.config.params.vectors

            # Standard single-vector collection.
            if hasattr(vectors_config, "size"):
                self._dimension = vectors_config.size

            logger.info(
                f"Collection '{self.collection_name}' ready. "
                f"dimension={self._dimension}, "
                f"total_vectors={self.count}"
            )

        except Exception as e:
            logger.warning(
                f"Collection initialization check failed: {e}"
            )

    def _create_collection(
        self,
        dimension: int,
    ) -> None:
        """Create a Qdrant collection with cosine similarity."""

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
                f"with dimension={dimension}"
            )

        except Exception as e:
            logger.exception(
                f"Collection creation failed: {e}"
            )
            raise

    # ======================================================================
    # Upsert
    # ======================================================================

    def upsert_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> None:
        """
        Upload document chunks and embeddings to Qdrant.

        Large-document optimization:
        Instead of building and sending hundreds/thousands of vectors
        in one request, vectors are sent in batches.

        This reduces:
        - memory usage
        - HTTP payload size
        - Qdrant timeout risk
        - failures with large PDFs
        """

        if not chunks:
            logger.warning(
                "upsert_chunks called with no chunks"
            )
            return

        if not embeddings:
            logger.warning(
                "upsert_chunks called with no embeddings"
            )
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunk/embedding count mismatch: "
                f"chunks={len(chunks)}, "
                f"embeddings={len(embeddings)}"
            )

        dimension = len(embeddings[0])

        if dimension <= 0:
            raise ValueError(
                "Embedding dimension cannot be zero"
            )

        try:
            collection_exists = self._collection_exists()

            # --------------------------------------------------------------
            # First upload: create collection
            # --------------------------------------------------------------
            if not collection_exists:
                self._create_collection(
                    dimension
                )

            # --------------------------------------------------------------
            # Ensure existing dimension is known
            # --------------------------------------------------------------
            elif self._dimension is None:
                info = self.client.get_collection(
                    self.collection_name
                )

                vectors_config = info.config.params.vectors

                if hasattr(vectors_config, "size"):
                    self._dimension = (
                        vectors_config.size
                    )

            # --------------------------------------------------------------
            # Embedding model dimension changed
            # --------------------------------------------------------------
            if (
                self._dimension is not None
                and dimension != self._dimension
            ):
                logger.warning(
                    "Embedding dimension changed: "
                    f"{self._dimension} -> {dimension}. "
                    "Recreating Qdrant collection."
                )

                self.client.delete_collection(
                    collection_name=self.collection_name
                )

                self._create_collection(
                    dimension
                )

            self._dimension = dimension

            total_chunks = len(chunks)

            logger.info(
                f"Starting Qdrant upsert: "
                f"{total_chunks} vectors, "
                f"batch_size={QDRANT_BATCH_SIZE}"
            )

            # --------------------------------------------------------------
            # Batch upload
            # --------------------------------------------------------------
            for start in range(
                0,
                total_chunks,
                QDRANT_BATCH_SIZE,
            ):
                end = min(
                    start + QDRANT_BATCH_SIZE,
                    total_chunks,
                )

                batch_chunks = chunks[start:end]
                batch_embeddings = embeddings[start:end]

                points: List[PointStruct] = []

                for chunk, embedding in zip(
                    batch_chunks,
                    batch_embeddings,
                ):
                    if len(embedding) != dimension:
                        raise ValueError(
                            "Wrong embedding dimension. "
                            f"Expected {dimension}, "
                            f"got {len(embedding)} "
                            f"for chunk {chunk.chunk_id}"
                        )

                    point = PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embedding,
                        payload={
                            "chunk_id": (
                                chunk.chunk_id
                            ),
                            "document_id": (
                                chunk.document_id
                            ),
                            "document_name": (
                                chunk.document_name
                            ),
                            "file_type": (
                                chunk.file_type
                            ),
                            "page_number": (
                                chunk.page_number
                            ),
                            "section": (
                                chunk.section
                            ),
                            "text": (
                                chunk.text
                            ),
                            "metadata": (
                                chunk.metadata
                            ),
                        },
                    )

                    points.append(point)

                logger.info(
                    f"Uploading Qdrant batch: "
                    f"{start + 1}-{end}/"
                    f"{total_chunks}"
                )

                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True,
                )

                logger.info(
                    f"Qdrant progress: "
                    f"{end}/{total_chunks} vectors uploaded"
                )

                # Release the temporary PointStruct objects
                # before the next batch.
                del points

            logger.info(
                f"Successfully upserted "
                f"{total_chunks} vectors to Qdrant"
            )

        except Exception as e:
            logger.exception(
                f"Qdrant upsert failed: {e}"
            )
            raise

    # ======================================================================
    # Search
    # ======================================================================

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """
        Search Qdrant for document chunks similar to a query.

        Args:
            query_embedding:
                Query embedding vector.

            top_k:
                Maximum number of results.

            document_ids:
                Optional document IDs to restrict search.

        Returns:
            Document chunks ordered by vector similarity.
        """

        try:
            if not self._collection_exists():
                logger.warning(
                    f"Collection '{self.collection_name}' "
                    "does not exist"
                )

                return []

            query_filter = None

            # --------------------------------------------------------------
            # Optional document filtering
            # --------------------------------------------------------------
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

            logger.info(
                f"Searching Qdrant: "
                f"top_k={top_k}, "
                f"document_filter="
                f"{bool(document_ids)}"
            )

            # --------------------------------------------------------------
            # Modern Qdrant query API
            # --------------------------------------------------------------
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

            results = response.points

            chunks: List[DocumentChunk] = []

            # --------------------------------------------------------------
            # Convert Qdrant points to application DocumentChunk objects
            # --------------------------------------------------------------
            for scored_point in results:
                payload = (
                    scored_point.payload
                    or {}
                )

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
                    "Top Qdrant result: "
                    f"{chunks[0].document_name}, "
                    f"score={chunks[0].score:.3f}"
                )

            return chunks

        except Exception as e:
            logger.exception(
                f"Qdrant search failed: {e}"
            )

            return []

    # ======================================================================
    # Delete document vectors
    # ======================================================================

    def delete_by_document(
        self,
        document_id: str,
    ) -> int:
        """
        Delete every vector belonging to one document.

        Returns:
            1 when deletion was performed.
            0 when collection does not exist or deletion failed.
        """

        try:
            if not self._collection_exists():
                logger.warning(
                    "Cannot delete document vectors: "
                    "collection does not exist"
                )

                return 0

            document_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(
                            value=document_id
                        ),
                    )
                ]
            )

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=document_filter
                ),
                wait=True,
            )

            logger.info(
                f"Deleted Qdrant vectors for "
                f"document {document_id}"
            )

            return 1

        except Exception as e:
            logger.exception(
                f"Qdrant document deletion failed: {e}"
            )

            return 0

    # ======================================================================
    # Clear collection
    # ======================================================================

    def clear(self) -> None:
        """Delete the complete Qdrant collection."""

        try:
            if self._collection_exists():
                self.client.delete_collection(
                    collection_name=self.collection_name
                )

                logger.info(
                    f"Collection "
                    f"'{self.collection_name}' deleted"
                )

            self._dimension = None

        except Exception as e:
            logger.exception(
                f"Qdrant clear failed: {e}"
            )

    # ======================================================================
    # Properties
    # ======================================================================

    @property
    def dimension(self) -> Optional[int]:
        """Return the active embedding dimension."""

        return self._dimension

    @property
    def count(self) -> int:
        """Return total number of vectors in the collection."""

        try:
            if not self._collection_exists():
                return 0

            result = self.client.count(
                collection_name=self.collection_name,
                exact=True,
            )

            return result.count

        except Exception as e:
            logger.warning(
                f"Qdrant count failed: {e}"
            )

            return 0


# ==========================================================================
# Singleton
# ==========================================================================

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the singleton VectorStore instance."""

    global _vector_store

    if _vector_store is None:
        _vector_store = VectorStore()

    return _vector_store