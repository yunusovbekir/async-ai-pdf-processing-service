"""Provider registry and factory."""

from app.config import Settings, get_settings
from app.llm.base import LLMConfigError, LLMProvider
from app.llm.gemini import GeminiProvider
from app.llm.openai import OpenAIProvider

# To add a provider: implement a class like GeminiProvider and register it here.
PROVIDERS: dict[str, type[GeminiProvider] | type[OpenAIProvider]] = {
    GeminiProvider.name: GeminiProvider,
    OpenAIProvider.name: OpenAIProvider,
}

_provider: LLMProvider | None = None


def create_provider(settings: Settings) -> LLMProvider:
    """Build the provider selected by LLM_PROVIDER, using LLM_MODEL or its default model.

    Raises:
        LLMConfigError: If the provider is unknown or its API key is missing.
    """
    name = settings.LLM_PROVIDER.strip().lower()
    cls = PROVIDERS.get(name)
    if cls is None:
        raise LLMConfigError(
            f"unknown LLM_PROVIDER '{settings.LLM_PROVIDER}' (available: {', '.join(PROVIDERS)})"
        )
    return cls(settings, settings.LLM_MODEL.strip() or cls.default_model)


def get_provider() -> LLMProvider:
    """Return the process-wide provider, creating it on first use.

    Raises:
        LLMConfigError: If the provider is unknown or its API key is missing.
    """
    global _provider
    if _provider is None:
        _provider = create_provider(get_settings())
    return _provider
