"""
live-survey-eval/scripts/_shared.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shared config/loaders/metrics for 10_operator_benchmark.py, 11_redundancy_check.py,
and 12_chained_composition.py — extracted 2026-07-14 so 11 and 12 import this
module normally instead of dynamically loading 10_operator_benchmark.py's
whole module body via importlib.util.spec_from_file_location (which
re-executed 10's top-level code, including its dotenv load, on every import).
See wiki/litdiscover/phase-discovery-roadmap.md §1.2/§1.3.

Does NOT rebuild gold sets or seeds — loads the existing, already-resolved
data/gold-sets/*.json and data/seeds/*.json written by 09_live_validation.py.
Manual corrections to those files are respected as-is.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    # litdiscover's own .env carries SEMANTIC_SCHOLAR_API_KEY
    load_dotenv(Path(__file__).parent.parent.parent.parent.parent / "litdiscover" / ".env")
except ImportError:
    pass

from litdiscover.discovery import s2_client
from litdiscover.discovery.operators import (
    author_expansion_operator, venue_expansion_operator,
    recency_search_operator, embedding_search_operator, co_citation_operator,
    _normalise_paper, _get_json,
)
from litdiscover.discovery.traverse import (
    backward_traversal_operator, forward_traversal_operator, OperatorResult,
)
from litdiscover.discovery.budget import run_with_cost

# ── Paths (reuse existing live-survey-eval track, don't duplicate it) ────────
TRACK    = Path(__file__).parent.parent
GOLD_DIR = TRACK / "data" / "gold-sets"
SEED_DIR = TRACK / "data" / "seeds"
OUT_DIR  = TRACK / "data" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Survey config: topic query for recency/venue fallback, since_year for
# the recency operator. Deliberately conservative — the recency operator is
# structurally aimed at post-survey papers, which by definition cannot appear
# in a gold set drawn from the survey's own (necessarily earlier) reference
# list. Included anyway for an honest, not cherry-picked, baseline. ─────────
SURVEYS: dict[str, dict] = {
    "Ge21-HSS": {"topic_query": "human social sensing", "since_year": 2020},
    "K17-RGC":  {"topic_query": "random geometric complexes persistent homology", "since_year": 2016},
    "Le25-GLLM": {"topic_query": "graph augmented LLM agents literature review", "since_year": 2024},
}


def _load_gold(survey_id: str) -> set[str]:
    path = GOLD_DIR / f"{survey_id}_gold.json"
    with open(path) as f:
        entries = json.load(f)
    gold: set[str] = set()
    for e in entries:
        sid = e.get("manual_s2_id") or e.get("s2_id")
        if sid:
            gold.add(sid)
    return gold


def _load_seed_ids(survey_id: str) -> list[str]:
    path = SEED_DIR / f"{survey_id}_seeds.json"
    with open(path) as f:
        seeds = json.load(f)
    return [s["s2_id"] for s in seeds if s.get("s2_id")]


def _fetch_full_paper(s2_id: str) -> dict | None:
    """
    Fetch one paper's full record (incl. authors/venue, which
    09_live_validation.py's own cache never captured) via litdiscover's own S2
    client fields/rate-limiter — needed because author_expansion_operator and
    venue_expansion_operator derive their query from `papers[i]["authors"]`/
    `["venue"]`, which 09's seed JSON doesn't carry.

    Reuses operators._get_json (429-retry-with-backoff, see
    wiki/litdiscover/phase-discovery-roadmap.md §4.3/§7 step 6) rather than a
    bare httpx call — a plain call here previously dropped a Le25-GLLM seed
    silently on a 429 with no retry.
    """
    try:
        return _normalise_paper(
            _get_json(f"{s2_client.S2_BASE}/{s2_id}", {"fields": s2_client.S2_FIELDS}),
            source="seed", depth=0)
    except Exception as e:
        print(f"  [fetch] failed for {s2_id}: {e}")
        return None


def _candidate_ids(result: OperatorResult) -> set[str]:
    return {c["s2_id"] for c in result.candidates if c.get("s2_id")}


def _recall(found: set[str], gold: set[str]) -> float:
    return len(found & gold) / len(gold) if gold else 0.0


def _precision(found: set[str], gold: set[str]) -> float:
    """
    Fraction of `found` that's actually gold. Matters operationally because
    production screens every candidate through an LLM call before inclusion
    — an operator with high recall but terrible precision is expensive in
    exactly the currency that isn't S2 API calls (which recall_per_call
    already measures), it's screening-call volume. Returns 0.0 for an empty
    `found` set rather than dividing by zero.
    """
    return len(found & gold) / len(found) if found else 0.0


OPERATORS = {
    "backward_traversal": lambda seeds, cfg: run_with_cost(backward_traversal_operator, seeds),
    "forward_traversal":  lambda seeds, cfg: run_with_cost(forward_traversal_operator, seeds),
    "embedding_search":   lambda seeds, cfg: run_with_cost(embedding_search_operator, seeds),
    "co_citation":        lambda seeds, cfg: run_with_cost(co_citation_operator, seeds),
    "author_expansion":   lambda seeds, cfg: run_with_cost(author_expansion_operator, seeds),
    "venue_expansion":    lambda seeds, cfg: run_with_cost(
        venue_expansion_operator, seeds, topic_query=cfg["topic_query"]),
    "recency_search":     lambda seeds, cfg: run_with_cost(
        recency_search_operator, cfg["topic_query"], cfg["since_year"]),
}

# Order for the marginal-contribution curve (§4.4) — the two graph operators
# first (closest to current production behavior), then the non-graph
# operators in roughly ascending cost order. This ordering is itself an
# input to §4.6's ordering experiment, not a claimed-optimal sequence.
MARGINAL_ORDER = [
    "backward_traversal", "forward_traversal", "embedding_search",
    "co_citation", "author_expansion", "venue_expansion", "recency_search",
]
