"""Health and readiness endpoints."""
from fastapi import APIRouter, status

from app.storage.vector_store import get_vector_store
from app.storage.document_store import get_document_store

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "service": "crag-backend"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    try:
        vs = get_vector_store()
        vs.client.get_collections()
        ds = get_document_store()
        return {"status": "ready", "qdrant": True, "database": True}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}
