"""
Phase 4: Simulate traversal strategies on the APS citation graph and measure
coverage of the gold reference set at each step.

**Traversal engine updated 2026-07-14** to call litdiscover's real production
operators (backward_traversal_operator, forward_traversal_operator) via a
ClosedCorpusSource, instead of hand-rolled BFS loops over cites/cited_by
directly — see wiki/litdiscover/phase-discovery-roadmap.md §1.3 and
04b_cold_start_lowseed.py's own migration for the fuller account.

One deliberate design choice, different from 04b's migration: this script's
whole point is an explicit Pareto-PERCENTILE SWEEP (10..90) as a controlled
experimental variable. Production's pareto_hub_threshold() applies a
Gini-adaptive override (relaxing to 90th/95th percentile for lower-Gini
frontiers) that would silently overrule some of the requested sweep values —
defeating the sweep's purpose. So this script computes each percentile
threshold directly (np.percentile over the FRONTIER's own citation_count,
matching production's pre-expansion filter POINT — see below) and passes it
straight to forward_traversal_operator's hub_threshold, bypassing
pareto_hub_threshold()'s Gini calibration. The actual candidate-fetching and
filtering MECHANICS still come from the real production operator; only the
threshold-selection policy is swapped for the sweep's sake.

This also corrects the same filter-point issue 04b's migration corrected:
the legacy version of this script (percentile applied post-hoc to collected
CITERS' own out-degree) is replaced with production's pre-expansion filter
on the FRONTIER paper's own citation_count (in-degree within this closed
corpus). Expect different numbers from any previously-committed run of this
script for the same reason 04b's numbers changed.

Strategies compared (all seeded with top-5 gold refs by in-degree — NOT the survey DOI):
  A. Backward-only BFS (follow references, depth 1..6)
  B. Forward-only BFS  (follow citations,  depth 1..6)
  C. Bidirectional BFS (both directions simultaneously, depth 1..6)
  D. Bidirectional + Pareto filter on forward step
       — at each depth, suppress FRONTIER papers (not collected candidates)
         whose own citation_count exceeds the p-th percentile of the current
         frontier's citation_counts — tested at p = 10..90.

For each strategy × survey × depth we record:
  - corpus_size:  total nodes visited so far (cost)
  - recall_refs:  fraction of gold_refs recovered
  - recall_1hop:  fraction of gold_1hop recovered
  - precision:    gold_refs ∩ visited / visited  (how many visited are relevant)
  - f1:           harmonic mean of recall_refs and precision

Results saved to data/outputs/traversal_results.json
Figures saved to data/outputs/figures/
"""
from __future__ import annotations

import json
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from _corpus_loader import load_adjacency, build_closed_corpus_source  # noqa: E402

from litdiscover.discovery.traverse import (
    backward_traversal_operator, forward_traversal_operator,
)

# ── Setup ─────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).parent.parent.parent
OUT  = _REPO / "data" / "outputs"
FIGS = OUT / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

