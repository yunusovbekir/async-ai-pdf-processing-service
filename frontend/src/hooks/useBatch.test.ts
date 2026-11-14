import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, getBatch, openBatchEvents } from "../api";
import type { BatchResponse } from "../types";
import { POLL_INTERVAL_MS, useBatch } from "./useBatch";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  getBatch: vi.fn(),
  openBatchEvents: vi.fn(),
}));

class FakeSource {
  onerror: (() => void) | null = null;
  closed = false;
  listeners: Record<string, (e: Event) => void> = {};
  addEventListener(type: string, fn: (e: Event) => void) {
    this.listeners[type] = fn;
  }
  close() {
    this.closed = true;
  }
  emit(type: string, data: unknown) {
    this.listeners[type]?.(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
}

const batchWith = (status: "parsing" | "completed"): BatchResponse => ({
  id: "b",
  parser: "pypdf",
  created_at: "2025-01-01T00:00:00Z",
  documents: [
    {
      id: "d",
      batch_id: "b",
      filename: "d.pdf",
      parser: "pypdf",
      status,
      summary_status: "pending",
      summary: null,
      error: null,
      page_count: 1,
      attempts: 1,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:01Z",
    },
  ],
});

let source: FakeSource;

beforeEach(() => {
  vi.useFakeTimers();
  source = new FakeSource();
  vi.mocked(openBatchEvents).mockReturnValue(source as unknown as EventSource);
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("useBatch", () => {
  it("reads snapshot and done from the event stream", () => {
    const { result } = renderHook(() => useBatch("b"));
    act(() => source.emit("snapshot", batchWith("completed")));
    act(() => source.emit("done", {}));
    expect(result.current.state.connection).toBe("closed");
    expect(source.closed).toBe(true);
  });

  it("falls back to polling every 2s until all documents are terminal", async () => {
    vi.mocked(getBatch).mockResolvedValueOnce(batchWith("parsing")).mockResolvedValue(batchWith("completed"));
    const { result, unmount } = renderHook(() => useBatch("b"));
    await act(async () => source.onerror?.());
    expect(source.closed).toBe(true);
    expect(result.current.state.connection).toBe("polling");
    expect(getBatch).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
    });
    expect(getBatch).toHaveBeenCalledTimes(2);
    expect(result.current.state.connection).toBe("closed");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3);
    });
    expect(getBatch).toHaveBeenCalledTimes(2);
    unmount();
  });

  it("reports a missing batch", async () => {
    vi.mocked(getBatch).mockRejectedValue(new ApiError(404, "not found"));
    const { result } = renderHook(() => useBatch("b"));
    await act(async () => source.onerror?.());
    expect(result.current.error).toBe("Batch not found or expired");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 2);
    });
    expect(getBatch).toHaveBeenCalledTimes(1);
  });

  it("closes the stream on unmount", () => {
    const { unmount } = renderHook(() => useBatch("b"));
    unmount();
    expect(source.closed).toBe(true);
  });
});
