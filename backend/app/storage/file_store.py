"""Local file storage for uploaded documents."""
import shutil
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_safe_path

logger = get_logger("storage.file")


class FileStore:
    """Simple local filesystem storage for document files."""

    def __init__(self, upload_dir: str):
        self.upload_dir = Path(upload_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, source_path: str, secure_filename: str) -> Path:
        target = get_safe_path(str(self.upload_dir), secure_filename)
        shutil.copy2(source_path, target)
        logger.info(f"Saved file: {target}")
        return target

    def get_path(self, secure_filename: str) -> Path:
        return get_safe_path(str(self.upload_dir), secure_filename)

    def delete(self, secure_filename: str) -> bool:
        target = self.get_path(secure_filename)
        if target.exists():
            target.unlink()
            logger.info(f"Deleted file: {target}")
            return True
        return False


# Singleton
_file_store: Optional[FileStore] = None


def get_file_store() -> FileStore:
    global _file_store
    if _file_store is None:
        settings = get_settings()
        _file_store = FileStore(settings.upload_dir)
    return _file_store
