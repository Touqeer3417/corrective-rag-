"""Chat and RAG orchestration service."""
from typing import AsyncGenerator

from app.config import get_settings
from app.core.logging import get_logger
from app.rag.graph import get_crag_graph
from app.rag.models import get_llm_provider
from app.rag.prompts import RESPONDER_SYSTEM_PROMPT, RESPONDER_USER_TEMPLATE
from app.schemas.chat import ChatResponse, StreamingChunk, Citation

logger = get_logger("services.chat")


class ChatService:
    """Handle chat queries and streaming responses."""

    def __init__(self):
        self.crag = get_crag_graph()
        self.llm = get_llm_provider()

    async def chat(self, question: str) -> ChatResponse:
        """Synchronous chat with full CRAG pipeline."""
        result = self.crag.invoke(question)

        return ChatResponse(
            answer=result.get("answer") or "No answer generated.",
            citations=result.get("citations", []),
            confidence=result.get("retrieval_score") or 0.0,
            retry_count=result.get("retry_count", 0),
            transformed_query=result.get("transformed_query"),
            generation_metadata=result.get("generation_metadata", {}),
        )

    async def chat_stream(self, question: str):
        """Streaming chat response via SSE."""
        result = self.crag.invoke(question)
        docs = result.get("reranked_documents", [])
        answer = result.get("answer", "")

        if not docs or result.get("generation_metadata", {}).get("insufficient_evidence"):
            yield f'data: {{"type": "token", "content": {repr(answer)}}}\n\n'
            yield f'data: {{"type": "done"}}\n\n'
            return

        context_parts = []
        for i, doc in enumerate(docs[:8], 1):
            context_parts.append(
                f"[Document {i}] {doc.document_name} (Page {doc.page_number or 'N/A'}):\n{doc.text[:1000]}"
            )
        context = "\n\n".join(context_parts)
        prompt = RESPONDER_USER_TEMPLATE.format(context=context, question=question)

        for token in self.llm.generate_stream(
            system_prompt=RESPONDER_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=2048,
        ):
            yield f'data: {{"type": "token", "content": {repr(token)}}}\n\n'

        citations = result.get("citations", [])
        for citation in citations:
            yield f'data: {{"type": "citation", "data": {citation.model_dump_json()}}}\n\n'

        yield f'data: {{"type": "metadata", "data": {{"retry_count": {result.get("retry_count", 0)}, "transformed_query": {repr(result.get("transformed_query"))}}}}}\n\n'
        yield f'data: {{"type": "done"}}\n\n'


def get_chat_service() -> ChatService:
    return ChatService()
