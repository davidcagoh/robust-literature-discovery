"""
Phase 6-8: Cold-Start Escape Hatch Simulation
(superseded by eval/04b_cold_start_lowseed.py — see CLAUDE.md; this script's
own output, cold_start_results.json, has never been generated, which leaves
sweep/07_elbow_analysis.py permanently inoperable. Left in place, migrated
for engine consistency, not because it's an active paper-claims script.)

Simulates the LitReview v2 loop starting from keyword search seeds
(no survey paper itself), measuring how well traversal + escape hatch
can recover the gold reference set.

**Traversal engine updated 2026-07-14** to call litdiscover's real production
operators (backward_traversal_operator, forward_traversal_operator,
pareto_hub_threshold) via a ClosedCorpusSource, matching the correction made
in eval/04b_cold_start_lowseed.py, eval/03_traversal_simulation.py, and
sweep/07_rounds_sweep.py — the Pareto filter now applies pre-expansion on the
FRONTIER paper's own citation_count (production's actual filter point), not
post-hoc on collected CITERS' own out-degree. See
wiki/litdiscover/phase-discovery-roadmap.md §1.3. This migration was NOT
followed by a full run (the seed-size/N_ROUNDS regime here — k up to 50,
N_ROUNDS=4 — is expensive at this corpus scale; see the wiki's
"real-world performance finding" note in §1.4) — code correctness was
verified by matching this script's traversal shape line-for-line against
eval/04b's already-validated migration, not by re-running to completion.

See experiment_design.md for full methodology.
"""
from __future__ import annotations

import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
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
FIGS = OUT / "figures"
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
YIELD_THRESHOLD = 0.05   # stop when screen yield drops below 5%
MAX_DEPTH = 8


def bidir_pareto_traversal(seed_set, gold_refs, visited_already=None,
                            pareto_p=PARETO_P, yield_thresh=YIELD_THRESHOLD,
                            max_depth=MAX_DEPTH):
    """
    Bidirectional BFS via real production operators, Pareto filter applied
    pre-expansion on the frontier's own citation_count (see module docstring).
    Stops when screen yield (new gold / new nodes) drops below yield_thresh.

    Returns:
        visited: set of all nodes visited
        curve:   list of dicts with per-depth stats
        stop_depth: depth at which yield threshold was triggered
    """
    visited  = set(visited_already) if visited_already else set()
    for s in seed_set:
        visited.add(s)
    frontier = set(seed_set) - (visited_already or set())
    if not frontier:
        frontier = set(seed_set)

    curve = []
    stop_depth = max_depth

    for d in range(1, max_depth + 1):
        prev_size = len(visited)
        prev_gold = len(visited & gold_refs)

        frontier_papers = [doi_to_paper[doi] for doi in frontier if doi in doi_to_paper]
        if not frontier_papers:
            stop_depth = d
            break

        bwd = backward_traversal_operator(frontier_papers, source=source)
        if pareto_p is not None:
            threshold, _, _ = pareto_hub_threshold(frontier_papers, base_percentile=pareto_p)
        else:
            threshold = float("inf")
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

        tp = len(visited & gold_refs)
        recall = tp / len(gold_refs) if gold_refs else 0.0

        curve.append({
            "depth":       d,
            "corpus_size": len(visited),
            "recall":      recall,
            "tp":          tp,
            "new_nodes":   new_nodes,
            "new_gold":    new_gold,
            "screen_yield": sy,
        })

        if sy < yield_thresh and d >= 2:
            stop_depth = d
            break
        if not frontier:
            stop_depth = d
            break

    return visited, curve, stop_depth


# ── Seed generation strategies ────────────────────────────────────────────────
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
    k_good = max(1, int(k * (1 - contamination)))
    k_bad  = k - k_good
    pool_good = list(gold_refs)
    pool_bad  = list(all_nodes - gold_refs)
    if rng:
        rng.shuffle(pool_good); rng.shuffle(pool_bad)
    else:
        random.shuffle(pool_good); random.shuffle(pool_bad)
    return set(pool_good[:k_good]) | set(pool_bad[:k_bad])


