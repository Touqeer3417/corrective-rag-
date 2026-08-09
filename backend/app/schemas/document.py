"""Document-related Pydantic schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """A single document chunk with metadata."""
    chunk_id: str
    document_id: str
    document_name: str
    file_type: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: Optional[float] = None


class DocumentUpload(BaseModel):
    """Document upload response."""
    document_id: str
    filename: str
    file_type: str
    status: str  # "pending", "processing", "indexed", "error"
    message: Optional[str] = None
    chunk_count: Optional[int] = None
    created_at: datetime


class DocumentInfo(BaseModel):
    """Document information for listing."""
    document_id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    page_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """List of documents response."""
    documents: List[DocumentInfo]
    total: int


class DocumentDeleteResponse(BaseModel):
    """Document deletion response."""
    document_id: str
    deleted: bool
    message: str
