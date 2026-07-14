"""
Experiment 1 — Composition: Chained vs. Independent-Union Retrieval
wiki/litdiscover/phase-discovery-roadmap.md §4.6 "Experiment 1 — Composition"

H0: running operators sequentially on the accumulated corpus produces no
    meaningful recall increase over independently running each operator from
    seeds and taking the union.
H1: sequential composition lets downstream operators exploit newly-discovered
    papers, finding additional relevant papers the independent-union approach
    would miss.

The independent-union arm already exists — it's §4.5's `full_recall` in
data/outputs/operator_benchmark_results.json (seeds union every operator run
independently from seeds). This script adds exactly the one new arm needed:
a single chained run, using the existing MARGINAL_ORDER sequence (ordering
itself is a separate, gated question — see §4.6 in the wiki) and one
frontier-selection default (rank the accumulated corpus by citation_count
descending before each operator's own internal list[:max_N] cap, so that cap
becomes "top N by citations" instead of an arbitrary accumulation-order
slice — same choice already used in 11_redundancy_check.py's round-2
frontier; frontier selection AS A VARIABLE is also a separate, gated
question, not tested here).

Reports, per survey: chained_recall, full_recall (loaded from the existing
results file), and chaining_delta = chained_recall - full_recall — the metric
that isolates chaining's effect from merely re-measuring the same union.

Usage:
  PYTHONUNBUFFERED=1 python3 12_chained_composition.py --survey K17-RGC
  PYTHONUNBUFFERED=1 python3 12_chained_composition.py   # all three
"""
from __future__ import annotations

import argparse
import json

# Reuse 10_operator_benchmark.py's loaders/config via _shared.py (2026-07-14 —
# previously loaded 10_operator_benchmark.py's whole module body via
# importlib.util.spec_from_file_location; now a normal import).
import _shared


def run_chained(seeds: list[dict], cfg: dict, order: list[str],
                 gold: set[str]) -> tuple[set[str], int, list[dict]]:
    """
    One growing accumulated-papers list; each operator in `order` receives it
    (ranked by citation_count desc — the frontier-selection default) rather
    than the fixed seed set. Returns (accumulated_ids, total_s2_calls, curve),
    where curve tracks recall/precision *per step* — needed to diagnose
    exactly where a chained run's signal degrades (e.g. a late operator
    querying an over-broad venue on a noisy corpus), not just the final
    aggregate number. See wiki/litdiscover/phase-discovery-roadmap.md §4.6
    "recall alone isn't enough" discussion (2026-07-14).
    """
    accumulated: list[dict] = list(seeds)
    accumulated_ids: set[str] = {p["s2_id"] for p in seeds if p.get("s2_id")}
    total_s2_calls = 0
    curve: list[dict] = [{
        "step": "seeds_only",
        "recall": _shared._recall(accumulated_ids, gold),
        "new_gold": len(accumulated_ids & gold),
        "corpus_size": len(accumulated_ids),
    }]

    for name in order:
        ranked = sorted(accumulated, key=lambda p: p.get("citation_count") or 0, reverse=True)
        print(f"  Running {name} on accumulated corpus ({len(ranked)} papers)...")
        result, cost = _shared.OPERATORS[name](ranked, cfg)
        total_s2_calls += cost.s2_calls

        new_ids_this_step: set[str] = set()
        for c in result.candidates:
            cid = c.get("s2_id")
            if cid and cid not in accumulated_ids:
                accumulated_ids.add(cid)
                accumulated.append(c)
                new_ids_this_step.add(cid)

        step_precision = _shared._precision(new_ids_this_step, gold)
        step_new_gold = len(new_ids_this_step & gold)
        curve.append({
            "step": name,
            "recall": _shared._recall(accumulated_ids, gold),
            "new_gold": step_new_gold,
            "new_candidates_this_step": len(new_ids_this_step),
            "step_precision": step_precision,
            "s2_calls": cost.s2_calls,
            "corpus_size": len(accumulated_ids),
        })
        print(f"    -> +{len(new_ids_this_step)} new papers into the accumulated corpus "
              f"(+{step_new_gold} gold, step precision={step_precision:.1%}, "
              f"{cost.s2_calls} S2 calls)")

    return accumulated_ids, total_s2_calls, curve