# ── Escape Hatch loop ─────────────────────────────────────────────────────────
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
    visited = set()
    rounds  = []

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
        # that are outside the visited set
        included = visited & gold_refs
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

        # Pick the k_escape highest in-degree candidates (simulate a targeted search)
        escape_sorted = sorted(escape_candidates,
                               key=lambda x: len(cited_by.get(x, set())), reverse=True)
        current_seeds = set(escape_sorted[:k_escape])

    return rounds


# ── Run experiments ────────────────────────────────────────────────────────────
print("\nRunning cold-start experiments...")

all_nodes = set(cites.keys()) | set(cited_by.keys())

SEED_SIZES = [5, 10, 20, 50]
N_ROUNDS   = 4
K_ESCAPE   = 20

all_results = {}

for key, info in gt.items():
    doi       = info["doi"]
    gold_refs = set(info["gold_refs"])
    print(f"\n  {key} ({doi}) | gold_refs={len(gold_refs)}")

    res = {"top_k": {}, "random": {}, "contaminated": {}}

    for k in SEED_SIZES:
        # --- Top-k seeds (best case) ---
        seeds_top = make_seeds_top_k(gold_refs, k, cited_by)
        rounds_top = escape_hatch_loop(seeds_top, gold_refs, all_nodes,
                                       n_rounds=N_ROUNDS, k_escape=K_ESCAPE)
        res["top_k"][k] = rounds_top
        final_recall = rounds_top[-1]["recall"]
        print(f"    k={k:2d} top-k:       recall={final_recall:.3f} after {len(rounds_top)} rounds, corpus={rounds_top[-1]['corpus_size']:,}")

        # --- Random seeds (average case) ---
        seeds_rand = make_seeds_random(gold_refs, k)
        rounds_rand = escape_hatch_loop(seeds_rand, gold_refs, all_nodes,
                                        n_rounds=N_ROUNDS, k_escape=K_ESCAPE)
        res["random"][k] = rounds_rand
        final_recall = rounds_rand[-1]["recall"]
        print(f"    k={k:2d} random:      recall={final_recall:.3f} after {len(rounds_rand)} rounds, corpus={rounds_rand[-1]['corpus_size']:,}")

        # --- Contaminated seeds (noisy case, 50% irrelevant) ---
        seeds_cont = make_seeds_contaminated(gold_refs, all_nodes, k, contamination=0.5)
        rounds_cont = escape_hatch_loop(seeds_cont, gold_refs, all_nodes,
                                        n_rounds=N_ROUNDS, k_escape=K_ESCAPE)
        res["contaminated"][k] = rounds_cont
        final_recall = rounds_cont[-1]["recall"]
        print(f"    k={k:2d} contaminated: recall={final_recall:.3f} after {len(rounds_cont)} rounds, corpus={rounds_cont[-1]['corpus_size']:,}")

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

with open(OUT / "cold_start_results.json", "w") as f:
    json.dump(to_serialisable(all_results), f, indent=2)
print(f"\nSaved cold-start results to {OUT / 'cold_start_results.json'}")


# ── Plotting ──────────────────────────────────────────────────────────────────
print("Generating figures...")

# ── Fig 1: Recall after each round, by seed size and quality (k=10 and k=20) ──
for k_plot in [10, 20]:
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    seed_styles = {
        "top_k":       {"color": "#1b7837", "ls": "-",  "lw": 2.0, "marker": "o", "label": f"Top-{k_plot} by citation count (best-case search)"},
        "random":      {"color": "#762a83", "ls": "--", "lw": 2.0, "marker": "s", "label": f"Random {k_plot} gold refs (avg-case search)"},
        "contaminated":{"color": "#d73027", "ls": ":",  "lw": 2.0, "marker": "^", "label": f"{k_plot} seeds, 50% irrelevant (noisy search)"},
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

# ── Fig 2: Recall vs. seed size (final recall after all rounds) ───────────────
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
handles, labels_leg = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=3, fontsize=9,
           bbox_to_anchor=(0.5, -0.05))
