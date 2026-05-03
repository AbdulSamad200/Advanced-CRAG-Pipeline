# file: reranker.py
# ─────────────────────────────────────────────────────────────
# PURPOSE: Reranking stage using FastEmbed.
#
# Takes Top-N results from Qdrant and uses a Cross-Encoder
# (BAAI/bge-reranker-base) to re-score them against the query.
# ─────────────────────────────────────────────────────────────

import math
from typing import Optional
from fastembed.rerank.cross_encoder import TextCrossEncoder
from config import RERANK_MODEL, TOP_K_RERANK

# Global instance for lazy loading
_reranker: Optional[TextCrossEncoder] = None

def get_reranker() -> TextCrossEncoder:
    """Initialise and return the singleton reranker instance."""
    global _reranker
    if _reranker is None:
        print(f"🔄  Initialising Reranker: {RERANK_MODEL} ...")
        _reranker = TextCrossEncoder(model_name=RERANK_MODEL)
        print(f"✅  Reranker ready: {RERANK_MODEL}")
    return _reranker

def _calibrated_sigmoid(x: float, temperature: float = 1.5) -> float:
    """
    Apply Temperature Scaling to the Sigmoid function.
    Higher temperature (e.g., 1.5 or 2.0) makes the model more 'skeptical' 
    by flattening the curve.
    """
    return 1 / (1 + math.exp(-x / temperature))

def rerank_results(query: str, results: list[dict], top_n: int = TOP_K_RERANK) -> list[dict]:
    """
    Reranks results using a Cross-Encoder.
    - Preserves the original 'score' as 'vector_score' (if not already present).
    - Adds 'rerank_score' based on the Cross-Encoder output.
    - Sorts by 'rerank_score'.
    """
    if not results:
        return []

    print(f"🔢  Reranking {len(results)} chunks ...")
    
    reranker = get_reranker()
    documents = [r["text"] for r in results]
    
    # Get raw logits from BGE Reranker
    raw_scores = list(reranker.rerank(query, documents))
    
    reranked = []
    for i, res in enumerate(results):
        # If 'vector_score' isn't already there (e.g. first rerank), move current 'score' to it
        vector_score = res.get("vector_score", res.get("score", 0.0))
        
        # Apply Temperature Scaling (T=1.5)
        normalized_score = _calibrated_sigmoid(float(raw_scores[i]), temperature=1.5)
        
        reranked.append({
            **res,
            "vector_score": vector_score,
            "rerank_score": round(normalized_score, 4),
            "raw_logit": round(float(raw_scores[i]), 4),
            "score": round(normalized_score, 4), # Keep 'score' for generic sorting
            "is_reranked": True
        })
    
    # Sort by rerank score
    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    final_results = reranked[:top_n]
    print(f"✅  Reranking complete — top rerank score: {final_results[0]['rerank_score']}")
    
    return final_results
