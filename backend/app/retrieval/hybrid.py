"""Hybrid retrieval: dense + sparse fusion using Reciprocal Rank Fusion (RRF) + CACHING + PARALLEL."""
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.core.cache import get_retrieval_cache, _make_key
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
    """Fuse dense and sparse results using Reciprocal Rank Fusion."""
    dense_scores: Dict[str, float] = {}
    sparse_scores: Dict[str, float] = {}
    all_chunks: Dict[str, DocumentChunk] = {}

    for rank, chunk in enumerate(dense_results, start=1):
        cid = chunk.chunk_id
        dense_scores[cid] = 1.0 / (k + rank)
        all_chunks[cid] = chunk

    for rank, chunk in enumerate(sparse_results, start=1):
        cid = chunk.chunk_id
        sparse_scores[cid] = 1.0 / (k + rank)
        if cid not in all_chunks:
            all_chunks[cid] = chunk

    fused_scores: Dict[str, float] = {}
    for cid in all_chunks:
        fused_scores[cid] = dense_scores.get(cid, 0.0) + sparse_scores.get(cid, 0.0)

    sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)

    results = []
    for cid in sorted_ids[:top_k]:
        chunk = all_chunks[cid]
        chunk.score = fused_scores[cid]
        results.append(chunk)

    return results


class HybridRetriever:
    """Hybrid retriever combining dense and sparse search WITH CACHING + PARALLEL SEARCH."""

    def __init__(self):
        self.dense = get_dense_retriever()
        self.sparse = get_bm25_index()
        self._cache = get_retrieval_cache()

    def search(
        self,
        query: str,
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """Perform hybrid search with RRF fusion and caching."""
        settings = get_settings()

        if not getattr(settings, "cache_enabled", True):
            return self._search_raw(query, top_k, document_ids)

        # Build cache key
        cache_key = _make_key(
            "hybrid_search",
            query.strip().lower(),
            top_k,
            tuple(sorted(document_ids)) if document_ids else None
        )

        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(f"[RETRIEVAL CACHE] HIT for query: {query[:50]}... ({len(cached)} docs)")
            # Reconstruct DocumentChunk objects
            return [DocumentChunk(**doc) for doc in cached]

        results = self._search_raw(query, top_k, document_ids)

        # Cache as dicts for JSON serialization
        self._cache.set(cache_key, [doc.model_dump() for doc in results])
        logger.info(f"[RETRIEVAL CACHE] MISS for query: {query[:50]}... - cached {len(results)} docs")
        return results

    def _search_raw(
        self,
        query: str,
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        """Raw search without cache — DENSE + SPARSE IN PARALLEL."""
        settings = get_settings()
        parallel = getattr(settings, "hybrid_parallel", True)

        logger.info(f"Hybrid search: '{query[:50]}...' (parallel={parallel})")

        if parallel:
            # ------------------------------------------------------------------
            # PRODUCTION FIX: Run dense and sparse in parallel via thread pool
            # Saves ~600-800ms per query (dense embedding API is the bottleneck)
            # ------------------------------------------------------------------
            with ThreadPoolExecutor(max_workers=2) as executor:
                dense_future = executor.submit(
                    self.dense.search, query, top_k=top_k, document_ids=document_ids
                )
                sparse_future = executor.submit(self.sparse.search, query, top_k=top_k)
                dense_results = dense_future.result()
                sparse_results = sparse_future.result()
        else:
            # Sequential fallback (for debugging)
            dense_results = self.dense.search(query, top_k=top_k, document_ids=document_ids)
            sparse_results = self.sparse.search(query, top_k=top_k)

        if document_ids:
            sparse_results = [r for r in sparse_results if r.document_id in document_ids]

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