STYLE = {
    "S1_MIT":  {"color": "#2166ac", "label": "S1: Metal-insulator transitions (1998)"},
    "S2_UCG":  {"color": "#d6604d", "label": "S2: Ultracold gases (2008)"},
    "S3_TOPO": {"color": "#4dac26", "label": "S3: Topological photonics (2019)"},
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

MAX_DEPTH = 6
PARETO_PERCENTILES = [10, 20, 30, 40, 50, 70, 80, 90]

# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading APS citation graph via shared _corpus_loader...")
cites, cited_by = load_adjacency()
print(f"  {sum(len(v) for v in cites.values()):,} edges")

source, doi_to_paper = build_closed_corpus_source(cites, cited_by)

with open(OUT / "ground_truth.json") as f:
    gt = json.load(f)


# ── Helper: compute metrics ───────────────────────────────────────────────────
def metrics(visited, gold_refs, gold_1hop):
    tp_refs  = len(visited & gold_refs)
    tp_1hop  = len(visited & gold_1hop)
    rec_refs = tp_refs / len(gold_refs)  if gold_refs else 0.0
    rec_1hop = tp_1hop / len(gold_1hop) if gold_1hop else 0.0
    prec     = tp_refs / len(visited)   if visited   else 0.0
    f1       = 2*rec_refs*prec/(rec_refs+prec) if (rec_refs+prec) > 0 else 0.0
    return {
        "corpus_size": len(visited),
        "recall_refs": rec_refs,
        "recall_1hop": rec_1hop,
        "precision":   prec,
        "f1":          f1,
        "tp_refs":     tp_refs,
        "tp_1hop":     tp_1hop,
    }


def _frontier_papers(frontier_dois):
    return [doi_to_paper[doi] for doi in frontier_dois if doi in doi_to_paper]


# ── Strategy A: Backward-only BFS (real backward_traversal_operator) ──────────
def strategy_backward(seed_set, gold_refs, gold_1hop, max_depth=MAX_DEPTH):
    visited  = set(seed_set)
    frontier = set(seed_set)
    curve = [{"depth": 0, **metrics(visited, gold_refs, gold_1hop)}]
    for d in range(1, max_depth + 1):
        bwd = backward_traversal_operator(_frontier_papers(frontier), source=source)
        nxt = set()
        for cand in bwd.candidates:
            doi = cand.get("doi")
            if doi and doi not in visited:
                visited.add(doi); nxt.add(doi)
        frontier = nxt
        curve.append({"depth": d, **metrics(visited, gold_refs, gold_1hop)})
        if not frontier:
            break
    return curve


# ── Strategy B: Forward-only BFS (real forward_traversal_operator, unfiltered) ─
def strategy_forward(seed_set, gold_refs, gold_1hop, max_depth=MAX_DEPTH):
    visited  = set(seed_set)
    frontier = set(seed_set)
    curve = [{"depth": 0, **metrics(visited, gold_refs, gold_1hop)}]
    for d in range(1, max_depth + 1):
        fwd = forward_traversal_operator(_frontier_papers(frontier),
                                          hub_threshold=float("inf"), source=source)
        nxt = set()
        for cand in fwd.candidates:
            doi = cand.get("doi")
            if doi and doi not in visited:
                visited.add(doi); nxt.add(doi)
        frontier = nxt
        curve.append({"depth": d, **metrics(visited, gold_refs, gold_1hop)})
        if not frontier:
            break
    return curve


# ── Strategy C: Bidirectional BFS (both operators, unfiltered) ────────────────
def strategy_bidir(seed_set, gold_refs, gold_1hop, max_depth=MAX_DEPTH):
    visited  = set(seed_set)
    frontier = set(seed_set)
    curve = [{"depth": 0, **metrics(visited, gold_refs, gold_1hop)}]
    for d in range(1, max_depth + 1):
        papers = _frontier_papers(frontier)
        bwd = backward_traversal_operator(papers, source=source)
        fwd = forward_traversal_operator(papers, hub_threshold=float("inf"), source=source)
        nxt = set()
        for cand in bwd.candidates + fwd.candidates:
            doi = cand.get("doi")
            if doi and doi not in visited:
                visited.add(doi); nxt.add(doi)
        frontier = nxt
        curve.append({"depth": d, **metrics(visited, gold_refs, gold_1hop)})
        if not frontier:
            break
    return curve


# ── Strategy D: Bidirectional + Pareto filter, PRE-expansion on frontier ──────
def strategy_bidir_pareto(seed_set, gold_refs, gold_1hop, percentile=80, max_depth=MAX_DEPTH):
    """
    At each depth:
      - Backward step: real backward_traversal_operator, unfiltered.
      - Forward step:  threshold = np.percentile(frontier's own citation_count,
                       percentile) — computed directly (bypassing Gini
                       calibration, see module docstring) — then real
                       forward_traversal_operator(hub_threshold=threshold),
                       which skips FETCHING citers of any frontier paper
                       above that threshold entirely (production's actual
                       filter point, not a post-hoc filter on already-
                       collected candidates).
    """
    visited  = set(seed_set)
    frontier = set(seed_set)
    curve = [{"depth": 0, **metrics(visited, gold_refs, gold_1hop)}]
    for d in range(1, max_depth + 1):
        papers = _frontier_papers(frontier)
        bwd = backward_traversal_operator(papers, source=source)

        cit_counts = [p["citation_count"] for p in papers if p.get("citation_count") is not None]
        threshold = float(np.percentile(cit_counts, percentile)) if cit_counts else float("inf")
        fwd = forward_traversal_operator(papers, hub_threshold=threshold, source=source)

        nxt = set()
        for cand in bwd.candidates + fwd.candidates:
            doi = cand.get("doi")
            if doi and doi not in visited:
                visited.add(doi); nxt.add(doi)
        frontier = nxt
        curve.append({"depth": d, **metrics(visited, gold_refs, gold_1hop)})
        if not frontier:
            break
    return curve


# ── Run all strategies for all surveys ────────────────────────────────────────
print("\nRunning traversal simulations...")
all_results = {}

for key, info in gt.items():
    doi       = info["doi"]
    gold_refs = set(info["gold_refs"])
    gold_1hop = set(info["gold_1hop"])
    print(f"\n  {key} ({doi})")

    gold_sorted = sorted(gold_refs, key=lambda x: len(cited_by.get(x, set())), reverse=True)
    seed_set    = set(gold_sorted[:5])
    print(f"    Seeds (top-5 by in-degree): {sorted(seed_set)[:3]}...")

    def _d3(curve):
        pt = next((p for p in curve if p["depth"] == 3), curve[-1])
        return pt["recall_refs"], pt["corpus_size"]

    res = {}
    res["backward"] = strategy_backward(seed_set, gold_refs, gold_1hop)
    r, c = _d3(res["backward"])
    print(f"    Backward done. Depth-3 recall_refs={r:.3f}, corpus={c:,}")

    res["forward"]  = strategy_forward(seed_set, gold_refs, gold_1hop)
    r, c = _d3(res["forward"])
    print(f"    Forward  done. Depth-3 recall_refs={r:.3f}, corpus={c:,}")

    res["bidir"]    = strategy_bidir(seed_set, gold_refs, gold_1hop)
    r, c = _d3(res["bidir"])
    print(f"    Bidir    done. Depth-3 recall_refs={r:.3f}, corpus={c:,}")

    for p in PARETO_PERCENTILES:
        k = f"bidir_pareto{p}"
        res[k] = strategy_bidir_pareto(seed_set, gold_refs, gold_1hop, percentile=p)
        r, c = _d3(res[k])
        print(f"    Bidir+Pareto{p} done. Depth-3 recall_refs={r:.3f}, corpus={c:,}")

    all_results[key] = res

with open(OUT / "traversal_results.json", "w") as f:
    json.dump(all_results, f, indent=2)
print(f"\nSaved traversal results to {OUT / 'traversal_results.json'}")

# ── Plotting ──────────────────────────────────────────────────────────────────
print("Generating figures...")

fig, axes = plt.subplots(2, 3, figsize=(15, 9))

strat_styles = {
    "backward":       {"color": "#1b7837", "ls": "-",  "lw": 2.0, "label": "Backward only"},
    "forward":        {"color": "#762a83", "ls": "-",  "lw": 2.0, "label": "Forward only"},
    "bidir":          {"color": "#000000", "ls": "-",  "lw": 2.5, "label": "Bidirectional"},
    "bidir_pareto50": {"color": "#d73027", "ls": "--", "lw": 1.5, "label": "Bidir + Pareto-50"},
    "bidir_pareto70": {"color": "#f46d43", "ls": "--", "lw": 1.5, "label": "Bidir + Pareto-70"},
    "bidir_pareto80": {"color": "#fdae61", "ls": "--", "lw": 1.5, "label": "Bidir + Pareto-80"},
    "bidir_pareto90": {"color": "#fee090", "ls": "--", "lw": 1.5, "label": "Bidir + Pareto-90"},
}

for col, (key, info) in enumerate(gt.items()):
    res = all_results[key]
    s   = STYLE[key]

    for row, metric in enumerate(["recall_refs", "corpus_size"]):
        ax = axes[row][col]
        for strat, style in strat_styles.items():
            if strat not in res:
                continue
            depths = [pt["depth"] for pt in res[strat]]
            vals   = [pt[metric]  for pt in res[strat]]
            ax.plot(depths, vals, color=style["color"], ls=style["ls"],
                    lw=style["lw"], label=style["label"], marker="o", ms=3)

        if row == 0:
            ax.set_title(s["label"], fontsize=9)
            ax.set_ylabel("Recall (gold refs)")
            ax.set_ylim(0, 1.05)
            ax.axhline(1.0, color="grey", lw=0.8, ls=":")
        else:
            ax.set_ylabel("Corpus size (nodes visited)")
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
        ax.set_xlabel("BFS depth")

handles, labels = axes[0][0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
           bbox_to_anchor=(0.5, -0.03))
fig.suptitle("Traversal Strategy Comparison: Recall & Corpus Size vs. BFS Depth", fontsize=12)
fig.tight_layout(rect=[0, 0.05, 1, 1])
fig.savefig(FIGS / "traversal_recall_vs_depth.png", dpi=150, bbox_inches="tight")
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, info) in zip(axes, gt.items()):
    res = all_results[key]
    s   = STYLE[key]
    for strat, style in strat_styles.items():
        if strat not in res:
            continue
        xs = [pt["corpus_size"]  for pt in res[strat]]
        ys = [pt["recall_refs"]  for pt in res[strat]]
        ax.plot(xs, ys, color=style["color"], ls=style["ls"],
                lw=style["lw"], label=style["label"], marker="o", ms=3)
    ax.set_xlabel("Corpus size (nodes visited)")
    ax.set_ylabel("Recall (gold refs)")
    ax.set_title(s["label"], fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.axhline(1.0, color="grey", lw=0.8, ls=":")
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
           bbox_to_anchor=(0.5, -0.03))
