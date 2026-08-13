"""LangGraph node implementations for CRAG workflow."""
import json
import re
from typing import List
from typing import List, Optional
from app.config import get_settings
from app.core.logging import get_logger
from app.rag.state import RAGState
from app.rag.models import get_llm_provider
from app.rag.prompts import (
    GRADER_SYSTEM_PROMPT,
    GRADER_USER_TEMPLATE,
    TRANSFORM_SYSTEM_PROMPT,
    TRANSFORM_USER_TEMPLATE,
    RESPONDER_SYSTEM_PROMPT,
    RESPONDER_USER_TEMPLATE,
    INSUFFICIENT_EVIDENCE_MESSAGE,
)
from app.retrieval.hybrid import get_hybrid_retriever
from app.retrieval.reranker import get_reranker
from app.retrieval.embeddings import get_embedding_model
from app.schemas.document import DocumentChunk

logger = get_logger("rag.nodes")


class RAGNodes:
    """Collection of LangGraph node functions."""

    def __init__(self):
        self.hybrid = get_hybrid_retriever()
        self.reranker = get_reranker()
        self.llm = get_llm_provider()
        self.embedder = get_embedding_model()

    def retrieve_docs(self, state: RAGState) -> RAGState:
        """Node: Hybrid retrieval (BM25 + Dense)."""
        query = state.get("transformed_query") or state["question"]
        settings = get_settings()

        logger.info(f"[RETRIEVER] Query: {query[:60]}... (retry={state['retry_count']})")

        try:
            docs = self.hybrid.search(query, top_k=settings.top_k_hybrid)
            state["documents"] = docs
            state["error"] = None
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            state["documents"] = []
            state["error"] = f"Retrieval error: {str(e)}"

        return state

    def grade_documents(self, state: RAGState) -> RAGState:
        """Node: LLM-based document relevance grading."""
        docs = state.get("documents", [])
        question = state["question"]

        if not docs:
            logger.warning("[GRADER] No documents to grade")
            state["graded_documents"] = []
            state["retrieval_score"] = 0.0
            state["relevance_scores"] = []
            return state

        logger.info(f"[GRADER] Grading {len(docs)} documents")

        graded = []
        scores = []

        
        for doc in docs[:20]:
            try:
                prompt = GRADER_USER_TEMPLATE.format(
                    question=question,
                    document_text=doc.text[:800],  # Limit context for grading
                )
                result = self.llm.generate(
                    system_prompt=GRADER_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    temperature=0.0,
                    max_tokens=256,
                    json_mode=True,
                )

                # Parse JSON response
                text = result["text"].strip()
                # Extract JSON if wrapped in markdown
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()

                grade = json.loads(text)
                score = float(grade.get("score", 0.0))
                relevant = grade.get("relevant", False)

                doc.score = score
                if relevant or score >= 0.3:  # Keep marginally relevant docs
                    graded.append(doc)
                    scores.append(score)

            except Exception as e:
                logger.warning(f"Grading failed for chunk {doc.chunk_id}: {e}")
                # Default to keeping the document
                doc.score = 0.5
                graded.append(doc)
                scores.append(0.5)

        state["graded_documents"] = graded
        state["relevance_scores"] = scores
        state["retrieval_score"] = sum(scores) / len(scores) if scores else 0.0

        logger.info(f"[GRADER] Avg relevance: {state['retrieval_score']:.3f}, kept {len(graded)}/{len(docs)}")
        return state

    def transform_query(self, state: RAGState) -> RAGState:
        """Node: Query transformation for corrective retrieval."""
        question = state["original_question"]
        current_transformed = state.get("transformed_query")

        # If already transformed once, try expanding further
        if current_transformed:
            prompt = f"The previous query rewrite did not yield good results. Original: {question}. Previous rewrite: {current_transformed}. Generate a different, more specific search query."
        else:
            prompt = TRANSFORM_USER_TEMPLATE.format(question=question)

        logger.info(f"[TRANSFORM] Rewriting query: {question[:60]}...")

        try:
            result = self.llm.generate(
                system_prompt=TRANSFORM_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=100,
            )
            transformed = result["text"].strip().strip('"').strip("'")
            state["transformed_query"] = transformed
            state["retry_count"] = state.get("retry_count", 0) + 1
            logger.info(f"[TRANSFORM] New query: {transformed[:60]}...")
        except Exception as e:
            logger.error(f"Query transformation failed: {e}")
            # Fallback: append keywords
            state["transformed_query"] = f"{question} company policy procedure"
            state["retry_count"] = state.get("retry_count", 0) + 1

        return state

    def rerank_documents(self, state: RAGState) -> RAGState:
        """Node: Cross-encoder reranking."""
        docs = state.get("graded_documents", [])
        question = state.get("transformed_query") or state["question"]
        settings = get_settings()

        if not docs:
            logger.warning("[RERANKER] No documents to rerank")
            state["reranked_documents"] = []
            return state

        logger.info(f"[RERANKER] Reranking {len(docs)} documents")

        try:
            reranked = self.reranker.rerank(
                query=question,
                chunks=docs,
                top_k=settings.top_k_rerank,
            )
            state["reranked_documents"] = reranked
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Fallback: use graded documents sorted by score
            state["reranked_documents"] = sorted(
                docs, key=lambda x: x.score or 0.0, reverse=True
            )[:settings.top_k_rerank]

        top_score = state['reranked_documents'][0].score if state['reranked_documents'] else 0
        logger.info(f"[RERANKER] Top score: {top_score:.3f}")
        return state

    def generate_answer(self, state: RAGState) -> RAGState:
        """Node: Generate grounded answer without citations."""
        docs = state.get("reranked_documents", [])
        question = state["original_question"]
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

        # Check if we have sufficient evidence
        if not docs or (state.get("retrieval_score", 0) < 0.2 and retry_count >= max_retries):
            logger.warning("[RESPONDER] Insufficient evidence after max retries")
            state["answer"] = INSUFFICIENT_EVIDENCE_MESSAGE
            state["citations"] = []
            state["generation_metadata"] = {
                "model": "none",
                "tokens_used": 0,
                "latency_ms": 0,
                "insufficient_evidence": True,
            }
            return state

        # Build context from top documents
        context_parts = []
        for i, doc in enumerate(docs[:8], 1):  # Use top 8 for context
            context_parts.append(
                f"[Document {i}] {doc.document_name} (Page {doc.page_number or 'N/A'}):\n{doc.text[:800]}"
            )
        context = "\n\n".join(context_parts)

        prompt = RESPONDER_USER_TEMPLATE.format(context=context, question=question)

        logger.info(f"[RESPONDER] Generating answer with {len(docs)} documents")

        try:
            result = self.llm.generate(
                system_prompt=RESPONDER_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.6,  # Higher temperature for paraphrasing/synthesis
                max_tokens=2048,
            )

            answer = result["text"].strip()

            # NO CITATIONS — always empty
            state["answer"] = answer
            state["citations"] = []
            state["generation_metadata"] = {
                "model": result.get("model", "unknown"),
                "tokens_used": result.get("tokens_used", 0),
                "latency_ms": result.get("latency_ms", 0),
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            state["answer"] = "I apologize, but I encountered an error while generating the answer. Please try again."
            state["citations"] = []
            state["error"] = str(e)

        return state


# Singleton instance
_nodes_instance: Optional[RAGNodes] = None


def get_rag_nodes() -> RAGNodes:
    global _nodes_instance
    if _nodes_instance is None:
        _nodes_instance = RAGNodes()
    return _nodes_instance