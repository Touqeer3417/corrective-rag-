"""Chat and RAG orchestration service."""
import asyncio
import json
from typing import AsyncGenerator

from app.config import get_settings
from app.core.logging import get_logger
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
    """Handle chat queries and streaming responses."""

    def __init__(self):
        self.crag = get_crag_graph()
        self.llm = get_llm_provider()

    async def chat(self, question: str) -> ChatResponse:
        """Async chat with full CRAG pipeline via thread pool."""
        try:
            # Run blocking sync invoke in thread pool — event loop block nahi hoga
            result = await asyncio.to_thread(self.crag.invoke, question)

            return ChatResponse(
                answer=result.get("answer") or "No answer generated.",
                citations=[],  # NO CITATIONS
                confidence=result.get("retrieval_score") or 0.0,
                retry_count=result.get("retry_count", 0),
                transformed_query=result.get("transformed_query"),
                generation_metadata=result.get("generation_metadata", {}),
            )
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
        """Streaming chat response via SSE — true async token streaming.

        PRODUCTION FIX:
        - Runs CRAG retrieval/grading/reranking ONCE via prepare() (NO LLM call)
        - Streams answer generation via generate_stream() — exactly ONE LLM call
        - First SSE token sent as soon as generation starts
        - No duplicate LLM calls, no discarded answers, no blocking before stream
        """
        try:
            # ------------------------------------------------------------------
            # STEP 1: Run CRAG pipeline up to reranking (NO generation LLM call)
            # ------------------------------------------------------------------
            result = await asyncio.to_thread(self.crag.prepare, question)
            docs = result.get("reranked_documents", [])
            retry_count = result.get("retry_count", 0)
            max_retries = result.get("max_retries", 2)
            retrieval_score = result.get("retrieval_score", 0) or 0.0
            transformed_query = result.get("transformed_query")

            # ------------------------------------------------------------------
            # STEP 2: Check for insufficient evidence (same logic as generate_answer)
            # ------------------------------------------------------------------
            if not docs or (retrieval_score < 0.2 and retry_count >= max_retries):
                yield _sse({"type": "token", "content": INSUFFICIENT_EVIDENCE_MESSAGE})
                yield _sse({"type": "done"})
                return

            # ------------------------------------------------------------------
            # STEP 3: Build prompt from reranked documents (same as generate_answer)
            # ------------------------------------------------------------------
            context_parts = []
            for i, doc in enumerate(docs[:8], 1):
                context_parts.append(
                    f"[Document {i}] {doc.document_name} (Page {doc.page_number or 'N/A'}):\n{doc.text[:800]}"
                )
            context = "\n\n".join(context_parts)
            prompt = RESPONDER_USER_TEMPLATE.format(context=context, question=question)

            # ------------------------------------------------------------------
            # STEP 4: Stream LLM generation — true async, first token immediately
            # ------------------------------------------------------------------
            # Use asyncio.Queue to bridge blocking generator to async stream.
            # The blocking generate_stream() runs in a thread, pushing tokens
            # to the async queue. The event loop yields them immediately.
            loop = asyncio.get_running_loop()
            token_queue: asyncio.Queue = asyncio.Queue()

            def _generate_in_thread():
                """Run blocking LLM.generate_stream() in background thread."""
                try:
                    for token in self.llm.generate_stream(
                        system_prompt=RESPONDER_SYSTEM_PROMPT,
                        user_prompt=prompt,
                        temperature=0.6,  # Match generate_answer node
                        max_tokens=2048,
                    ):
                        loop.call_soon_threadsafe(token_queue.put_nowait, token)
                    loop.call_soon_threadsafe(token_queue.put_nowait, None)
                except Exception as exc:
                    loop.call_soon_threadsafe(token_queue.put_nowait, exc)

            # Start generation in thread pool (non-blocking for event loop)
            asyncio.create_task(asyncio.to_thread(_generate_in_thread))

            # Yield tokens as they arrive — first token sent immediately
            while True:
                token = await token_queue.get()
                if token is None:
                    break
                if isinstance(token, Exception):
                    raise token

                yield _sse({"type": "token", "content": token})

            # ------------------------------------------------------------------
            # STEP 5: Send metadata and done signal
            # ------------------------------------------------------------------
            yield _sse({
                "type": "metadata",
                "data": {
                    "retry_count": retry_count,
                    "transformed_query": transformed_query,
                    "retrieval_score": round(retrieval_score, 3),
                },
            })
            yield _sse({"type": "done"})

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield _sse({"type": "error", "content": f"Error: {str(e)}"})
            yield _sse({"type": "done"})


def get_chat_service() -> ChatService:
    return ChatService()