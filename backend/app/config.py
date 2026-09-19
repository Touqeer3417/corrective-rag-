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
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
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

    # -----------------------------------------------------------------------
    # LLM Provider (openai / groq / local)
    # -----------------------------------------------------------------------
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.5, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        allowed = {"openai", "groq", "local"}
        if v.lower() not in allowed:
            raise ValueError(f"llm_provider must be one of {allowed}, got '{v}'")
        return v.lower()

    # OpenAI (shared key for embeddings + LLM)
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_llm_model: str = Field(default="gpt-4o-mini", alias="OPENAI_LLM_MODEL")

    # Groq
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-70b-versatile", alias="GROQ_MODEL")

    # Local LLM (fallback)
    local_llm_model: str = Field(
        default="microsoft/Phi-3-mini-4k-instruct", alias="LOCAL_LLM_MODEL"
    )

    # -----------------------------------------------------------------------
    # Embeddings (OpenAI + Local fallback)
    # -----------------------------------------------------------------------
    embedding_provider: str = Field(default="openai", alias="EMBEDDING_PROVIDER")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")
    embedding_batch_size: int = Field(default=32, alias="EMBEDDING_BATCH_SIZE")

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, v: str) -> str:
        allowed = {"openai", "local", "huggingface"}
        if v.lower() not in allowed:
            raise ValueError(f"embedding_provider must be one of {allowed}, got '{v}'")
        return v.lower()

    # Reranker
    reranker_enabled: bool = Field(default=True, alias="RERANKER_ENABLED")
    reranker_model: str = Field(default="BAAI/bge-reranker-base", alias="RERANKER_MODEL")
    reranker_device: str = Field(default="cpu", alias="RERANKER_DEVICE")
    reranker_batch_size: int = Field(default=16, alias="RERANKER_BATCH_SIZE")
    reranker_skip_threshold: float = Field(default=0.75, alias="RERANKER_SKIP_THRESHOLD")

    # Qdrant
   # Qdrant
    qdrant_url: Optional[str] = Field(default=None, alias="QDRANT_URL")
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(
        default="company_documents",
        alias="QDRANT_COLLECTION",
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        alias="QDRANT_API_KEY",
    )

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
    max_retries: int = Field(default=1, alias="MAX_RETRIES")
    top_k_hybrid: int = Field(default=50, alias="TOP_K_HYBRID")
    top_k_rerank: int = Field(default=10, alias="TOP_K_RERANK")
    rrf_k: int = Field(default=60, alias="RRF_K")
    relevance_threshold_high: float = Field(default=0.7, alias="RELEVANCE_THRESHOLD_HIGH")
    relevance_threshold_low: float = Field(default=0.45, alias="RELEVANCE_THRESHOLD_LOW")
    chunk_size: int = Field(default=350, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, alias="CHUNK_OVERLAP")

    # -----------------------------------------------------------------------
    # SPEED OPTIMIZATION (NEW — Production Speed Settings)
    # -----------------------------------------------------------------------
    hybrid_parallel: bool = Field(default=True, alias="HYBRID_PARALLEL")
    grade_max_docs_per_batch: int = Field(default=8, alias="GRADE_MAX_DOCS_PER_BATCH")
    grade_max_chars_per_doc: int = Field(default=400, alias="GRADE_MAX_CHARS_PER_DOC")
    grade_embedding_pre_filter: bool = Field(default=True, alias="GRADE_EMBEDDING_PRE_FILTER")
    grade_embedding_threshold: float = Field(default=0.20, alias="GRADE_EMBEDDING_THRESHOLD")
    grade_fast_path_enabled: bool = Field(default=True, alias="GRADE_FAST_PATH_ENABLED")
    grade_fast_path_threshold: float = Field(default=0.90, alias="GRADE_FAST_PATH_THRESHOLD")
    grade_max_tokens: int = Field(default=1024, alias="GRADE_MAX_TOKENS")
    transform_heuristic_first: bool = Field(default=True, alias="TRANSFORM_HEURISTIC_FIRST")
    warmup_on_startup: bool = Field(default=True, alias="WARMUP_ON_STARTUP")

    # Security
    allowed_extensions: list = Field(default=["pdf", "docx", "txt", "md"], alias="ALLOWED_EXTENSIONS")

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip().lower() for ext in v.split(",")]
        return v

    # -----------------------------------------------------------------------
    # Caching (Redis + In-Memory) -- NEW
    # -----------------------------------------------------------------------
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_embedding_ttl: int = Field(default=86400, alias="CACHE_EMBEDDING_TTL")  # 24h
    cache_retrieval_ttl: int = Field(default=3600, alias="CACHE_RETRIEVAL_TTL")  # 1h
    cache_grade_ttl: int = Field(default=3600, alias="CACHE_GRADE_TTL")  # 1h
    cache_answer_ttl: int = Field(default=1800, alias="CACHE_ANSWER_TTL")  # 30m

    # -----------------------------------------------------------------------
    # Helper properties
    # -----------------------------------------------------------------------
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_batch_size_bytes(self) -> int:
        return self.max_batch_size_mb * 1024 * 1024

    @property
    def embedding_dimensions(self) -> int:
        """Return expected vector dimensions based on the active embedding provider."""
        dims_map = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        if self.embedding_provider == "openai":
            return dims_map.get(self.openai_embedding_model, 1536)
        if "small" in self.embedding_model:
            return 384
        if "base" in self.embedding_model:
            return 768
        if "large" in self.embedding_model:
            return 1024
        return 384

    @property
    def active_llm_model(self) -> str:
        """Return the active LLM model name based on provider."""
        if self.llm_provider == "openai":
            return self.openai_llm_model
        if self.llm_provider == "groq":
            return self.groq_model
        return self.local_llm_model

@lru_cache()
def get_settings() -> Settings:
    return Settings()