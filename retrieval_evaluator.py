# file: retrieval_evaluator.py
# ─────────────────────────────────────────────────────────────
# PURPOSE: CRAG-style retrieval quality evaluation.
#
# Implements the three-zone confidence model from Corrective RAG:
#
#   CORRECT   (top score >= HIGH_THRESHOLD)
#     → PDF context is good. Use it. Skip web search entirely.
#
#   AMBIGUOUS (top score >= LOW_THRESHOLD but < HIGH_THRESHOLD)
#     → PDF context is partial. Run LLM judge to confirm.
#       If judge agrees it's relevant → PDF only.
#       If judge is unsure             → PDF + web search.
#
#   INCORRECT (top score < LOW_THRESHOLD, or no results)
#     → PDF context is useless for this query.
#       Discard PDF results. Use web search only.
#
# The LLM judge is only invoked in the AMBIGUOUS zone —
# keeping it cheap for the common cases (CORRECT / INCORRECT).
#
# Key difference from the old keyword-scan approach:
#   Decision is based on HOW WELL the retrieved chunks match
#   the query, NOT on which words appear in the query.
#   A topic absent from the PDFs will always score low → web search.
#   A topic present in the PDFs will score high → PDF used directly.
# ─────────────────────────────────────────────────────────────

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from google import genai
from google.genai import types as genai_types

from config import (
    CRAG_HIGH_THRESHOLD,
    CRAG_LOW_THRESHOLD,
    GENERATION_MODEL,
)


# ── Confidence zones ──────────────────────────────────────────

class RetrievalConfidence(Enum):
    CORRECT   = "correct"    # PDF context is sufficient
    AMBIGUOUS = "ambiguous"  # PDF context is partial — may need web
    INCORRECT = "incorrect"  # PDF context is useless — use web only


@dataclass
class EvaluationResult:
    confidence: RetrievalConfidence
    top_score: float
    use_pdf: bool
    use_web: bool
    reason: str


# ── Score-based zone classification ──────────────────────────

def _classify_by_score(pdf_results: list[dict]) -> tuple[RetrievalConfidence, float]:
    """
    Assign a confidence zone from vector similarity scores alone.
    We look for 'vector_score' specifically.
    """
    if not pdf_results:
        return RetrievalConfidence.INCORRECT, 0.0

    # Look for vector_score, fallback to score if not found
    top_score = max(r.get("vector_score", r.get("score", 0.0)) for r in pdf_results)

    if top_score >= CRAG_HIGH_THRESHOLD:
        return RetrievalConfidence.CORRECT, top_score
    elif top_score >= CRAG_LOW_THRESHOLD:
        return RetrievalConfidence.AMBIGUOUS, top_score
    else:
        return RetrievalConfidence.INCORRECT, top_score


# ── LLM relevance judge (AMBIGUOUS zone only) ─────────────────

def _llm_judge(query: str, pdf_results: list[dict], api_key: str | None = None) -> float:
    """
    Ask Gemini: on a scale 0–10, how relevant are these passages to the query?
    Returns a normalised float 0.0–1.0.
    Only called when score-based classification lands in AMBIGUOUS.
    """
    from embedder import _client as gemini_client

    if gemini_client is None:
        # Fallback: treat as ambiguous without confirmation
        return 0.5

    # Show the top 3 chunks to the judge (enough context, low token cost)
    top_chunks = pdf_results[:3]
    passages = "\n\n".join(
        f"[{i+1}] {r['text'][:400]}" for i, r in enumerate(top_chunks)
    )

    judge_prompt = f"""You are a relevance evaluator for a retrieval system.

QUESTION:
{query}

RETRIEVED PASSAGES:
{passages}

TASK:
Score how relevant these passages are to answering the question.

Respond with ONLY a single integer from 0 to 10, where:
  0  = completely irrelevant, passages are about a different topic
  5  = partially relevant, touches the topic but misses the core
  10 = highly relevant, passages directly answer the question

Output ONLY the number. No explanation."""

    try:
        response = gemini_client.models.generate_content(
            model=GENERATION_MODEL,
            contents=judge_prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=5,
            ),
        )
        raw = response.text.strip().split()[0]
        score_int = int("".join(c for c in raw if c.isdigit()))
        score_int = max(0, min(10, score_int))
        return score_int / 10.0
    except Exception as exc:
        print(f"⚠️   LLM judge call failed: {exc} — defaulting to 0.5")
        return 0.5


# ── Public evaluation entry point ─────────────────────────────

def evaluate_retrieval(query: str, pdf_results: list[dict]) -> EvaluationResult:
    """
    Main entry point. Returns an EvaluationResult based on VECTOR similarity.
    Reranker scores are used for sorting, but VECTOR scores are for safety.
    """
    zone, top_vector_score = _classify_by_score(pdf_results)
    
    # Check if these results came from the Reranker
    is_reranked = any(r.get("is_reranked") for r in pdf_results)

    print(f"\n📊  Retrieval evaluation (Vector-Based):")
    print(f"    Top Vector Score : {top_vector_score:.4f}")
    if is_reranked:
        print(f"    Top Rerank Score : {pdf_results[0].get('rerank_score', 'N/A')}")
    print(f"    Thresholds       : HIGH={CRAG_HIGH_THRESHOLD}  LOW={CRAG_LOW_THRESHOLD}")
    print(f"    Evaluation Zone  : {zone.value.upper()}")

    # ── CORRECT: fast path ────────────────────────────────────
    if zone == RetrievalConfidence.CORRECT:
        print(f"✅  CORRECT — High certainty vector match. Web search skipped.")
        return EvaluationResult(
            confidence=RetrievalConfidence.CORRECT,
            top_score=top_vector_score,
            use_pdf=True,
            use_web=False,
            reason=f"Top vector score {top_vector_score:.4f} >= HIGH threshold",
        )

    # ── INCORRECT: fast path ──────────────────────────────────
    if zone == RetrievalConfidence.INCORRECT:
        print(f"✅  INCORRECT — Weak vector match. Web search activated.")
        return EvaluationResult(
            confidence=RetrievalConfidence.INCORRECT,
            top_score=top_vector_score,
            use_pdf=False,
            use_web=True,
            reason=f"Top vector score {top_vector_score:.4f} < LOW threshold",
        )

    # ── AMBIGUOUS / VERIFICATION: force LLM judge ────────────
    print(f"    Zone requires verification — invoking LLM relevance judge...")
    judge_score = _llm_judge(query, pdf_results)
    print(f"    LLM judge score  : {judge_score:.2f}/1.0")

    if judge_score >= 0.6:
        print(f"✅  AMBIGUOUS → CORRECT (judge confirmed relevance).")
        return EvaluationResult(
            confidence=RetrievalConfidence.AMBIGUOUS,
            top_score=top_vector_score,
            use_pdf=True,
            use_web=False,
            reason=f"Vector score {top_vector_score:.4f} ambiguous; LLM judge={judge_score:.2f} confirmed relevance",
        )
    else:
        print(f"✅  AMBIGUOUS → needs web supplement.")
        return EvaluationResult(
            confidence=RetrievalConfidence.AMBIGUOUS,
            top_score=top_vector_score,
            use_pdf=True,
            use_web=True,
            reason=f"Vector score {top_vector_score:.4f} ambiguous; LLM judge={judge_score:.2f} suggested supplement",
        )