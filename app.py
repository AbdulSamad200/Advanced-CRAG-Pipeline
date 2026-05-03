# file: app.py
# ─────────────────────────────────────────────────────────────
# FastAPI backend — wraps the existing RAG pipeline.
# Exposes:
#   POST /api/chat        — SSE stream (logs + answer)
#   POST /api/upload-pdf  — Ingest a PDF into Qdrant
#   GET  /api/pdfs        — List uploaded PDFs
#   GET  /api/health      — Liveness probe
#
# Log capture strategy:
#   A ContextVar holds a per-request asyncio.Queue.
#   builtins.print is monkey-patched to also push each line
#   onto that queue via call_soon_threadsafe(), so every print()
#   call inside the sync RAG modules appears in the SSE stream.
# ─────────────────────────────────────────────────────────────
# file: app.py
# file: app.py

from __future__ import annotations

import asyncio
import builtins
import json
from contextvars import ContextVar
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Load .env ─────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("📂  .env loaded")
except ImportError:
    pass

# ════════════════════════════════════════════════════════════
# LOG CAPTURE — monkey-patch print + ContextVar queue
# ════════════════════════════════════════════════════════════

_log_queue: ContextVar[asyncio.Queue | None] = ContextVar("_log_queue", default=None)
_event_loop: asyncio.AbstractEventLoop | None = None
_original_print = builtins.print


def _patched_print(*args, **kwargs):
    _original_print(*args, **kwargs)
    q = _log_queue.get()
    
    text = " ".join(str(a) for a in args)
    if not text.strip():
        return

    # Diagnostic: if we have a queue, we should be able to send to it
    if q is not None and _event_loop is not None:
        try:
            _event_loop.call_soon_threadsafe(q.put_nowait, ("log", text.strip()))
        except Exception as e:
            _original_print(f"❌  Failed to push log to queue: {e}")
    else:
        # Fallback diagnostic to see if prints are even hitting this function
        # in the thread without a queue
        pass


builtins.print = _patched_print

# ── RAG imports ───────────────────────────────────────────────
try:
    from config import MAX_CONTEXT_CHUNKS, PDF_DIR, QDRANT_COLLECTION, TOP_K_RETRIEVE, validate_env
    from embedder import embed_chunks, embed_query, init_gemini
    from generator import generate_answer, generate_answer_stream
    from pdf_loader import (
        chunk_text, detect_changed_pdfs, extract_text_from_pdf,
        get_pdf_paths, load_hash_store, process_new_pdfs, update_hash_store,
    )
    from retrieval_evaluator import evaluate_retrieval
    from reranker import rerank_results
    from vector_store import ensure_collection, get_client, search_vectors, upsert_chunks
    from web_search import run_web_search
    RAG_IMPORT_OK = True
except ImportError as _e:
    RAG_IMPORT_OK = False
    _IMPORT_ERROR = str(_e)

_rag_cfg: dict | None = None
_qdrant = None
_init_error: str | None = None


def _initialize_rag() -> None:
    global _rag_cfg, _qdrant, _init_error
    if not RAG_IMPORT_OK:
        _init_error = f"RAG imports failed: {_IMPORT_ERROR}"
        return
    try:
        _rag_cfg = validate_env()
        init_gemini(_rag_cfg["GEMINI_API_KEY"])
        _qdrant = get_client(_rag_cfg["QDRANT_URL"], _rag_cfg["QDRANT_API_KEY"])
        ensure_collection(_qdrant)
        _original_print("✅  RAG pipeline initialised and ready")
    except SystemExit:
        _init_error = "Missing required environment variables — check your .env file"
    except Exception as exc:
        _init_error = str(exc)


