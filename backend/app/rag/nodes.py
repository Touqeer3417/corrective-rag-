"""LangGraph node implementations for CRAG workflow WITH CACHING."""
import json
from typing import List, Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.core.cache import get_grade_cache, _make_key
from app.rag.state import RAGState
from app.rag.models import get_llm_provider
from app.rag.prompts import (
    BATCH_GRADER_SYSTEM_PROMPT,
    BATCH_GRADER_USER_TEMPLATE,
    TRANSFORM_SYSTEM_PROMPT,
    TRANSFORM_USER_TEMPLATE,
    RESPONDER_SYSTEM_PROMPT,
    RESPONDER_USER_TEMPLATE,
    INSUFFICIENT_EVIDENCE_MESSAGE,
)
from app.retrieval.hybrid import get_hybrid_retriever
from app.retrieval.reranker import get_reranker
from app.retrieval.embeddings import get_embedding_model

logger = get_logger("rag.nodes")

class RAGNodes:
    """Collection of LangGraph node functions."""

    def __init__(self):
        self.hybrid = get_hybrid_retriever()
        self.reranker = get_reranker()
        self.llm = get_llm_provider()
        self.embedder = get_embedding_model()
        self._grade_cache = get_grade_cache()

    # ========================================================================
    # NODE: Retrieve Documents
    # ========================================================================
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

    # ========================================================================
    # NODE: Grade Documents (PRODUCTION-GRADE BATCHED + CACHED)
    # ========================================================================
    def grade_documents(self, state: RAGState) -> RAGState:
        """Node: LLM-based document relevance grading — BATCHED + CACHED."""
        docs = state.get("documents", [])
        question = state["question"]

        if not docs:
            logger.warning("[GRADER] No documents to grade")
            state["graded_documents"] = []
            state["retrieval_score"] = 0.0
            state["relevance_scores"] = []
            state["grading_metadata"] = {"error": "no_documents"}
            return state

        settings = get_settings()
        use_cache = getattr(settings, "cache_enabled", True)

        # Build documents block for cache key
        doc_parts = []
        for i, doc in enumerate(docs[:20]):
            text = doc.text[:800]
            if len(doc.text) > 800:
                text += "... [truncated]"
            doc_parts.append(f"--- DOCUMENT [{i}] ---\n{text}\n")
        documents_block = "\n".join(doc_parts)

        # Try cache first
        if use_cache:
            cache_key = _make_key(
                "grade_documents",
                question.strip().lower(),
                documents_block,
                BATCH_GRADER_SYSTEM_PROMPT
            )
            cached = self._grade_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[GRADE CACHE] HIT for {len(docs)} documents")
                state["graded_documents"] = [docs[i] for i in cached["kept_indices"]]
                state["relevance_scores"] = cached["relevance_scores"]
                state["retrieval_score"] = cached["retrieval_score"]
                state["grading_metadata"] = cached["grading_metadata"]
                return state

        logger.info(f"[GRADER] Grading {len(docs)} documents in 1 batched LLM call")

        user_prompt = BATCH_GRADER_USER_TEMPLATE.format(
            question=question,
            documents=documents_block,
        )

        graded = []
        scores = []
        grading_metadata = {
            "total_docs": len(docs),
            "llm_calls_made": 1,
            "fallback_used": False,
            "details": [],
        }

        try:
            result = self.llm.generate(
                system_prompt=BATCH_GRADER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=2048,
                json_mode=True,
            )

            text = result["text"].strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            batch_result = json.loads(text)
            grades = batch_result.get("grades", [])
            needs_web_search = batch_result.get("needs_web_search", False)
            overall_assessment = batch_result.get("overall_assessment", "")

            grade_map = {}
            for g in grades:
                try:
                    idx = int(g.get("doc_index", -1))
                    if 0 <= idx < len(docs):
                        grade_map[idx] = g
                except (ValueError, TypeError):
                    continue

            relevant_count = 0
            kept_indices = []
            
            for i, doc in enumerate(docs):
                grade = grade_map.get(i)

                if grade:
                    score = float(grade.get("score", 0.0))
                    relevant = grade.get("relevant", False)
                    reason = grade.get("reason", "")
                else:
                    score = 0.5
                    relevant = True
                    reason = "Missing grade - fallback to yes"
                    grading_metadata["fallback_used"] = True

                doc.score = score
                grading_metadata["details"].append({
                    "doc_index": i,
                    "relevant": relevant,
                    "score": score,
                    "reason": reason,
                })

                if relevant or score >= 0.3:
                    graded.append(doc)
                    scores.append(score)
                    kept_indices.append(i)
                    if relevant:
                        relevant_count += 1
                else:
                    scores.append(score)

            grading_metadata["relevant_docs"] = relevant_count
            grading_metadata["overall_assessment"] = overall_assessment
            grading_metadata["needs_web_search"] = needs_web_search

            logger.info(
                f"[GRADER] Avg relevance: {sum(scores)/len(scores) if scores else 0:.3f}, "
                f"kept {len(graded)}/{len(docs)}, "
                f"LLM calls: 1 (was {len(docs)})"
            )

            # Store in cache
            if use_cache:
                cache_value = {
                    "kept_indices": kept_indices,
                    "relevance_scores": scores,
                    "retrieval_score": sum(scores) / len(scores) if scores else 0.0,
                    "grading_metadata": grading_metadata,
                }
                self._grade_cache.set(cache_key, cache_value)
                logger.info(f"[GRADE CACHE] Stored result for {len(docs)} docs")

        except Exception as e:
            logger.error(f"[GRADER] Batched grading failed: {e}. Falling back to keeping all docs.")
            for doc in docs:
                doc.score = 0.5
                graded.append(doc)
                scores.append(0.5)

            grading_metadata["fallback_used"] = True
            grading_metadata["error"] = str(e)
            grading_metadata["relevant_docs"] = len(docs)

        state["graded_documents"] = graded
        state["relevance_scores"] = scores
        state["retrieval_score"] = sum(scores) / len(scores) if scores else 0.0
        state["grading_metadata"] = grading_metadata

        return state

    # ========================================================================
    # NODE: Transform Query
    # ========================================================================
    def transform_query(self, state: RAGState) -> RAGState:
        """Node: Query transformation for corrective retrieval."""
        question = state["original_question"]
        current_transformed = state.get("transformed_query")

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
            state["transformed_query"] = f"{question} company policy procedure"
            state["retry_count"] = state.get("retry_count", 0) + 1

        return state

    # ========================================================================
    # NODE: Rerank Documents
    # ========================================================================
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
            state["reranked_documents"] = sorted(
                docs, key=lambda x: x.score or 0.0, reverse=True
            )[:settings.top_k_rerank]

        top_score = state['reranked_documents'][0].score if state['reranked_documents'] else 0
        logger.info(f"[RERANKER] Top score: {top_score:.3f}")
        return state

    # ========================================================================
    # NODE: Generate Answer
    # ========================================================================
    def generate_answer(self, state: RAGState) -> RAGState:
        """Node: Generate grounded answer without citations."""
        docs = state.get("reranked_documents", [])
        question = state["original_question"]
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 2)

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

        context_parts = []
        for i, doc in enumerate(docs[:8], 1):
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
                temperature=0.4,
                max_tokens=2048,
            )

            answer = result["text"].strip()

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