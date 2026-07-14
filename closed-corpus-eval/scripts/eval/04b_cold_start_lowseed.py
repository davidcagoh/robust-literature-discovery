"""
Cold-Start Escape Hatch Simulation — Low-Seed and Full-Coverage Regime
(canonical experiment — this is the paper's primary result)

**Promoted to canonical 2026-07-14**, superseding the original
04b_cold_start_lowseed.py (archived as 04b_cold_start_lowseed_legacy.py).
k in {1,2,3,4,5,10} seeds, N_ROUNDS=2, top-k/random/contaminated seed
strategies, per-round Escape Hatch loop — same experimental design as the
legacy script, but the traversal engine itself is now the real production
code: litdiscover.discovery.traverse.backward_traversal_operator /
forward_traversal_operator / pareto_hub_threshold, run against a
ClosedCorpusSource (see _corpus_loader.py) instead of a hand-rolled
standalone bidir_traversal(). See wiki/litdiscover/phase-discovery-roadmap.md
§1.3 for the full account of why this repo's closed-corpus and live-S2
tracks can now share one operator implementation.

The one substantive behavioural change from the legacy script: the Pareto
hub filter now applies where production applies it — pre-expansion, on a
FRONTIER paper's own in-degree (citation_count), via
pareto_hub_threshold()'s Gini-calibrated percentile — rather than the
legacy script's post-hoc filter on already-collected CITERS' own
out-degree, which could discard a genuine gold paper purely for having a
high out-degree itself (a property unrelated to relevance). Full 54-condition
comparison (2026-07-14): mean recall 93.5% (legacy) -> 99.6% (this script),
mean corpus size 205,021 -> 66,023 (3.1x smaller); one legible trade-off in
contaminated-seed/low-k conditions (small recall decreases, 1.9-4.9pp) from
less indiscriminate exploration within the fixed 2-round budget. See the
legacy script's docstring and wiki §1.3 for the full write-up.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import random

sys.path.insert(0, str(Path(__file__).parent.parent))
from _corpus_loader import load_adjacency, build_closed_corpus_source  # noqa: E402

from litdiscover.discovery.traverse import (
    backward_traversal_operator, forward_traversal_operator, pareto_hub_threshold,
)

random.seed(42)
np.random.seed(42)

_REPO = Path(__file__).parent.parent.parent
OUT = _REPO / "data" / "outputs"
FIGS = OUT / "figures_lowseed"
OUT.mkdir(parents=True, exist_ok=True)
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

PARETO_P = 80
YIELD_THRESHOLD = 0.05
MAX_DEPTH = 8
SEED_SIZES = [1, 2, 3, 4, 5, 10]
N_ROUNDS = 2
K_ESCAPE = 20


# ── Traversal engine — delegates to real production operators ─────────────

def bidir_traversal(seed_dois, gold_refs, source, doi_to_paper,
                     visited_already=None, pareto_p=PARETO_P,
                     yield_thresh=YIELD_THRESHOLD, max_depth=MAX_DEPTH):
    """
    Bidirectional BFS with yield-based stopping, same per-depth shape as the
    legacy script's bidir_traversal(), but each depth step delegates to the
    real litdiscover production operators (backward_traversal_operator,
    forward_traversal_operator, pareto_hub_threshold) via a
    ClosedCorpusSource, instead of touching cites/cited_by directly.
    """
    visited = set(visited_already) if visited_already else set()
    for s in seed_dois:
        visited.add(s)
    frontier_dois = set(seed_dois) - (visited_already or set())
    if not frontier_dois:
        frontier_dois = set(seed_dois)

    curve = []
    stop_depth = max_depth

    for d in range(1, max_depth + 1):
        prev_size = len(visited)
        prev_gold = len(visited & gold_refs)

        frontier_papers = [doi_to_paper[doi] for doi in frontier_dois if doi in doi_to_paper]
        if not frontier_papers:
            stop_depth = d
            break

        bwd = backward_traversal_operator(frontier_papers, source=source)

        if pareto_p is not None:
            threshold, hub_pct, _ = pareto_hub_threshold(frontier_papers, base_percentile=pareto_p)
        else:
            threshold = float("inf")
        fwd = forward_traversal_operator(frontier_papers, hub_threshold=threshold, source=source)

        nxt = set()
        for cand in bwd.candidates + fwd.candidates:
            doi = cand.get("doi")
            if doi and doi not in visited:
                visited.add(doi)
                nxt.add(doi)

        frontier_dois = nxt
        new_nodes = len(visited) - prev_size
        new_gold = len(visited & gold_refs) - prev_gold
        sy = new_gold / new_nodes if new_nodes > 0 else 0.0
        tp = len(visited & gold_refs)
        recall = tp / len(gold_refs) if gold_refs else 0.0

        curve.append({
            "depth": d, "corpus_size": len(visited), "recall": recall,
            "tp": tp, "new_nodes": new_nodes, "new_gold": new_gold,
            "screen_yield": sy,
        })

        if sy < yield_thresh and d >= 2:
            stop_depth = d
            break
        if not frontier_dois:
            stop_depth = d
            break

    return visited, curve, stop_depth


# ── Seed generation strategies (unchanged) ─────────────────────────────────

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
    k_bad = k - k_good
    pool_good = list(gold_refs)
    pool_bad = list(all_nodes - gold_refs)
    if rng:
        rng.shuffle(pool_good); rng.shuffle(pool_bad)
    else:
        random.shuffle(pool_good); random.shuffle(pool_bad)
    return set(pool_good[:k_good]) | set(pool_bad[:k_bad])


# ── Escape Hatch loop ────────────────────────────────────────────────────

def escape_hatch_loop(seed_set, gold_refs, all_nodes, source, doi_to_paper,
                       cites, cited_by, n_rounds=2, k_escape=20,
                       pareto_p=PARETO_P, yield_thresh=YIELD_THRESHOLD):
    """
    Multi-round Escape Hatch simulation. Round 1 traverses from seed_set
    until yield drops; round N picks k_escape new seeds from the
    neighbourhood of papers found so far and traverses again.
    """
    visited = set()
    rounds = []
    current_seeds = set(seed_set)

    for r in range(1, n_rounds + 1):
        visited_before = len(visited)
        gold_before = len(visited & gold_refs)

        visited, curve, stop_d = bidir_traversal(
            current_seeds, gold_refs, source, doi_to_paper,
            visited_already=visited, pareto_p=pareto_p, yield_thresh=yield_thresh,
        )

        recall = len(visited & gold_refs) / len(gold_refs) if gold_refs else 0.0
        rounds.append({
            "round": r, "corpus_size": len(visited), "recall": recall,
            "tp": len(visited & gold_refs), "new_nodes": len(visited) - visited_before,
            "new_gold": len(visited & gold_refs) - gold_before,
            "stop_depth": stop_d, "curve": curve,
        })

        if recall >= 1.0:
            break

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

        escape_sorted = sorted(escape_candidates,
                                key=lambda x: len(cited_by.get(x, set())), reverse=True)
        current_seeds = set(escape_sorted[:k_escape])

    return rounds


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


def run_experiments(seed_sizes=SEED_SIZES):
    print("Loading APS citation graph via shared _corpus_loader...")
    t0 = time.monotonic()
    cites, cited_by = load_adjacency()
    print(f"  Adjacency built in {time.monotonic() - t0:.1f}s")

    source, doi_to_paper = build_closed_corpus_source(cites, cited_by)

    with open(OUT / "ground_truth.json") as f:
        gt = json.load(f)

    all_nodes = set(cites.keys()) | set(cited_by.keys())

    print("\nRunning cold-start experiments (production-operator engine)...")
    all_results = {}

    for key, info in gt.items():
        doi = info["doi"]
        gold_refs = set(info["gold_refs"])
        print(f"\n  {key} ({doi}) | gold_refs={len(gold_refs)}")

        res = {"top_k": {}, "random": {}, "contaminated": {}}

        for k in seed_sizes:
            t_k = time.monotonic()
            seeds_top = make_seeds_top_k(gold_refs, k, cited_by)
            rounds_top = escape_hatch_loop(
                seeds_top, gold_refs, all_nodes, source, doi_to_paper,
                cites, cited_by, n_rounds=N_ROUNDS, k_escape=K_ESCAPE,
            )
            res["top_k"][k] = rounds_top
            print(f"    k={k:2d} top-k:        recall={rounds_top[-1]['recall']:.3f} "
                  f"after {len(rounds_top)} rounds, corpus={rounds_top[-1]['corpus_size']:,} "
                  f"({time.monotonic() - t_k:.1f}s)")

            seeds_rand = make_seeds_random(gold_refs, k)
            rounds_rand = escape_hatch_loop(
                seeds_rand, gold_refs, all_nodes, source, doi_to_paper,
                cites, cited_by, n_rounds=N_ROUNDS, k_escape=K_ESCAPE,
            )
            res["random"][k] = rounds_rand
            print(f"    k={k:2d} random:       recall={rounds_rand[-1]['recall']:.3f} "
                  f"after {len(rounds_rand)} rounds, corpus={rounds_rand[-1]['corpus_size']:,}")

            seeds_cont = make_seeds_contaminated(gold_refs, all_nodes, k, contamination=0.5)
            rounds_cont = escape_hatch_loop(
                seeds_cont, gold_refs, all_nodes, source, doi_to_paper,
                cites, cited_by, n_rounds=N_ROUNDS, k_escape=K_ESCAPE,
            )
            res["contaminated"][k] = rounds_cont
            print(f"    k={k:2d} contaminated: recall={rounds_cont[-1]['recall']:.3f} "
                  f"after {len(rounds_cont)} rounds, corpus={rounds_cont[-1]['corpus_size']:,}")

        all_results[key] = res

    out_json = OUT / "cold_start_results_lowseed.json"
    with open(out_json, "w") as f:
        json.dump(to_serialisable(all_results), f, indent=2)
    print(f"\nSaved results to {out_json}")
    return all_results, gt


# ── Plotting ────────────────────────────────────────────────────────────

def make_figures(all_results, gt):
    print("Generating figures...")

    for k_plot in [k for k in SEED_SIZES if k <= 5]:
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
            s = SURVEY_STYLE[key]
            for seed_type, sty in seed_styles.items():
                rounds = res[seed_type].get(k_plot) or res[seed_type].get(str(k_plot), [])
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

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    seed_styles_simple = {
        "top_k":        {"color": "#1b7837", "ls": "-",  "lw": 2.0, "marker": "o", "label": "Top-k (best-case)"},
        "random":       {"color": "#762a83", "ls": "--", "lw": 2.0, "marker": "s", "label": "Random (avg-case)"},
        "contaminated": {"color": "#d73027", "ls": ":",  "lw": 2.0, "marker": "^", "label": "Contaminated (noisy)"},
    }
    for ax, (key, info) in zip(axes, gt.items()):
        res = all_results[key]
        s = SURVEY_STYLE[key]
        for seed_type, sty in seed_styles_simple.items():
            xs = sorted(res[seed_type].keys(), key=int)
            ys = [res[seed_type][k][-1]["recall"] for k in xs]
            xs_int = [int(x) for x in xs]
            ax.plot(xs_int, ys, color=sty["color"], ls=sty["ls"], lw=sty["lw"],
                    marker=sty["marker"], ms=6, label=sty["label"])
        ax.axhline(1.0, color="grey", lw=0.8, ls=":")
        ax.set_xlabel("Initial seed size k")
        ax.set_ylabel(f"Final recall (after {N_ROUNDS} rounds)")
        ax.set_title(s["label"], fontsize=9)
        ax.set_ylim(0, 1.08)
        ax.set_xticks(SEED_SIZES)
        ax.axvspan(1, 5, alpha=0.07, color="#f46d43", label="Typical user range (k=1–5)")
    handles, labels_leg = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels_leg, loc="lower center", ncol=4, fontsize=9,
               bbox_to_anchor=(0.5, -0.05))
    fig.suptitle(f"Final Recall vs. Seed Size (after {N_ROUNDS} Escape Hatch rounds)\nShaded region = typical user seed range",
                 fontsize=12)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(FIGS / "cold_start_recall_vs_seed_size_extended.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved cold_start_recall_vs_seed_size_extended.png")

    survey_keys = list(gt.keys())
    survey_labels = [SURVEY_STYLE[k]["label"].split(":")[1].strip() for k in survey_keys]
    recall_matrix = np.array([
        [all_results[key]["top_k"][str(k) if str(k) in all_results[key]["top_k"] else k][-1]["recall"]
         for k in SEED_SIZES]
        for key in survey_keys
    ])

    fig, ax = plt.subplots(figsize=(10, 3.5))
    cmap = plt.cm.RdYlGn
    im = ax.imshow(recall_matrix, cmap=cmap, vmin=0.80, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(SEED_SIZES)))
    ax.set_xticklabels([f"k={k}" for k in SEED_SIZES])
    ax.set_yticks(range(len(survey_keys)))
    ax.set_yticklabels(survey_labels, fontsize=9)
    ax.set_xlabel("Initial seed size")
    ax.set_title(f"Final Recall (top-k seeds, after {N_ROUNDS} rounds)\nColour scale: 80% → 100%", fontsize=11)

    for i in range(len(survey_keys)):
        for j in range(len(SEED_SIZES)):
            val = recall_matrix[i, j]
            text_color = "black" if val > 0.88 else "white"
            ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                    fontsize=9, color=text_color, fontweight="bold")

    ax.axvline(x=SEED_SIZES.index(10) - 0.5, color="black", lw=2, ls="--")
    ax.text(SEED_SIZES.index(10) - 0.5, -0.7, "← typical users | full-coverage →",
            ha="center", va="top", fontsize=8, color="black")

    plt.colorbar(im, ax=ax, label="Recall", fraction=0.03, pad=0.04)
    fig.tight_layout()
    fig.savefig(FIGS / "cold_start_recall_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved cold_start_recall_heatmap.png")

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), sharey=True)
    for col, (key, info) in enumerate(gt.items()):
        res = all_results[key]
        s = SURVEY_STYLE[key]
        for row, k_plot in enumerate([2, 5]):
            ax = axes[row][col]
            for seed_type, sty in seed_styles_simple.items():
                rounds = res[seed_type].get(k_plot) or res[seed_type].get(str(k_plot), [])
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
            ax.set_title(f"k={k_plot} | " + s["label"], fontsize=8)

    handles, labels_leg = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels_leg, loc="lower center", ncol=3, fontsize=9,
               bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Recall Convergence from Ultra-Cold Start (k=2 vs k=5 seeds)", fontsize=13)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(FIGS / "cold_start_recall_k2_vs_k5.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved cold_start_recall_k2_vs_k5.png")

    print(f"\nAll figures saved to {FIGS}")


def main(seed_sizes=SEED_SIZES):
    all_results, gt = run_experiments(seed_sizes=seed_sizes)
    if seed_sizes == SEED_SIZES:
        make_figures(all_results, gt)
    else:
        print("(quick run — skipping figure generation, which expects the full seed-size range)")
    return all_results


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    main(seed_sizes=[1, 2, 5] if quick else SEED_SIZES)
    print("Done.")
