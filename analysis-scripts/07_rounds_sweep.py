"""
Phase 9: N_ROUNDS Hyperparameter Sweep

This script runs the cold-start Escape Hatch loop up to a high ceiling (e.g., 10 rounds)
to explicitly map out the diminishing returns curve.

For each round, it records:
- new_gold: How many new gold papers were found in this round?
- new_nodes: How many total new papers were visited (screened) in this round?
- recall: Cumulative recall after this round.

It outputs a CSV and a set of plots showing these three metrics side-by-side
as a function of N_ROUNDS, allowing you to empirically choose the right fixed cap.
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import defaultdict
from pathlib import Path
import random

random.seed(42)
np.random.seed(42)

OUT  = Path("/home/ubuntu/litreview-coverage")
FIGS = OUT / "pub_figures"
FIGS.mkdir(exist_ok=True)

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
print("Loading APS citation graph...")
try:
    df = pd.read_csv("/home/ubuntu/aps-citations.csv")
except FileNotFoundError:
    print("Error: /home/ubuntu/aps-citations.csv not found. Please ensure the dataset is present.")
    exit(1)

with open(OUT / "ground_truth.json") as f:
    gt = json.load(f)

print("Building adjacency index...")
cites    = defaultdict(set)
cited_by = defaultdict(set)
for row in df.itertuples(index=False):
    cites[row.citing_doi].add(row.cited_doi)
    cited_by[row.cited_doi].add(row.citing_doi)
print("  Done.")

# ── Core traversal engine ─────────────────────────────────────────────────────
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

        nxt = set()
        # Backward
        for node in frontier:
            for nb in cites.get(node, set()):
                if nb not in visited:
                    visited.add(nb); nxt.add(nb)

        # Forward
        fwd_candidates = []
        for node in frontier:
            for nb in cited_by.get(node, set()):
                if nb not in visited:
                    fwd_candidates.append(nb)
        if fwd_candidates:
            out_degs = np.array([len(cites.get(nb, set())) for nb in fwd_candidates])
            threshold = np.percentile(out_degs, PARETO_P)
            for nb, od in zip(fwd_candidates, out_degs):
                if od <= threshold and nb not in visited:
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

        # Escape Hatch
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
# Rows: 1) new_gold, 2) new_nodes, 3) cumulative_recall
# Cols: Surveys

for col, (key, info) in enumerate(gt.items()):
    s_data = df_res[df_res["survey"] == key]
    color = SURVEY_STYLE[key]["color"]
    label = SURVEY_STYLE[key]["label"]
    
    rounds = s_data["round"].values
    
    # Row 0: New Gold
    ax0 = axes[0, col]
    ax0.bar(rounds, s_data["new_gold"], color=color, alpha=0.8)
    ax0.set_title(label, fontsize=10)
    if col == 0: ax0.set_ylabel("New Gold Papers Found")
    
    # Row 1: New Nodes (Screening Cost)
    ax1 = axes[1, col]
    ax1.bar(rounds, s_data["new_nodes"], color="gray", alpha=0.7)
    if col == 0: ax1.set_ylabel("New Nodes Visited (Cost)")
    
    # Row 2: Cumulative Recall
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
