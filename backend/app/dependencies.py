"""FastAPI dependency injection."""
from app.services.document_service import DocumentService, get_document_service
from app.services.ingestion_service import IngestionService, get_ingestion_service
from app.services.chat_service import ChatService, get_chat_service


def get_doc_service() -> DocumentService:
    return get_document_service()


def get_ingest_service() -> IngestionService:
    return get_ingestion_service()


def get_chat_svc() -> ChatService:
    return get_chat_service()
