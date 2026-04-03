"""
Phase 6-8 (Extended): Cold-Start Escape Hatch Simulation — Low-Seed Regime

Extends 04_cold_start_simulation.py to cover the realistic user seed range of
k ∈ {2, 3, 4, 5, 6}, with k=10 and k=20 retained as anchors to the original
results. All other parameters (PARETO_P, YIELD_THRESHOLD, N_ROUNDS, K_ESCAPE)
are unchanged so results are directly comparable.

Output files are written to a separate figures_lowseed/ subdirectory so the
original figures from script 04 are not overwritten.
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from collections import defaultdict
from pathlib import Path
import random

random.seed(42)
np.random.seed(42)

OUT  = Path("/home/ubuntu/litreview-coverage")
FIGS = OUT / "figures_lowseed"
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
print("Loading APS citation graph...")
df = pd.read_csv("/home/ubuntu/aps-citations.csv")
print(f"  {len(df):,} edges")

with open(OUT / "ground_truth.json") as f:
    gt = json.load(f)

print("Building adjacency index...")
cites    = defaultdict(set)
cited_by = defaultdict(set)
for row in df.itertuples(index=False):
    cites[row.citing_doi].add(row.cited_doi)
    cited_by[row.cited_doi].add(row.citing_doi)
print("  Done.")

# ── Core traversal engine (unchanged from 04) ─────────────────────────────────
PARETO_P        = 80
YIELD_THRESHOLD = 0.05   # stop when screen yield drops below 5%
MAX_DEPTH       = 8

def bidir_pareto_traversal(seed_set, gold_refs, visited_already=None,
                            pareto_p=PARETO_P, yield_thresh=YIELD_THRESHOLD,
                            max_depth=MAX_DEPTH):
    """
    Bidirectional BFS with Pareto filter on forward step.
    Stops when screen yield (new gold / new nodes) drops below yield_thresh.

    Returns:
        visited:    set of all nodes visited
        curve:      list of dicts with per-depth stats
        stop_depth: depth at which yield threshold was triggered
    """
    visited  = set(visited_already) if visited_already else set()
    for s in seed_set:
        visited.add(s)
    frontier = set(seed_set) - (visited_already or set())
    if not frontier:
        frontier = set(seed_set)

    curve      = []
    stop_depth = max_depth

    for d in range(1, max_depth + 1):
        prev_size = len(visited)
        prev_gold = len(visited & gold_refs)

        nxt = set()
        # Backward (unfiltered)
        for node in frontier:
            for nb in cites.get(node, set()):
                if nb not in visited:
                    visited.add(nb); nxt.add(nb)

        # Forward (Pareto-filtered)
        fwd_candidates = []
        for node in frontier:
            for nb in cited_by.get(node, set()):
                if nb not in visited:
                    fwd_candidates.append(nb)
        if fwd_candidates:
            out_degs  = np.array([len(cites.get(nb, set())) for nb in fwd_candidates])
            threshold = np.percentile(out_degs, pareto_p)
            for nb, od in zip(fwd_candidates, out_degs):
                if od <= threshold and nb not in visited:
                    visited.add(nb); nxt.add(nb)

        frontier  = nxt
        new_nodes = len(visited) - prev_size
        new_gold  = len(visited & gold_refs) - prev_gold
        sy        = new_gold / new_nodes if new_nodes > 0 else 0.0

        tp     = len(visited & gold_refs)
        recall = tp / len(gold_refs) if gold_refs else 0.0

        curve.append({
            "depth":        d,
            "corpus_size":  len(visited),
            "recall":       recall,
            "tp":           tp,
            "new_nodes":    new_nodes,
            "new_gold":     new_gold,
            "screen_yield": sy,
        })

        if sy < yield_thresh and d >= 2:
            stop_depth = d
            break
        if not frontier:
            stop_depth = d
            break

    return visited, curve, stop_depth


# ── Seed generation strategies (unchanged from 04) ───────────────────────────
def make_seeds_top_k(gold_refs, k, cited_by_map):
    """Top-k gold refs by in-degree (best-case search result)."""
    scored = sorted(gold_refs, key=lambda x: len(cited_by_map.get(x, set())), reverse=True)
    return set(scored[:k])

def make_seeds_random(gold_refs, k, rng=None):
    """Random k gold refs (average-case search)."""
    pool = list(gold_refs)
    if rng:
        rng.shuffle(pool)
    else:
        random.shuffle(pool)
    return set(pool[:k])

def make_seeds_contaminated(gold_refs, all_nodes, k, contamination=0.5, rng=None):
    """k/2 gold refs + k/2 random non-gold papers (noisy search)."""
    k_good    = max(1, int(k * (1 - contamination)))
    k_bad     = k - k_good
    pool_good = list(gold_refs)
    pool_bad  = list(all_nodes - gold_refs)
    if rng:
        rng.shuffle(pool_good); rng.shuffle(pool_bad)
    else:
        random.shuffle(pool_good); random.shuffle(pool_bad)
    return set(pool_good[:k_good]) | set(pool_bad[:k_bad])


# ── Escape Hatch loop (unchanged from 04) ────────────────────────────────────
def escape_hatch_loop(seed_set, gold_refs, all_nodes, n_rounds=3, k_escape=20,
                      pareto_p=PARETO_P, yield_thresh=YIELD_THRESHOLD):
    """
    Multi-round Escape Hatch simulation.

    Round 1: Traverse from seed_set until yield drops.
    Round N: From the newly included papers (gold_refs found so far),
             pick k_escape new seeds from their neighbourhood that haven't
             been visited yet, and traverse again.

    Returns list of round-level stats.
    """
    visited       = set()
    rounds        = []
    current_seeds = set(seed_set)

    for r in range(1, n_rounds + 1):
        visited_before = len(visited)
        gold_before    = len(visited & gold_refs)

        visited, curve, stop_d = bidir_pareto_traversal(
            current_seeds, gold_refs,
            visited_already=visited,
            pareto_p=pareto_p,
            yield_thresh=yield_thresh,
        )

        recall = len(visited & gold_refs) / len(gold_refs)
        rounds.append({
            "round":       r,
            "corpus_size": len(visited),
            "recall":      recall,
            "tp":          len(visited & gold_refs),
            "new_nodes":   len(visited) - visited_before,
            "new_gold":    len(visited & gold_refs) - gold_before,
            "stop_depth":  stop_d,
            "curve":       curve,
        })

        if recall >= 1.0:
            break

        # Escape Hatch: find new seeds from the neighbourhood of included papers
        included          = visited & gold_refs
        escape_candidates = set()
        for p in included:
            for nb in cites.get(p, set()):
                if nb not in visited:
                    escape_candidates.add(nb)
            for nb in cited_by.get(p, set()):
                if nb not in visited:
                    escape_candidates.add(nb)

        if not escape_candidates:
            break

        escape_sorted = sorted(escape_candidates,
                               key=lambda x: len(cited_by.get(x, set())), reverse=True)
        current_seeds = set(escape_sorted[:k_escape])

    return rounds


# ── Run experiments ────────────────────────────────────────────────────────────
print("\nRunning cold-start experiments (low-seed extension)...")

all_nodes = set(cites.keys()) | set(cited_by.keys())

# Extended seed range: 2–6 are the new realistic values; 10 and 20 are anchors
SEED_SIZES_LOW    = [2, 3, 4, 5, 6]
SEED_SIZES_ANCHOR = [10, 20]
SEED_SIZES        = SEED_SIZES_LOW + SEED_SIZES_ANCHOR
N_ROUNDS          = 4
K_ESCAPE          = 20

all_results = {}

for key, info in gt.items():
    doi       = info["doi"]
    gold_refs = set(info["gold_refs"])
    print(f"\n  {key} ({doi}) | gold_refs={len(gold_refs)}")

    res = {"top_k": {}, "random": {}, "contaminated": {}}

    for k in SEED_SIZES:
        # --- Top-k seeds (best case) ---
        seeds_top  = make_seeds_top_k(gold_refs, k, cited_by)
        rounds_top = escape_hatch_loop(seeds_top, gold_refs, all_nodes,
                                       n_rounds=N_ROUNDS, k_escape=K_ESCAPE)
        res["top_k"][k] = rounds_top
        print(f"    k={k:2d} top-k:        recall={rounds_top[-1]['recall']:.3f} "
              f"after {len(rounds_top)} rounds, corpus={rounds_top[-1]['corpus_size']:,}")

        # --- Random seeds (average case) ---
        seeds_rand  = make_seeds_random(gold_refs, k)
        rounds_rand = escape_hatch_loop(seeds_rand, gold_refs, all_nodes,
                                        n_rounds=N_ROUNDS, k_escape=K_ESCAPE)
        res["random"][k] = rounds_rand
        print(f"    k={k:2d} random:       recall={rounds_rand[-1]['recall']:.3f} "
              f"after {len(rounds_rand)} rounds, corpus={rounds_rand[-1]['corpus_size']:,}")

        # --- Contaminated seeds (noisy case, 50% irrelevant) ---
        seeds_cont  = make_seeds_contaminated(gold_refs, all_nodes, k, contamination=0.5)
        rounds_cont = escape_hatch_loop(seeds_cont, gold_refs, all_nodes,
                                        n_rounds=N_ROUNDS, k_escape=K_ESCAPE)
        res["contaminated"][k] = rounds_cont
        print(f"    k={k:2d} contaminated: recall={rounds_cont[-1]['recall']:.3f} "
              f"after {len(rounds_cont)} rounds, corpus={rounds_cont[-1]['corpus_size']:,}")

    all_results[key] = res

# Serialise (strip numpy types)
def to_serialisable(obj):
    if isinstance(obj, dict):
        return {k: to_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_serialisable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj

out_json = OUT / "cold_start_results_lowseed.json"
with open(out_json, "w") as f:
    json.dump(to_serialisable(all_results), f, indent=2)
print(f"\nSaved results to {out_json}")


# ── Plotting ──────────────────────────────────────────────────────────────────
print("Generating figures...")

# ── Fig A: Per-round recall for each low-seed k value (one panel per survey) ──
# One figure per k in the low-seed range, mirroring the original fig5 style.
for k_plot in SEED_SIZES_LOW:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    seed_styles = {
        "top_k":        {"color": "#1b7837", "ls": "-",  "lw": 2.0, "marker": "o",
                         "label": f"Top-{k_plot} by citation count (best-case)"},
        "random":       {"color": "#762a83", "ls": "--", "lw": 2.0, "marker": "s",
                         "label": f"{k_plot} random gold refs (avg-case)"},
        "contaminated": {"color": "#d73027", "ls": ":",  "lw": 2.0, "marker": "^",
                         "label": f"{k_plot} seeds, 50% irrelevant (noisy)"},
    }
    for ax, (key, info) in zip(axes, gt.items()):
        res = all_results[key]
        s   = SURVEY_STYLE[key]
        for seed_type, sty in seed_styles.items():
            rounds = res[seed_type].get(k_plot, [])
            if not rounds:
                continue
            xs = [r["round"] for r in rounds]
            ys = [r["recall"] for r in rounds]
            ax.plot(xs, ys, color=sty["color"], ls=sty["ls"], lw=sty["lw"],
                    marker=sty["marker"], ms=6, label=sty["label"])
        ax.axhline(1.0, color="grey", lw=0.8, ls=":")
        ax.set_xlabel("Escape Hatch round")
        ax.set_ylabel("Recall (gold refs)")
        ax.set_title(s["label"], fontsize=9)
        ax.set_ylim(0, 1.08)
        ax.set_xticks(range(1, N_ROUNDS + 1))
    handles, labels_leg = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels_leg, loc="lower center", ncol=3, fontsize=8,
               bbox_to_anchor=(0.5, -0.05))
    fig.suptitle(f"Cold-Start Recall per Escape Hatch Round (k={k_plot} initial seeds)", fontsize=12)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(FIGS / f"cold_start_recall_k{k_plot}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved cold_start_recall_k{k_plot}.png")

# ── Fig B: Recall vs. seed size (full range 2–20, final recall after N rounds) ─
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
seed_styles_simple = {
    "top_k":        {"color": "#1b7837", "ls": "-",  "lw": 2.0, "marker": "o", "label": "Top-k (best-case)"},
    "random":       {"color": "#762a83", "ls": "--", "lw": 2.0, "marker": "s", "label": "Random (avg-case)"},
    "contaminated": {"color": "#d73027", "ls": ":",  "lw": 2.0, "marker": "^", "label": "Contaminated (noisy)"},
}
for ax, (key, info) in zip(axes, gt.items()):
    res = all_results[key]
    s   = SURVEY_STYLE[key]
    for seed_type, sty in seed_styles_simple.items():
        xs = sorted(res[seed_type].keys())
        ys = [res[seed_type][k][-1]["recall"] for k in xs]
        ax.plot(xs, ys, color=sty["color"], ls=sty["ls"], lw=sty["lw"],
                marker=sty["marker"], ms=6, label=sty["label"])
    ax.axhline(1.0, color="grey", lw=0.8, ls=":")
    ax.set_xlabel("Initial seed size k")
    ax.set_ylabel(f"Final recall (after {N_ROUNDS} rounds)")
    ax.set_title(s["label"], fontsize=9)
    ax.set_ylim(0, 1.08)
    ax.set_xticks(SEED_SIZES)
    # Shade the realistic user zone
    ax.axvspan(2, 6, alpha=0.07, color="#f46d43", label="Typical user range (k=2–6)")
handles, labels_leg = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=4, fontsize=9,
           bbox_to_anchor=(0.5, -0.05))
fig.suptitle(f"Final Recall vs. Seed Size (after {N_ROUNDS} Escape Hatch rounds)\nShaded region = typical user seed range",
             fontsize=12)
fig.tight_layout(rect=[0, 0.08, 1, 1])
fig.savefig(FIGS / "cold_start_recall_vs_seed_size_extended.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved cold_start_recall_vs_seed_size_extended.png")

# ── Fig C: Summary heatmap — final recall by (survey × seed size), top-k only ─
# Rows = surveys, Columns = seed sizes, cell = final recall
import matplotlib.colors as mcolors

survey_keys   = list(gt.keys())
survey_labels = [SURVEY_STYLE[k]["label"].split(":")[1].strip() for k in survey_keys]
recall_matrix = np.array([
    [all_results[key]["top_k"][k][-1]["recall"] for k in SEED_SIZES]
    for key in survey_keys
])

fig, ax = plt.subplots(figsize=(10, 3.5))
cmap = plt.cm.RdYlGn
im   = ax.imshow(recall_matrix, cmap=cmap, vmin=0.80, vmax=1.0, aspect="auto")
ax.set_xticks(range(len(SEED_SIZES)))
ax.set_xticklabels([f"k={k}" for k in SEED_SIZES])
ax.set_yticks(range(len(survey_keys)))
ax.set_yticklabels(survey_labels, fontsize=9)
ax.set_xlabel("Initial seed size")
ax.set_title(f"Final Recall (top-k seeds, after {N_ROUNDS} rounds)\nColour scale: 80% → 100%", fontsize=11)

# Annotate cells
for i in range(len(survey_keys)):
    for j in range(len(SEED_SIZES)):
        val = recall_matrix[i, j]
        text_color = "black" if val > 0.88 else "white"
        ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                fontsize=9, color=text_color, fontweight="bold")

# Draw a vertical line between k=6 and k=10 to mark the realistic-user boundary
ax.axvline(x=len(SEED_SIZES_LOW) - 0.5, color="black", lw=2, ls="--")
ax.text(len(SEED_SIZES_LOW) - 0.5, -0.7, "← typical users | anchors →",
        ha="center", va="top", fontsize=8, color="black")

plt.colorbar(im, ax=ax, label="Recall", fraction=0.03, pad=0.04)
fig.tight_layout()
fig.savefig(FIGS / "cold_start_recall_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved cold_start_recall_heatmap.png")

# ── Fig D: Round-by-round recall for k=2 and k=5 side-by-side (all 3 surveys) ─
# Shows how many rounds are needed to converge from the hardest starting points.
fig, axes = plt.subplots(2, 3, figsize=(15, 9), sharey=True)
for col, (key, info) in enumerate(gt.items()):
    res = all_results[key]
    s   = SURVEY_STYLE[key]
    for row, k_plot in enumerate([2, 5]):
        ax = axes[row][col]
        for seed_type, sty in seed_styles_simple.items():
            rounds = res[seed_type].get(k_plot, [])
            if not rounds:
                continue
            xs = [r["round"] for r in rounds]
            ys = [r["recall"] for r in rounds]
            ax.plot(xs, ys, color=sty["color"], ls=sty["ls"], lw=2,
                    marker=sty["marker"], ms=6, label=sty["label"])
        ax.axhline(1.0, color="grey", lw=0.8, ls=":")
        ax.set_ylim(0, 1.08)
        ax.set_xticks(range(1, N_ROUNDS + 1))
        ax.set_xlabel("Escape Hatch round")
        ax.set_ylabel("Recall")
        title_prefix = f"k={k_plot} | "
        ax.set_title(title_prefix + s["label"], fontsize=8)

handles, labels_leg = axes[0][0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=3, fontsize=9,
           bbox_to_anchor=(0.5, -0.03))
fig.suptitle("Recall Convergence from Ultra-Cold Start (k=2 vs k=5 seeds)", fontsize=13)
fig.tight_layout(rect=[0, 0.06, 1, 1])
fig.savefig(FIGS / "cold_start_recall_k2_vs_k5.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved cold_start_recall_k2_vs_k5.png")

print(f"\nAll figures saved to {FIGS}")
print("Done.")
