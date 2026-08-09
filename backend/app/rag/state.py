"""LangGraph RAG state definition."""
from typing import Any, Dict, List, Optional, TypedDict

from app.schemas.document import DocumentChunk
from app.schemas.chat import Citation


class RAGState(TypedDict):
    """Strongly typed state for the CRAG LangGraph workflow.

    Fields:
        question: Current query (may be transformed)
        original_question: User's original query
        documents: Raw hybrid retrieval results
        graded_documents: Documents with relevance grades
        reranked_documents: Cross-encoder reranked documents
        transformed_query: Query rewrite for corrective retrieval
        retry_count: Current corrective loop iteration
        max_retries: Maximum allowed retries
        retrieval_score: Average relevance score from grader
        relevance_scores: Individual relevance scores
        answer: Generated answer text
        citations: Structured citations for the answer
        generation_metadata: LLM usage metadata (tokens, latency, model)
        error: Error message if pipeline fails
    """
    # Input
    question: str
    original_question: str

    # Retrieval
    documents: List[DocumentChunk]
    graded_documents: List[DocumentChunk]
    reranked_documents: List[DocumentChunk]

    # Correction
    transformed_query: Optional[str]
    retry_count: int
    max_retries: int

    # Grading
    retrieval_score: Optional[float]
    relevance_scores: List[float]

    # Output
    answer: Optional[str]
    citations: List[Citation]

    # Metadata
    generation_metadata: Dict[str, Any]
    error: Optional[str]
