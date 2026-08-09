"""Chat and RAG-related Pydantic schemas."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation with source metadata."""
    citation_id: str
    document_id: str
    document_name: str
    page_number: Optional[int] = None
    chunk_id: str
    text: str
    score: float


class ChatRequest(BaseModel):
    """Chat request from user."""
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Synchronous chat response."""
    answer: str
    citations: List[Citation]
    confidence: float
    retry_count: int
    transformed_query: Optional[str] = None
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamingChunk(BaseModel):
    """A single chunk in a streaming response."""
    type: str  # "token", "citation", "metadata", "error", "done"
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    """A single chat message for history."""
    role: str  # "user", "assistant"
    content: str
    citations: Optional[List[Citation]] = None
    timestamp: str
