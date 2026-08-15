"""Cross-encoder reranker using local BGE reranker model — WITH FAST PATH."""
from typing import List, Optional

from sentence_transformers import CrossEncoder

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk

logger = get_logger("retrieval.reranker")


class Reranker:
    """Cross-encoder reranker for precise relevance scoring — WITH FAST PATH."""

    def __init__(self):
        settings = get_settings()
        self.enabled = getattr(settings, "reranker_enabled", True)
        self.skip_threshold = getattr(settings, "reranker_skip_threshold", 0.75)

        if not self.enabled:
            logger.info("Reranker DISABLED in config — skipping cross-encoder loading")
            self.model = None
            self.batch_size = 16
            return

        logger.info(f"Loading reranker: {settings.reranker_model} on {settings.reranker_device}")
        self.model = CrossEncoder(
            settings.reranker_model,
            device=settings.reranker_device,
            max_length=512,
        )
        self.batch_size = settings.reranker_batch_size
        logger.info("Reranker loaded successfully")

    def should_rerank(self, chunks: List[DocumentChunk]) -> bool:
        """Fast check: if docs already have very high scores, skip slow cross-encoder."""
        if not self.enabled or not chunks:
            return False

        # If average score is already high, cross-encoder won't change much
        scores = [c.score for c in chunks if c.score is not None]
        if not scores:
            return True

        avg_score = sum(scores) / len(scores)
        if avg_score >= self.skip_threshold:
            logger.info(
                f"[RERANKER] SKIP — avg hybrid score {avg_score:.3f} >= threshold "
                f"{self.skip_threshold:.3f}. Saving ~{len(chunks) * 150}ms cross-encoder time."
            )
            return False
        return True

    def rerank(
        self,
        query: str,
        chunks: List[DocumentChunk],
        top_k: int = 10,
    ) -> List[DocumentChunk]:
        """Rerank chunks by cross-encoder relevance score.

        PRODUCTION: Skips cross-encoder if hybrid scores are already excellent.
        Returns: Top-k reranked chunks with updated scores
        """
        if not chunks:
            return []

        # ------------------------------------------------------------------
        # FAST PATH: Skip expensive cross-encoder when confidence is high
        # ------------------------------------------------------------------
        if not self.should_rerank(chunks):
            # Just sort by existing score and trim
            ranked = sorted(chunks, key=lambda x: x.score or 0.0, reverse=True)
            return ranked[:top_k]

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