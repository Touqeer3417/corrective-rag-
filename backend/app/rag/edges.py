"""Conditional edge routing logic for CRAG LangGraph."""
from typing import Literal

from app.config import get_settings
from app.core.logging import get_logger
from app.rag.state import RAGState

logger = get_logger("rag.edges")


def route_after_retrieval(state: RAGState) -> Literal["grade_documents", "transform_query"]:
    """Route after initial retrieval.

    If retrieval returned documents, grade them.
    If empty, try query transformation directly.
    """
    try:
        docs = state.get("documents", [])
        if docs:
            return "grade_documents"

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        if retry_count < max_retries:
            logger.info("[EDGE] No documents retrieved, routing to transform_query")
            return "transform_query"

        # Max retries reached, still route to grader (will fail gracefully)
        return "grade_documents"
    except Exception as e:
        logger.error(f"[EDGE] route_after_retrieval crashed: {e}")
        return "grade_documents"


def decide_after_grading(state: RAGState) -> Literal["reranker", "transform_query", "responder"]:
    """Decide next step after document grading.

    Routes:
    - reranker: Good relevance, proceed to generation
    - transform_query: Poor relevance, attempt corrective retrieval
    - responder: Max retries reached or insufficient evidence

    PRODUCTION FIX: More aggressive thresholds to avoid expensive corrective loops.
    Each loop costs 1 LLM call + 1 retrieval (~5-8 seconds).
    """
    try:
        # SAFE defaults — agar config mein missing ho toh bhi crash nahi hoga
        retrieval_score = state.get("retrieval_score", 0.0) or 0.0
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)
        graded_docs = state.get("graded_documents", [])

        # Thresholds with safe defaults — HIGHER to avoid loops
        high_threshold = 0.65
        low_threshold = 0.40
        try:
            settings = get_settings()
            high_threshold = getattr(settings, "relevance_threshold_high", 0.65)
            low_threshold = getattr(settings, "relevance_threshold_low", 0.40)
            max_retries = state.get("max_retries", getattr(settings, "max_retries", 1))
        except Exception as cfg_err:
            logger.warning(f"[EDGE] Config read failed, using defaults: {cfg_err}")

        logger.info(
            f"[EDGE] Grading decision: score={retrieval_score:.3f}, "
            f"retry={retry_count}/{max_retries}, docs={len(graded_docs)}"
        )

        # ------------------------------------------------------------------
        # HIGH relevance: proceed to rerank (no corrective loop)
        # ------------------------------------------------------------------
        if retrieval_score >= high_threshold and graded_docs:
            logger.info(f"[EDGE] High relevance ({retrieval_score:.3f}) → reranker")
            return "reranker"

        # ------------------------------------------------------------------
        # LOW relevance BUT retries remaining: corrective path
        # PRODUCTION: Only transform if we have SOME docs and score is marginal.
        # If score is extremely low (<0.15) or no docs, skip transform and
        # go straight to responder — transform won't help.
        # ------------------------------------------------------------------
        if retrieval_score < low_threshold and retry_count < max_retries:
            if not graded_docs or retrieval_score < 0.15:
                logger.warning(
                    f"[EDGE] Score too low ({retrieval_score:.3f}) and no docs — "
                    f"skipping transform, going to responder"
                )
                return "responder"
            logger.info(f"[EDGE] Low relevance ({retrieval_score:.3f}) → transform_query")
            return "transform_query"

        # ------------------------------------------------------------------
        # MARGINAL relevance or max retries: proceed with what we have
        # ------------------------------------------------------------------
        if graded_docs:
            logger.info(f"[EDGE] Marginal relevance → reranker with {len(graded_docs)} docs")
            return "reranker"

        # No documents at all after max retries
        logger.warning("[EDGE] No relevant documents after grading → responder")
        return "responder"
    except Exception as e:
        logger.error(f"[EDGE] decide_after_grading crashed: {e}")
        # Graceful fallback: responder par bhejo taake user ko kuch toh mile
        return "responder"