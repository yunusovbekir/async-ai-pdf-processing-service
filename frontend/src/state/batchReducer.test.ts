import { describe, expect, it } from "vitest";
import type { BatchResponse, DocumentSummaryView } from "../types";
import { allTerminal, batchReducer, initialBatchState } from "./batchReducer";

const doc = (id: string, over: Partial<DocumentSummaryView> = {}): DocumentSummaryView => ({
  id,
  batch_id: "b",
  filename: `${id}.pdf`,
  parser: "pypdf",
  status: "queued",
  summary_status: "pending",
  summary: null,
  error: null,
  page_count: null,
  attempts: 1,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:01Z",
  ...over,
});

const batch = (documents: DocumentSummaryView[]): BatchResponse => ({
  id: "b",
  parser: "pypdf",
  created_at: "2025-01-01T00:00:00Z",
  documents,
});

describe("batchReducer", () => {
  it("stores a snapshot", () => {
    const s = batchReducer(initialBatchState, { type: "snapshot", batch: batch([doc("a"), doc("b")]) });
    expect(s.batch?.id).toBe("b");
    expect(s.order).toEqual(["a", "b"]);
    expect(allTerminal(s)).toBe(false);
  });

  it("applies newer document updates", () => {
    let s = batchReducer(initialBatchState, { type: "snapshot", batch: batch([doc("a")]) });
    s = batchReducer(s, { type: "document", document: doc("a", { status: "parsing", updated_at: "2025-01-01T00:00:05Z" }) });
    expect(s.documents.a?.status).toBe("parsing");
  });

  it("ignores stale updates", () => {
    let s = batchReducer(initialBatchState, {
      type: "snapshot",
      batch: batch([doc("a", { status: "completed", updated_at: "2025-01-01T00:00:09Z" })]),
    });
    s = batchReducer(s, { type: "document", document: doc("a", { status: "parsing", updated_at: "2025-01-01T00:00:05Z" }) });
    expect(s.documents.a?.status).toBe("completed");
  });

  it("marks the connection closed on done", () => {
    expect(batchReducer(initialBatchState, { type: "done" }).connection).toBe("closed");
  });

  it("allTerminal requires every document completed or failed", () => {
    const s = batchReducer(initialBatchState, {
      type: "snapshot",
      batch: batch([doc("a", { status: "completed" }), doc("b", { status: "failed" })]),
    });
    expect(allTerminal(s)).toBe(true);
    expect(allTerminal(batchReducer(s, { type: "document", document: doc("b", { status: "parsing", updated_at: "2026-01-01T00:00:00Z" }) }))).toBe(false);
  });
});
