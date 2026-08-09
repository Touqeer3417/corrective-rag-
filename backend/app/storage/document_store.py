"""SQLite-based document metadata storage."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.document import DocumentInfo, DocumentUpload

logger = get_logger("storage.document")

INIT_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    chunk_count INTEGER DEFAULT 0,
    page_count INTEGER,
    metadata TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at);
"""


class DocumentStore:
    """SQLite document metadata store."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(INIT_SQL)
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_document(
        self,
        filename: str,
        original_name: str,
        file_type: str,
        file_size: int,
        page_count: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> DocumentUpload:
        doc_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO documents 
                   (document_id, filename, original_name, file_type, file_size, 
                    status, page_count, metadata, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, filename, original_name, file_type, file_size,
                 "pending", page_count, json.dumps(metadata or {}), now, now),
            )
            conn.commit()
        logger.info(f"Created document record: {doc_id}")
        return DocumentUpload(
            document_id=doc_id,
            filename=original_name,
            file_type=file_type,
            status="pending",
            created_at=datetime.fromisoformat(now),
        )

    def update_status(
        self,
        document_id: str,
        status: str,
        chunk_count: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            updates = ["status = ?", "updated_at = ?"]
            params = [status, now]
            if chunk_count is not None:
                updates.append("chunk_count = ?")
                params.append(chunk_count)
            params.append(document_id)
            sql = f"UPDATE documents SET {', '.join(updates)} WHERE document_id = ?"
            conn.execute(sql, params)
            conn.commit()
        logger.info(f"Updated document {document_id} status to {status}")

    def get_document(self, document_id: str) -> Optional[DocumentInfo]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?", (document_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_info(row)

    def list_documents(self, limit: int = 100, offset: int = 0) -> List[DocumentInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_info(row) for row in rows]

    def delete_document(self, document_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM documents WHERE document_id = ?", (document_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted document: {document_id}")
        return deleted

    def _row_to_info(self, row: sqlite3.Row) -> DocumentInfo:
        return DocumentInfo(
            document_id=row["document_id"],
            filename=row["filename"],
            original_name=row["original_name"],
            file_type=row["file_type"],
            file_size=row["file_size"],
            status=row["status"],
            chunk_count=row["chunk_count"] or 0,
            page_count=row["page_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# Singleton instance
_document_store: Optional[DocumentStore] = None


def get_document_store() -> DocumentStore:
    global _document_store
    if _document_store is None:
        settings = get_settings()
        _document_store = DocumentStore(settings.database_url.replace("sqlite:///", ""))
    return _document_store
