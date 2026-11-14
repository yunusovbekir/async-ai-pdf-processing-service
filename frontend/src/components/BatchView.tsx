import { useState } from "react";
import { useBatch } from "../hooks/useBatch";
import { allTerminal, orderedDocuments } from "../state/batchReducer";
import type { DocumentSummaryView } from "../types";
import DocumentDetail from "./DocumentDetail";

function DocumentCard({ doc }: { doc: DocumentSummaryView }) {
  const [open, setOpen] = useState(false);
  const panelId = `detail-${doc.id}`;
  const canExpand = doc.status === "completed";
  return (
    <li className="doc-card">
      <div className="doc-row">
        <span className="doc-name">{doc.filename}</span>
        <span className={`badge badge-${doc.status}`}>{doc.status}</span>
        {doc.page_count !== null && (
          <span className="muted">
            {doc.page_count} {doc.page_count === 1 ? "page" : "pages"}
          </span>
        )}
        {doc.attempts > 1 && <span className="muted">attempts: {doc.attempts}</span>}
        {canExpand && (
          <button type="button" className="secondary" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
            {open ? "Hide results" : "Show results"}
          </button>
        )}
      </div>
      {doc.status === "failed" && doc.error && <p className="error">{doc.error}</p>}
      {open && canExpand && (
        <div id={panelId}>
          <DocumentDetail documentId={doc.id} />
        </div>
      )}
    </li>
  );
}

export default function BatchView({ batchId, onNewUpload }: { batchId: string; onNewUpload: () => void }) {
  const { state, loading, error } = useBatch(batchId);
  const docs = orderedDocuments(state);
  const done = docs.filter((d) => d.status === "completed" || d.status === "failed").length;
  const finished = allTerminal(state);

  return (
    <section className="card">
      <div className="batch-head">
        <h2>Batch</h2>
        <button type="button" onClick={onNewUpload}>
          New upload
        </button>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {loading && <p className="muted" role="status">Loading batch…</p>}
      {state.batch && (
        <>
          <p className="batch-meta">
            <code>{state.batch.id}</code> · parser: {state.batch.parser}
          </p>
          <p aria-live="polite">
            {done} of {docs.length} done
            {finished && " — all finished"}
            {!finished && state.connection !== "closed" && (
              <span className={`conn conn-${state.connection}`}> · {state.connection === "sse" ? "live" : "polling"}</span>
            )}
          </p>
          <progress max={docs.length || 1} value={done} aria-label="Batch progress" />
          {docs.length === 0 ? (
            <p className="muted">This batch has no documents.</p>
          ) : (
            <ul className="doc-list">
              {docs.map((d) => (
                <DocumentCard key={d.id} doc={d} />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
