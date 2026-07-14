"""
Phase 9: N_ROUNDS Hyperparameter Sweep

This script runs the cold-start Escape Hatch loop up to a high ceiling (e.g., 10 rounds)
to explicitly map out the diminishing returns curve.

**Traversal engine updated 2026-07-14** to call litdiscover's real production
operators (backward_traversal_operator, forward_traversal_operator) via a
ClosedCorpusSource, matching the correction made in
eval/04b_cold_start_lowseed.py and eval/03_traversal_simulation.py — the
Pareto filter now applies pre-expansion on the FRONTIER paper's own
citation_count (production's actual filter point), not post-hoc on
collected CITERS' own out-degree. See
wiki/litdiscover/phase-discovery-roadmap.md §1.3. Expect this sweep's numbers
to differ from any previously-committed run for the same reason 04b's did —
this is a parameter-justification script (not a paper-claimed figure per
this repo's own CLAUDE.md), so the change matters less here, but is still
worth knowing about if this sweep is ever revisited.

Note: this script's K_SEED=20 is a pre-existing inconsistency with the
canonical k=5 used elsewhere (eval/04b/05) — left unchanged here, this
migration only swaps the traversal engine, not the experimental design.

For each round, it records:
- new_gold: How many new gold papers were found in this round?
- new_nodes: How many total new papers were visited (screened) in this round?
- recall: Cumulative recall after this round.

It outputs a CSV and a set of plots showing these three metrics side-by-side
as a function of N_ROUNDS, allowing you to empirically choose the right fixed cap.
"""
from __future__ import annotations

import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import random

sys.path.insert(0, str(Path(__file__).parent.parent))
from _corpus_loader import load_adjacency, build_closed_corpus_source  # noqa: E402

from litdiscover.discovery.traverse import (
    backward_traversal_operator, forward_traversal_operator, pareto_hub_threshold,
)

random.seed(42)
np.random.seed(42)

_REPO = Path(__file__).parent.parent.parent
OUT  = _REPO / "data" / "outputs"
FIGS = OUT / "pub_figures"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

SURVEY_STYLE = {
    "S1_MIT":  {"color": "#2166ac", "label": "S1: Metal-insulator transitions (1998)"},
    "S2_UCG":  {"color": "#d6604d", "label": "S2: Ultracold gases (2008)"},
    "S3_TOPO": {"color": "#4dac26", "label": "S3: Topological photonics (2019)"},
}

# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading APS citation graph via shared _corpus_loader...")
cites, cited_by = load_adjacency()
print(f"  {sum(len(v) for v in cites.values()):,} edges")

source, doi_to_paper = build_closed_corpus_source(cites, cited_by)

with open(OUT / "ground_truth.json") as f:
    gt = json.load(f)

# ── Core traversal engine (real litdiscover production operators) ─────────────
PARETO_P = 80
YIELD_THRESHOLD = 0.05
MAX_DEPTH = 8


def bidir_pareto_traversal(seed_set, gold_refs, visited_already=None):
    visited  = set(visited_already) if visited_already else set()
    for s in seed_set:
        visited.add(s)
    frontier = set(seed_set) - (visited_already or set())
    if not frontier:
        frontier = set(seed_set)

    for d in range(1, MAX_DEPTH + 1):
        prev_size = len(visited)
        prev_gold = len(visited & gold_refs)

        frontier_papers = [doi_to_paper[doi] for doi in frontier if doi in doi_to_paper]
        if not frontier_papers:
            break

        bwd = backward_traversal_operator(frontier_papers, source=source)
        threshold, _, _ = pareto_hub_threshold(frontier_papers, base_percentile=PARETO_P)
        fwd = forward_traversal_operator(frontier_papers, hub_threshold=threshold, source=source)

        nxt = set()
        for cand in bwd.candidates + fwd.candidates:
            nb = cand.get("doi")
            if nb and nb not in visited:
                visited.add(nb); nxt.add(nb)

        frontier = nxt
        new_nodes = len(visited) - prev_size
        new_gold  = len(visited & gold_refs) - prev_gold
        sy = new_gold / new_nodes if new_nodes > 0 else 0.0

        if sy < YIELD_THRESHOLD and d >= 2:
            break
        if not frontier:
            break

    return visited


