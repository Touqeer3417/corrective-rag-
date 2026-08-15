"""LangGraph node implementations for CRAG workflow WITH CACHING + SPEED OPTIMIZATIONS."""
import hashlib
import json
from typing import List, Optional

import numpy as np

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
    # NODE: Grade Documents (PRODUCTION-GRADE 3-TIER: Embedding + Batch LLM)
    # ========================================================================
    def grade_documents(self, state: RAGState) -> RAGState:
        """Node: Optimized relevance grading — Embedding pre-filter + 1 batched LLM call.

        Tier 1: Embedding cosine similarity (FREE) — filters & sorts docs.
        Tier 2: Fast path — if top doc similarity > threshold, skip LLM entirely.
        Tier 3: Batch LLM grade — only top-N docs, truncated to max chars.
        """
        docs = state.get("documents", [])
        question = state["question"]

        if not docs:
            logger.warning("[GRADER] No documents to grade")
            state["graded_documents"] = []
            state["retrieval_score"] = 0.0
            state["relevance_scores"] = []
            state["grading_metadata"] = {"error": "no_documents", "llm_calls_made": 0}
            return state

        settings = get_settings()
        use_cache = getattr(settings, "cache_enabled", True)
        max_docs = settings.grade_max_docs_per_batch
        max_chars = settings.grade_max_chars_per_doc
        pre_filter = settings.grade_embedding_pre_filter
        emb_threshold = settings.grade_embedding_threshold
        fast_path = settings.grade_fast_path_enabled
        fast_threshold = settings.grade_fast_path_threshold
        grade_max_tokens = getattr(settings, "grade_max_tokens", 1024)

        # ======================================================================
        # TIER 1: Embedding Similarity Pre-Filter
        # ======================================================================
        pre_filtered_docs = docs
        embedding_scores: List[float] = []
        pre_filter_applied = False

        if pre_filter and len(docs) > 1 and self.embedder is not None:
            try:
                # Encode query (cached internally by embedder)
                query_emb = self.embedder.encode_query(question)
                q_vec = np.array(query_emb, dtype=np.float32)
                q_norm = np.linalg.norm(q_vec)
                if q_norm == 0:
                    q_norm = 1.0

                # Batch encode all docs (1 API call for OpenAI, 1 batch for local)
                doc_texts = [d.text[:max_chars] for d in docs]
                doc_embs = self.embedder.encode(doc_texts)

                # Compute cosine similarities
                similarities = []
                for emb in doc_embs:
                    d_vec = np.array(emb, dtype=np.float32)
                    d_norm = np.linalg.norm(d_vec)
                    if d_norm == 0:
                        similarities.append(0.0)
                    else:
                        sim = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))
                        similarities.append(sim)

                # Attach similarities to doc metadata for observability
                for doc, sim in zip(docs, similarities):
                    doc.metadata["embedding_similarity"] = round(sim, 4)

                # Sort by similarity descending
                scored_docs = list(zip(docs, similarities))
                scored_docs.sort(key=lambda x: x[1], reverse=True)

                # ------------------------------------------------------------------
                # TIER 2: Fast Path — skip LLM if top doc is extremely similar
                # ------------------------------------------------------------------
                if fast_path and scored_docs and scored_docs[0][1] >= fast_threshold:
                    top_sim = scored_docs[0][1]
                    logger.info(f"[GRADER] FAST PATH triggered (top_sim={top_sim:.3f}). Skipping LLM.")

                    graded = []
                    scores = []
                    kept_indices = []
                    for i, (doc, sim) in enumerate(scored_docs):
                        relevant = sim >= emb_threshold
                        doc.score = min(sim, 1.0)
                        if relevant:
                            graded.append(doc)
                            scores.append(doc.score)
                            kept_indices.append(i)

                    retrieval_score = sum(scores) / len(scores) if scores else 0.0

                    grading_metadata = {
                        "total_docs": len(docs),
                        "llm_calls_made": 0,
                        "fallback_used": False,
                        "fast_path": True,
                        "pre_filter_applied": True,
                        "relevant_docs": len(graded),
                        "details": [
                            {
                                "doc_index": i,
                                "relevant": sim >= emb_threshold,
                                "score": round(sim, 3),
                                "reason": f"Embedding similarity: {sim:.3f}",
                            }
                            for i, (_, sim) in enumerate(scored_docs)
                        ],
                    }

                    state["graded_documents"] = graded
                    state["relevance_scores"] = scores
                    state["retrieval_score"] = retrieval_score
                    state["grading_metadata"] = grading_metadata
                    return state

                # Filter out docs below threshold, keep top max_docs
                filtered = [(d, s) for d, s in scored_docs if s >= emb_threshold]
                if not filtered:
                    # Safety: if nothing passes threshold, keep top 3
                    filtered = scored_docs[:3]

                pre_filtered_docs = [d for d, s in filtered[:max_docs]]
                embedding_scores = [s for d, s in filtered[:max_docs]]
                pre_filter_applied = True

                logger.info(
                    f"[GRADER] Pre-filter: {len(docs)} docs → {len(pre_filtered_docs)} docs "
                    f"(top_sim={scored_docs[0][1]:.3f}, threshold={emb_threshold})"
                )

            except Exception as e:
                logger.warning(f"[GRADER] Embedding pre-filter failed: {e}. Falling back to all docs.")
                pre_filtered_docs = docs
                embedding_scores = []

        # ======================================================================
        # Build optimized prompt with reduced docs & chars
        # ======================================================================
        docs_to_grade = pre_filtered_docs if pre_filter_applied else docs[:max_docs]

        if not docs_to_grade:
            logger.warning("[GRADER] No documents after pre-filter")
            state["graded_documents"] = []
            state["retrieval_score"] = 0.0
            state["relevance_scores"] = []
            state["grading_metadata"] = {
                "error": "no_documents_after_prefilter",
                "llm_calls_made": 0,
            }
            return state

        doc_parts = []
        for i, doc in enumerate(docs_to_grade):
            text = doc.text[:max_chars]
            if len(doc.text) > max_chars:
                text += "... [truncated]"
            meta = f"Source: {doc.document_name}"
            if doc.page_number:
                meta += f", Page {doc.page_number}"
            doc_parts.append(f"--- DOC [{i}] | {meta} ---\n{text}\n")
        documents_block = "\n".join(doc_parts)

        # ======================================================================
        # Cache check (optimized key using SHA256 hash — no giant strings)
        # ======================================================================
        cache_key: Optional[str] = None
        if use_cache:
            docs_hash = hashlib.sha256(documents_block.encode("utf-8")).hexdigest()[:24]
            cache_key = _make_key(
                "grade_documents_v2",
                question.strip().lower(),
                docs_hash,
                len(docs_to_grade),
                max_chars,
            )
            cached = self._grade_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[GRADE CACHE] HIT for {len(docs_to_grade)} documents")
                state["graded_documents"] = [
                    docs_to_grade[i] for i in cached["kept_indices"] if 0 <= i < len(docs_to_grade)
                ]
                state["relevance_scores"] = cached["relevance_scores"]
                state["retrieval_score"] = cached["retrieval_score"]
                state["grading_metadata"] = cached["grading_metadata"]
                return state

        # ======================================================================
        # TIER 3: LLM Batch Grade (1 call, ~70% smaller prompt than before)
        # ======================================================================
        logger.info(f"[GRADER] Grading {len(docs_to_grade)} documents in 1 batched LLM call")

        user_prompt = BATCH_GRADER_USER_TEMPLATE.format(
            question=question,
            documents=documents_block,
        )

        graded: List = []
        scores: List[float] = []
        kept_indices: List[int] = []
        grading_metadata = {
            "total_docs": len(docs),
            "graded_count": len(docs_to_grade),
            "llm_calls_made": 1,
            "fallback_used": False,
            "pre_filter_applied": pre_filter_applied,
            "fast_path": False,
            "details": [],
        }

        try:
            result = self.llm.generate(
                system_prompt=BATCH_GRADER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=grade_max_tokens,
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
                    if 0 <= idx < len(docs_to_grade):
                        grade_map[idx] = g
                except (ValueError, TypeError):
                    continue

            relevant_count = 0

            for i, doc in enumerate(docs_to_grade):
                grade = grade_map.get(i)

                if grade:
                    score = float(grade.get("score", 0.0))
                    relevant = grade.get("relevant", False)
                    reason = grade.get("reason", "")
                else:
                    # Fallback: use embedding score if available, else neutral 0.5
                    if pre_filter_applied and i < len(embedding_scores):
                        score = embedding_scores[i]
                        relevant = score >= emb_threshold
                        reason = f"Missing LLM grade — fallback to embedding score: {score:.3f}"
                    else:
                        score = 0.5
                        relevant = True
                        reason = "Missing grade — fallback to yes"
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
                f"kept {len(graded)}/{len(docs_to_grade)} (of {len(docs)} total), "
                f"LLM calls: 1"
            )

            # Store in cache
            if use_cache and cache_key is not None:
                cache_value = {
                    "kept_indices": kept_indices,
                    "relevance_scores": scores,
                    "retrieval_score": sum(scores) / len(scores) if scores else 0.0,
                    "grading_metadata": grading_metadata,
                }
                self._grade_cache.set(cache_key, cache_value)
                logger.info(f"[GRADE CACHE] Stored result for {len(docs_to_grade)} docs")

        except Exception as e:
            logger.error(f"[GRADER] Batched grading failed: {e}. Falling back.")

            # Smart fallback: if pre-filter was applied, use embedding scores
            if pre_filter_applied and embedding_scores:
                graded = []
                scores = []
                for i, doc in enumerate(docs_to_grade):
                    score = embedding_scores[i] if i < len(embedding_scores) else 0.5
                    doc.score = score
                    if score >= 0.3:
                        graded.append(doc)
                        scores.append(score)
                grading_metadata["fallback_used"] = True
                grading_metadata["error"] = str(e)
                grading_metadata["relevant_docs"] = len(graded)
            else:
                # Ultimate fallback: keep all with neutral score
                for doc in docs_to_grade:
                    doc.score = 0.5
                    graded.append(doc)
                    scores.append(0.5)
                grading_metadata["fallback_used"] = True
                grading_metadata["error"] = str(e)
                grading_metadata["relevant_docs"] = len(docs_to_grade)

        state["graded_documents"] = graded
        state["relevance_scores"] = scores
        state["retrieval_score"] = sum(scores) / len(scores) if scores else 0.0
        state["grading_metadata"] = grading_metadata

        return state

    # ========================================================================
    # NODE: Transform Query  (HEURISTIC FAST PATH ADDED)
    # ========================================================================
    def transform_query(self, state: RAGState) -> RAGState:
        """Node: Query transformation for corrective retrieval.
        
        PRODUCTION FIX: Uses heuristic expansion first (FREE, <10ms).
        Only falls back to LLM rewrite on 2nd+ retry or when heuristic is disabled.
        """
        question = state["original_question"]
        current_transformed = state.get("transformed_query")
        retry_count = state.get("retry_count", 0)
        settings = get_settings()
        use_heuristic = getattr(settings, "transform_heuristic_first", True)

        # ------------------------------------------------------------------
        # FAST PATH: Heuristic expansion (no LLM call, instant)
        # ------------------------------------------------------------------
        if use_heuristic and retry_count == 0 and not current_transformed:
            # Simple keyword expansion — adds domain context without LLM latency
            expanded = self._heuristic_expand(question)
            if expanded != question:
                state["transformed_query"] = expanded
                state["retry_count"] = retry_count + 1
                logger.info(f"[TRANSFORM] HEURISTIC fast path: {expanded[:60]}...")
                return state

        # LLM-based rewrite (slower, but more intelligent)
        if current_transformed:
            prompt = f"The previous query rewrite did not yield good results. Original: {question}. Previous rewrite: {current_transformed}. Generate a different, more specific search query."
        else:
            prompt = TRANSFORM_USER_TEMPLATE.format(question=question)

        logger.info(f"[TRANSFORM] LLM rewrite: {question[:60]}...")

        try:
            result = self.llm.generate(
                system_prompt=TRANSFORM_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=100,
            )
            transformed = result["text"].strip().strip('"').strip("'")
            state["transformed_query"] = transformed
            state["retry_count"] = retry_count + 1
            logger.info(f"[TRANSFORM] New query: {transformed[:60]}...")
        except Exception as e:
            logger.error(f"Query transformation failed: {e}")
            state["transformed_query"] = f"{question} company policy procedure"
            state["retry_count"] = retry_count + 1

        return state

    def _heuristic_expand(self, query: str) -> str:
        """Fast heuristic query expansion — no LLM needed."""
        q = query.strip().lower()

        # If already keyword-rich and long, return as-is
        if len(q.split()) >= 6:
            return query

        # Expand common abbreviations and add domain context
        expansions = []
        if "hr" in q.split() or "hr " in q:
            expansions.append("human resources")
        if "it" in q.split():
            expansions.append("information technology")
        if "ceo" in q:
            expansions.append("chief executive officer")
        if "cfo" in q:
            expansions.append("chief financial officer")

        # Add domain boosters for short queries
        boosters = ["company policy", "procedure", "guidelines"]
        # Only add if not already present
        for b in boosters:
            if b not in q:
                expansions.append(b)
                break  # Just add one to keep it concise

        if expansions:
            return f"{query} {' '.join(expansions)}"

        return query

    # ========================================================================
    # NODE: Rerank Documents  (FAST PATH — skip cross-encoder when confident)
    # ========================================================================
    def rerank_documents(self, state: RAGState) -> RAGState:
        """Node: Cross-encoder reranking — WITH FAST PATH."""
        docs = state.get("graded_documents", [])
        question = state.get("transformed_query") or state["question"]
        settings = get_settings()

        if not docs:
            logger.warning("[RERANKER] No documents to rerank")
            state["reranked_documents"] = []
            return state

        # ------------------------------------------------------------------
        # PRODUCTION FIX: Skip slow cross-encoder if graded docs are already
        # high quality. This saves 3-5 seconds on CPU per query.
        # ------------------------------------------------------------------
        if not self.reranker.enabled:
            logger.info("[RERANKER] Disabled in config — passing through graded docs")
            state["reranked_documents"] = sorted(
                docs, key=lambda x: x.score or 0.0, reverse=True
            )[:settings.top_k_rerank]
            return state

        if not self.reranker.should_rerank(docs):
            # Fast path: already good scores from hybrid + grading
            state["reranked_documents"] = sorted(
                docs, key=lambda x: x.score or 0.0, reverse=True
            )[:settings.top_k_rerank]
            top_score = state["reranked_documents"][0].score if state["reranked_documents"] else 0
            logger.info(f"[RERANKER] Fast pass — top score: {top_score:.3f}")
            return state

        logger.info(f"[RERANKER] Running cross-encoder on {len(docs)} documents")

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

        top_score = state["reranked_documents"][0].score if state["reranked_documents"] else 0
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