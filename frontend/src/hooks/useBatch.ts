import { useEffect, useReducer, useState } from "react";
import { ApiError, getBatch, openBatchEvents } from "../api";
import { batchReducer, initialBatchState, type BatchState } from "../state/batchReducer";
import type { BatchResponse, DocumentSummaryView } from "../types";

export const POLL_INTERVAL_MS = 2000;
const NOT_FOUND = "Batch not found or expired";

export interface UseBatch {
  state: BatchState;
  loading: boolean;
  error: string | null;
}

export function useBatch(batchId: string): UseBatch {
  const [state, dispatch] = useReducer(batchReducer, initialBatchState);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let disposed = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const fail = (e: unknown) => {
      if (disposed) return;
      setError(e instanceof ApiError && e.status === 404 ? NOT_FOUND : e instanceof Error ? e.message : String(e));
    };

    const applySnapshot = (batch: BatchResponse) => {
      setLoaded(true);
      setError(null);
      dispatch({ type: "snapshot", batch });
      return batch.documents.length > 0 && batch.documents.every((d) => d.status === "completed" || d.status === "failed");
    };

    const poll = async () => {
      try {
        const batch = await getBatch(batchId);
        if (disposed) return;
        if (applySnapshot(batch)) {
          dispatch({ type: "done" });
          return;
        }
      } catch (e) {
        fail(e);
        if (e instanceof ApiError && e.status === 404) return;
      }
      if (!disposed) timer = setTimeout(poll, POLL_INTERVAL_MS);
    };

    const startPolling = () => {
      dispatch({ type: "connection", connection: "polling" });
      void poll();
    };

    source = openBatchEvents(batchId);
    const parse = <T,>(event: Event): T => JSON.parse((event as MessageEvent<string>).data) as T;
    source.addEventListener("snapshot", (e) => {
      dispatch({ type: "connection", connection: "sse" });
      applySnapshot(parse<BatchResponse>(e));
    });
    source.addEventListener("document", (e) => dispatch({ type: "document", document: parse<DocumentSummaryView>(e) }));
    source.addEventListener("done", () => {
      source?.close();
      dispatch({ type: "done" });
    });
    source.onerror = () => {
      source?.close();
      source = null;
      if (!disposed) startPolling();
    };

    return () => {
      disposed = true;
      source?.close();
      if (timer) clearTimeout(timer);
    };
  }, [batchId]);

  return { state, loading: !loaded && !error, error };
}