# ════════════════════════════════════════════════════════════
# FastAPI app
# ════════════════════════════════════════════════════════════
app = FastAPI(title="RAG MVP", version="2.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    global _event_loop
    _event_loop = asyncio.get_running_loop()
    await _event_loop.run_in_executor(None, _initialize_rag)


class ChatRequest(BaseModel):
    query: str
    session_id: str = ""


# ════════════════════════════════════════════════════════════
# RAG PIPELINE — sync, runs in ThreadPoolExecutor
# ════════════════════════════════════════════════════════════

def _run_rag_pipeline_until_generation(query: str) -> list[dict]:
    """
    Stages 3–7. Every print() inside is intercepted by _patched_print
    and pushed onto the per-request log_queue via call_soon_threadsafe().
    """
    print("─" * 52)
    print("📂  Stage 3 · PDF Ingestion")
    pdf_paths  = get_pdf_paths()
    hash_store = load_hash_store()

    if pdf_paths:
        new_or_changed, _ = detect_changed_pdfs(pdf_paths, hash_store)
        if new_or_changed:
            print(f"📄  {len(new_or_changed)} new/changed PDF(s) — embedding now...")
            chunks = process_new_pdfs(new_or_changed)
            if chunks:
                print("─" * 52)
                print("🔢  Stage 3a · Embedding chunks")
                embedded = embed_chunks(chunks)
                print("─" * 52)
                print("💾  Stage 3b · Storing vectors in Qdrant")
                upsert_chunks(_qdrant, embedded)
                update_hash_store(hash_store, new_or_changed)
                print("✅  Hash store updated")
        else:
            print("✅  All PDFs unchanged — reusing existing Qdrant vectors")
    else:
        print("✅  No PDFs found — web search only mode")

    print("─" * 52)
    print("🔢  Stage 4 · Query Embedding")
    query_vector = embed_query(query)
    if query_vector is None:
        raise RuntimeError("Failed to embed query — check GEMINI_API_KEY")

    print("─" * 52)
    print("🗄️  Stage 5 · Vector Retrieval")
    collection_size = _qdrant.count(collection_name=QDRANT_COLLECTION).count
    if collection_size == 0:
        print("⚠️   Qdrant collection is empty — switching to web-only mode")
        pdf_results: list[dict] = []
    else:
        # 1. Retrieve a larger set of candidates (e.g. 20)
        initial_results = search_vectors(_qdrant, query_vector, limit=TOP_K_RETRIEVE)
        
        # 2. Rerank PDF results to identify the Top 5
        print("🔢  Stage 5a · Primary PDF Reranking")
        pdf_results = rerank_results(query, initial_results)

    print("─" * 52)
    print("🧠  Stage 6 · CRAG Retrieval Evaluation")
    # 3. Evaluate based on the Vector Scores of the top reranked results
    evaluation = evaluate_retrieval(query, pdf_results)
    print(f"    ▶ Decision  : {evaluation.confidence.value.upper()}")
    print(f"    ▶ Use PDF   : {evaluation.use_pdf}")
    print(f"    ▶ Use Web   : {evaluation.use_web}")
    print(f"    ▶ Reason    : {evaluation.reason}")

    print("─" * 52)
    print("📚  Stage 7 · Context Assembly & Source Fusion")
    combined: list[dict] = []

    if evaluation.use_pdf:
        combined.extend(pdf_results)
        print(f"✅  PDF context included ({len(pdf_results)} chunks)")
    else:
        print("⏭️   PDF context discarded by CRAG evaluator")

    if evaluation.use_web:
        print("🌐  Running Tavily web search...")
        web_results = run_web_search(query, _rag_cfg["TAVILY_API_KEY"])
        combined.extend(web_results)
        print(f"✅  Web search returned {len(web_results)} results")
        
        # 4. Final Rerank (Source Fusion)
        # If we have mixed sources, rerank them ALL to find the absolute best Top 10
        if combined:
            print("🔢  Stage 7a · Final Source Fusion Reranking")
            final_context = rerank_results(query, combined, top_n=MAX_CONTEXT_CHUNKS)
        else:
            final_context = []
    else:
        print("⏭️   Web search skipped — PDF context is sufficient")
        # PDF results are already sorted by rerank_score from Stage 5a
        final_context = combined[:MAX_CONTEXT_CHUNKS]

    print(f"✅  {len(final_context)} chunks assembled for generation:")
    for i, r in enumerate(final_context, 1):
        v_score = r.get("vector_score", 0.0)
        r_score = r.get("rerank_score", 0.0)
        print(f"    [{i}] vector={v_score:.4f} rerank={r_score:.4f}  {r.get('source', 'unknown')[:65]}")

    print("─" * 52)
    print("⚡  Stage 8 · Answer Generation (streaming...)")
    return final_context


def _sse(d: dict) -> str:
    return f"data: {json.dumps(d)}\n\n"


# ════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status":    "ok" if _rag_cfg else "degraded",
        "rag_ready": _rag_cfg is not None,
        "error":     _init_error,
    }


