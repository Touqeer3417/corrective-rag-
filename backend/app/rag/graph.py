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
        # PRODUCTION FIX: Build prepare graph for streaming (no generation)
        self.prepare_graph = self._build_prepare_graph()

    def _build_graph(self):
        """Build and compile the full CRAG LangGraph (with generation)."""
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


    def _build_prepare_graph(self):
        """Build graph that runs retrieval/grading/reranking WITHOUT generation."""
        builder = StateGraph(RAGState)

        # Add nodes with error handling (same as full graph, minus responder)
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

        # Set entry point
        builder.set_entry_point("retriever")

        # Conditional edges from retriever (same as full graph)
        builder.add_conditional_edges(
            "retriever",
            route_after_retrieval,
            {
                "grade_documents": "grade_documents",
                "transform_query": "transform_query",
            }
        )

        # Conditional edges from grader
        # "responder" route means "insufficient evidence, skip to answer"
        # In prepare mode, we map it to END — the streaming handler will
        # detect insufficient evidence and stream the fallback message
        builder.add_conditional_edges(
            "grade_documents",
            decide_after_grading,
            {
                "reranker": "reranker",
                "transform_query": "transform_query",
                "responder": END,  # Skip generation in prepare mode
            }
        )

        # Deterministic edges
        builder.add_edge("transform_query", "retriever")  # Corrective loop
        builder.add_edge("reranker", END)

        compiled = builder.compile()
        logger.info("CRAG prepare graph compiled successfully (no generation)")
        return compiled

    def invoke(self, question: str, max_retries: int = 2) -> RAGState:
        """Run the full CRAG pipeline synchronously (blocking chat).

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
            "grading_metadata": {},
            "answer": None,
            "citations": [],
            "generation_metadata": {},
            "error": None,
        }

        logger.info(f"Invoking CRAG graph for: {question[:60]}...")
        result = self.graph.invoke(initial_state)
        logger.info(f"CRAG graph completed. Answer length: {len(result.get('answer', '') or '')}")
        return result

    def prepare(self, question: str, max_retries: int = 2) -> RAGState:
        """Run CRAG pipeline up to reranking (excludes LLM generation).

        Use this for streaming: run retrieval/grading/reranking once,
        then stream the answer generation separately via generate_stream().

        Args:
            question: User question
            max_retries: Maximum corrective retrieval attempts

        Returns:
            RAGState with reranked_documents ready for streaming generation.
            Check result['reranked_documents'] and result['retrieval_score']
            to determine if sufficient evidence exists.
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
            "grading_metadata": {},
            "answer": None,
            "citations": [],
            "generation_metadata": {},
            "error": None,
        }

        logger.info(f"Preparing CRAG context for: {question[:60]}...")
        result = self.prepare_graph.invoke(initial_state)
        doc_count = len(result.get("reranked_documents", []))
        score = result.get("retrieval_score", 0) or 0.0
        logger.info(f"CRAG prepare completed. Docs: {doc_count}, score: {score:.3f}")
        return result


# Singleton
_crag_graph: Optional[CRAGGraph] = None

def get_crag_graph() -> CRAGGraph:
    global _crag_graph
    if _crag_graph is None:
        _crag_graph = CRAGGraph()
    return _crag_graph