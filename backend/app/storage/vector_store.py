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
        self.meta_file = self.data_dir / "meta.json"

        self.embeddings: List[Dict[str, Any]] = []
        self._dimension: Optional[int] = None
        self._load()

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    def _load_meta(self) -> Optional[int]:
        """Return stored dimension from meta file, or None."""
        if self.meta_file.exists():
            try:
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                return meta.get("dimension")
            except Exception:
                return None
        return None

    def _save_meta(self, dimension: int) -> None:
        try:
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump({"dimension": dimension}, f)
        except Exception as e:
            logger.error(f"Failed to save meta: {e}")

    def _clear_store(self) -> None:
        """Remove all stored vectors and metadata."""
        self.embeddings = []
        self._dimension = None
        if self.data_file.exists():
            self.data_file.unlink()
        if self.meta_file.exists():
            self.meta_file.unlink()
        logger.warning("Vector store cleared due to dimension mismatch.")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.data_file.exists():
            self.embeddings = []
            return

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                raw = json.load(f)

            self.embeddings = []
            for item in raw:
                item["embedding"] = np.array(item["embedding"], dtype=np.float32)
                item["chunk"] = DocumentChunk(**item["chunk"])
                self.embeddings.append(item)

            # Validate dimension consistency
            if self.embeddings:
                stored_dim = self.embeddings[0]["embedding"].shape[0]
                meta_dim = self._load_meta()

                if meta_dim is not None and stored_dim != meta_dim:
                    logger.warning(
                        f"Stored dimension mismatch: file={stored_dim}, meta={meta_dim}. "
                        f"Clearing store."
                    )
                    self._clear_store()
                    return

                self._dimension = stored_dim
                self._save_meta(stored_dim)

            logger.info(f"Loaded {len(self.embeddings)} vectors from disk (dim={self._dimension})")
        except Exception as e:
            logger.warning(f"Could not load vectors: {e}")
            self.embeddings = []
            self._dimension = None

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

            if self._dimension is not None:
                self._save_meta(self._dimension)

            logger.info(f"Saved {len(self.embeddings)} vectors to disk")
        except Exception as e:
            logger.error(f"Failed to save vectors: {e}")

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
    def upsert_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        if not chunks or not embeddings:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must have same length"
            )

        # Detect dimension from first new embedding
        new_dim = len(embeddings[0])

        # If store has existing vectors with different dimension → clear
        if self._dimension is not None and new_dim != self._dimension:
            logger.warning(
                f"Dimension mismatch: existing={self._dimension}, new={new_dim}. "
                f"Clearing old vectors before upsert."
            )
            self._clear_store()

        self._dimension = new_dim

        for chunk, emb in zip(chunks, embeddings):
            if len(emb) != new_dim:
                raise ValueError(
                    f"Inconsistent embedding dimension: expected {new_dim}, got {len(emb)}"
                )
            self.embeddings.append({
                "embedding": np.array(emb, dtype=np.float32),
                "chunk": chunk,
            })

        self._save()
        logger.info(f"Upserted {len(chunks)} vectors (dim={new_dim})")

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

        # Dimension guard
        if self._dimension is not None and query.shape[0] != self._dimension:
            logger.error(
                f"Query dimension ({query.shape[0]}) does not match store dimension ({self._dimension}). "
                f"Did you change the embedding model? Try clearing the vector store."
            )
            return []

        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []

        scores = []
        for item in self.embeddings:
            emb = item["embedding"]
            dot = np.dot(query, emb)
            norm = query_norm * np.linalg.norm(emb)
            score = float(dot / norm) if norm != 0 else 0.0
            scores.append(score)

        indices = list(range(len(self.embeddings)))
        if document_ids:
            indices = [i for i in indices if self.embeddings[i]["chunk"].document_id in document_ids]

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

    def clear(self) -> None:
        """Manually clear all vectors. Useful when switching embedding models."""
        self._clear_store()
        logger.info("Vector store manually cleared.")

    @property
    def dimension(self) -> Optional[int]:
        return self._dimension

    @property
    def count(self) -> int:
        return len(self.embeddings)


_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store