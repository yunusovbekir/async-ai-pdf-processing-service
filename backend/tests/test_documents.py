import asyncio
import os
from pathlib import Path

from httpx import AsyncClient

PDF = b"%PDF-1.4\n" + b"x" * 100


def _files(*items: tuple[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, data, "application/pdf")) for name, data in items]


async def test_upload_happy_path(client: AsyncClient, fake_redis, upload_dir: Path) -> None:
    response = await client.post("/documents", files=_files(("a.pdf", PDF), ("b.pdf", PDF)))
    assert response.status_code == 202
    body = response.json()
    assert [d["filename"] for d in body["documents"]] == ["a.pdf", "b.pdf"]
    assert {d["status"] for d in body["documents"]} == {"queued"}

    ids = [d["id"] for d in body["documents"]]
    for document_id in ids:
        assert (upload_dir / f"{document_id}.pdf").read_bytes() == PDF
        assert await fake_redis.ttl(f"doc:{document_id}") > 0

    entries = await fake_redis.xrange("docs:jobs")
    assert [fields["document_id"] for _, fields in entries] == ids
    assert {fields["attempt"] for _, fields in entries} == {"1"}

    doc = (await client.get(f"/documents/{ids[0]}")).json()
    assert doc["status"] == "queued"
    assert doc["parser"] == "pypdf"
    assert doc["pages"] == []
    assert doc["summary"] is None

    batch = (await client.get(f"/batches/{body['batch_id']}")).json()
    assert [d["id"] for d in batch["documents"]] == ids
    assert "pages" not in batch["documents"][0]


async def test_non_pdf_rejects_whole_request(
    client: AsyncClient, fake_redis, upload_dir: Path
) -> None:
    response = await client.post("/documents", files=_files(("a.pdf", PDF), ("b.pdf", b"nope")))
    assert response.status_code == 400
    assert response.json()["detail"] == [
        {"filename": "b.pdf", "error": "not a PDF file (missing %PDF- header)"}
    ]
    assert await asyncio.to_thread(os.listdir, upload_dir) == []
    assert await fake_redis.xlen("docs:jobs") == 0


async def test_oversized_rejected(client: AsyncClient, upload_dir: Path) -> None:
    big = PDF + b"0" * (1024 * 1024)
    response = await client.post("/documents", files=_files(("big.pdf", big)))
    assert response.status_code == 413
    assert response.json()["detail"][0]["filename"] == "big.pdf"
    assert await asyncio.to_thread(os.listdir, upload_dir) == []


async def test_too_many_files(client: AsyncClient) -> None:
    response = await client.post("/documents", files=_files(*[(f"{i}.pdf", PDF) for i in range(4)]))
    assert response.status_code == 400


async def test_invalid_parser(client: AsyncClient) -> None:
    response = await client.post("/documents", files=_files(("a.pdf", PDF)), data={"parser": "ocr"})
    assert response.status_code == 422


async def test_gemini_parser_stored(client: AsyncClient) -> None:
    response = await client.post(
        "/documents", files=_files(("a.pdf", PDF)), data={"parser": "gemini"}
    )
    document_id = response.json()["documents"][0]["id"]
    assert (await client.get(f"/documents/{document_id}")).json()["parser"] == "gemini"


async def test_get_404s(client: AsyncClient) -> None:
    assert (await client.get("/documents/missing")).status_code == 404
    assert (await client.get("/batches/missing")).status_code == 404
