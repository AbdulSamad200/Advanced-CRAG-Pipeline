
import time
from typing import Optional

from google import genai
from google.genai import types as genai_types

from config import EMBEDDING_MODEL, EMBEDDING_DIMENSION

# Module-level client — initialised once by init_gemini()
_client: Optional[genai.Client] = None


def init_gemini(api_key: str) -> None:
    """Create the shared Gemini client. Call once at startup."""
    global _client
    _client = genai.Client(api_key=api_key)
    print(f"✅  Gemini client initialised — model: {EMBEDDING_MODEL}, dims: {EMBEDDING_DIMENSION}")


def _get_client() -> genai.Client:
    if _client is None:
        raise RuntimeError("Gemini client not initialised — call init_gemini() first")
    return _client


def _embed_single(text: str, task_type: str, retries: int = 3) -> Optional[list[float]]:
    """
    Embed a single text string with explicit output_dimensionality.
    task_type:
      "RETRIEVAL_DOCUMENT" — chunks being stored in Qdrant
      "RETRIEVAL_QUERY"    — the user's search question
    """
    client = _get_client()
    for attempt in range(retries):
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=genai_types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBEDDING_DIMENSION,  # pin to 768
                ),
            )
            # response.embeddings is a list of ContentEmbedding objects
            return response.embeddings[0].values
        except Exception as exc:
            wait = 2 ** attempt
            if attempt < retries - 1:
                print(f"⚠️   Embed attempt {attempt + 1} failed: {exc} — retry in {wait}s")
                time.sleep(wait)
            else:
                print(f"❌  Embedding failed after {retries} attempts: {exc}")
                return None


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed every chunk dict.
    Adds a "vector" key ({EMBEDDING_DIMENSION}-dim list) to each dict.
    Skips any chunk whose embedding fails.
    """
    embedded = []
    total = len(chunks)

    for i, chunk in enumerate(chunks, 1):
        vector = _embed_single(chunk["text"], task_type="RETRIEVAL_DOCUMENT")
        if vector is None:
            print(f"⚠️   Chunk {i}/{total} skipped — embedding failed")
            continue
        embedded.append({**chunk, "vector": vector})

        if i % 10 == 0 or i == total:
            print(f"   Embedded {i}/{total} chunks ...")

        time.sleep(0.12)   # ~8 req/s — safe within free-tier quota

    print(f"✅  Embeddings generated: {len(embedded)}/{total} chunks embedded ({EMBEDDING_DIMENSION}-dim)")
    return embedded


def embed_query(query: str) -> Optional[list[float]]:
    """Embed the user query with RETRIEVAL_QUERY task type."""
    vector = _embed_single(query, task_type="RETRIEVAL_QUERY")
    if vector:
        print(f"✅  Query embedded ({len(vector)}-dim vector)")
    return vector