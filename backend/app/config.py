"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration shared by the API and the worker."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    REDIS_URL: str = "redis://localhost:6379/0"
    UPLOAD_DIR: str = "/data/uploads"
    DATA_TTL_SECONDS: int = 7 * 24 * 3600
    UPLOAD_TTL_SECONDS: int = 7 * 24 * 3600
    UPLOAD_CLEANUP_INTERVAL_SECONDS: int = 3600
    MAX_FILE_SIZE_MB: int = 20
    MAX_FILES_PER_UPLOAD: int = 10
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MAX_CONCURRENCY: int = Field(
        2, validation_alias=AliasChoices("LLM_MAX_CONCURRENCY", "GEMINI_MAX_CONCURRENCY")
    )
    LLM_TIMEOUT_SECONDS: int = Field(
        60, validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS", "GEMINI_TIMEOUT_SECONDS")
    )
    LLM_MAX_RETRIES: int = Field(
        4, validation_alias=AliasChoices("LLM_MAX_RETRIES", "GEMINI_MAX_RETRIES")
    )
    SUMMARY_MAX_INPUT_CHARS: int = 100_000
    WORKER_CONCURRENCY: int = 4
    MAX_ATTEMPTS: int = 3
    CLAIM_IDLE_MS: int = 60_000
    SSE_HEARTBEAT_SECONDS: int = 15
    SSE_MAX_DURATION_SECONDS: int = 600
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