fig.suptitle(f"Final Recall vs. Seed Size (after {N_ROUNDS} Escape Hatch rounds)", fontsize=12)
fig.tight_layout(rect=[0, 0.08, 1, 1])
fig.savefig(FIGS / "cold_start_recall_vs_seed_size.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 3: Corpus size vs. recall (efficiency) for top-k seeds ───────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
cmap = plt.cm.Blues
for ax, (key, info) in zip(axes, gt.items()):
    res = all_results[key]
    s   = SURVEY_STYLE[key]
    for i, k in enumerate(SEED_SIZES):
        rounds = res["top_k"].get(k, [])
        if not rounds:
            continue
        color = cmap(0.4 + 0.6 * i / (len(SEED_SIZES) - 1))
        xs = [r["corpus_size"] for r in rounds]
        ys = [r["recall"]      for r in rounds]
        ax.plot(xs, ys, color=color, lw=2, marker="o", ms=5, label=f"k={k}")
    ax.axhline(1.0, color="grey", lw=0.8, ls=":")
    ax.set_xlabel("Corpus size (nodes visited)")
    ax.set_ylabel("Recall (gold refs)")
    ax.set_title(s["label"], fontsize=9)
    ax.set_ylim(0, 1.08)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
handles, labels_leg = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=4, fontsize=9,
           bbox_to_anchor=(0.5, -0.05))
fig.suptitle("Cold-Start Efficiency: Recall vs. Corpus Size (top-k seeds, per round)", fontsize=12)
fig.tight_layout(rect=[0, 0.08, 1, 1])
fig.savefig(FIGS / "cold_start_efficiency.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 4: Per-round screen yield (depth-level, for k=20 top-k, round 1) ─────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, info) in zip(axes, gt.items()):
    res = all_results[key]
    s   = SURVEY_STYLE[key]
    round_colors = ["#1b7837", "#762a83", "#d73027", "#f46d43"]
    for r_idx, round_data in enumerate(res["top_k"].get(20, [])):
        curve = round_data["curve"]
        depths = [pt["depth"] for pt in curve]
        yields = [pt["screen_yield"] for pt in curve]
        color  = round_colors[r_idx % len(round_colors)]
        ax.plot(depths, yields, color=color, lw=2, marker="o", ms=4,
                label=f"Round {round_data['round']}")
    ax.axhline(YIELD_THRESHOLD, color="black", lw=1, ls="--",
               label=f"Yield threshold ({YIELD_THRESHOLD})")
    ax.set_xlabel("BFS depth within round")
    ax.set_ylabel("Screen yield (new gold / new nodes)")
    ax.set_title(s["label"], fontsize=9)
    ax.set_ylim(0, None)
handles, labels_leg = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=5, fontsize=8,
           bbox_to_anchor=(0.5, -0.05))
fig.suptitle("Screen Yield per Depth per Round (k=20 top-k seeds)\nDashed line = yield threshold that triggers Escape Hatch", fontsize=11)
fig.tight_layout(rect=[0, 0.08, 1, 1])
fig.savefig(FIGS / "cold_start_screen_yield_per_round.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 5: Recall gap (1 - final_recall) vs seed quality, all surveys ─────────
fig, ax = plt.subplots(figsize=(8, 5))
survey_colors = [s["color"] for s in SURVEY_STYLE.values()]
survey_labels = [s["label"] for s in SURVEY_STYLE.values()]
x = np.arange(len(SEED_SIZES))
width = 0.25

for i, (key, info) in enumerate(gt.items()):
    res = all_results[key]
    gaps = [1.0 - res["top_k"][k][-1]["recall"] for k in SEED_SIZES]
    ax.bar(x + i * width, gaps, width, label=SURVEY_STYLE[key]["label"],
           color=SURVEY_STYLE[key]["color"], alpha=0.85)

ax.set_xlabel("Initial seed size k")
ax.set_ylabel(f"Recall gap (1 − recall after {N_ROUNDS} rounds)")
ax.set_title("Residual Coverage Gap after Escape Hatch Loop\n(top-k seeds, best-case search)")
ax.set_xticks(x + width)
ax.set_xticklabels([str(k) for k in SEED_SIZES])
ax.legend(fontsize=8)
ax.set_ylim(0, None)
fig.tight_layout()
fig.savefig(FIGS / "cold_start_recall_gap.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print(f"\nAll figures saved to {FIGS}")
print("Done.")
