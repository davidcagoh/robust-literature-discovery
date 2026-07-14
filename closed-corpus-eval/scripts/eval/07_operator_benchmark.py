"""
Closed-Corpus Operator Benchmark — mirrors live-survey-eval/10_operator_benchmark.py

Runs litdiscover's real production operators (backward_traversal_operator,
forward_traversal_operator, pareto_hub_threshold) against the closed APS
corpus via ClosedCorpusSource, for all 3 closed-corpus surveys (S1_MIT,
S2_UCG, S3_TOPO). This is the actual "redo Experiment 1 differently"
deliverable named in wiki/litdiscover/phase-discovery-roadmap.md §1.4: the
closed-corpus track can now benchmark real production operators, not a
hand-rolled proxy of them.

**Author/venue expansion are NOT included here — a real data limitation,
not an oversight.** The APS `.mat` file (aps-2022-author-doi-citation-affil.mat)
does carry author-DOI linkage in principle, but its authorName/doi/
affiliationName/pubDate fields are stored as MATLAB's `string` type wrapped
in MCOS object encoding. Both h5py (raw HDF5 access — the fields resolve to
opaque object references into a `#refs#`/`MCOS` subsystem with no public
schema) and mat73 (a maintained library built specifically for this MATLAB
version) fail to decode them — mat73 raises "MATLAB type not supported:
string, (uint32)" directly. The underlying sparse matrices (B/C/D/E) do
decode, but without the label strings their row/column indices can't be
mapped back to real DOIs or author names. Reverse-engineering MATLAB's
proprietary MCOS object graph from scratch to recover this mapping is a
real, bounded-but-large undertaking with meaningful correctness risk for a
benchmark that would feed a paper — not attempted here. See
wiki/litdiscover/phase-discovery-roadmap.md §1.4 for the full account.
`author_expansion_operator`/`venue_expansion_operator` remain S2-only until
this is resolved (e.g. via an official MATLAB export to decode the file, or
locating an original tabular/CSV export of the author data upstream).

Usage:
  cd closed-corpus-eval/scripts/eval && python3 07_operator_benchmark.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _corpus_loader import load_adjacency, build_closed_corpus_source  # noqa: E402

from litdiscover.discovery.traverse import (
    backward_traversal_operator, forward_traversal_operator, pareto_hub_threshold,
)
from litdiscover.discovery.budget import run_with_cost, recall_per_call

_REPO = Path(__file__).parent.parent.parent
OUT = _REPO / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

PARETO_P = 80
SEED_SIZE = 5


def make_seeds_top_k(gold_refs: set[str], k: int, cited_by_map: dict) -> set[str]:
    scored = sorted(gold_refs, key=lambda x: len(cited_by_map.get(x, set())), reverse=True)
    return set(scored[:k])


def _recall(found: set[str], gold: set[str]) -> float:
    return len(found & gold) / len(gold) if gold else 0.0


def _precision(found: set[str], gold: set[str]) -> float:
    return len(found & gold) / len(found) if found else 0.0


def run_survey(survey_id: str, info: dict, cites: dict, cited_by: dict,
               source, doi_to_paper: dict) -> dict:
    print(f"\n{'='*60}\nClosed-corpus operator benchmark: {survey_id}\n{'='*60}")
    gold = set(info["gold_refs"])
    seed_ids = make_seeds_top_k(gold, SEED_SIZE, cited_by)
    seeds = [doi_to_paper[doi] for doi in seed_ids if doi in doi_to_paper]
    print(f"  Gold: {len(gold)} papers. Seeds: {len(seeds)} (top-{SEED_SIZE} by in-degree).")

    seed_only_ids = {s["doi"] for s in seeds}
    baseline_recall = _recall(seed_only_ids, gold)
    print(f"  Baseline (seeds only): recall={baseline_recall:.1%} "
          f"({len(seed_only_ids & gold)}/{len(gold)})")

    # ── backward_traversal_operator, isolated ────────────────────────────────
    print("  Running backward_traversal...")
    bwd_result, bwd_cost = run_with_cost(backward_traversal_operator, seeds, source=source)
    bwd_ids = {c["doi"] for c in bwd_result.candidates if c.get("doi")}
    bwd_new_gold = len(bwd_ids & gold)
    print(f"    -> +{bwd_new_gold} new gold, {len(bwd_ids)} candidates "
          f"(precision={_precision(bwd_ids, gold):.1%}), {bwd_cost.wall_seconds:.1f}s")

    # ── forward_traversal_operator, isolated, Pareto-filtered ────────────────
    print("  Running forward_traversal (Pareto-80)...")
    threshold, hub_pct, calib_reason = pareto_hub_threshold(seeds, base_percentile=PARETO_P)
    print(f"    Hub threshold: {threshold:.0f} ({calib_reason})")
    fwd_result, fwd_cost = run_with_cost(
        forward_traversal_operator, seeds, hub_threshold=threshold, source=source)
    fwd_ids = {c["doi"] for c in fwd_result.candidates if c.get("doi")}
    fwd_new_gold = len(fwd_ids & gold)
    print(f"    -> +{fwd_new_gold} new gold, {len(fwd_ids)} candidates "
          f"(precision={_precision(fwd_ids, gold):.1%}), {fwd_cost.wall_seconds:.1f}s")

    # ── Union (both operators, single pass, no traversal rounds) ────────────
    union_ids = seed_only_ids | bwd_ids | fwd_ids
    union_recall = _recall(union_ids, gold)
    union_precision = _precision(union_ids - seed_only_ids, gold)
    print(f"  Union (seeds + backward + forward, single pass): "
          f"recall={union_recall:.1%}, precision={union_precision:.1%}")

    # ── Ablation (leave-one-out) ──────────────────────────────────────────────
    without_bwd = _recall(seed_only_ids | fwd_ids, gold)
    without_fwd = _recall(seed_only_ids | bwd_ids, gold)
    print(f"  Ablation: recall drops to {without_bwd:.1%} without backward "
          f"(Δ={union_recall - without_bwd:+.1%}), "
          f"{without_fwd:.1%} without forward (Δ={union_recall - without_fwd:+.1%})")

    return {
        "survey_id": survey_id,
        "gold_size": len(gold),
        "seed_count": len(seeds),
        "baseline_recall": baseline_recall,
        "backward_traversal": {
            "recall": _recall(seed_only_ids | bwd_ids, gold),
            "precision": _precision(bwd_ids, gold),
            "candidates": len(bwd_ids),
            "new_gold_found": bwd_new_gold,
            "wall_seconds": round(bwd_cost.wall_seconds, 2),
            "recall_per_call": recall_per_call(bwd_cost, bwd_new_gold),
        },
        "forward_traversal": {
            "recall": _recall(seed_only_ids | fwd_ids, gold),
            "precision": _precision(fwd_ids, gold),
            "candidates": len(fwd_ids),
            "new_gold_found": fwd_new_gold,
            "hub_threshold": threshold,
            "hub_percentile": hub_pct,
            "wall_seconds": round(fwd_cost.wall_seconds, 2),
            "recall_per_call": recall_per_call(fwd_cost, fwd_new_gold),
        },
        "union_recall": union_recall,
        "union_precision": union_precision,
        "ablation": {
            "recall_without_backward": without_bwd,
            "recall_drop_backward": union_recall - without_bwd,
            "recall_without_forward": without_fwd,
            "recall_drop_forward": union_recall - without_fwd,
        },
        "author_expansion": "NOT_RUN — author/DOI linkage in the .mat file is "
                             "MCOS-encoded and not decodable with available tools, "
                             "see module docstring",
        "venue_expansion": "NOT_RUN — no venue/journal field in the closed corpus "
                            "beyond DOI-prefix inference (_infer_venue_from_doi), "
                            "not benchmarked separately here",
    }


def main() -> None:
    print("Loading APS citation graph via shared _corpus_loader...")
    cites, cited_by = load_adjacency()
    print(f"  {sum(len(v) for v in cites.values()):,} edges")

    source, doi_to_paper = build_closed_corpus_source(cites, cited_by)

    with open(OUT / "ground_truth.json") as f:
        gt = json.load(f)

    all_results = {}
    for survey_id, info in gt.items():
        all_results[survey_id] = run_survey(survey_id, info, cites, cited_by, source, doi_to_paper)

    out_path = OUT / "closed_corpus_operator_benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
