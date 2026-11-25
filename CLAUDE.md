# CLAUDE.md

## Role and Mission

Act as the senior full-stack AI engineer maintaining this repository. Your mission is to understand the existing implementation before changing it, preserve the current architecture where practical, and deliver reliable, secure, testable improvements to this Corrective Retrieval-Augmented Generation (CRAG) application.

Treat the source code and configuration as the source of truth. Do not infer behavior from product names, comments, UI labels, or documentation alone. Before modifying a flow, trace it across its API, service, schema, storage/retrieval, and frontend callers.

## Repository Overview

This is a single-page document knowledge assistant with:

- A Python 3.11+ FastAPI backend.
- A React 18 + TypeScript + Vite frontend.
- A LangGraph-based corrective RAG workflow.
- Hybrid retrieval using Qdrant dense vectors and BM25 sparse search, fused with Reciprocal Rank Fusion (RRF).
- Optional cross-encoder reranking, OpenAI/Groq/local LLM providers, configurable embeddings, and Redis/in-memory caching.
- PDF, DOCX, TXT, and Markdown ingestion.

The application currently behaves as a shared document knowledge base. Do not assume authentication, per-user document isolation, chat history, or multi-tenant access controls exist.

## Architecture and Change Boundaries

### Backend: backend/app

- main.py: FastAPI application creation, CORS, lifespan, model warmup, and router registration.
- config.py: Pydantic Settings. Environment variables are loaded from backend/.env; process environment variables can also override them.
- api/v1/: HTTP endpoints for health, documents, and chat. Keep HTTP concerns in this layer.
- dependencies.py: FastAPI dependency providers for services.
- services/: Application orchestration:
  - ingestion_service.py coordinates validation, file persistence, parsing, chunking, embeddings, Qdrant/BM25 indexing, and document status.
  - document_service.py handles document listing, lookup, and deletion across stores.
  - chat_service.py coordinates the CRAG graph, answer caching, and SSE streaming.
- rag/: LangGraph state, nodes, conditional routing, prompts, and LLM provider abstraction.
- retrieval/: Embedding generation, dense retrieval, BM25 retrieval, hybrid RRF fusion, and reranking.
- ingestion/: Text cleaning, recursive chunking, parser dispatch, and PDF/DOCX/TXT/MD loaders.
- storage/: Qdrant vectors, SQLite document metadata, and local uploaded files.
- core/: Settings-backed cache, constants, logging, exceptions, and file-security helpers.
- schemas/: Pydantic request/response models and document chunk/citation types.

### Frontend: frontend/src

- main.tsx: React entry point, BrowserRouter, and global CSS.
- App.tsx: Main layout, sidebar navigation, routes, and session-only splash screen.
- pages/: Dashboard, UploadPage, DocumentLibrary, and ChatPage.
- services/: Axios API client, document operations, and SSE chat streaming.
- stores/documentStore.ts: Zustand document-list state.
- types/: Shared TypeScript document/chat contracts.
- components/SplashScreen.tsx: Animated introductory screen.

Keep frontend API access in services rather than adding ad-hoc network calls to page components. Reuse the Zustand document store for document-list state. Preserve strict TypeScript settings and the existing dark visual language unless the task explicitly calls for a redesign.

## Main Request Flows

### Document ingestion

1. POST /api/v1/documents/upload accepts a file and saves it to a temporary file in chunks.
2. FastAPI BackgroundTasks starts IngestionService.ingest_document after returning HTTP 202.
3. The ingestion service validates extension, MIME consistency, size, and PDF/DOCX magic bytes; generates a unique safe filename; saves the file; and creates a SQLite metadata record.
4. The parser selects the matching loader, cleans extracted text, and creates metadata-bearing chunks.
5. The embedding model encodes chunks. The vector store upserts them to Qdrant and the BM25 index persists its corresponding chunks.
6. The metadata record is marked indexed; failures mark it error and remove the saved upload file.

The upload response means the file was accepted for background processing, not that indexing has completed. Do not describe HTTP 202 as proof of a successful index. The frontend currently uploads selected files one at a time and refreshes its list after a short delay; it does not use the backend batch-upload endpoint.

### Retrieval and answer generation

The current full graph is:

retriever -> grade_documents -> (reranker | transform_query | responder)
transform_query -> retriever
reranker -> responder
responder -> END

- Dense search embeds the query and searches Qdrant.
- Sparse search tokenizes text for BM25.
- HybridRetriever runs both searches in parallel by default and fuses results with RRF.
- Grading can use embedding pre-filtering, an embedding fast path, or one batched LLM grading call. Grading decisions and retry routing are implemented in rag/nodes.py and rag/edges.py.
- Query transformation first attempts a lightweight heuristic. LLM rewriting is used when the heuristic path is unavailable or a further retry is needed.
- The reranker may pass through already-strong results or use the configured cross-encoder.
- The responder generates an answer from the selected document context and has an insufficient-evidence fallback.

