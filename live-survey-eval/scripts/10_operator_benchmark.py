"""
Discovery-Operator Benchmark — §4.3/§4.4/§4.5 of
wiki/litdiscover/phase-discovery-roadmap.md

Runs the real production operators (litdiscover.discovery.operators +
litdiscover.discovery.traverse) against the three live-survey gold sets
(K17-RGC, Ge21-HSS, Le25-GLLM) already built by 09_live_validation.py. Per
phase-discovery-roadmap.md §5, the non-graph operators (author/venue/recency/
embedding/co-citation) can only be validated against production semantics or
this live-survey track, not the APS closed-corpus simulation — this script is
that validation.

Every operator runs exactly once per survey, from the fixed seed set (none of
them take an accumulated/expanding corpus as input) — so a single pass derives
all three measurements below from the same candidate sets, rather than
re-invoking operators per measurement:
  - §4.3 Baselines: seed-only recall, and each operator's recall in isolation.
  - §4.4 Marginal contribution: an additive sequence (traversal -> embedding
    -> co-citation -> author -> venue -> recency) over the same per-operator
    sets. Because operators don't chain on each other's output, reordering
    this sequence changes which step gets "credit" for overlapping finds, not
    the final cumulative recall — a genuine ordering experiment (§4.6) needs
    operators run on the expanding corpus, not implemented here.
  - §4.5 Ablation: full-set recall vs. recall with each operator's candidates
    removed, via set difference over the same per-operator sets — no extra
    API calls needed beyond §4.3's single pass.

Does NOT rebuild gold sets or seeds — loads the existing, already-resolved
data/gold-sets/*.json and data/seeds/*.json written by 09_live_validation.py.
Manual corrections to those files are respected as-is.

**2026-07-14:** loaders/config/metrics (SURVEYS, _load_gold, _load_seed_ids,
_fetch_full_paper, _recall, _precision, OPERATORS, MARGINAL_ORDER) moved to
_shared.py — 11_redundancy_check.py and 12_chained_composition.py now import
that module normally instead of dynamically loading this whole script's
module body via importlib.util.spec_from_file_location.

This calls litdiscover's real operators, which hit the live S2 API through
the package's own shared rate limiter (1 req/sec) — no separate caching layer
here, unlike 09_live_validation.py's disk cache. Expect this to take a few
minutes per survey, not be instant.

Usage:
  cd litdiscover && pip install -e .   # once, if not already installed
  cd ../lit-review/robust-literature-discovery/live-survey-eval/scripts
  PYTHONUNBUFFERED=1 python3 10_operator_benchmark.py --survey K17-RGC
  PYTHONUNBUFFERED=1 python3 10_operator_benchmark.py   # all three
"""
from __future__ import annotations

import argparse
import json

from _shared import (  # noqa: E402
    SURVEYS, OUT_DIR, _load_gold, _load_seed_ids, _fetch_full_paper,
    _candidate_ids, _recall, _precision, OPERATORS, MARGINAL_ORDER,
)
from litdiscover.discovery.budget import recall_per_call


