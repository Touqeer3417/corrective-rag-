"""Hybrid retrieval: dense + sparse fusion using Reciprocal Rank Fusion (RRF)."""
from typing import Dict, List
from typing import List, Optional
from app.config import get_settings
from app.core.logging import get_logger
from app.retrieval.dense import get_dense_retriever
from app.retrieval.sparse import get_bm25_index
from app.schemas.document import DocumentChunk

logger = get_logger("retrieval.hybrid")


def reciprocal_rank_fusion(
    dense_results: List[DocumentChunk],
    sparse_results: List[DocumentChunk],
    k: int = 60,
    top_k: int = 50,
) -> List[DocumentChunk]:
    """Fuse dense and sparse results using Reciprocal Rank Fusion.

    RRF formula: score = sum(1 / (k + rank)) for each list containing the doc
    """
    # Build score maps by chunk_id
    dense_scores: Dict[str, float] = {}
    sparse_scores: Dict[str, float] = {}
    all_chunks: Dict[str, DocumentChunk] = {}

    # Dense ranks (already sorted by score descending)
    for rank, chunk in enumerate(dense_results, start=1):
        cid = chunk.chunk_id
        dense_scores[cid] = 1.0 / (k + rank)
        all_chunks[cid] = chunk

    # Sparse ranks (sorted by BM25 score descending)
    for rank, chunk in enumerate(sparse_results, start=1):
        cid = chunk.chunk_id
        sparse_scores[cid] = 1.0 / (k + rank)
        if cid not in all_chunks:
            all_chunks[cid] = chunk

    # Combine scores
    fused_scores: Dict[str, float] = {}
    for cid in all_chunks:
        fused_scores[cid] = dense_scores.get(cid, 0.0) + sparse_scores.get(cid, 0.0)

    # Sort by fused score descending
    sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)

    results = []
    for cid in sorted_ids[:top_k]:
        chunk = all_chunks[cid]
        chunk.score = fused_scores[cid]
        results.append(chunk)

    return results


class HybridRetriever:
    """Hybrid retriever combining dense and sparse search."""

    def __init__(self):
        self.dense = get_dense_retriever()
        self.sparse = get_bm25_index()

    def search(
        self,
        query: str,
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """Perform hybrid search with RRF fusion.

        Returns:
            Fused and ranked list of DocumentChunks
        """
        settings = get_settings()

        logger.info(f"Hybrid search: '{query[:50]}...'")

        # Parallel retrieval (in practice, could be async)
        dense_results = self.dense.search(query, top_k=top_k, document_ids=document_ids)
        sparse_results = self.sparse.search(query, top_k=top_k)

        # Filter sparse results by document_ids if specified
        if document_ids:
            sparse_results = [r for r in sparse_results if r.document_id in document_ids]

        # Fuse results
        fused = reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            k=settings.rrf_k,
            top_k=top_k,
        )

        logger.info(f"Hybrid fusion returned {len(fused)} results")
        return fused


# Singleton
_hybrid_retriever: Optional[HybridRetriever] = None


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever
