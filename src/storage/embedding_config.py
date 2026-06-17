import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

from src.config.runtime_contract import (
    CANONICAL_EMBEDDING_DIMENSION,
    CANONICAL_EMBEDDING_MODEL,
    CANONICAL_EMBEDDING_PROVIDER,
)
from src.utils.embedding_usage import TrackingEmbeddings

logger = logging.getLogger(__name__)

load_dotenv()


def _select_default_embedding_provider(explicit_provider: Optional[str] = None) -> str:
    explicit = (
        explicit_provider
        if explicit_provider is not None
        else os.getenv("DART_EMBEDDING_PROVIDER", "")
    ).strip().lower()
    if explicit:
        return explicit

    canonical = CANONICAL_EMBEDDING_PROVIDER.strip().lower()
    if canonical == "openai" and os.getenv("OPENAI_API_KEY"):
        return "openai"
    if canonical == "google" and os.getenv("GOOGLE_API_KEY"):
        return "google"
    if canonical == "huggingface":
        return "huggingface"

    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GOOGLE_API_KEY"):
        return "google"
    return "huggingface"


DEFAULT_EMBEDDING_PROVIDER = _select_default_embedding_provider()
DEFAULT_GOOGLE_EMBEDDING_MODEL = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-2")
DEFAULT_OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", CANONICAL_EMBEDDING_MODEL)
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
    override = os.getenv("DART_EMBEDDING_DIMENSION", "").strip()
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
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY is required for Google API embeddings.")
        embeddings = GoogleGenerativeAIEmbeddings(
            model=selected_model or DEFAULT_GOOGLE_EMBEDDING_MODEL,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
        return TrackingEmbeddings(embeddings) if track_usage else embeddings

    if selected_provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for OpenAI API embeddings.")
        embeddings = OpenAIEmbeddings(
            model=selected_model or DEFAULT_OPENAI_EMBEDDING_MODEL,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        return TrackingEmbeddings(embeddings) if track_usage else embeddings

    if selected_provider == "huggingface":
        embeddings = HuggingFaceEmbeddings(model_name=selected_model or DEFAULT_HUGGINGFACE_EMBEDDING_MODEL)
        return TrackingEmbeddings(embeddings) if track_usage else embeddings

    raise ValueError(
        f"Unsupported embedding provider: {selected_provider}. "
        "Use one of: google, openai, huggingface."
    )
