import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getDocument } from "../api";
import type { DocumentResponse } from "../types";
import DocumentDetail from "./DocumentDetail";
import { cache } from "./documentCache";

vi.mock("../api", async (importOriginal) => ({ ...(await importOriginal<typeof import("../api")>()), getDocument: vi.fn() }));

const response = (over: Partial<DocumentResponse>): DocumentResponse => ({
  id: "d1",
  batch_id: "b",
  filename: "d.pdf",
  parser: "pypdf",
  status: "completed",
  summary_status: "completed",
  summary: "Hello **summary**",
  error: null,
  page_count: 1,
  attempts: 1,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:01Z",
  pages: [{ page: 1, content: "| a | b |\n|---|---|\n| 1 | 2 |" }],
  ...over,
});

afterEach(() => {
  cleanup();
  cache.clear();
  vi.clearAllMocks();
});

describe("DocumentDetail", () => {
  it("renders pypdf pages as preformatted text", async () => {
    vi.mocked(getDocument).mockResolvedValue(response({ id: "p1", parser: "pypdf" }));
    const { container } = render(<DocumentDetail documentId="p1" />);
    await screen.findByText("Pages");
    expect(container.querySelector("pre")?.textContent).toContain("| a | b |");
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector("strong")?.textContent).toBe("summary");
  });

  it("renders gemini pages as markdown", async () => {
    vi.mocked(getDocument).mockResolvedValue(response({ id: "g1", parser: "gemini" }));
    const { container } = render(<DocumentDetail documentId="g1" />);
    await screen.findByRole("table");
    expect(container.querySelector("pre")).toBeNull();
  });

  it("shows a notice when the summary failed and a message for empty pages", async () => {
    vi.mocked(getDocument).mockResolvedValue(
      response({ id: "f1", summary_status: "failed", summary: null, error: "boom", pages: [{ page: 1, content: " " }] }),
    );
    render(<DocumentDetail documentId="f1" />);
    expect(await screen.findByText(/Summary failed: boom/)).toBeTruthy();
    expect(screen.getByText("No text on this page")).toBeTruthy();
  });

  it("fetches each document once", async () => {
    vi.mocked(getDocument).mockResolvedValue(response({ id: "c1" }));
    const first = render(<DocumentDetail documentId="c1" />);
    await screen.findByText("Pages");
    first.unmount();
    render(<DocumentDetail documentId="c1" />);
    await screen.findByText("Pages");
    expect(getDocument).toHaveBeenCalledTimes(1);
  });
});