def make_seeds_top_k(gold_refs, k, cited_by_map):
    scored = sorted(gold_refs, key=lambda x: len(cited_by_map.get(x, set())), reverse=True)
    return set(scored[:k])


# ── Sweep Loop ────────────────────────────────────────────────────────────────
def sweep_rounds(seed_set, gold_refs, max_rounds=10, k_escape=20):
    visited = set()
    rounds_data = []
    current_seeds = set(seed_set)

    for r in range(1, max_rounds + 1):
        visited_before = len(visited)
        gold_before    = len(visited & gold_refs)

        visited = bidir_pareto_traversal(current_seeds, gold_refs, visited_already=visited)

        new_nodes = len(visited) - visited_before
        new_gold  = len(visited & gold_refs) - gold_before
        recall    = len(visited & gold_refs) / len(gold_refs)

        rounds_data.append({
            "round": r,
            "new_nodes": new_nodes,
            "new_gold": new_gold,
            "cumulative_recall": recall,
            "cumulative_nodes": len(visited)
        })

        if recall >= 1.0:
            break

        included = visited & gold_refs
        escape_candidates = set()
        for p in included:
            for nb in cites.get(p, set()):
                if nb not in visited: escape_candidates.add(nb)
            for nb in cited_by.get(p, set()):
                if nb not in visited: escape_candidates.add(nb)

        if not escape_candidates:
            break

        escape_sorted = sorted(escape_candidates,
                               key=lambda x: len(cited_by.get(x, set())), reverse=True)
        current_seeds = set(escape_sorted[:k_escape])

    return rounds_data


# ── Run Sweep ─────────────────────────────────────────────────────────────────
print("\nRunning N_ROUNDS sweep (up to 10 rounds, k=20 top-k seeds)...")

MAX_ROUNDS = 10
K_SEED = 20

all_results = []

for key, info in gt.items():
    gold_refs = set(info["gold_refs"])
    print(f"  {key} | gold_refs={len(gold_refs)}")

    seeds = make_seeds_top_k(gold_refs, K_SEED, cited_by)
    sweep_data = sweep_rounds(seeds, gold_refs, max_rounds=MAX_ROUNDS)

    for row in sweep_data:
        row["survey"] = key
        all_results.append(row)

df_res = pd.DataFrame(all_results)
df_res = df_res[["survey", "round", "new_gold", "new_nodes", "cumulative_recall", "cumulative_nodes"]]

csv_path = OUT / "n_rounds_sweep.csv"
df_res.to_csv(csv_path, index=False)
print(f"\nSaved sweep results to {csv_path}")

# ── Plotting ──────────────────────────────────────────────────────────────────
print("Generating sweep plots...")

fig, axes = plt.subplots(3, 3, figsize=(15, 10), sharex=True)

for col, (key, info) in enumerate(gt.items()):
    s_data = df_res[df_res["survey"] == key]
    color = SURVEY_STYLE[key]["color"]
    label = SURVEY_STYLE[key]["label"]

    rounds = s_data["round"].values

    ax0 = axes[0, col]
    ax0.bar(rounds, s_data["new_gold"], color=color, alpha=0.8)
    ax0.set_title(label, fontsize=10)
    if col == 0: ax0.set_ylabel("New Gold Papers Found")

    ax1 = axes[1, col]
    ax1.bar(rounds, s_data["new_nodes"], color="gray", alpha=0.7)
    if col == 0: ax1.set_ylabel("New Nodes Visited (Cost)")

    ax2 = axes[2, col]
    ax2.plot(rounds, s_data["cumulative_recall"], marker="o", color=color, lw=2)
    ax2.axhline(1.0, color="black", ls="--", lw=1, alpha=0.5)
    ax2.set_ylim(0, 1.05)
    ax2.set_xlabel("N_ROUNDS")
    ax2.set_xticks(range(1, MAX_ROUNDS + 1))
    if col == 0: ax2.set_ylabel("Cumulative Recall")

fig.suptitle("N_ROUNDS Hyperparameter Sweep: Marginal Gains vs. Costs per Round", fontsize=14)
fig.tight_layout(rect=[0, 0.03, 1, 0.97])

plot_path = FIGS / "fig9_n_rounds_sweep.png"
fig.savefig(plot_path, dpi=150, bbox_inches="tight")
plt.close(fig)

print(f"Saved plot to {plot_path}")
print("Done.")