@app.post("/api/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    SSE events:
      {"type":"log",   "message":"..."}   pipeline step
      {"type":"chunk", "content":"..."}   streaming Gemini token
      {"type":"error", "message":"..."}   error
      {"type":"done"}                     stream finished
    """
    if not request.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    if _init_error:
        raise HTTPException(503, _init_error)
    if not _qdrant or not _rag_cfg:
        raise HTTPException(503, "RAG pipeline not ready")

    async def event_stream() -> AsyncGenerator[str, None]:
        log_queue: asyncio.Queue = asyncio.Queue()
        token = _log_queue.set(log_queue)   # copied into executor threads automatically
        loop  = asyncio.get_running_loop()

        # Keep-alive comment so the browser knows the connection is open
        yield ": connected\n\n"
        
        # Immediate confirmation that the stream is alive
        yield _sse({"type": "log", "message": "🚀 RAG Pipeline connected and starting..."})
        yield _sse({"type": "log", "message": f"🔍 Query: {request.query}"})

        # ── Phase 1: stages 3-7 in a thread ──────────────────────
        # to_thread (Python 3.9+) automatically propagates contextvars
        # correctly compared to manual run_in_executor in many cases.
        pipeline_task = asyncio.create_task(
            asyncio.to_thread(_run_rag_pipeline_until_generation, request.query)
        )

        while not pipeline_task.done():
            try:
                # High frequency polling
                kind, payload = await asyncio.wait_for(
                    log_queue.get(), timeout=0.05
                )
                if kind == "log":
                    yield _sse({"type": "log", "message": payload})
            except asyncio.TimeoutError:
                pass

        # Final flush
        await asyncio.sleep(0.1)
        while not log_queue.empty():
            try:
                kind, payload = log_queue.get_nowait()
                if kind == "log":
                    yield _sse({"type": "log", "message": payload})
            except asyncio.QueueEmpty:
                break

        # ── Get pipeline result ───────────────────────────────────
        try:
            final_context = await pipeline_task
        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})
            yield _sse({"type": "done"})
            _log_queue.reset(token)
            return

        # ── Phase 2: stream Gemini tokens ────────────────────────
        gen_queue: asyncio.Queue = asyncio.Queue()

        def _run_generation():
            try:
                for text_chunk in generate_answer_stream(request.query, final_context):
                    loop.call_soon_threadsafe(gen_queue.put_nowait, ("chunk", text_chunk))
            except Exception as exc:
                loop.call_soon_threadsafe(gen_queue.put_nowait, ("error", str(exc)))
            finally:
                loop.call_soon_threadsafe(gen_queue.put_nowait, ("done", None))

        gen_future = loop.run_in_executor(None, _run_generation)

        while True:
            # Also drain any late log messages during generation
            while not log_queue.empty():
                try:
                    kind, payload = log_queue.get_nowait()
                    if kind == "log":
                        yield _sse({"type": "log", "message": payload})
                except asyncio.QueueEmpty:
                    break

            try:
                kind, payload = await asyncio.wait_for(gen_queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                yield _sse({"type": "error", "message": "Generation timed out"})
                break

            if kind == "chunk":
                yield _sse({"type": "chunk", "content": payload})
            elif kind == "error":
                yield _sse({"type": "error", "message": payload})
                break
            elif kind == "done":
                yield _sse({"type": "done"})
                break

        _log_queue.reset(token)
        await gen_future

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    if not _qdrant or not _rag_cfg:
        raise HTTPException(503, "RAG pipeline not ready")

    pdf_dir = Path(PDF_DIR)
    pdf_dir.mkdir(exist_ok=True)
    dest = pdf_dir / file.filename
    dest.write_bytes(await file.read())

    def _process():
        text = extract_text_from_pdf(str(dest))
        if not text:
            return 0
        chunks   = chunk_text(text, source=str(dest))
        embedded = embed_chunks(chunks)
        upsert_chunks(_qdrant, embedded)
        update_hash_store(load_hash_store(), [str(dest)])
        return len(chunks)

    loop        = asyncio.get_event_loop()
    chunk_count = await loop.run_in_executor(None, _process)

    return {
        "status":        "success",
        "filename":      file.filename,
        "chunks_stored": chunk_count,
        "message":       f"PDF ingested — {chunk_count} chunks embedded into Qdrant",
    }


@app.get("/api/pdfs")
async def list_pdfs():
    pdf_dir = Path(PDF_DIR)
    if not pdf_dir.exists():
        return {"pdfs": []}
    return {
        "pdfs": [
            {"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1)}
            for p in sorted(pdf_dir.glob("*.pdf"))
        ]
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)