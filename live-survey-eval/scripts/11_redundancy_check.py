"""
Co-Citation vs. Multi-Round Forward Traversal — Redundancy Pre-Check

Cheap sanity check before scoping §4.6's true operator-ordering experiment
(wiki/litdiscover/phase-discovery-roadmap.md §4.6). §4.5's ablation found
co_citation is the only non-traversal operator with a nonzero recall drop on
every survey — before building a bigger, more expensive chained-execution
experiment around it, check whether it's actually redundant with something
cheaper we already have.

Both co_citation_operator and a hypothetical 2-round forward traversal hop
through the same intermediate set (seeds' citers), but pull different signal
out of it:
  - co_citation:   seed -> citers -> each citer's OWN REFERENCES -> candidate
                   kept if >=2 citers share it (looks backward from citers).
  - 2-round fwd:    seed -> citers (round 1) -> CITERS OF THOSE CITERS (round
                    2) -> candidate is anyone citing a round-1 citer (looks
                    forward again from citers).

This script runs both from the same seed set per survey and reports overlap
(Jaccard on candidate sets, and specifically on new-gold-found sets) — if
they're mostly finding the same papers, co-citation may be a cheaper proxy
for multi-round forward traversal (or vice versa); if they diverge, both are
independently worth keeping and the ordering question is more interesting,
not less.

Deliberately capped for a quick sanity test, not a full experiment: round-2
frontier is capped to the round-1 candidates with the highest citation_count
(most likely to have interesting further citers), same cost-bounding
philosophy as co_citation_operator's own max_citers_per_seed cap.

Usage:
  PYTHONUNBUFFERED=1 python3 11_redundancy_check.py --survey K17-RGC
  PYTHONUNBUFFERED=1 python3 11_redundancy_check.py   # all three
"""
from __future__ import annotations

import argparse
import json

from litdiscover.discovery.operators import co_citation_operator
from litdiscover.discovery.traverse import forward_traversal_operator

# Reuse 10_operator_benchmark.py's loaders/config via _shared.py (2026-07-14 —
# previously loaded 10_operator_benchmark.py's whole module body via
# importlib.util.spec_from_file_location; now a normal import).
import _shared

ROUND2_FRONTIER_CAP = 15  # cap round-1 candidates fed into round 2, by citation_count desc


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def run_survey(survey_id: str) -> dict:
    print(f"\n{'='*60}\nRedundancy check: {survey_id}\n{'='*60}")
    gold = _shared._load_gold(survey_id)
    seed_ids = _shared._load_seed_ids(survey_id)
    if not gold or not seed_ids:
        print(f"  Missing gold or seeds for {survey_id}. Skipping.")
        return {}

    seeds = [p for sid in seed_ids if (p := _shared._fetch_full_paper(sid)) is not None]
    if not seeds:
        print("  Could not resolve seeds. Skipping.")
        return {}
    seed_only_ids = {s["s2_id"] for s in seeds}

    # ── Multi-round forward traversal: round 1, then round 2 from the
    # highest-cited round-1 candidates (cost cap — see module docstring) ────
    print("  Forward traversal round 1...")
    r1_result = forward_traversal_operator(seeds)
    r1_ids = {c["s2_id"] for c in r1_result.candidates if c.get("s2_id")}
    r1_new = r1_ids - seed_only_ids

    frontier = sorted(
        (c for c in r1_result.candidates if c.get("s2_id") in r1_new),
        key=lambda c: c.get("citation_count") or 0, reverse=True,
    )[:ROUND2_FRONTIER_CAP]
    print(f"  Forward traversal round 2, from top {len(frontier)} round-1 candidates by citations...")
    r2_result = forward_traversal_operator(frontier)
    r2_ids = {c["s2_id"] for c in r2_result.candidates if c.get("s2_id")}

    multi_round_fwd = (r1_ids | r2_ids) - seed_only_ids

    # ── Co-citation, same seeds ──────────────────────────────────────────────
    print("  Co-citation...")
    cc_result = co_citation_operator(seeds)
    co_citation_ids = {c["s2_id"] for c in cc_result.candidates if c.get("s2_id")} - seed_only_ids

    # ── Overlap ───────────────────────────────────────────────────────────────
    candidate_jaccard = _jaccard(multi_round_fwd, co_citation_ids)
    fwd_gold = multi_round_fwd & gold
    cc_gold = co_citation_ids & gold
    gold_jaccard = _jaccard(fwd_gold, cc_gold)

    print(f"  Multi-round fwd traversal: {len(multi_round_fwd)} candidates, "
          f"{len(fwd_gold)} new gold")
    print(f"  Co-citation:               {len(co_citation_ids)} candidates, "
          f"{len(cc_gold)} new gold")
    print(f"  Candidate-set Jaccard overlap: {candidate_jaccard:.2f}")
    print(f"  New-gold-set Jaccard overlap:  {gold_jaccard:.2f} "
          f"(shared gold: {len(fwd_gold & cc_gold)}, "
          f"fwd-only gold: {len(fwd_gold - cc_gold)}, "
          f"cc-only gold: {len(cc_gold - fwd_gold)})")

    return {
        "survey_id": survey_id,
        "multi_round_fwd_candidates": len(multi_round_fwd),
        "multi_round_fwd_new_gold": len(fwd_gold),
        "co_citation_candidates": len(co_citation_ids),
        "co_citation_new_gold": len(cc_gold),
        "candidate_jaccard": candidate_jaccard,
        "gold_jaccard": gold_jaccard,
        "shared_gold": len(fwd_gold & cc_gold),
        "fwd_only_gold": len(fwd_gold - cc_gold),
        "cc_only_gold": len(cc_gold - fwd_gold),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Co-citation vs. multi-round forward traversal redundancy check")
    parser.add_argument("--survey", choices=list(_shared.SURVEYS.keys()),
                         help="Run only this survey (default: all)")
    args = parser.parse_args()

    surveys_to_run = [args.survey] if args.survey else list(_shared.SURVEYS.keys())
    all_results = {}
    for sid in surveys_to_run:
        result = run_survey(sid)
        if result:
            all_results[sid] = result

    out_path = _shared.OUT_DIR / "redundancy_check_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
