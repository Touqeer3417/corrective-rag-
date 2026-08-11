"""Application configuration using Pydantic Settings."""
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Robust .env path resolution
# ---------------------------------------------------------------------------
# This file lives at: backend/app/config.py
# The .env file lives at: backend/.env
# We walk up one directory so it works no matter where the script is run from.
BASE_DIR = Path(__file__).resolve().parent.parent          # -> backend/
ENV_FILE = BASE_DIR / ".env"

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,          # Allow both field name & alias
    )

    # App
    app_name: str = Field(default="CRAG-Company-Search", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")

    # CORS
    cors_origins: list = Field(default=["http://localhost:5173"], alias="CORS_ORIGINS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # LLM
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    llm_model: str = Field(default="llama-3.1-70b-versatile", alias="LLM_MODEL")
    llm_provider: str = Field(default="groq", alias="LLM_PROVIDER")
    local_llm_model: str = Field(
        default="microsoft/Phi-3-mini-4k-instruct", alias="LOCAL_LLM_MODEL"
    )

    # Embeddings
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")

    # Reranker
    reranker_model: str = Field(default="BAAI/bge-reranker-base", alias="RERANKER_MODEL")
    reranker_device: str = Field(default="cpu", alias="RERANKER_DEVICE")
    reranker_batch_size: int = Field(default=16, alias="RERANKER_BATCH_SIZE")

    # Qdrant
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="company_documents", alias="QDRANT_COLLECTION")
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")

    # BM25
    bm25_index_path: str = Field(default="./data/bm25", alias="BM25_INDEX_PATH")
    bm25_k1: float = Field(default=1.5, alias="BM25_K1")
    bm25_b: float = Field(default=0.75, alias="BM25_B")

    # Storage
    upload_dir: str = Field(default="./data/uploads", alias="UPLOAD_DIR")
    database_url: str = Field(default="sqlite:///./data/sqlite/crag.db", alias="DATABASE_URL")
    max_file_size_mb: int = Field(default=50, alias="MAX_FILE_SIZE_MB")
    max_batch_size_mb: int = Field(default=200, alias="MAX_BATCH_SIZE_MB")

    # RAG
    max_retries: int = Field(default=2, alias="MAX_RETRIES")
    top_k_hybrid: int = Field(default=50, alias="TOP_K_HYBRID")
    top_k_rerank: int = Field(default=10, alias="TOP_K_RERANK")
    rrf_k: int = Field(default=60, alias="RRF_K")
    relevance_threshold_high: float = Field(default=0.7, alias="RELEVANCE_THRESHOLD_HIGH")
    relevance_threshold_low: float = Field(default=0.4, alias="RELEVANCE_THRESHOLD_LOW")
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, alias="CHUNK_OVERLAP")

    # Security
    allowed_extensions: list = Field(default=["pdf", "docx", "txt", "md"], alias="ALLOWED_EXTENSIONS")

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(",")]
        return v

    # -----------------------------------------------------------------------
    # Helper properties
    # -----------------------------------------------------------------------
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_batch_size_bytes(self) -> int:
        return self.max_batch_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    return Settings()