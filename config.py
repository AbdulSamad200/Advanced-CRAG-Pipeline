# file: config.py
# ─────────────────────────────────────────────────────────────
# PURPOSE: Central configuration — env validation + constants.
# All tunable parameters live here. Never scatter magic values.
# ─────────────────────────────────────────────────────────────

import os
import sys

# ── Required API keys & URLs ──────────────────────────────────
REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "TAVILY_API_KEY",
]

# ── File paths ────────────────────────────────────────────────
PDF_DIR         = "pdfs"               # << PUT YOUR PDFs IN THIS FOLDER
HASH_STORE_FILE = ".pdf_hashes.json"   # Auto-generated; tracks ingested PDFs

# ── Qdrant ────────────────────────────────────────────────────
QDRANT_COLLECTION   = "rag_documents"
EMBEDDING_DIMENSION = 768   # Pinned via output_dimensionality in embedder.py

# ── Gemini models ─────────────────────────────────────────────
EMBEDDING_MODEL  = "gemini-embedding-001"
GENERATION_MODEL = "gemini-2.5-flash"

# ── Chunking ──────────────────────────────────────────────────
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

# ── Retrieval ─────────────────────────────────────────────────
TOP_K_RESULTS          = 8
WEB_SEARCH_MAX_RESULTS = 5
MAX_CONTEXT_CHUNKS     = 10

# ── Reranking ─────────────────────────────────────────────────
RERANK_MODEL   = "BAAI/bge-reranker-base"
TOP_K_RETRIEVE = 20   # How many to pull from Qdrant initially
TOP_K_RERANK   = 5    # How many to keep after reranking
# ── CRAG Confidence Thresholds ────────────────────────────────
# These drive the three-zone decision in retrieval_evaluator.py.
#
# How to tune these values:
#   Run your system on 10-20 sample queries and look at the
#   logged "Top cosine score" values:
#     - Queries where PDF clearly answers → scores should be >= HIGH
#     - Queries where PDF has nothing     → scores should be < LOW
#   Adjust thresholds so the zones match your observations.
#
#   gemini-embedding-001 cosine scores typically range 0.6–0.95
#   for a relevant match against a well-chunked corpus.
#
CRAG_HIGH_THRESHOLD = 0.75
# score >= 0.75 → CORRECT   → use PDF only, no web search

CRAG_LOW_THRESHOLD = 0.50
# score >= 0.50 → AMBIGUOUS → LLM judge decides (PDF / PDF+web)
# score <  0.50 → INCORRECT → discard PDF, use web search only


def validate_env() -> dict:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print("\n❌  Missing required environment variables:")
        for var in missing:
            print(f"    - {var}")
        print("\nFix: set each variable in your .env file:\n")
        for var in missing:
            print(f"    {var}=your_value_here")
        print()
        sys.exit(1)

    cfg = {v: os.environ[v] for v in REQUIRED_ENV_VARS}
    print("✅  Environment validated — all required variables present")
    return cfg