The streaming path runs CRAGGraph.prepare (retrieval through reranking), then streams LLM generation separately. Preserve this separation; do not run the full graph and then generate a second answer for the same stream.

### Document lifecycle and persistence

- SQLite stores document metadata using DATABASE_URL.
- Uploaded source files are stored under UPLOAD_DIR.
- Qdrant stores chunk vectors and payload metadata.
- BM25 persists its pickle index and JSON metadata under BM25_INDEX_PATH.
- Redis is optional; CacheManager falls back to in-memory TTL caches when Redis is unavailable.
- Deletion must keep SQLite, filesystem, Qdrant, BM25, and relevant caches consistent. Inspect failure behavior in every store before changing deletion or re-indexing logic.

## API Contract

The API prefix defaults to /api/v1.

- GET /api/v1/health
- GET /api/v1/ready
- POST /api/v1/documents/upload
- POST /api/v1/documents/upload-batch
- GET /api/v1/documents?limit=100&offset=0
- GET /api/v1/documents/{document_id}
- DELETE /api/v1/documents/{document_id}
- POST /api/v1/chat
- POST /api/v1/chat/stream (Server-Sent Events)

ChatRequest currently contains question and optional session_id. The current endpoint/service flow uses question only; session_id is not yet used for conversation persistence or isolation. Do not build on an assumed conversation-history feature.

## Configuration and Providers

Use Settings in backend/app/config.py as the canonical list of supported environment settings. Do not introduce a new environment variable without adding it to Settings, documenting its purpose, and providing safe defaults where appropriate.

Important groups:

- Application: APP_NAME, APP_VERSION, DEBUG, LOG_LEVEL, API_PREFIX, SECRET_KEY.
- CORS: CORS_ORIGINS (comma-separated values are parsed).
- LLM: LLM_PROVIDER (openai, groq, local), OPENAI_API_KEY, OPENAI_LLM_MODEL, GROQ_API_KEY, GROQ_MODEL, LOCAL_LLM_MODEL.
- Embeddings: EMBEDDING_PROVIDER (openai, local, huggingface), OPENAI_EMBEDDING_MODEL, EMBEDDING_MODEL, EMBEDDING_DEVICE, EMBEDDING_BATCH_SIZE.
- Reranking: RERANKER_ENABLED, RERANKER_MODEL, RERANKER_DEVICE, RERANKER_BATCH_SIZE, RERANKER_SKIP_THRESHOLD.
- Qdrant: QDRANT_URL or QDRANT_HOST/QDRANT_PORT, QDRANT_COLLECTION, QDRANT_API_KEY.
- Local indexes/storage: BM25_INDEX_PATH, DATABASE_URL, UPLOAD_DIR.
- Ingestion/RAG: ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, MAX_BATCH_SIZE_MB, CHUNK_SIZE, CHUNK_OVERLAP, MAX_RETRIES, TOP_K_HYBRID, TOP_K_RERANK, RRF_K, RELEVANCE_THRESHOLD_HIGH, RELEVANCE_THRESHOLD_LOW.
- Performance/grading: HYBRID_PARALLEL, GRADE_MAX_DOCS_PER_BATCH, GRADE_MAX_CHARS_PER_DOC, GRADE_EMBEDDING_PRE_FILTER, GRADE_EMBEDDING_THRESHOLD, GRADE_FAST_PATH_ENABLED, GRADE_FAST_PATH_THRESHOLD, GRADE_MAX_TOKENS, TRANSFORM_HEURISTIC_FIRST, WARMUP_ON_STARTUP.
- Caching: REDIS_URL, CACHE_ENABLED, CACHE_EMBEDDING_TTL, CACHE_RETRIEVAL_TTL, CACHE_GRADE_TTL, CACHE_ANSWER_TTL.

Provider behavior:
- LLM_PROVIDER defaults to openai. OpenAI and Groq require their respective API keys. The local LLM provider loads a Transformers model.
- EMBEDDING_PROVIDER defaults to openai. Local embedding providers use sentence-transformers.
- RERANKER_ENABLED defaults to true and requires sentence-transformers when enabled.
- QDRANT_URL selects the configured remote/cloud endpoint. Without it, the backend tries QDRANT_HOST/QDRANT_PORT and can fall back to embedded local Qdrant for development.
- Redis is optional; do not make application correctness depend on Redis being available.

The production requirements file does not include sentence-transformers, while reranking is enabled by default. Before changing deployment dependencies or provider defaults, reconcile this mismatch. Do not silently assume production requirements support the default reranker configuration.

## Development Commands

Backend (run from the backend directory):

