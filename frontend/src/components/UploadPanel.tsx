import { useMemo, useRef, useState } from "react";
import type { DragEvent } from "react";
import { ApiError, uploadDocuments } from "../api";
import type { ParserType, ParsersResponse, UploadResponse } from "../types";
import { formatSize, mergeFiles, validateFiles } from "../validation";

interface Props {
  parsers: ParsersResponse;
  onUploaded: (result: UploadResponse) => void;
}

/** Splits an API message like "a.pdf: empty; b.pdf: bad" into per-file errors and a general remainder. */
function splitBackendError(message: string, files: File[]): { perFile: Map<string, string>; general: string[] } {
  const perFile = new Map<string, string>();
  const general: string[] = [];
  for (const part of message.split("; ")) {
    const file = files.find((f) => part.startsWith(`${f.name}: `));
    if (file) perFile.set(file.name, part.slice(file.name.length + 2));
    else general.push(part);
  }
  return { perFile, general };
}

export default function UploadPanel({ parsers, onUploaded }: Props) {
  const unavailable = useMemo(() => new Set(parsers.unavailable_parsers ?? []), [parsers]);
  const [files, setFiles] = useState<File[]>([]);
  const [parser, setParser] = useState<ParserType>(
    parsers.parsers.find((p) => !unavailable.has(p)) ?? parsers.default,
  );
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const errors = useMemo(() => validateFiles(files, parsers), [files, parsers]);
  const fileErrors = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const e of errors) if (e.file) map.set(e.file, [...(map.get(e.file) ?? []), e.message]);
    return map;
  }, [errors]);
  const generalErrors = errors.filter((e) => e.file === null);
  const backend = useMemo(
    () => (backendError ? splitBackendError(backendError, files) : null),
    [backendError, files],
  );

  const addFiles = (incoming: FileList | File[] | null) => {
    if (!incoming || uploading) return;
    setBackendError(null);
    setFiles((current) => mergeFiles(current, Array.from(incoming)));
  };

  const removeFile = (file: File) => {
    setBackendError(null);
    setFiles((current) => current.filter((f) => f !== file));
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    addFiles(event.dataTransfer.files);
  };

  const upload = async () => {
    setUploading(true);
    setBackendError(null);
    try {
      const result = await uploadDocuments(files, parser);
      setFiles([]);
      onUploaded(result);
    } catch (e) {
      setBackendError(e instanceof ApiError ? e.message : "Upload failed. Please try again.");
      setUploading(false);
    }
  };

  const canUpload = files.length > 0 && errors.length === 0 && !uploading;

  return (
    <section className="card upload-panel">
      <h2>Upload PDFs</h2>
      <div
        className={`dropzone${dragging ? " dropzone-active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        role="group"
        aria-label="Drop PDF files here"
        data-testid="dropzone"
      >
        <p>Drag and drop PDF files here, or</p>
        <button type="button" disabled={uploading} onClick={() => inputRef.current?.click()}>
          Choose files
        </button>
        <input
          ref={inputRef}
          className="visually-hidden"
          type="file"
          accept="application/pdf,.pdf"
          multiple
          tabIndex={-1}
          disabled={uploading}
          aria-label="PDF files"
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <p className="muted">
          Up to {parsers.max_files_per_upload} files, {parsers.max_file_size_mb} MB each.
        </p>
      </div>

      {files.length > 0 && (
        <ul className="file-list" aria-label="Selected files">
          {files.map((file) => {
            const messages = [...(fileErrors.get(file.name) ?? [])];
            const remote = backend?.perFile.get(file.name);
            if (remote) messages.push(remote);
            return (
              <li key={`${file.name}-${file.size}-${file.lastModified}`}>
                <div className="file-row">
                  <span className="file-name">{file.name}</span>
                  <span className="muted">{formatSize(file.size)}</span>
                  <button type="button" disabled={uploading} onClick={() => removeFile(file)} aria-label={`Remove ${file.name}`}>
                    Remove
                  </button>
                </div>
                {messages.map((m) => (
                  <p key={m} className="error" role="alert">
                    {m}
                  </p>
                ))}
              </li>
            );
          })}
        </ul>
      )}

      {generalErrors.map((e) => (
        <p key={e.message} className="error" role="alert">
          {e.message}
        </p>
      ))}
      {backend?.general.map((m) => (
        <p key={m} className="error" role="alert">
          {m}
        </p>
      ))}

      <div className="upload-actions">
        <label className="field">
          Parser
          <select value={parser} disabled={uploading} onChange={(e) => setParser(e.target.value as ParserType)}>
            {parsers.parsers.map((p) => (
              <option key={p} value={p} disabled={unavailable.has(p)}>
                {p}
                {unavailable.has(p) ? " (API key not configured)" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="primary" disabled={!canUpload} onClick={upload}>
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>
    </section>
  );
}
