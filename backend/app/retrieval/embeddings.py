"""Embedding model with OpenAI and local fallback support."""
from typing import List, Optional

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("retrieval.embeddings")


class EmbeddingModel:
    """Wrapper for embeddings — OpenAI (default) or local sentence-transformers."""

    def __init__(self):
        self.settings = get_settings()
        self.provider = self.settings.embedding_provider
        self._client = None
        self._local_model = None

        if self.provider == "openai":
            self._init_openai()
        else:
            self._init_local()

    # ------------------------------------------------------------------
    # Initializers
    # ------------------------------------------------------------------
    def _init_openai(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Run: pip install openai"
            )

        if not self.settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai. "
                "Add it to your backend/.env file."
            )

        self._client = OpenAI(api_key=self.settings.openai_api_key)
        self.model_name = self.settings.openai_embedding_model
        self._dimensions = self.settings.embedding_dimensions
        logger.info(
            f"OpenAI embedding client ready. Model: {self.model_name}, "
            f"Dimensions: {self._dimensions}"
        )

    def _init_local(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )

        logger.info(
            f"Loading local embedding model: {self.settings.embedding_model} "
            f"on {self.settings.embedding_device}"
        )
        self._local_model = SentenceTransformer(
            self.settings.embedding_model,
            device=self.settings.embedding_device,
        )
        self._dimensions = self._local_model.get_sentence_embedding_dimension()
        self.batch_size = self.settings.embedding_batch_size
        logger.info(f"Local embedding model loaded. Dimension: {self._dimensions}")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def dimensions(self) -> int:
        return self._dimensions

    # ------------------------------------------------------------------
    # Encode
    # ------------------------------------------------------------------
    def encode(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Encode texts to embeddings."""
        if not texts:
            return []

        texts = [t.strip() for t in texts if t.strip()]
        if not texts:
            return []

        if self.provider == "openai":
            return self._encode_openai(texts)
        return self._encode_local(texts, batch_size)

    def _encode_openai(self, texts: List[str]) -> List[List[float]]:
        """Call OpenAI Embeddings API with automatic batching."""
        # OpenAI allows up to 2048 texts per request, but smaller batches are safer
        OPENAI_BATCH_LIMIT = 2048
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), OPENAI_BATCH_LIMIT):
            batch = texts[i : i + OPENAI_BATCH_LIMIT]
            try:
                response = self._client.embeddings.create(
                    model=self.model_name,
                    input=batch,
                    encoding_format="float",
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"OpenAI embedding API error: {e}")
                raise

        return all_embeddings

    def _encode_local(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Encode using local sentence-transformers model."""
        batch_size = batch_size or self.batch_size
        embeddings = self._local_model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    # ------------------------------------------------------------------
    # Query encode
    # ------------------------------------------------------------------
    def encode_query(self, text: str) -> List[float]:
        """Encode a single query."""
        if self.provider == "openai":
            # OpenAI embeddings are symmetric — no instruction prefix needed
            return self.encode([text])[0]

        # Local BGE-style models benefit from instruction prefix for asymmetric search
        query_text = f"Represent this sentence for searching relevant passages: {text}"
        return self.encode([query_text])[0]


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------
_embedding_model: Optional[EmbeddingModel] = None


def get_embedding_model() -> EmbeddingModel:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model