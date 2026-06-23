import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import dotenv_values

from src.config.runtime_contract import (
    CANONICAL_EMBEDDING_DIMENSION,
    CANONICAL_EMBEDDING_MODEL,
    CANONICAL_EMBEDDING_PROVIDER,
)
from src.utils.embedding_usage import TrackingEmbeddings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOTENV_VALUES = {
    key: str(value)
    for key, value in dotenv_values(_PROJECT_ROOT / ".env").items()
    if value is not None
}


def _env_value(key: str, default: str = "") -> str:
    return str(os.getenv(key) or _DOTENV_VALUES.get(key) or default)


def _select_default_embedding_provider(explicit_provider: Optional[str] = None) -> str:
    explicit = (
        explicit_provider
        if explicit_provider is not None
        else _env_value("DART_EMBEDDING_PROVIDER")
    ).strip().lower()
    if explicit:
        return explicit

    canonical = CANONICAL_EMBEDDING_PROVIDER.strip().lower()
    if canonical == "openai" and _env_value("OPENAI_API_KEY"):
        return "openai"
    if canonical == "google" and _env_value("GOOGLE_API_KEY"):
        return "google"
    if canonical == "huggingface":
        return "huggingface"

    if _env_value("OPENAI_API_KEY"):
        return "openai"
    if _env_value("GOOGLE_API_KEY"):
        return "google"
    return "huggingface"


DEFAULT_EMBEDDING_PROVIDER = _select_default_embedding_provider()
DEFAULT_GOOGLE_EMBEDDING_MODEL = _env_value("GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-2")
DEFAULT_OPENAI_EMBEDDING_MODEL = _env_value("OPENAI_EMBEDDING_MODEL", CANONICAL_EMBEDDING_MODEL)
DEFAULT_HUGGINGFACE_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_EMBEDDING_MODEL = (
    DEFAULT_GOOGLE_EMBEDDING_MODEL
    if DEFAULT_EMBEDDING_PROVIDER == "google"
    else DEFAULT_OPENAI_EMBEDDING_MODEL
    if DEFAULT_EMBEDDING_PROVIDER == "openai"
    else DEFAULT_HUGGINGFACE_EMBEDDING_MODEL
)

_KNOWN_EMBEDDING_DIMENSIONS = {
    ("google", "models/gemini-embedding-2"): 3072,
    ("google", "models/text-embedding-004"): 768,
    ("openai", "text-embedding-3-large"): CANONICAL_EMBEDDING_DIMENSION,
    ("openai", "text-embedding-3-small"): 1536,
    ("openai", "text-embedding-ada-002"): 1536,
    ("huggingface", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"): 384,
}


def infer_embedding_dimension(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Optional[int]:
    selected_provider = (provider or DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    selected_model = (model_name or DEFAULT_EMBEDDING_MODEL).strip()
    override = _env_value("DART_EMBEDDING_DIMENSION").strip()
    if override:
        try:
            return int(override)
        except ValueError:
            logger.warning("Ignoring invalid DART_EMBEDDING_DIMENSION=%r", override)
    return _KNOWN_EMBEDDING_DIMENSIONS.get((selected_provider, selected_model))


def get_embedding_runtime_spec(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    selected_provider = (provider or DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    selected_model = (model_name or DEFAULT_EMBEDDING_MODEL).strip()
    return {
        "provider": selected_provider,
        "model_name": selected_model,
        "dimension": infer_embedding_dimension(selected_provider, selected_model),
    }


def create_embeddings(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    track_usage: bool = True,
) -> Any:
    selected_provider = (provider or DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    selected_model = (model_name or DEFAULT_EMBEDDING_MODEL).strip()

    if selected_provider == "google":
        google_api_key = _env_value("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for Google API embeddings.")
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embeddings = GoogleGenerativeAIEmbeddings(
            model=selected_model or DEFAULT_GOOGLE_EMBEDDING_MODEL,
            google_api_key=google_api_key,
        )
        return TrackingEmbeddings(embeddings) if track_usage else embeddings

    if selected_provider == "openai":
        openai_api_key = _env_value("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI API embeddings.")
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(
            model=selected_model or DEFAULT_OPENAI_EMBEDDING_MODEL,
            api_key=openai_api_key,
        )
        return TrackingEmbeddings(embeddings) if track_usage else embeddings

    if selected_provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(model_name=selected_model or DEFAULT_HUGGINGFACE_EMBEDDING_MODEL)
        return TrackingEmbeddings(embeddings) if track_usage else embeddings

    raise ValueError(
        f"Unsupported embedding provider: {selected_provider}. "
        "Use one of: google, openai, huggingface."
    )