fig.suptitle("Coverage Efficiency: Recall vs. Corpus Size (the efficiency frontier)", fontsize=12)
fig.tight_layout(rect=[0, 0.05, 1, 1])
fig.savefig(FIGS / "traversal_efficiency_frontier.png", dpi=150, bbox_inches="tight")
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, info) in zip(axes, gt.items()):
    res = all_results[key]
    s   = STYLE[key]
    for strat, style in strat_styles.items():
        if strat not in res:
            continue
        xs = [pt["recall_refs"] for pt in res[strat]]
        ys = [pt["precision"]   for pt in res[strat]]
        ax.plot(xs, ys, color=style["color"], ls=style["ls"],
                lw=style["lw"], label=style["label"], marker="o", ms=3)
    ax.set_xlabel("Recall (gold refs)")
    ax.set_ylabel("Precision")
    ax.set_title(s["label"], fontsize=9)
    ax.set_xlim(0, 1.05); ax.set_ylim(0, 1.05)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
           bbox_to_anchor=(0.5, -0.03))
fig.suptitle("Precision–Recall Curves by Traversal Strategy", fontsize=12)
fig.tight_layout(rect=[0, 0.05, 1, 1])
fig.savefig(FIGS / "traversal_precision_recall.png", dpi=150, bbox_inches="tight")
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
key_strats = ["backward", "bidir", "bidir_pareto80"]
key_labels = ["Backward only", "Bidirectional", "Bidir + Pareto-80"]
key_colors = ["#1b7837", "#000000", "#fdae61"]
for ax, (key, info) in zip(axes, gt.items()):
    res = all_results[key]
    s   = STYLE[key]
    for strat, label, color in zip(key_strats, key_labels, key_colors):
        if strat not in res:
            continue
        tps = [pt["tp_refs"] for pt in res[strat]]
        marginal = [tps[0]] + [tps[i] - tps[i-1] for i in range(1, len(tps))]
        depths   = [pt["depth"] for pt in res[strat]]
        ax.bar([d + key_strats.index(strat)*0.25 for d in depths],
               marginal, width=0.22, color=color, label=label, alpha=0.85)
    ax.set_xlabel("BFS depth")
    ax.set_ylabel("New gold refs discovered")
    ax.set_title(s["label"], fontsize=9)
