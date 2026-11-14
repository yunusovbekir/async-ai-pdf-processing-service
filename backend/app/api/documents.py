import logging
import uuid
from pathlib import Path
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app import queue, repository, storage
from app.config import get_settings
from app.redis_client import get_redis
from app.schemas import (
    BatchResponse,
    DocumentResponse,
    DocumentStatus,
    ParserType,
    UploadedDocument,
    UploadResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

RedisDep = Annotated[redis.Redis, Depends(get_redis)]


@router.post("/documents", status_code=202, response_model=UploadResponse)
async def upload_documents(
    client: RedisDep,
    files: Annotated[list[UploadFile], File()],
    parser: Annotated[ParserType, Form()] = ParserType.pypdf,
) -> UploadResponse | JSONResponse:
    max_files = get_settings().MAX_FILES_PER_UPLOAD
    if len(files) > max_files:
        raise HTTPException(400, f"too many files: {len(files)} (max {max_files})")

    saved: list[tuple[str, str, Path]] = []
    errors: list[dict[str, str]] = []
    status_code = 400
    for file in files:
        filename = file.filename or "unnamed.pdf"
        document_id = uuid.uuid4().hex
        try:
            path = await storage.save_upload(file, document_id)
        except storage.InvalidUploadError as exc:
            errors.append({"filename": filename, "error": exc.message})
            status_code = max(status_code, exc.status_code)
        else:
            saved.append((document_id, filename, path))

    if errors:
        await storage.delete_files([path for _, _, path in saved])
        logger.warning("upload rejected errors=%d", len(errors))
        return JSONResponse({"detail": errors}, status_code=status_code)

    batch_id = uuid.uuid4().hex
    try:
        await repository.create_batch(
            client, batch_id, parser, [(document_id, name) for document_id, name, _ in saved]
        )
        for document_id, _, _ in saved:
            await queue.enqueue(client, document_id)
    except Exception:
        await storage.delete_files([path for _, _, path in saved])
        logger.exception("upload failed batch_id=%s", batch_id)
        raise HTTPException(503, "failed to enqueue documents") from None

    return UploadResponse(
        batch_id=batch_id,
        documents=[
            UploadedDocument(id=document_id, filename=name, status=DocumentStatus.queued)
            for document_id, name, _ in saved
        ],
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, client: RedisDep) -> dict[str, object]:
    document = await repository.get_document(client, document_id)
    if document is None:
        raise HTTPException(404, "document not found")
    return document


@router.get("/batches/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: str, client: RedisDep) -> dict[str, object]:
    batch = await repository.get_batch(client, batch_id)
    if batch is None:
        raise HTTPException(404, "batch not found")
    return batch
