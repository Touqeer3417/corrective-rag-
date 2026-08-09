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


def decide_after_grading(state: RAGState) -> Literal["reranker", "transform_query", "responder"]:
    """Decide next step after document grading.

    Routes:
        - reranker: Good relevance, proceed to generation
        - transform_query: Poor relevance, attempt corrective retrieval
        - responder: Max retries reached or insufficient evidence
    """
    settings = get_settings()
    retrieval_score = state.get("retrieval_score", 0.0) or 0.0
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.max_retries)
    graded_docs = state.get("graded_documents", [])

    logger.info(f"[EDGE] Grading decision: score={retrieval_score:.3f}, retry={retry_count}/{max_retries}")

    # High relevance: proceed to rerank
    if retrieval_score >= settings.relevance_threshold_high and graded_docs:
        return "reranker"

    # Low relevance but retries remaining: corrective path
    if retrieval_score < settings.relevance_threshold_low and retry_count < max_retries:
        logger.info(f"[EDGE] Low relevance ({retrieval_score:.3f}), routing to transform_query")
        return "transform_query"

    # Marginal relevance or max retries: proceed with what we have
    if graded_docs:
        logger.info(f"[EDGE] Proceeding to reranker with {len(graded_docs)} docs")
        return "reranker"

    # No documents at all after max retries
    logger.warning("[EDGE] No relevant documents after grading, routing to responder")
    return "responder"
