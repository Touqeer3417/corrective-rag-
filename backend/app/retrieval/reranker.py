"""Cross-encoder reranker using local BGE reranker model."""
from typing import List, Optional

from sentence_transformers import CrossEncoder

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk

logger = get_logger("retrieval.reranker")


class Reranker:
    """Cross-encoder reranker for precise relevance scoring."""

    def __init__(self):
        settings = get_settings()
        logger.info(f"Loading reranker: {settings.reranker_model} on {settings.reranker_device}")
        self.model = CrossEncoder(
            settings.reranker_model,
            device=settings.reranker_device,
            max_length=512,
        )
        self.batch_size = settings.reranker_batch_size
        logger.info("Reranker loaded successfully")

    def rerank(
        self,
        query: str,
        chunks: List[DocumentChunk],
        top_k: int = 10,
    ) -> List[DocumentChunk]:
        """Rerank chunks by cross-encoder relevance score.

        Returns:
            Top-k reranked chunks with updated scores
        """
        if not chunks:
            return []

        logger.info(f"Reranking {len(chunks)} chunks for query: {query[:50]}...")

        # Prepare query-document pairs
        pairs = [(query, chunk.text) for chunk in chunks]

        # Score in batches
        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        # Attach scores and sort
        for chunk, score in zip(chunks, scores):
            chunk.score = float(score)

        ranked = sorted(chunks, key=lambda x: x.score or 0.0, reverse=True)
        top_results = ranked[:top_k]

        # Fixed: f-string mein if-else alag se handle karo
        if top_results:
            logger.info(f"Reranker top score: {top_results[0].score:.3f}")
        else:
            logger.info("Reranker top score: 0")

        return top_results


# Singleton
_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker