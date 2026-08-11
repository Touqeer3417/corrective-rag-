"""Chat and RAG orchestration service."""
import asyncio
import json
from typing import AsyncGenerator

from app.config import get_settings
from app.core.logging import get_logger
from app.rag.graph import get_crag_graph
from app.rag.models import get_llm_provider
from app.rag.prompts import RESPONDER_SYSTEM_PROMPT, RESPONDER_USER_TEMPLATE
from app.schemas.chat import ChatResponse

logger = get_logger("services.chat")


class ChatService:
    """Handle chat queries and streaming responses."""

    def __init__(self):
        self.crag = get_crag_graph()
        self.llm = get_llm_provider()

    async def chat(self, question: str) -> ChatResponse:
        """Synchronous chat with full CRAG pipeline."""
        try:
            # Run blocking sync invoke in thread pool
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
        """Streaming chat response via SSE."""
        try:
            # Run blocking sync invoke in thread pool — isse event loop block nahi hoga
            result = await asyncio.to_thread(self.crag.invoke, question)
            docs = result.get("reranked_documents", [])
            answer = result.get("answer", "")
            retry_count = result.get("retry_count", 0)
            transformed_query = result.get("transformed_query")

            # Agar insufficient evidence hai ya koi doc nahi — seedha answer bhejo
            if not docs or result.get("generation_metadata", {}).get("insufficient_evidence"):
                safe_answer = json.dumps(answer)  # PROPER JSON string, repr() Nahi!
                yield f'data: {{"type": "token", "content": {safe_answer}}}\n\n'
                yield f'data: {{"type": "done"}}\n\n'
                return

            # Context build karo
            context_parts = []
            for i, doc in enumerate(docs[:8], 1):
                context_parts.append(
                    f"[Document {i}] {doc.document_name} (Page {doc.page_number or 'N/A'}):\n{doc.text[:1000]}"
                )
            context = "\n\n".join(context_parts)
            prompt = RESPONDER_USER_TEMPLATE.format(context=context, question=question)

            # Stream answer with proper JSON encoding
            for token in self.llm.generate_stream(
                system_prompt=RESPONDER_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.1,
                max_tokens=2048,
            ):
                safe_token = json.dumps(token)  # PROPER JSON encoding
                yield f'data: {{"type": "token", "content": {safe_token}}}\n\n'

            # Metadata bhejo
            safe_query = json.dumps(transformed_query) if transformed_query else "null"
            yield f'data: {{"type": "metadata", "data": {{"retry_count": {retry_count}, "transformed_query": {safe_query}}}}}\n\n'
            yield f'data: {{"type": "done"}}\n\n'

        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_msg = json.dumps(f"Error: {str(e)}")
            yield f'data: {{"type": "error", "content": {error_msg}}}\n\n'
            yield f'data: {{"type": "done"}}\n\n'


def get_chat_service() -> ChatService:
    return ChatService()