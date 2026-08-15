"""FastAPI application factory."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import setup_logging, get_logger

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

logger = get_logger("main")


def _warmup_models() -> None:
    """Pre-load all heavy singletons so first request is fast."""
    try:
        from app.retrieval.embeddings import get_embedding_model
        from app.retrieval.hybrid import get_hybrid_retriever
        from app.retrieval.reranker import get_reranker
        from app.retrieval.sparse import get_bm25_index
        from app.rag.models import get_llm_provider
        from app.storage.vector_store import get_vector_store
        from app.storage.document_store import get_document_store

        get_embedding_model()
        get_vector_store()
        get_bm25_index()
        get_hybrid_retriever()
        get_reranker()
        get_llm_provider()
        get_document_store()

        logger.info("=" * 50)
        logger.info("STARTUP WARMUP COMPLETE — All models loaded")
        logger.info("=" * 50)
    except Exception as e:
        logger.warning(f"Startup warmup failed (non-critical): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()

    # Warmup heavy models in background so first request is <10s
    if getattr(settings, "warmup_on_startup", True):
        logger.info("Warming up models in background...")
        asyncio.create_task(asyncio.to_thread(_warmup_models))

    yield
    logger.info("Shutting down CRAG API")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-Ready Corrective RAG (CRAG) for Company Document Search",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_prefix

    # Existing routes
    from app.api.v1 import health, documents, chat
    app.include_router(health.router, prefix=prefix, tags=["Health"])
    app.include_router(documents.router, prefix=f"{prefix}/documents", tags=["Documents"])
    app.include_router(chat.router, prefix=f"{prefix}/chat", tags=["Chat"])

    return app


app = create_app()