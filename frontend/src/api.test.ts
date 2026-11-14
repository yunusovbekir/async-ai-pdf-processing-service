import { describe, expect, it } from "vitest";
import { ApiError, toApiError } from "./api";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("toApiError", () => {
  it("uses a string detail", async () => {
    const error = await toApiError(json(404, { detail: "Document not found" }));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
    expect(error.message).toBe("Document not found");
  });

  it("joins upload validation list detail", async () => {
    const error = await toApiError(
      json(400, { detail: [{ filename: "a.txt", error: "not a PDF" }, { filename: "b.pdf", error: "empty" }] }),
    );
    expect(error.status).toBe(400);
    expect(error.message).toBe("a.txt: not a PDF; b.pdf: empty");
  });

  it("formats FastAPI validation errors", async () => {
    const error = await toApiError(
      json(422, { detail: [{ loc: ["body", "parser"], msg: "Input should be 'pypdf'", type: "enum" }] }),
    );
    expect(error.message).toBe("parser: Input should be 'pypdf'");
  });

  it("falls back to the status text for non-JSON bodies", async () => {
    const error = await toApiError(new Response("oops", { status: 502, statusText: "Bad Gateway" }));
    expect(error.message).toBe("Bad Gateway");
  });
});
