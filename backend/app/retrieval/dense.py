"""Dense vector retrieval via Qdrant."""
from typing import List, Optional

from app.core.logging import get_logger
from app.retrieval.embeddings import get_embedding_model
from app.storage.vector_store import get_vector_store
from app.schemas.document import DocumentChunk

logger = get_logger("retrieval.dense")


class DenseRetriever:
    """Dense semantic retrieval using vector embeddings."""

    def __init__(self):
        self.embedder = get_embedding_model()
        self.vector_store = get_vector_store()

    def search(
        self,
        query: str,
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """Search using dense vector similarity."""
        logger.info(f"Dense retrieval: query='{query[:50]}...', top_k={top_k}")
        query_embedding = self.embedder.encode_query(query)
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            document_ids=document_ids,
        )
        logger.info(f"Dense retrieval returned {len(results)} results")
        return results


# Singleton
_dense_retriever: Optional[DenseRetriever] = None


def get_dense_retriever() -> DenseRetriever:
    global _dense_retriever
    if _dense_retriever is None:
        _dense_retriever = DenseRetriever()
    return _dense_retriever
