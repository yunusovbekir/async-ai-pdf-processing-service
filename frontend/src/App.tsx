import { useEffect, useState } from "react";
import { getHealth, getParsers } from "./api";
import type { ParsersResponse } from "./types";

type Health = { state: "loading" } | { state: "ok" } | { state: "down"; message: string };

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function App() {
  const [health, setHealth] = useState<Health>({ state: "loading" });
  const [parsers, setParsers] = useState<ParsersResponse | null>(null);
  const [parsersError, setParsersError] = useState<string | null>(null);

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
        <section className="card">
          <h2>Available parsers</h2>
          {parsersError && <p className="error">{parsersError}</p>}
          {!parsers && !parsersError && <p className="muted">Loading…</p>}
          {parsers && (
            <>
              <ul>
                {parsers.parsers.map((p) => (
                  <li key={p}>
                    {p}
                    {p === parsers.default && <span className="muted"> (default)</span>}
                  </li>
                ))}
              </ul>
              <p className="muted">
                Up to {parsers.max_files_per_upload} files, {parsers.max_file_size_mb} MB each.
              </p>
            </>
          )}
        </section>
      </main>
      <footer className="app-footer">
        <span className={`status status-${health.state}`} title={health.state === "down" ? health.message : undefined}>
          {statusText}
        </span>
      </footer>
    </div>
  );
}
