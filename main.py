# file: main.py
# ─────────────────────────────────────────────────────────────
# ENTRY POINT — run with:  python main.py
#
# Change ONLY user_query below to ask a different question.
# ─────────────────────────────────────────────────────────────

# ╔══════════════════════════════════════════════════════════╗
# ║           CHANGE THIS LINE TO ASK A NEW QUESTION        ║
user_query = "Tell me about META AI ?"
# ╚══════════════════════════════════════════════════════════╝

import sys
from pathlib import Path

# ── Load .env file ────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"📂  Loaded environment from {env_path}")
    else:
        print(f"ℹ️   No .env file found at {env_path} — using shell env vars")
except ImportError:
    print("⚠️   python-dotenv not installed — using shell environment only")

# ── Project imports ───────────────────────────────────────────
from config import validate_env, MAX_CONTEXT_CHUNKS, QDRANT_COLLECTION, TOP_K_RETRIEVE
from pdf_loader import (
    get_pdf_paths,
    load_hash_store,
    detect_changed_pdfs,
    process_new_pdfs,
    update_hash_store,
)
from embedder          import init_gemini, embed_chunks, embed_query
from vector_store      import get_client, ensure_collection, upsert_chunks, search_vectors
from reranker          import rerank_results
from retrieval_evaluator import evaluate_retrieval, RetrievalConfidence
from web_search        import run_web_search
from generator         import generate_answer


def _banner(label: str = "") -> None:
    w = 62
    if label:
        pad = max(0, (w - len(label) - 2) // 2)
        print(f"\n{'─' * pad} {label} {'─' * pad}")
    else:
        print(f"\n{'─' * w}")


def main() -> None:
    _banner("RAG MVP  ·  CRAG Edition")
    print(f"🔍  Query: {user_query}\n")

    # ── Stage 1: Environment ──────────────────────────────────
    _banner("1 · Environment")
    cfg = validate_env()

    # ── Stage 2: Clients ──────────────────────────────────────
    _banner("2 · Clients")
    init_gemini(cfg["GEMINI_API_KEY"])
    qdrant = get_client(cfg["QDRANT_URL"], cfg["QDRANT_API_KEY"])
    ensure_collection(qdrant)

    # ── Stage 3: Incremental PDF ingestion ───────────────────
    _banner("3 · PDF Ingestion")
    pdf_paths  = get_pdf_paths()
    hash_store = load_hash_store()

    if pdf_paths:
        new_or_changed, unchanged = detect_changed_pdfs(pdf_paths, hash_store)
        if new_or_changed:
            print(f"\n📄  Processing {len(new_or_changed)} PDF(s)...")
            chunks = process_new_pdfs(new_or_changed)
            if chunks:
                _banner("3a · Embedding")
                embedded = embed_chunks(chunks)
                _banner("3b · Storing vectors")
                upsert_chunks(qdrant, embedded)
                update_hash_store(hash_store, new_or_changed)
                print("✅  Hash store updated")
            else:
                print("⚠️   No text extracted — check if PDFs are scanned images")
        else:
            print("✅  All PDFs unchanged — reusing existing Qdrant vectors")
    else:
        print("✅  No PDFs found — will rely entirely on web search")

    # ── Stage 4: Embed query ──────────────────────────────────
    _banner("4 · Query Embedding")
    query_vector = embed_query(user_query)
    if query_vector is None:
        print("❌  Cannot embed query — aborting")
        sys.exit(1)

    # ── Stage 5: Vector retrieval ─────────────────────────────
    _banner("5 · Vector Retrieval")
    collection_size = qdrant.count(collection_name=QDRANT_COLLECTION).count
    if collection_size == 0:
        print("⚠️   Qdrant collection is empty — PDF retrieval unavailable")
        pdf_results = []
    else:
        # 1. Retrieve a larger set of candidates (e.g. 20)
        initial_results = search_vectors(qdrant, query_vector, limit=TOP_K_RETRIEVE)
        
        # 2. Rerank PDF results to identify the Top 5
        _banner("5a · Primary PDF Reranking")
        pdf_results = rerank_results(user_query, initial_results)

    # ── Stage 6: CRAG evaluation ──────────────────────────────
    _banner("6 · CRAG Retrieval Evaluation")
    # 3. Evaluate based on Vector Scores of the top results
    evaluation = evaluate_retrieval(user_query, pdf_results)
    print(f"\n    Decision : {evaluation.confidence.value.upper()}")
    print(f"    Use PDF  : {evaluation.use_pdf}")
    print(f"    Use Web  : {evaluation.use_web}")
    print(f"    Reason   : {evaluation.reason}")

    # ── Stage 7: Web search & Source Fusion ───────────────────
    _banner("7 · Web Search & Source Fusion")
    combined: list[dict] = []

    if evaluation.use_pdf:
        combined.extend(pdf_results)
        print(f"✅  PDF context included ({len(pdf_results)} chunks)")
    else:
        print("⏭️   PDF context discarded by CRAG evaluator")

    if evaluation.use_web:
        print("🌐  Running web search...")
        web_results = run_web_search(user_query, cfg["TAVILY_API_KEY"])
        combined.extend(web_results)
        
        # 4. Final Rerank (Source Fusion)
        if combined:
            _banner("7a · Final Source Fusion Reranking")
            final_context = rerank_results(user_query, combined, top_n=MAX_CONTEXT_CHUNKS)
        else:
            final_context = []
    else:
        print("⏭️   Web search skipped — PDF context is sufficient")
        final_context = combined[:MAX_CONTEXT_CHUNKS]

    # ── Stage 8: Context Assembly ─────────────────────────────
    _banner("8 · Context Assembly")
    if not final_context:
        print("⚠️   No context from any source — will respond with fallback")
    else:
        print(f"✅  {len(final_context)} chunks assembled for generation")
        for i, r in enumerate(final_context, 1):
            src   = r.get("source", "unknown")
            v_score = r.get("vector_score", 0.0)
            r_score = r.get("rerank_score", 0.0)
            print(f"    [{i}] vector={v_score:.4f} rerank={r_score:.4f}  {src[:65]}")

    # ── Stage 9: Generate answer ──────────────────────────────
    _banner("9 · Answer Generation")
    answer = generate_answer(user_query, final_context)

    # ── Final output ──────────────────────────────────────────
    _banner("ANSWER")
    print(f"\n{answer}\n")
    _banner()


if __name__ == "__main__":
    main()





