def run_survey(survey_id: str, existing_results: dict) -> dict:
    print(f"\n{'='*60}\nComposition experiment: {survey_id}\n{'='*60}")
    cfg = _shared.SURVEYS[survey_id]
    gold = _shared._load_gold(survey_id)
    seed_ids = _shared._load_seed_ids(survey_id)
    if not gold or not seed_ids:
        print(f"  Missing gold or seeds for {survey_id}. Skipping.")
        return {}

    prior = existing_results.get(survey_id)
    if not prior or "full_recall" not in prior:
        print(f"  No §4.5 full_recall on file for {survey_id} — run "
              f"10_operator_benchmark.py first. Skipping.")
        return {}
    full_recall = prior["full_recall"]
    full_precision = prior.get("full_precision")

    seeds = [p for sid in seed_ids if (p := _shared._fetch_full_paper(sid)) is not None]
    if not seeds:
        print("  Could not resolve seeds. Skipping.")
        return {}

    seed_only_ids = {s["s2_id"] for s in seeds}
    accumulated_ids, total_s2_calls, curve = run_chained(seeds, cfg, _shared.MARGINAL_ORDER, gold)
    chained_recall = _shared._recall(accumulated_ids, gold)
    chained_precision = _shared._precision(accumulated_ids - seed_only_ids, gold)
    chaining_delta = chained_recall - full_recall
    precision_delta = (chained_precision - full_precision) if full_precision is not None else None

    print(f"  full_recall (independent union, from §4.5):    {full_recall:.1%}")
    print(f"  chained_recall:                                 {chained_recall:.1%}")
    print(f"  chaining_delta (recall):                        {chaining_delta:+.1%}")
    if full_precision is not None:
        print(f"  full_precision (independent union, from §4.5): {full_precision:.1%}")
        print(f"  chained_precision:                              {chained_precision:.1%}")
        print(f"  precision_delta:                                {precision_delta:+.1%}")
    print(f"  ({total_s2_calls} S2 calls spent on the chained run, "
          f"corpus size {len(accumulated_ids)})")

    return {
        "survey_id": survey_id,
        "full_recall": full_recall,
        "full_precision": full_precision,
        "chained_recall": chained_recall,
        "chained_precision": chained_precision,
        "chaining_delta": chaining_delta,
        "precision_delta": precision_delta,
        "chained_s2_calls": total_s2_calls,
        "chained_corpus_size": len(accumulated_ids),
        "chained_curve": curve,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Composition experiment (chained vs. independent union)")
    parser.add_argument("--survey", choices=list(_shared.SURVEYS.keys()),
                         help="Run only this survey (default: all)")
    args = parser.parse_args()

    results_path = _shared.OUT_DIR / "operator_benchmark_results.json"
    if not results_path.exists():
        print(f"Missing {results_path} — run 10_operator_benchmark.py first.")
        return
    with open(results_path) as f:
        existing_results = json.load(f)

    surveys_to_run = [args.survey] if args.survey else list(_shared.SURVEYS.keys())
    all_results = {}
    for sid in surveys_to_run:
        result = run_survey(sid, existing_results)
        if result:
            all_results[sid] = result

    print(f"\n{'='*60}\nSummary\n{'='*60}")
    for sid, r in all_results.items():
        verdict = "H1 (chaining helped)" if r["chaining_delta"] > 0 else \
                  ("H0 (no difference)" if r["chaining_delta"] == 0 else "chaining WORSE")
        p_delta = r.get("precision_delta")
        p_str = f", precision_delta={p_delta:+.1%}" if p_delta is not None else ""
        print(f"  {sid}: chaining_delta={r['chaining_delta']:+.1%}{p_str} -> {verdict}")

    out_path = _shared.OUT_DIR / "composition_experiment_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
