"""Chat and streaming endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.dependencies import get_chat_svc
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter()


class ChatBody(BaseModel):
    question: str


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    chat_service: ChatService = Depends(get_chat_svc),
):
    """Synchronous chat endpoint."""
    try:
        return await chat_service.chat(body.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    body: ChatBody,
    chat_service: ChatService = Depends(get_chat_svc),
):
    """Streaming chat endpoint via SSE."""
    try:
        return StreamingResponse(
            chat_service.chat_stream(body.question),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
