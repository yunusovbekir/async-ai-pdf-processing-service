"""API and domain schemas."""

from enum import StrEnum

from pydantic import BaseModel


class ParserType(StrEnum):
    """Available PDF parsers."""

    pypdf = "pypdf"
    gemini = "gemini"


class DocumentStatus(StrEnum):
    """Processing status of a document."""

    queued = "queued"
    parsing = "parsing"
    summarizing = "summarizing"
    completed = "completed"
    failed = "failed"


class SummaryStatus(StrEnum):
    """Status of the Gemini summary of a document."""

    pending = "pending"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class UploadedDocument(BaseModel):
    """A document accepted by the upload endpoint."""

    id: str
    filename: str
    status: DocumentStatus


class UploadResponse(BaseModel):
    """Response of `POST /documents`."""

    batch_id: str
    documents: list[UploadedDocument]


class Page(BaseModel):
    """Content of one page (1-based)."""

    page: int
    content: str


class DocumentSummaryView(BaseModel):
    """Document metadata without pages."""

    id: str
    batch_id: str
    filename: str
    parser: ParserType
    status: DocumentStatus
    summary_status: SummaryStatus
    summary: str | None = None
    error: str | None = None
    page_count: int | None = None
    attempts: int = 0
    created_at: str
    updated_at: str


class DocumentResponse(DocumentSummaryView):
    """Document metadata with pages."""

    pages: list[Page]


class BatchResponse(BaseModel):
    """A batch with its documents (without pages)."""

    id: str
    parser: ParserType
    created_at: str
    documents: list[DocumentSummaryView]
