# file: web_search.py
# ─────────────────────────────────────────────────────────────
# PURPOSE: Tavily web search — pure execution, no routing logic.
#
# NOTE: The decision of WHETHER to run web search is now made
# entirely by retrieval_evaluator.py (CRAG logic).
# This file only handles the mechanics of running the search.
# ─────────────────────────────────────────────────────────────

from tavily import TavilyClient
from config import WEB_SEARCH_MAX_RESULTS


def run_web_search(query: str, api_key: str) -> list[dict]:
    """
    Run a Tavily search and return normalised result dicts:
      { text, source (URL), score }
    """
    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=WEB_SEARCH_MAX_RESULTS,
        include_answer=False,
    )
    results = []
    for r in response.get("results", []):
        content = r.get("content", "").strip()
        if content:
            results.append({
                "text":   content,
                "source": r.get("url", "web"),
                "score":  round(r.get("score", 0.0), 4),
            })

    print(f"✅  Web search complete: {len(results)} results from Tavily")
    return results