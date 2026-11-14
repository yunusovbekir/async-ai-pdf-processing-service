import type {
  BatchResponse,
  DocumentResponse,
  HealthResponse,
  ParserType,
  ParsersResponse,
  UploadResponse,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const { filename, error, msg, loc } = item as Record<string, unknown>;
        const text = typeof error === "string" ? error : typeof msg === "string" ? msg : null;
        if (text === null) return JSON.stringify(item);
        const prefix =
          typeof filename === "string"
            ? filename
            : Array.isArray(loc)
              ? loc.filter((p) => p !== "body").join(".")
              : "";
        return prefix ? `${prefix}: ${text}` : text;
      }
      return String(item);
    });
    return parts.join("; ") || null;
  }
  return null;
}

export async function toApiError(response: Response): Promise<ApiError> {
  let message = response.statusText || `HTTP ${response.status}`;
  try {
    const body: unknown = await response.json();
    const parsed = detailToMessage((body as { detail?: unknown } | null)?.detail);
    if (parsed) message = parsed;
  } catch {
    // body is not JSON; keep the status text
  }
  return new ApiError(response.status, message);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init);
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export const getHealth = (): Promise<HealthResponse> => request("/health");

export const getParsers = (): Promise<ParsersResponse> => request("/parsers");

export function uploadDocuments(files: File[], parser: ParserType): Promise<UploadResponse> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  form.append("parser", parser);
  return request("/documents", { method: "POST", body: form });
}

export const getBatch = (id: string): Promise<BatchResponse> =>
  request(`/batches/${encodeURIComponent(id)}`);

export const getDocument = (id: string): Promise<DocumentResponse> =>
  request(`/documents/${encodeURIComponent(id)}`);

export const openBatchEvents = (batchId: string): EventSource =>
  new EventSource(`${BASE}/batches/${encodeURIComponent(batchId)}/events`);
