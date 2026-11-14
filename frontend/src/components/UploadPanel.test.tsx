import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, uploadDocuments } from "../api";
import type { ParsersResponse } from "../types";
import UploadPanel from "./UploadPanel";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  uploadDocuments: vi.fn(),
}));

const parsers: ParsersResponse = {
  parsers: ["pypdf", "llm"],
  default: "pypdf",
  max_file_size_mb: 1,
  max_files_per_upload: 3,
};

const pdf = (name: string, size = 10) => new File([new Uint8Array(size)], name, { type: "application/pdf", lastModified: 1 });

function select(files: File[]) {
  fireEvent.change(screen.getByLabelText("PDF files"), { target: { files } });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UploadPanel", () => {
  it("uploads the selected files with the chosen parser and lifts the result", async () => {
    const result = { batch_id: "b1", documents: [{ id: "d1", filename: "a.pdf", status: "queued" as const }] };
    vi.mocked(uploadDocuments).mockResolvedValue(result);
    const onUploaded = vi.fn();
    render(<UploadPanel parsers={parsers} onUploaded={onUploaded} />);

    const a = pdf("a.pdf");
    select([a, pdf("a.pdf")]);
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.change(screen.getByLabelText("Parser"), { target: { value: "llm" } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(result));
    expect(uploadDocuments).toHaveBeenCalledWith([a], "llm");
  });

  it("disables upload while validation errors exist", () => {
    render(<UploadPanel parsers={parsers} onUploaded={vi.fn()} />);
    const upload = screen.getByRole("button", { name: "Upload" });
    expect((upload as HTMLButtonElement).disabled).toBe(true);
    select([new File(["x"], "notes.txt", { type: "text/plain" })]);
    expect(screen.getByText("Not a PDF file")).toBeTruthy();
    expect((upload as HTMLButtonElement).disabled).toBe(true);
  });

  it("disables unavailable parsers and defaults to the first available", () => {
    render(<UploadPanel parsers={{ ...parsers, unavailable_parsers: ["pypdf"] }} onUploaded={vi.fn()} />);
    expect((screen.getByLabelText("Parser") as HTMLSelectElement).value).toBe("llm");
    expect((screen.getByRole("option", { name: /pypdf.*API key not configured/ }) as HTMLOptionElement).disabled).toBe(true);
  });

  it("shows backend errors per file", async () => {
    vi.mocked(uploadDocuments).mockRejectedValue(new ApiError(400, "a.pdf: corrupted; Too many files"));
    render(<UploadPanel parsers={parsers} onUploaded={vi.fn()} />);
    select([pdf("a.pdf")]);
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByText("corrupted")).toBeTruthy();
    expect(screen.getByText("Too many files")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Upload" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
