from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str = "redis://localhost:6379/0"
    UPLOAD_DIR: str = "/data/uploads"
    DATA_TTL_SECONDS: int = 7 * 24 * 3600
    MAX_FILE_SIZE_MB: int = 20
    MAX_FILES_PER_UPLOAD: int = 10
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_MAX_CONCURRENCY: int = 2
    GEMINI_TIMEOUT_SECONDS: int = 60
    GEMINI_MAX_RETRIES: int = 4
    SUMMARY_MAX_INPUT_CHARS: int = 100_000
    WORKER_CONCURRENCY: int = 4
    MAX_ATTEMPTS: int = 3
    CLAIM_IDLE_MS: int = 60_000
    LOG_LEVEL: str = "INFO"

    @field_validator("GEMINI_MODEL")
    @classmethod
    def _strip_model(cls, value: str) -> str:
        return value.strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