def run_survey(survey_id: str) -> dict:
    cfg = SURVEYS[survey_id]
    print(f"\n{'='*60}\nOperator benchmark: {survey_id}\n{'='*60}")

    gold = _load_gold(survey_id)
    seed_ids = _load_seed_ids(survey_id)
    if not gold or not seed_ids:
        print(f"  Missing gold or seeds for {survey_id} — run 09_live_validation.py first. Skipping.")
        return {}

    print(f"  Gold: {len(gold)} papers. Seeds: {len(seed_ids)}.")
    print("  Fetching full seed records (authors/venue needed by some operators)...")
    seeds = [p for sid in seed_ids if (p := _fetch_full_paper(sid)) is not None]
    if not seeds:
        print("  Could not resolve any seed records. Skipping.")
        return {}

    seed_only_ids = {s["s2_id"] for s in seeds}
    baseline_recall = _recall(seed_only_ids, gold)
    print(f"  Baseline (seeds only): recall={baseline_recall:.1%} ({len(seed_only_ids & gold)}/{len(gold)})")

    # ── §4.3: single-operator recall, each run in isolation from seeds ──────
    # Every operator here takes the fixed `seeds` list, never an accumulated/
    # expanded set (see module note above §4.5) — so one run per operator is
    # enough to derive §4.3 (isolated recall), §4.4 (marginal contribution),
    # and §4.5 (ablation) all from the same candidate sets, instead of the
    # previous approach of re-invoking every operator a second time inside
    # §4.4's loop (2x the API cost, and inconsistent since S2 search results
    # vary slightly call-to-call — observed directly: K17-RGC's recency_search
    # found +1 gold on one run and +0 on an immediate rerun).
    single_op: dict[str, dict] = {}
    found_sets: dict[str, set[str]] = {}
    for name, fn in OPERATORS.items():
        print(f"  Running {name}...")
        result, cost = fn(seeds, cfg)
        found = _candidate_ids(result)
        found_sets[name] = found
        new_gold = len(found & gold)
        r_p_c = recall_per_call(cost, new_gold)
        precision = _precision(found, gold)
        single_op[name] = {
            "recall": _recall(found | seed_only_ids, gold),
            "precision": precision,
            "candidates": len(found),
            "new_gold_found": new_gold,
            "s2_calls": cost.s2_calls,
            "wall_seconds": round(cost.wall_seconds, 1),
            "recall_per_call": r_p_c,
            "stats": result.stats,
        }
        print(f"    -> +{new_gold} new gold, {len(found)} candidates "
              f"(precision={precision:.1%}), "
              f"{cost.s2_calls} S2 calls, {cost.wall_seconds:.1f}s, "
              f"recall/call={r_p_c:.3f}")

    # ── §4.4: marginal contribution — additive sequence over the same sets ──
    # NOTE: because every operator's `found` set above was computed
    # independently from the fixed seed set (not from each other's output),
    # reordering MARGINAL_ORDER cannot change the final cumulative recall —
    # it only changes which step gets "credit" for a paper multiple operators
    # would have found. A genuine ordering experiment (§4.6) requires
    # operators to run on the *expanding* corpus (op N's input = seeds + all
    # prior ops' candidates), which is a separate, more expensive design not
    # implemented here — flagged, not silently assumed away.
    print("  Deriving marginal-contribution curve...")
    accumulated = set(seed_only_ids)
    curve = [{"step": "seeds_only", "recall": baseline_recall,
              "new_gold": len(accumulated & gold), "cumulative_candidates": len(accumulated)}]
    for name in MARGINAL_ORDER:
        before_gold = len(accumulated & gold)
        new_this_step = found_sets[name] - accumulated
        accumulated |= found_sets[name]
        after_gold = len(accumulated & gold)
        recall = _recall(accumulated, gold)
        step_new_gold = after_gold - before_gold
        step_precision = _precision(new_this_step, gold)
        curve.append({
            "step": name,
            "recall": recall,
            "new_gold": step_new_gold,
            "new_candidates_this_step": len(new_this_step),
            "step_precision": step_precision,
            "cumulative_candidates": len(accumulated),
        })
        print(f"    + {name}: recall={recall:.1%} (+{step_new_gold} gold / "
              f"+{len(new_this_step)} candidates this step, "
              f"step precision={step_precision:.1%})")

    # ── §4.5: ablation (leave-one-out) — also derived from the same sets ────
    print("  Deriving ablation (leave-one-out)...")
    full_set = set(seed_only_ids)
    for s in found_sets.values():
        full_set |= s
    full_recall = _recall(full_set, gold)
    full_precision = _precision(full_set - seed_only_ids, gold)
    print(f"    Full-set precision (all candidates beyond seeds): {full_precision:.1%}")
    ablation: dict[str, dict] = {}
    for name in OPERATORS:
        without = set(seed_only_ids)
        for other_name, s in found_sets.items():
            if other_name != name:
                without |= s
        recall_without = _recall(without, gold)
        drop = full_recall - recall_without
        ablation[name] = {"recall_without": recall_without, "recall_drop": drop}
        print(f"    - {name}: recall drops from {full_recall:.1%} to "
              f"{recall_without:.1%} (Δ={drop:.1%}) if removed")

    return {
        "survey_id": survey_id,
        "gold_size": len(gold),
        "seed_count": len(seeds),
        "baseline_recall": baseline_recall,
        "single_operator": single_op,
        "marginal_curve": curve,
        "full_recall": full_recall,
        "full_precision": full_precision,
        "ablation": ablation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Discovery-operator benchmark (§4.3/§4.4)")
    parser.add_argument("--survey", choices=list(SURVEYS.keys()),
                         help="Run only this survey (default: all)")
    args = parser.parse_args()

    surveys_to_run = [args.survey] if args.survey else list(SURVEYS.keys())
    all_results = {}
    for sid in surveys_to_run:
        result = run_survey(sid)
        if result:
            all_results[sid] = result

    out_path = OUT_DIR / "operator_benchmark_results.json"
    existing = {}
    if out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)
    existing.update(all_results)
    with open(out_path, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
