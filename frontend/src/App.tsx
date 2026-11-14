import { useEffect, useState } from "react";
import UploadPanel from "./components/UploadPanel";
import { getHealth, getParsers } from "./api";
import type { ParsersResponse, UploadResponse } from "./types";

type Health = { state: "loading" } | { state: "ok" } | { state: "down"; message: string };

const readBatchParam = (): string | null => new URLSearchParams(window.location.search).get("batch");

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function App() {
  const [health, setHealth] = useState<Health>({ state: "loading" });
  const [parsers, setParsers] = useState<ParsersResponse | null>(null);
  const [parsersError, setParsersError] = useState<string | null>(null);
  const [batchId, setBatchId] = useState<string | null>(readBatchParam);
  const [upload, setUpload] = useState<UploadResponse | null>(null);

  useEffect(() => {
    const onPopState = () => setBatchId(readBatchParam());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const handleUploaded = (result: UploadResponse) => {
    window.history.pushState(null, "", `?batch=${encodeURIComponent(result.batch_id)}`);
    setUpload(result);
    setBatchId(result.batch_id);
  };

  const startNewUpload = () => {
    window.history.pushState(null, "", window.location.pathname);
    setUpload(null);
    setBatchId(null);
  };

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then(() => !cancelled && setHealth({ state: "ok" }))
      .catch((e: unknown) => !cancelled && setHealth({ state: "down", message: errorMessage(e) }));
    getParsers()
      .then((data) => !cancelled && setParsers(data))
      .catch((e: unknown) => !cancelled && setParsersError(errorMessage(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  const statusText =
    health.state === "loading" ? "API: checking…" : health.state === "ok" ? "API ok" : "API unavailable";

  return (
    <div className="app">
      <header className="app-header">
        <h1>PDF processing</h1>
      </header>
      <main className="app-main">
        {parsersError && <p className="error">{parsersError}</p>}
        {!parsers && !parsersError && <p className="muted">Loading…</p>}
        {parsers && !batchId && <UploadPanel parsers={parsers} onUploaded={handleUploaded} />}
        {batchId && (
          <section className="card">
            <h2>Upload accepted</h2>
            <p>
              Batch id: <code>{batchId}</code>
            </p>
            {upload && (
              <ul>
                {upload.documents.map((d) => (
                  <li key={d.id}>
                    {d.filename} <span className="muted">({d.id})</span>
                  </li>
                ))}
              </ul>
            )}
            <button type="button" onClick={startNewUpload}>
              New upload
            </button>
          </section>
        )}
      </main>
      <footer className="app-footer">
        <span className={`status status-${health.state}`} title={health.state === "down" ? health.message : undefined}>
          {statusText}
        </span>
      </footer>
    </div>
  );
}
