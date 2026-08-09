"""Document upload and management endpoints."""
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, status

from app.core.exceptions import DocumentValidationError, IngestionError
from app.core.logging import get_logger
from app.dependencies import get_doc_service, get_ingest_service
from app.schemas.common import APIResponse
from app.schemas.document import DocumentListResponse, DocumentDeleteResponse
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService

logger = get_logger("api.documents")
router = APIRouter()


@router.post("/upload", response_model=APIResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_service: DocumentService = Depends(get_doc_service),
    ingest_service: IngestionService = Depends(get_ingest_service),
):
    """Upload and ingest a single document."""
    try:
        suffix = Path(file.filename).suffix if file.filename else ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        result = await ingest_service.ingest_document(
            file_path=tmp_path,
            original_filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
        )
        Path(tmp_path).unlink(missing_ok=True)

        return APIResponse(
            success=True,
            message="Document uploaded and indexed successfully",
            data=result.model_dump(),
        )

    except DocumentValidationError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except IngestionError as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected upload error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during upload")


@router.post("/upload-batch", response_model=APIResponse)
async def upload_batch(
    files: List[UploadFile] = File(...),
    ingest_service: IngestionService = Depends(get_ingest_service),
):
    """Upload multiple documents."""
    results = []
    errors = []

    for file in files:
        try:
            suffix = Path(file.filename).suffix if file.filename else ".tmp"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            result = await ingest_service.ingest_document(
                file_path=tmp_path,
                original_filename=file.filename or "unnamed",
                content_type=file.content_type or "application/octet-stream",
            )
            results.append(result.model_dump())
            Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            errors.append({"file": file.filename, "error": str(e)})

    return APIResponse(
        success=len(errors) == 0,
        message=f"Processed {len(files)} files, {len(results)} success, {len(errors)} errors",
        data={"results": results, "errors": errors},
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    doc_service: DocumentService = Depends(get_doc_service),
):
    """List all uploaded documents."""
    return await doc_service.list_documents(limit=limit, offset=offset)


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    doc_service: DocumentService = Depends(get_doc_service),
):
    """Get document details."""
    doc = await doc_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    doc_service: DocumentService = Depends(get_doc_service),
):
    """Delete a document and all its indexed data."""
    return await doc_service.delete_document(document_id)
