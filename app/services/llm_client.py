from openai import OpenAI
from app.core.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_BASE_URL,
    AZURE_OPENAI_DEPLOYMENT,
)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_BASE_URL:
            raise RuntimeError("Missing AZURE_OPENAI_API_KEY or AZURE_OPENAI_BASE_URL in .env")
        _client = OpenAI(api_key=AZURE_OPENAI_API_KEY, base_url=AZURE_OPENAI_BASE_URL)
    return _client


def get_deployment() -> str:
    if not AZURE_OPENAI_DEPLOYMENT:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not set")
    return AZURE_OPENAI_DEPLOYMENT
