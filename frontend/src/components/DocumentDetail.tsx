import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getDocument } from "../api";
import type { DocumentResponse, DocumentSummaryView } from "../types";

import { cache } from "./documentCache";

type Load = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; doc: DocumentResponse };

function useDocument(id: string): Load {
  const [load, setLoad] = useState<Load>(() => {
    const hit = cache.get(id);
    return hit ? { state: "ready", doc: hit } : { state: "loading" };
  });

  useEffect(() => {
    if (cache.has(id)) return;
    let cancelled = false;
    getDocument(id)
      .then((doc) => {
        cache.set(id, doc);
        if (!cancelled) setLoad({ state: "ready", doc });
      })
      .catch((e: unknown) => {
        if (!cancelled) setLoad({ state: "error", message: e instanceof Error ? e.message : String(e) });
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  return load;
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState<"idle" | "ok" | "fail">("idle");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied("ok");
    } catch {
      setCopied("fail");
    }
    setTimeout(() => setCopied("idle"), 1500);
  };
  return (
    <button type="button" className="secondary" onClick={() => void copy()}>
      {copied === "ok" ? "Copied" : copied === "fail" ? "Copy failed" : label}
    </button>
  );
}

function Summary({ doc }: { doc: DocumentSummaryView }) {
  if (doc.summary_status === "failed" || doc.summary_status === "skipped") {
    return (
      <p className="notice" role="status">
        Summary {doc.summary_status}
        {doc.error ? `: ${doc.error}` : "."}
      </p>
    );
  }
  if (!doc.summary) return <p className="muted">No summary available.</p>;
  return (
    <div className="markdown">
      <Markdown remarkPlugins={[remarkGfm]}>{doc.summary}</Markdown>
    </div>
  );
}

function Pages({ doc }: { doc: DocumentResponse }) {
  const [index, setIndex] = useState(0);
  if (doc.pages.length === 0) return <p className="muted">No pages.</p>;
  const page = doc.pages[Math.min(index, doc.pages.length - 1)];
  if (!page) return null;
  const asText = doc.parser === "pypdf";
  return (
    <div>
      <div className="page-nav">
        <button type="button" className="secondary" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          Previous
        </button>
        <ol aria-label="Pages" className="page-list">
          {doc.pages.map((p, i) => (
            <li key={p.page}>
              <button
                type="button"
                className={i === index ? "page-btn current" : "page-btn"}
                aria-current={i === index ? "page" : undefined}
                aria-label={`Page ${p.page}`}
                onClick={() => setIndex(i)}
              >
                {p.page}
              </button>
            </li>
          ))}
        </ol>
        <button
          type="button"
          className="secondary"
          disabled={index >= doc.pages.length - 1}
          onClick={() => setIndex(index + 1)}
        >
          Next
        </button>
        <CopyButton text={page.content} label="Copy page" />
      </div>
      {page.content.trim() === "" ? (
        <p className="muted">No text on this page</p>
      ) : asText ? (
        <pre className="page-text">{page.content}</pre>
      ) : (
        <div className="markdown">
          <Markdown remarkPlugins={[remarkGfm]}>{page.content}</Markdown>
        </div>
      )}
    </div>
  );
}

export default function DocumentDetail({ documentId }: { documentId: string }) {
  const load = useDocument(documentId);
  if (load.state === "loading") return <p className="muted" role="status">Loading document…</p>;
  if (load.state === "error") return <p className="error" role="alert">{load.message}</p>;
  const { doc } = load;
  return (
    <div className="detail">
      <section>
        <div className="detail-head">
          <h4>Summary</h4>
          {doc.summary && doc.summary_status === "completed" && <CopyButton text={doc.summary} label="Copy summary" />}
        </div>
        <Summary doc={doc} />
      </section>
      <section>
        <h4>Pages</h4>
        <Pages doc={doc} />
      </section>
    </div>
  );
}
