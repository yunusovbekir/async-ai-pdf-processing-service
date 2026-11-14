import { describe, expect, it } from "vitest";
import { mergeFiles, validateFiles } from "./validation";

const limits = { max_file_size_mb: 1, max_files_per_upload: 2 };
const MB = 1024 * 1024;

function makeFile(name: string, size: number, type = "application/pdf", lastModified = 1): File {
  return new File([new Uint8Array(size)], name, { type, lastModified });
}

describe("validateFiles", () => {
  it("accepts valid PDFs", () => {
    expect(validateFiles([makeFile("a.pdf", 10), makeFile("b.PDF", 10, "")], limits)).toEqual([]);
  });

  it("rejects non-PDF files", () => {
    const errors = validateFiles([makeFile("a.txt", 10, "text/plain")], limits);
    expect(errors).toEqual([{ file: "a.txt", message: "Not a PDF file" }]);
  });

  it("rejects oversize files", () => {
    const errors = validateFiles([makeFile("big.pdf", MB + 1)], limits);
    expect(errors).toEqual([{ file: "big.pdf", message: "Larger than 1 MB" }]);
  });

  it("rejects empty files", () => {
    expect(validateFiles([makeFile("e.pdf", 0)], limits)).toEqual([{ file: "e.pdf", message: "File is empty" }]);
  });

  it("rejects too many files", () => {
    const files = [makeFile("a.pdf", 1), makeFile("b.pdf", 1), makeFile("c.pdf", 1)];
    const errors = validateFiles(files, limits);
    expect(errors).toHaveLength(1);
    expect(errors[0]?.file).toBeNull();
  });
});

describe("mergeFiles", () => {
  it("ignores exact duplicates but keeps files differing in size or lastModified", () => {
    const a = makeFile("a.pdf", 10);
    const merged = mergeFiles([a], [makeFile("a.pdf", 10), makeFile("a.pdf", 11), makeFile("a.pdf", 10, "application/pdf", 2)]);
    expect(merged).toHaveLength(3);
    expect(merged[0]).toBe(a);
  });
});
