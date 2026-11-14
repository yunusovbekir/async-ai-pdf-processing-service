export type ParserType = "pypdf" | "llm" | "gemini";
export type DocumentStatus = "queued" | "parsing" | "summarizing" | "completed" | "failed";
export type SummaryStatus = "pending" | "completed" | "failed" | "skipped";

export interface UploadedDocument {
  id: string;
  filename: string;
  status: DocumentStatus;
}

export interface UploadResponse {
  batch_id: string;
  documents: UploadedDocument[];
}

export interface Page {
  page: number;
  content: string;
}

export interface DocumentSummaryView {
  id: string;
  batch_id: string;
  filename: string;
  parser: ParserType;
  status: DocumentStatus;
  summary_status: SummaryStatus;
  summary: string | null;
  error: string | null;
  page_count: number | null;
  attempts: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentResponse extends DocumentSummaryView {
  pages: Page[];
}

export interface BatchResponse {
  id: string;
  parser: ParserType;
  created_at: string;
  documents: DocumentSummaryView[];
}

export interface ParsersResponse {
  parsers: ParserType[];
  default: ParserType;
  /** Optional: parsers that are listed but cannot run (e.g. API key not configured). */
  unavailable_parsers?: ParserType[];
  max_file_size_mb: number;
  max_files_per_upload: number;
}

export interface HealthResponse {
  status: string;
  redis: string;
}
