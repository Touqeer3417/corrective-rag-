"""Cross-encoder reranker using local BGE reranker model — WITH FAST PATH."""
from typing import List, Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk

logger = get_logger("retrieval.reranker")


class Reranker:
    """Cross-encoder reranker for precise relevance scoring — WITH FAST PATH."""

    def __init__(self):
        settings = get_settings()

        self.enabled = getattr(settings, "reranker_enabled", True)
        self.skip_threshold = getattr(
            settings,
            "reranker_skip_threshold",
            0.75,
        )

        # Production/free-hosting mode:
        # Do not import sentence-transformers at all.
        if not self.enabled:
            logger.info(
                "Reranker DISABLED — skipping sentence-transformers model loading"
            )
            self.model = None
            self.batch_size = 16
            return

        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required when "
                "RERANKER_ENABLED=true"
            ) from exc

        logger.info(
            f"Loading reranker: {settings.reranker_model} "
            f"on {settings.reranker_device}"
        )

        self.model = CrossEncoder(
            settings.reranker_model,
            device=settings.reranker_device,
            max_length=512,
        )

        self.batch_size = settings.reranker_batch_size

        logger.info("Reranker loaded successfully")

    def should_rerank(
        self,
        chunks: List[DocumentChunk],
    ) -> bool:
        if not self.enabled or not chunks:
            return False

        scores = [
            c.score
            for c in chunks
            if c.score is not None
        ]

        if not scores:
            return True

        avg_score = sum(scores) / len(scores)

        if avg_score >= self.skip_threshold:
            logger.info(
                f"[RERANKER] SKIP — avg hybrid score "
                f"{avg_score:.3f} >= threshold "
                f"{self.skip_threshold:.3f}"
            )
            return False

        return True

    def rerank(
        self,
        query: str,
        chunks: List[DocumentChunk],
        top_k: int = 10,
    ) -> List[DocumentChunk]:

        if not chunks:
            return []

        if not self.should_rerank(chunks):
            ranked = sorted(
                chunks,
                key=lambda x: x.score or 0.0,
                reverse=True,
            )
            return ranked[:top_k]

        pairs = [
            (query, chunk.text)
            for chunk in chunks
        ]

        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        for chunk, score in zip(chunks, scores):
            chunk.score = float(score)

        ranked = sorted(
            chunks,
            key=lambda x: x.score or 0.0,
            reverse=True,
        )

        return ranked[:top_k]


_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    global _reranker

    if _reranker is None:
        _reranker = Reranker()

    return _reranker