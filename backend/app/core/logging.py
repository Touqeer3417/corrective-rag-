"""Structured logging configuration."""
import logging
import sys
from typing import Any, Dict

from app.config import get_settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, default=str)


def setup_logging() -> logging.Logger:
    """Configure application logging."""
    settings = get_settings()
    logger = logging.getLogger("crag")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if settings.debug:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            )
        else:
            formatter = JSONFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Redact sensitive fields
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(f"crag.{name}")
