# file: generator.py

from typing import Generator
from google import genai
from google.genai import types as genai_types

from config import GENERATION_MODEL

_SYSTEM_PROMPT = """You are an expert research assistant with deep analytical ability.

Your job is to give thorough, well-structured answers using the context passages provided.

Rules:
1. Answer using the provided context as your primary source.
2. If the context is insufficient, clearly say so and supplement with your own knowledge — but label it: (General Knowledge).
3. Give DETAILED, complete answers. Never cut off mid-sentence. Never give one-liners.
4. Structure your response clearly:
   - Use bullet points or numbered lists where appropriate
   - Use headings (##) for multi-part answers
   - Use **bold** for key terms or important points
5. Always cite your sources at the end in a "## Sources" section like:
   - [1] filename.pdf — brief description of what it contributed
   - [2] https://example.com — brief description
6. If multiple sources contributed, cite all of them.
7. Never fabricate facts or statistics.
8. Minimum response length: explain the topic fully. Do not truncate.
"""


def _get_client() -> genai.Client:
    from embedder import _client
    if _client is None:
        raise RuntimeError("Gemini client not initialised — call init_gemini() first")
    return _client


def _build_context_block(results: list[dict]) -> str:
    if not results:
        return "No context available."
    sections = []
    for i, r in enumerate(results, 1):
        source = r.get("source", "unknown")
        score  = r.get("score", 0.0)
        sections.append(
            f"[{i}] Source: {source}  (relevance score: {score:.4f})\n\n{r['text']}"
        )
    return "\n\n---\n\n".join(sections)


def generate_answer_stream(query: str, context_results: list[dict]) -> Generator[str, None, None]:
    """
    Stream the answer token-by-token using Gemini's streaming API.
    Yields text chunks as they arrive.
    """
    context_block = _build_context_block(context_results)

    prompt = (
        f"CONTEXT PASSAGES:\n\n{context_block}\n\n"
        f"{'─' * 60}\n\n"
        f"QUESTION:\n{query}\n\n"
        f"{'─' * 60}\n\n"
        f"Provide a thorough, well-structured answer. "
        f"Cite all sources used at the end under a '## Sources' heading.\n\n"
        f"ANSWER:"
    )

    client = _get_client()

    # generate_content_stream yields chunks as they are produced by the model
    response_stream = client.models.generate_content_stream(
        model=GENERATION_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=8192,
        ),
    )

    for chunk in response_stream:
        if chunk.text:
            yield chunk.text

    print(f"✅  Streaming answer complete ({GENERATION_MODEL})")


def generate_answer(query: str, context_results: list[dict]) -> str:
    """Non-streaming version — kept for terminal main.py compatibility."""
    return "".join(generate_answer_stream(query, context_results))