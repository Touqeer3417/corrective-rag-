"""BM25 sparse retrieval implementation."""
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentChunk

logger = get_logger("retrieval.sparse")


def tokenize(text: str) -> List[str]:
    """Simple whitespace tokenization with lowercase."""
    return text.lower().split()


class BM25Index:
    """In-memory BM25 index with persistence."""

    def __init__(self, index_path: str):
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.index_path / "metadata.json"
        self.index_file = self.index_path / "bm25.pkl"

        self.bm25: Optional[BM25Okapi] = None
        self.documents: List[DocumentChunk] = []
        self.tokenized_corpus: List[List[str]] = []
        self._load()

    def _load(self) -> None:
        """Load existing index from disk."""
        if self.index_file.exists() and self.metadata_file.exists():
            try:
                with open(self.index_file, "rb") as f:
                    self.bm25 = pickle.load(f)
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    self.documents = [DocumentChunk(**d) for d in meta.get("documents", [])]
                    self.tokenized_corpus = meta.get("tokenized_corpus", [])
                logger.info(f"Loaded BM25 index with {len(self.documents)} documents")
            except Exception as e:
                logger.warning(f"Failed to load BM25 index: {e}. Starting fresh.")
                self.bm25 = None
                self.documents = []
                self.tokenized_corpus = []

    def _save(self) -> None:
        """Persist index to disk."""
        try:
            with open(self.index_file, "wb") as f:
                pickle.dump(self.bm25, f)
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump({
                    "documents": [d.model_dump() for d in self.documents],
                    "tokenized_corpus": self.tokenized_corpus,
                }, f, default=str)
            logger.info(f"Saved BM25 index with {len(self.documents)} documents")
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")

    def add_documents(self, chunks: List[DocumentChunk]) -> None:
        """Add document chunks to the BM25 index."""
        if not chunks:
            return

        settings = get_settings()
        new_tokens = [tokenize(chunk.text) for chunk in chunks]

        self.documents.extend(chunks)
        self.tokenized_corpus.extend(new_tokens)

        # Rebuild BM25 index
        self.bm25 = BM25Okapi(
            self.tokenized_corpus,
            k1=settings.bm25_k1,
            b=settings.bm25_b,
        )
        self._save()
        logger.info(f"Added {len(chunks)} chunks to BM25 index")

    def search(self, query: str, top_k: int = 50) -> List[DocumentChunk]:
        """Search using BM25 scoring."""
        if self.bm25 is None or not self.documents:
            logger.warning("BM25 index empty, returning no results")
            return []

        logger.info(f"BM25 search: query='{query[:50]}...', top_k={top_k}")
        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk = self.documents[idx]
                chunk.score = float(scores[idx])
                results.append(chunk)

        logger.info(f"BM25 search returned {len(results)} results")
        return results

    def delete_by_document(self, document_id: str) -> int:
        """Remove all chunks for a document and rebuild index."""
        original_count = len(self.documents)
        # Filter out documents
        keep_indices = []
        new_docs = []
        new_tokens = []
        for i, doc in enumerate(self.documents):
            if doc.document_id != document_id:
                keep_indices.append(i)
                new_docs.append(doc)
                new_tokens.append(self.tokenized_corpus[i])

        deleted = original_count - len(new_docs)
        if deleted > 0:
            self.documents = new_docs
            self.tokenized_corpus = new_tokens
            if self.tokenized_corpus:
                settings = get_settings()
                self.bm25 = BM25Okapi(
                    self.tokenized_corpus,
                    k1=settings.bm25_k1,
                    b=settings.bm25_b,
                )
            else:
                self.bm25 = None
            self._save()
            logger.info(f"Deleted {deleted} chunks for document {document_id}")
        return deleted


# Singleton
_bm25_index: Optional[BM25Index] = None


def get_bm25_index() -> BM25Index:
    global _bm25_index
    if _bm25_index is None:
        settings = get_settings()
        _bm25_index = BM25Index(settings.bm25_index_path)
    return _bm25_index
