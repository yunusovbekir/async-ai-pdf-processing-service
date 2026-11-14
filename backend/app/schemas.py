from enum import StrEnum

from pydantic import BaseModel


class ParserType(StrEnum):
    pypdf = "pypdf"
    gemini = "gemini"


class DocumentStatus(StrEnum):
    queued = "queued"
    parsing = "parsing"
    summarizing = "summarizing"
    completed = "completed"
    failed = "failed"


class SummaryStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class UploadedDocument(BaseModel):
    id: str
    filename: str
    status: DocumentStatus


class UploadResponse(BaseModel):
    batch_id: str
    documents: list[UploadedDocument]


class Page(BaseModel):
    page: int
    content: str


class DocumentSummaryView(BaseModel):
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
    pages: list[Page]


class BatchResponse(BaseModel):
    id: str
    parser: ParserType
    created_at: str
    documents: list[DocumentSummaryView]
