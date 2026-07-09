import logging
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.documents import DocumentListResponse, DeleteResponse, DocumentItem
from backend.api.auth import get_current_user, FirebaseUser
from backend.api.dependencies import get_document_service, get_db
from backend.services.document_service import (
    DocumentService,
    DocumentNotFoundError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    current_user: FirebaseUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List indexed documents belonging to the authenticated user."""
    try:
        docs = await document_service.list_user_documents(db, current_user.uid)
        items = [
            DocumentItem(
                document_id=doc["document_id"],
                filename=doc["filename"],
                page_count=doc["page_count"],
                chunk_count=doc["chunk_count"],
                document_type=doc.get("document_type"),
                manufacturer=doc.get("manufacturer"),
                equipment=doc.get("equipment"),
                revision=doc.get("revision"),
                language=doc.get("language"),
            )
            for doc in docs
        ]
        return DocumentListResponse(documents=items)
    except Exception as exc:
        logger.exception("Failed to list documents")
        raise HTTPException(status_code=500, detail="Failed to retrieve document list.") from exc


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    current_user: FirebaseUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
    """Delete a document's vectors and raw file for the user."""
    from backend.utils.logging_context import document_id_var
    document_id_var.set(document_id)

    try:
        msg = await document_service.delete_user_document(db, document_id, current_user.uid)
        return DeleteResponse(message=msg)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to delete document %s", document_id)
        raise HTTPException(status_code=500, detail="An error occurred while deleting the document.") from exc


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: FirebaseUser = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
):
    """Download the original PDF file for an owned document."""
    from backend.utils.logging_context import document_id_var
    document_id_var.set(document_id)

    try:
        source = await document_service.get_download_source(db, document_id, current_user.uid)
        if source["type"] == "url":
            # 307 Temporary Redirect: offloads the transfer to S3/GCS directly
            return RedirectResponse(url=source["url"], status_code=307)
        # Fallback: stream raw bytes (local storage)
        return StreamingResponse(
            BytesIO(source["bytes"]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{source["filename"]}"'},
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to download document %s", document_id)
        raise HTTPException(status_code=500, detail="Failed to download document.") from exc
