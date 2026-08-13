"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import setup_logging
from app.api.v1 import documents, chat, health

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


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
    app.include_router(health.router, prefix=prefix, tags=["Health"])
    app.include_router(documents.router, prefix=f"{prefix}/documents", tags=["Documents"])
    app.include_router(chat.router, prefix=f"{prefix}/chat", tags=["Chat"])
    
    # from evaluation.api import router as evaluate_router
    # app.include_router(evaluate_router, prefix=f"{sys.prefix}/evaluate", tags=["Evaluation"])
    return app


app = create_app()