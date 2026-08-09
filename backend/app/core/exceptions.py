"""Custom exception hierarchy for the application."""


class CRAGException(Exception):
    """Base exception for the CRAG application."""
    pass


class DocumentValidationError(CRAGException):
    """Raised when document validation fails."""
    pass


class IngestionError(CRAGException):
    """Raised when document ingestion fails."""
    pass


class RetrievalError(CRAGException):
    """Raised when document retrieval fails."""
    pass


class GenerationError(CRAGException):
    """Raised when answer generation fails."""
    pass


class VectorStoreError(CRAGException):
    """Raised when vector store operations fail."""
    pass


class BM25IndexError(CRAGException):
    """Raised when BM25 index operations fail."""
    pass