handles, labels_leg = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=3, fontsize=9,
           bbox_to_anchor=(0.5, -0.03))
fig.suptitle("Marginal Gold Refs Discovered per BFS Depth Step", fontsize=12)
fig.tight_layout(rect=[0, 0.05, 1, 1])
fig.savefig(FIGS / "traversal_marginal_discovery.png", dpi=150, bbox_inches="tight")
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, info) in zip(axes, gt.items()):
    res = all_results[key]
    s   = STYLE[key]
    for strat, style in strat_styles.items():
        if strat not in res or len(res[strat]) < 2:
            continue
        pts = res[strat]
        depths  = [pts[i]["depth"] for i in range(1, len(pts))]
        yields  = []
        for i in range(1, len(pts)):
            new_nodes = pts[i]["corpus_size"] - pts[i-1]["corpus_size"]
            new_gold  = pts[i]["tp_refs"]     - pts[i-1]["tp_refs"]
            yields.append(new_gold / new_nodes if new_nodes > 0 else 0.0)
        ax.plot(depths, yields, color=style["color"], ls=style["ls"],
                lw=style["lw"], label=style["label"], marker="o", ms=3)
    ax.set_xlabel("BFS depth")
    ax.set_ylabel("Screen yield (new gold / new nodes)")
    ax.set_title(s["label"], fontsize=9)
    ax.set_ylim(0, None)
handles, labels_leg = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=4, fontsize=8,
           bbox_to_anchor=(0.5, -0.03))
fig.suptitle("Screen Yield per BFS Depth Step\n(new gold refs / new nodes — fruitfulness signal)", fontsize=12)
fig.tight_layout(rect=[0, 0.05, 1, 1])
fig.savefig(FIGS / "traversal_screen_yield.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print(f"\nAll figures saved to {FIGS}")
print("Done.")