- Create an environment: python -m venv .venv
- Activate on Windows PowerShell: .\.venv\Scripts\Activate.ps1
- Install development dependencies: python -m pip install -r requirements.txt
- Run API: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
- API docs: /docs and /redoc on the backend host.

Frontend (run from the frontend directory):

- Install locked dependencies: npm ci
- Start Vite: npm run dev
- Type-check and production build: npm run build
- Preview build: npm run preview

The frontend build script runs TypeScript checking before Vite bundling. Keep TypeScript strictness, noUnusedLocals, and noUnusedParameters passing.

## Engineering Rules

1. Read the relevant implementation and all callers before editing. Trace contracts end-to-end; do not make changes based only on README text or file names.
2. Make the smallest coherent change. Preserve established layers and interfaces unless there is a clear reason to change them.
3. Treat Pydantic schemas, FastAPI routes, frontend TypeScript types, and service payloads as one contract. Update all affected sides together.
4. Keep blocking model, embedding, vector-store, and CPU-heavy work off async request handlers where appropriate. Preserve the current thread-offloading pattern unless replacing it with a verified async implementation.
5. Keep ingestion bounded in memory. Preserve chunked upload reads, chunked embedding/upsert behavior, configured file limits, and background indexing semantics.
6. Validate external inputs at the boundary. Keep filename/path safety, extension/MIME checks, size limits, and PDF/DOCX signature validation. Do not trust browser-provided file metadata alone.
7. Keep document metadata and all indexes synchronized. Consider partial failures, retries, duplicate uploads, and cache invalidation before changing ingestion or deletion.
8. Preserve retrieval metadata (document ID/name, chunk ID, page, section, file type) through parsing, indexing, retrieval, and response construction.
9. Do not fabricate citations, document facts, scores, or model metrics. Ground generated answers in retrieved chunks and return an explicit insufficient-evidence response when support is inadequate.
10. Do not log API keys, secrets, full document contents, or unnecessary personal/sensitive data. Never commit .env files, credentials, uploaded documents, databases, or generated indexes.
11. Avoid broad refactors, dependency upgrades, model changes, collection resets, or changes to persisted data formats without a migration/rollback plan.
12. Add or update focused tests for behavior changes. Do not claim tests or load tests passed unless they were actually run; report unverified behavior clearly.

## Verified Limitations and Risks in the Current Code

These are observations from the current implementation, not features to assume are already solved:

- No actual automated backend test cases are present in backend/tests; the visible test files are package initializers only. Add tests when changing business logic.
- No web-search node or web-search provider is wired into the graph. The grader prompt/schema can return needs_web_search metadata, but the graph does not execute an external search fallback.
- Citation schemas and frontend citation rendering exist, but ChatService currently returns an empty citations list; the responder also sets citations to an empty list, and the streaming service does not emit citation events. Do not claim source citations are working end-to-end until this is implemented and tested.
- session_id is accepted by ChatRequest but is not used by the current chat endpoint/service. Chat history and session isolation are not implemented.
- There is no authentication or tenant-level authorization in the current routes. Treat the current document collection as shared application data; never imply private user isolation.
- Document listing returns len(current_page) as total rather than a database-wide count. Be careful when adding pagination or dashboard totals.
- The frontend Dashboard contains hard-coded trend labels; these are presentation values, not measured system metrics.
- The frontend UploadPage sends files sequentially through the single-upload endpoint. The backend batch endpoint is separate and not currently used by the UI.
- Qdrant VectorStore currently deletes and recreates the configured collection when an embedding dimension change is detected. This can remove existing vectors. Never change embedding model/dimensions or trigger collection recreation without explicitly handling data preservation and re-indexing.
- Qdrant search and document deletion catch some store errors and return empty/zero results. Do not treat those return values alone as proof that the underlying operation succeeded.
- BackgroundTasks is process-local. Do not describe it as a durable job queue; process restarts can interrupt pending work.
- Answer/retrieval/grade/embedding caches need deliberate invalidation when documents, embedding models, prompts, or retrieval settings change.

## Testing and Review Checklist

Before finishing a change:

- Identify affected API routes, schemas, services, graph nodes/edges, stores, frontend services/types, and UI consumers.
- Add focused regression tests for the changed behavior. The current test directories are placeholders.
- For backend changes, run the relevant tests and verify imports/startup where feasible.
- For frontend changes, run npm run build.
- For ingestion/retrieval changes, verify both Qdrant and BM25 behavior, metadata preservation, and document deletion consistency.
- For chat/RAG changes, verify answer grounding, insufficient-evidence behavior, retry limits, SSE event format, cancellation/error handling, and cache behavior.
- Review logs and error paths; ensure secrets and document contents are not exposed.
- Summarize exactly what changed, which commands/tests were run, their actual results, and any remaining limitations.