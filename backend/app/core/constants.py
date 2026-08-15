"""Application constants."""

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/x-markdown": "md",
}

SUPPORTED_EXTENSIONS = {"pdf", "docx", "txt", "md"}

MAGIC_BYTES = {
    b"%PDF": "pdf",
    b"PK\x03\x04": "docx",  # ZIP header (DOCX is a ZIP)
}

DEFAULT_SYSTEM_PROMPT = """You are a company document assistant. Your sole purpose is to answer questions based strictly on the provided company documents. You must NEVER use outside knowledge, general information, or hallucinated facts. If the provided context does not contain sufficient information to answer the question, clearly state that the answer cannot be determined from the uploaded documents. Every factual claim must be supported by a citation in the format [Source: DocumentName, Page X]."""

MAX_RETRIES_DEFAULT = 2
TOP_K_HYBRID_DEFAULT = 50
TOP_K_RERANK_DEFAULT = 10

# ---------------------------------------------------------------------------
# GRADING CONSTANTS (NEW — Production 3-Tier Grading)
# ---------------------------------------------------------------------------
GRADE_MAX_DOCS_DEFAULT = 8
GRADE_MAX_CHARS_DEFAULT = 400
GRADE_EMBEDDING_THRESHOLD_DEFAULT = 0.20
GRADE_FAST_PATH_THRESHOLD_DEFAULT = 0.90