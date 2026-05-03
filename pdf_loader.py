# file: pdf_loader.py
# ─────────────────────────────────────────────────────────────
# PURPOSE: Everything related to PDFs.
#   1. Detect which PDFs are new or changed  (SHA-256 hashing)
#   2. Extract plain text from PDFs           (PyMuPDF)
#   3. Split text into overlapping chunks     (sliding window)
# ─────────────────────────────────────────────────────────────

import os
import re
import hashlib
import json
from pathlib import Path
from typing import Optional

import pymupdf  # PyMuPDF — fastest pure-Python PDF extractor

from config import PDF_DIR, HASH_STORE_FILE, CHUNK_SIZE, CHUNK_OVERLAP


# ── Hash store (persists between runs) ───────────────────────

def load_hash_store() -> dict:
    """Load the JSON file that maps pdf_path -> {hash, chunk_count}."""
    if os.path.exists(HASH_STORE_FILE):
        with open(HASH_STORE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_hash_store(store: dict) -> None:
    with open(HASH_STORE_FILE, "w") as f:
        json.dump(store, f, indent=2)


def _hash_file(path: str) -> str:
    """SHA-256 hash of a file.  Changes if bytes change."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# ── PDF discovery ─────────────────────────────────────────────

def get_pdf_paths() -> list[str]:
    """
    Return sorted list of .pdf file paths inside PDF_DIR.
    Creates the folder if it doesn't exist yet.
    """
    pdf_dir = Path(PDF_DIR)
    if not pdf_dir.exists():
        pdf_dir.mkdir(parents=True)
        print(f"📁  Created PDF directory: {PDF_DIR}/  ← place your PDFs here")
    paths = sorted(pdf_dir.glob("*.pdf"))
    if not paths:
        print(f"⚠️   No PDFs found in {PDF_DIR}/  (web search only mode)")
    return [str(p) for p in paths]


# ── Change detection ──────────────────────────────────────────

def detect_changed_pdfs(
    pdf_paths: list[str], hash_store: dict
) -> tuple[list[str], list[str]]:
    """
    Compare current file hashes against stored hashes.
    Returns (new_or_changed, unchanged).
    """
    new_or_changed, unchanged = [], []
    for path in pdf_paths:
        current_hash = _hash_file(path)
        if hash_store.get(path, {}).get("hash") != current_hash:
            new_or_changed.append(path)
        else:
            unchanged.append(path)

    if new_or_changed:
        print(f"✅  {len(new_or_changed)} new/changed PDF(s) detected:")
        for p in new_or_changed:
            print(f"    + {p}")
    if unchanged:
        print(f"✅  {len(unchanged)} unchanged PDF(s) — vectors will be reused:")
        for p in unchanged:
            print(f"    = {p}")

    return new_or_changed, unchanged


def update_hash_store(hash_store: dict, pdf_paths: list[str]) -> dict:
    """Record current hashes for successfully ingested PDFs."""
    for path in pdf_paths:
        hash_store[path] = {"hash": _hash_file(path)}
    save_hash_store(hash_store)
    return hash_store


# ── Text extraction ───────────────────────────────────────────

def extract_text_from_pdf(path: str) -> Optional[str]:
    """
    Extract all text from a PDF using PyMuPDF.
    Returns None if the PDF has no extractable text (e.g. scanned image).
    """
    doc = pymupdf.open(path)
    pages_text = []
    for page in doc:
        text = page.get_text("text")
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            pages_text.append(text)
    doc.close()

    if not pages_text:
        print(f"⚠️   No extractable text in {path} (scanned/image PDF?)")
        return None

    full_text = " ".join(pages_text)
    print(f"✅  Text extracted: {path}  ({len(full_text):,} chars / {len(pages_text)} pages)")
    return full_text


# ── Chunking ──────────────────────────────────────────────────

def chunk_text(text: str, source: str) -> list[dict]:
    """
    Sliding-window character chunker.
    Each chunk carries metadata: source path + chunk index.
    """
    chunks = []
    start = 0
    index = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + CHUNK_SIZE, text_len)
        snippet = text[start:end].strip()
        if snippet:
            chunks.append({
                "text": snippet,
                "source": source,
                "chunk_index": index,
            })
            index += 1
        start += CHUNK_SIZE - CHUNK_OVERLAP   # slide forward with overlap

    print(f"✅  Text chunked: {len(chunks)} chunks  (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    return chunks


# ── High-level helper ─────────────────────────────────────────

def process_new_pdfs(pdf_paths: list[str]) -> list[dict]:
    """Extract text and chunk all PDFs in the given list."""
    all_chunks = []
    for path in pdf_paths:
        text = extract_text_from_pdf(path)
        if text:
            chunks = chunk_text(text, source=path)
            all_chunks.extend(chunks)
    return all_chunks