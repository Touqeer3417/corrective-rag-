"""Local CPU embedding model using sentence-transformers."""
from typing import List, Optional

from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("retrieval.embeddings")


class EmbeddingModel:
    """Singleton wrapper for local embedding model."""
    
    def __init__(self):
        settings = get_settings()
        logger.info(f"Loading embedding model: {settings.embedding_model} on {settings.embedding_device}")
        self.model = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )
        self.batch_size = settings.embedding_batch_size
        logger.info(f"Embedding model loaded. Dimension: {self.model.get_sentence_embedding_dimension()}")
    
    def encode(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """Encode texts to embeddings."""
        if not texts:
            return []
        
        texts = [t.strip() for t in texts if t.strip()]
        if not texts:
            return []
        
        batch_size = batch_size or self.batch_size
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()
    
    def encode_query(self, text: str) -> List[float]:
        """Encode a single query with instruction prefix for asymmetric search."""
        query_text = f"Represent this sentence for searching relevant passages: {text}"
        return self.encode([query_text])[0]


_embedding_model: Optional[EmbeddingModel] = None

def get_embedding_model() -> EmbeddingModel:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model