"""Document management service."""
from typing import List, Optional

from app.core.logging import get_logger
from app.schemas.document import DocumentInfo, DocumentUpload, DocumentDeleteResponse
from app.storage.document_store import get_document_store
from app.storage.file_store import get_file_store
from app.storage.vector_store import get_vector_store
from app.retrieval.sparse import get_bm25_index

logger = get_logger("services.document")


class DocumentService:
    """Handle document CRUD and lifecycle."""

    def __init__(self):
        self.doc_store = get_document_store()
        self.file_store = get_file_store()
        self.vector_store = get_vector_store()
        self.bm25 = get_bm25_index()

    async def list_documents(self, limit: int = 100, offset: int = 0):
        docs = self.doc_store.list_documents(limit=limit, offset=offset)
        return {"documents": docs, "total": len(docs)}

    async def get_document(self, document_id: str) -> Optional[DocumentInfo]:
        return self.doc_store.get_document(document_id)

    async def delete_document(self, document_id: str) -> DocumentDeleteResponse:
        info = self.doc_store.get_document(document_id)
        if not info:
            return DocumentDeleteResponse(
                document_id=document_id, deleted=False, message="Document not found"
            )

        self.vector_store.delete_by_document(document_id)
        self.bm25.delete_by_document(document_id)
        self.file_store.delete(info.filename)
        self.doc_store.delete_document(document_id)

        return DocumentDeleteResponse(
            document_id=document_id, deleted=True, message="Document deleted successfully"
        )


def get_document_service() -> DocumentService:
    return DocumentService()
