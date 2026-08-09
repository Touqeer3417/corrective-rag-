"""LangGraph CRAG workflow builder and compiler."""
from typing import Callable, Optional


from langgraph.graph import StateGraph, END

from app.core.logging import get_logger
from app.rag.state import RAGState
from app.rag.nodes import get_rag_nodes
from app.rag.edges import route_after_retrieval, decide_after_grading

logger = get_logger("rag.graph")


def with_error_handling(node_name: str):
    """Decorator to wrap node execution with error handling."""
    def decorator(func: Callable):
        def wrapper(state: RAGState) -> RAGState:
            try:
                return func(state)
            except Exception as e:
                logger.error(f"Node '{node_name}' failed: {e}")
                state["error"] = f"{node_name}: {str(e)}"
                # Graceful degradation: return state as-is
                return state
        return wrapper
    return decorator


class CRAGGraph:
    """Corrective RAG LangGraph state machine."""

    def __init__(self):
        self.nodes = get_rag_nodes()
        self.graph = self._build_graph()

    def _build_graph(self):
        """Build and compile the CRAG LangGraph."""
        builder = StateGraph(RAGState)

        # Add nodes with error handling
        builder.add_node(
            "retriever",
            with_error_handling("retriever")(self.nodes.retrieve_docs)
        )
        builder.add_node(
            "grade_documents",
            with_error_handling("grade_documents")(self.nodes.grade_documents)
        )
        builder.add_node(
            "transform_query",
            with_error_handling("transform_query")(self.nodes.transform_query)
        )
        builder.add_node(
            "reranker",
            with_error_handling("reranker")(self.nodes.rerank_documents)
        )
        builder.add_node(
            "responder",
            with_error_handling("responder")(self.nodes.generate_answer)
        )

        # Set entry point
        builder.set_entry_point("retriever")

        # Conditional edges from retriever
        builder.add_conditional_edges(
            "retriever",
            route_after_retrieval,
            {
                "grade_documents": "grade_documents",
                "transform_query": "transform_query",
            }
        )

        # Conditional edges from grader
        builder.add_conditional_edges(
            "grade_documents",
            decide_after_grading,
            {
                "reranker": "reranker",
                "transform_query": "transform_query",
                "responder": "responder",
            }
        )

        # Deterministic edges
        builder.add_edge("transform_query", "retriever")  # Corrective loop
        builder.add_edge("reranker", "responder")
        builder.add_edge("responder", END)

        compiled = builder.compile()
        logger.info("CRAG LangGraph compiled successfully")
        return compiled

    def invoke(self, question: str, max_retries: int = 2) -> RAGState:
        """Run the CRAG pipeline synchronously.

        Args:
            question: User question
            max_retries: Maximum corrective retrieval attempts

        Returns:
            Final RAGState with answer and citations
        """
        initial_state: RAGState = {
            "question": question,
            "original_question": question,
            "documents": [],
            "graded_documents": [],
            "reranked_documents": [],
            "transformed_query": None,
            "retry_count": 0,
            "max_retries": max_retries,
            "retrieval_score": None,
            "relevance_scores": [],
            "answer": None,
            "citations": [],
            "generation_metadata": {},
            "error": None,
        }

        logger.info(f"Invoking CRAG graph for: {question[:60]}...")
        result = self.graph.invoke(initial_state)
        logger.info(f"CRAG graph completed. Answer length: {len(result.get('answer', '') or '')}")
        return result


# Singleton
_crag_graph: Optional[CRAGGraph] = None


def get_crag_graph() -> CRAGGraph:
    global _crag_graph
    if _crag_graph is None:
        _crag_graph = CRAGGraph()
    return _crag_graph
