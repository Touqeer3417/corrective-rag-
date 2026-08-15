"""Chat and RAG orchestration service WITH ANSWER CACHING + SPEED OPTIMIZATIONS."""
import asyncio
import json
from typing import AsyncGenerator

from app.config import get_settings
from app.core.logging import get_logger
from app.core.cache import get_answer_cache, _make_key
from app.rag.graph import get_crag_graph
from app.rag.models import get_llm_provider
from app.rag.prompts import (
    RESPONDER_SYSTEM_PROMPT,
    RESPONDER_USER_TEMPLATE,
    INSUFFICIENT_EVIDENCE_MESSAGE,
)
from app.schemas.chat import ChatResponse

logger = get_logger("services.chat")


def _sse(data: dict) -> str:
    """Build an SSE event line from a dict."""
    return f"data: {json.dumps(data)}\n\n"


class ChatService:
    """Handle chat queries and streaming responses WITH CACHING."""

    def __init__(self):
        self.crag = get_crag_graph()
        self.llm = get_llm_provider()
        self._answer_cache = get_answer_cache()

    async def chat(self, question: str) -> ChatResponse:
        """Async chat with full CRAG pipeline via thread pool + caching."""
        settings = get_settings()
        use_cache = getattr(settings, "cache_enabled", True)

        # Try answer cache first
        cache_key = _make_key("chat_answer", question.strip().lower())
        if use_cache:
            cached = self._answer_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[ANSWER CACHE] HIT for question: {question[:60]}...")
                return ChatResponse(
                    answer=cached["answer"],
                    citations=[],
                    confidence=cached.get("confidence", 0.0),
                    retry_count=cached.get("retry_count", 0),
                    transformed_query=cached.get("transformed_query"),
                    generation_metadata=cached.get("generation_metadata", {}),
                )

        try:
            result = await asyncio.to_thread(self.crag.invoke, question)

            response = ChatResponse(
                answer=result.get("answer") or "No answer generated.",
                citations=[],
                confidence=result.get("retrieval_score") or 0.0,
                retry_count=result.get("retry_count", 0),
                transformed_query=result.get("transformed_query"),
                generation_metadata=result.get("generation_metadata", {}),
            )

            # Cache the answer
            if use_cache and response.answer and not response.answer.startswith("I apologize"):
                cache_value = {
                    "answer": response.answer,
                    "confidence": response.confidence,
                    "retry_count": response.retry_count,
                    "transformed_query": response.transformed_query,
                    "generation_metadata": response.generation_metadata,
                }
                self._answer_cache.set(cache_key, cache_value)
                logger.info(f"[ANSWER CACHE] Stored answer for: {question[:60]}...")

            return response

        except Exception as e:
            logger.error(f"Chat invocation failed: {e}")
            return ChatResponse(
                answer="I apologize, but I encountered an error processing your request. Please try again.",
                citations=[],
                confidence=0.0,
                retry_count=0,
                transformed_query=None,
                generation_metadata={"error": str(e)},
            )

    async def chat_stream(self, question: str) -> AsyncGenerator[str, None]:
        """Streaming chat response via SSE — with answer caching."""
        settings = get_settings()
        use_cache = getattr(settings, "cache_enabled", True)
        cache_key = _make_key("chat_answer", question.strip().lower())

        # Try answer cache first for streaming too
        if use_cache:
            cached = self._answer_cache.get(cache_key)
            if cached is not None:
                logger.info(f"[ANSWER CACHE] HIT for stream: {question[:60]}...")
                # Stream cached answer word by word for UX
                words = cached["answer"].split(" ")
                for word in words:
                    yield _sse({"type": "token", "content": word + " "})
                    await asyncio.sleep(0.01)  # Small delay for natural feel

                yield _sse({
                    "type": "metadata",
                    "data": {
                        "retry_count": cached.get("retry_count", 0),
                        "transformed_query": cached.get("transformed_query"),
                        "retrieval_score": round(cached.get("confidence", 0), 3),
                        "cached": True,
                    },
                })
                yield _sse({"type": "done"})
                return

        # ------------------------------------------------------------------
        # PRODUCTION FIX: Emit a "thinking" event immediately so UI doesn't
        # feel frozen during the 2-5 second retrieval/grading phase.
        # ------------------------------------------------------------------
        yield _sse({"type": "status", "content": "Searching documents..."})

        try:
            # Step 1: Run CRAG pipeline up to reranking
            result = await asyncio.to_thread(self.crag.prepare, question)
            docs = result.get("reranked_documents", [])
            retry_count = result.get("retry_count", 0)
            max_retries = result.get("max_retries", 2)
            retrieval_score = result.get("retrieval_score", 0) or 0.0
            transformed_query = result.get("transformed_query")

            if not docs or (retrieval_score < 0.2 and retry_count >= max_retries):
                yield _sse({"type": "token", "content": INSUFFICIENT_EVIDENCE_MESSAGE})
                yield _sse({"type": "done"})
                return

            # Step 2: Build prompt
            context_parts = []
            for i, doc in enumerate(docs[:8], 1):
                context_parts.append(
                    f"[Document {i}] {doc.document_name} (Page {doc.page_number or 'N/A'}):\n{doc.text[:800]}"
                )
            context = "\n\n".join(context_parts)
            prompt = RESPONDER_USER_TEMPLATE.format(context=context, question=question)

            yield _sse({"type": "status", "content": "Generating answer..."})

            # Step 3: Stream LLM generation
            loop = asyncio.get_running_loop()
            token_queue: asyncio.Queue = asyncio.Queue()
            full_answer_parts = []

            def _generate_in_thread():
                try:
                    for token in self.llm.generate_stream(
                        system_prompt=RESPONDER_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        temperature=0.6,
                        max_tokens=2048,
                    ):
                        full_answer_parts.append(token)
                        loop.call_soon_threadsafe(token_queue.put_nowait, token)
                    loop.call_soon_threadsafe(token_queue.put_nowait, None)
                except Exception as exc:
                    loop.call_soon_threadsafe(token_queue.put_nowait, exc)

            asyncio.create_task(asyncio.to_thread(_generate_in_thread))

            while True:
                token = await token_queue.get()
                if token is None:
                    break
                if isinstance(token, Exception):
                    raise token
                yield _sse({"type": "token", "content": token})

            # Step 4: Cache complete answer after streaming
            if use_cache:
                full_answer = "".join(full_answer_parts)
                cache_value = {
                    "answer": full_answer,
                    "confidence": retrieval_score,
                    "retry_count": retry_count,
                    "transformed_query": transformed_query,
                    "generation_metadata": {
                        "model": getattr(self.llm, "model", "unknown"),
                        "cached": False,
                    },
                }
                self._answer_cache.set(cache_key, cache_value)
                logger.info(f"[ANSWER CACHE] Stored streamed answer for: {question[:60]}...")

            yield _sse({
                "type": "metadata",
                "data": {
                    "retry_count": retry_count,
                    "transformed_query": transformed_query,
                    "retrieval_score": round(retrieval_score, 3),
                    "cached": False,
                },
            })
            yield _sse({"type": "done"})

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield _sse({"type": "error", "content": f"Error: {str(e)}"})
            yield _sse({"type": "done"})


def get_chat_service() -> ChatService:
    return ChatService()