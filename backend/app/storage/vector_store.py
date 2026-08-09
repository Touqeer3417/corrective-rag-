"""Pure Python in-memory vector store (no Qdrant needed)."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk

logger = get_logger("storage.vector")


class VectorStore:
    """In-memory vector store with numpy cosine similarity. No external DB needed."""

    def __init__(self):
        settings = get_settings()
        self.data_dir = Path(settings.bm25_index_path).parent / "vectors"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file = self.data_dir / "vectors.json"
        self.embeddings: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self.embeddings = []
                for item in raw:
                    item["embedding"] = np.array(item["embedding"])
                    item["chunk"] = DocumentChunk(**item["chunk"])
                    self.embeddings.append(item)
                logger.info(f"Loaded {len(self.embeddings)} vectors from disk")
            except Exception as e:
                logger.warning(f"Could not load vectors: {e}")
                self.embeddings = []

    def _save(self) -> None:
        try:
            serializable = []
            for item in self.embeddings:
                serializable.append({
                    "embedding": item["embedding"].tolist(),
                    "chunk": item["chunk"].model_dump(),
                })
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, default=str)
            logger.info(f"Saved {len(self.embeddings)} vectors to disk")
        except Exception as e:
            logger.error(f"Failed to save vectors: {e}")

    def upsert_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        if not chunks or not embeddings:
            return
        for chunk, emb in zip(chunks, embeddings):
            self.embeddings.append({
                "embedding": np.array(emb, dtype=np.float32),
                "chunk": chunk,
            })
        self._save()
        logger.info(f"Upserted {len(chunks)} vectors")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 50,
        document_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        if not self.embeddings:
            logger.warning("Vector store empty, returning no results")
            return []

        query = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query)

        if query_norm == 0:
            return []

        scores = []
        for item in self.embeddings:
            emb = item["embedding"]
            # Cosine similarity
            dot = np.dot(query, emb)
            norm = query_norm * np.linalg.norm(emb)
            score = float(dot / norm) if norm != 0 else 0.0
            scores.append(score)

        # Filter by document_ids if provided
        indices = list(range(len(self.embeddings)))
        if document_ids:
            indices = [i for i in indices if self.embeddings[i]["chunk"].document_id in document_ids]

        # Sort by score descending
        indices.sort(key=lambda i: scores[i], reverse=True)
        top_indices = indices[:top_k]

        results = []
        for idx in top_indices:
            chunk = self.embeddings[idx]["chunk"]
            chunk.score = scores[idx]
            results.append(chunk)

        logger.info(f"Vector search returned {len(results)} results")
        return results

    def delete_by_document(self, document_id: str) -> int:
        original = len(self.embeddings)
        self.embeddings = [e for e in self.embeddings if e["chunk"].document_id != document_id]
        deleted = original - len(self.embeddings)
        if deleted > 0:
            self._save()
            logger.info(f"Deleted {deleted} vectors for document {document_id}")
        return deleted


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store