"""Embedding model with OpenAI and local fallback support + CACHING."""
from typing import List, Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.core.cache import get_embedding_cache, _make_key

logger = get_logger("retrieval.embeddings")

class EmbeddingModel:
    """Wrapper for embeddings — OpenAI (default) or local sentence-transformers."""

    def __init__(self):
        self.settings = get_settings()
        self.provider = self.settings.embedding_provider
        self._client = None
        self._local_model = None
        self._cache = get_embedding_cache()

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

    def _encode_openai(
    self,
    texts: List[str],
) -> List[List[float]]:
        """
        Generate OpenAI embeddings in small batches.

        Small batches reduce:
        - memory usage
        - request size
        - timeout risk
        - failures on large documents
        """

        OPENAI_BATCH_SIZE = 64

        all_embeddings: List[List[float]] = []

        total = len(texts)

        logger.info(
            f"Generating embeddings for {total} chunks "
            f"in batches of {OPENAI_BATCH_SIZE}"
        )

        for start in range(
            0,
            total,
            OPENAI_BATCH_SIZE,
        ):
            end = min(
                start + OPENAI_BATCH_SIZE,
                total,
            )

            batch = texts[start:end]

            try:
                logger.info(
                    f"Embedding chunks "
                    f"{start + 1}-{end}/{total}"
                )

                response = self._client.embeddings.create(
                    model=self.model_name,
                    input=batch,
                    encoding_format="float",
                )

                batch_embeddings = [
                    item.embedding
                    for item in response.data
                ]

                all_embeddings.extend(
                    batch_embeddings
                )

            except Exception as e:
                logger.exception(
                    f"OpenAI embedding API error "
                    f"for chunks {start + 1}-{end}: {e}"
                )
                raise

        logger.info(
            f"Generated {len(all_embeddings)} embeddings"
        )

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
    # Query encode — WITH CACHE
    # ------------------------------------------------------------------
    def encode_query(self, text: str) -> List[float]:
        """Encode a single query with caching."""
        if not getattr(self.settings, "cache_enabled", True):
            return self._encode_query_raw(text)
        
        # Build cache key from query text + provider + model
        cache_key = _make_key(
            "encode_query",
            text.strip().lower(),
            self.provider,
            self.model_name if self.provider == "openai" else self.settings.embedding_model
        )
        
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(f"[EMBEDDING CACHE] HIT for query: {text[:50]}...")
            return cached
        
        result = self._encode_query_raw(text)
        self._cache.set(cache_key, result)
        logger.info(f"[EMBEDDING CACHE] MISS for query: {text[:50]}... - cached")
        return result

    def _encode_query_raw(self, text: str) -> List[float]:
        """Raw query encoding without cache."""
        if self.provider == "openai":
            return self.encode([text])[0]

        # Local BGE-style models benefit from instruction prefix
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