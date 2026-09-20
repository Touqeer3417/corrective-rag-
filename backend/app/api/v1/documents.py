"""Document upload and management endpoints."""

import asyncio
import tempfile
from pathlib import Path
from typing import List, Tuple

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from app.config import get_settings
from app.core.exceptions import DocumentValidationError
from app.core.logging import get_logger
from app.dependencies import get_doc_service, get_ingest_service
from app.schemas.common import APIResponse
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListResponse,
)
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService


logger = get_logger("api.documents")

router = APIRouter()


# ==========================================================================
# Upload helpers
# ==========================================================================

async def _save_upload_to_temp(
    file: UploadFile,
) -> Tuple[str, int]:
    """
    Save uploaded file into a temporary file.

    The file is copied in 1 MB chunks instead of loading the complete
    document into RAM. This is important for large PDFs.
    """

    settings = get_settings()

    suffix = (
        Path(file.filename).suffix
        if file.filename
        else ".tmp"
    )

    tmp_path = None
    total_size = 0

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as tmp:
            tmp_path = tmp.name

            while True:
                # Read only 1 MB at a time.
                data = await file.read(
                    1024 * 1024
                )

                if not data:
                    break

                total_size += len(data)

                # Prevent files larger than configured limit.
                if (
                    total_size
                    > settings.max_file_size_bytes
                ):
                    raise DocumentValidationError(
                        f"File exceeds maximum size of "
                        f"{settings.max_file_size_mb} MB"
                    )

                tmp.write(data)

        logger.info(
            f"Upload received: "
            f"{file.filename} "
            f"({total_size / 1024 / 1024:.2f} MB)"
        )

        return tmp_path, total_size

    except Exception:
        if tmp_path:
            Path(tmp_path).unlink(
                missing_ok=True
            )

        raise


def _process_document_background(
    tmp_path: str,
    filename: str,
    content_type: str,
    ingest_service: IngestionService,
) -> None:
    """
    Run document ingestion after the upload response has already
    been returned to the frontend.

    BackgroundTasks runs normal sync functions in a threadpool.
    asyncio.run() is used because ingest_document() is async.
    """

    logger.info(
        f"Background indexing started: {filename}"
    )

    try:
        result = asyncio.run(
            ingest_service.ingest_document(
                file_path=tmp_path,
                original_filename=filename,
                content_type=content_type,
            )
        )

        logger.info(
            f"Background indexing completed: "
            f"{filename} "
            f"({result.chunk_count or 0} chunks)"
        )

    except Exception as e:
        logger.exception(
            f"Background indexing failed "
            f"for {filename}: {e}"
        )

    finally:
        # Temporary upload is no longer required.
        Path(tmp_path).unlink(
            missing_ok=True
        )


# ==========================================================================
# Single document upload
# ==========================================================================

@router.post(
    "/upload",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ingest_service: IngestionService = Depends(
        get_ingest_service
    ),
):
    """
    Receive a file and queue document indexing in the background.

    IMPORTANT:
    The frontend does NOT wait for PDF parsing, embeddings,
    Qdrant indexing and BM25 indexing to finish.
    """

    tmp_path = None

    try:
        filename = (
            file.filename
            or "unnamed"
        )

        content_type = (
            file.content_type
            or "application/octet-stream"
        )

        # --------------------------------------------------------------
        # Step 1: Receive file
        # --------------------------------------------------------------
        tmp_path, file_size = (
            await _save_upload_to_temp(
                file
            )
        )

        # --------------------------------------------------------------
        # Step 2: Start expensive indexing in background
        # --------------------------------------------------------------
        background_tasks.add_task(
            _process_document_background,
            tmp_path,
            filename,
            content_type,
            ingest_service,
        )

        logger.info(
            f"Document queued for indexing: "
            f"{filename}"
        )

        # --------------------------------------------------------------
        # Step 3: Return response immediately
        # --------------------------------------------------------------
        return APIResponse(
            success=True,
            message=(
                "File uploaded successfully. "
                "Document indexing is running in the background."
            ),
            data={
                "filename": filename,
                "file_size": file_size,
                "status": "processing",
            },
        )

    except DocumentValidationError as e:
        if tmp_path:
            Path(tmp_path).unlink(
                missing_ok=True
            )

        logger.warning(
            f"Upload validation error: {e}"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception as e:
        if tmp_path:
            Path(tmp_path).unlink(
                missing_ok=True
            )

        logger.exception(
            f"Unexpected upload error: {e}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Internal server error while "
                "receiving the document"
            ),
        )


# ==========================================================================
# Batch upload
# ==========================================================================

@router.post(
    "/upload-batch",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    ingest_service: IngestionService = Depends(
        get_ingest_service
    ),
):
    """
    Receive multiple files and queue them for background indexing.
    """

    queued = []
    errors = []

    for file in files:
        tmp_path = None

        try:
            filename = (
                file.filename
                or "unnamed"
            )

            content_type = (
                file.content_type
                or "application/octet-stream"
            )

            tmp_path, file_size = (
                await _save_upload_to_temp(
                    file
                )
            )

            background_tasks.add_task(
                _process_document_background,
                tmp_path,
                filename,
                content_type,
                ingest_service,
            )

            queued.append(
                {
                    "filename": filename,
                    "file_size": file_size,
                    "status": "processing",
                }
            )

            logger.info(
                f"Queued for background indexing: "
                f"{filename}"
            )

        except Exception as e:
            if tmp_path:
                Path(tmp_path).unlink(
                    missing_ok=True
                )

            logger.exception(
                f"Failed to queue "
                f"{file.filename}: {e}"
            )

            errors.append(
                {
                    "filename": file.filename,
                    "error": str(e),
                }
            )

    return APIResponse(
        success=len(errors) == 0,
        message=(
            f"{len(queued)} document(s) queued "
            f"for indexing. "
            f"{len(errors)} failed."
        ),
        data={
            "queued": queued,
            "errors": errors,
        },
    )


# ==========================================================================
# List documents
# ==========================================================================

@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    doc_service: DocumentService = Depends(
        get_doc_service
    ),
):
    """List uploaded documents."""

    return await doc_service.list_documents(
        limit=limit,
        offset=offset,
    )


# ==========================================================================
# Get document
# ==========================================================================

@router.get(
    "/{document_id}",
)
async def get_document(
    document_id: str,
    doc_service: DocumentService = Depends(
        get_doc_service
    ),
):
    """Get information about one document."""

    document = await doc_service.get_document(
        document_id
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document


# ==========================================================================
# Delete document
# ==========================================================================

@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
)
async def delete_document(
    document_id: str,
    doc_service: DocumentService = Depends(
        get_doc_service
    ),
):
    """Delete document and associated indexes."""

    return await doc_service.delete_document(
        document_id
    )