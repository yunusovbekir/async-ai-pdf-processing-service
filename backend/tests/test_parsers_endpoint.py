from httpx import AsyncClient

from app.config import get_settings


async def test_parsers_lists_parsers_and_limits(client: AsyncClient) -> None:
    response = await client.get("/parsers")
    assert response.status_code == 200
    settings = get_settings()
    assert response.json() == {
        "parsers": ["pypdf", "llm"],
        "default": "pypdf",
        "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        "max_files_per_upload": settings.MAX_FILES_PER_UPLOAD,
    }
