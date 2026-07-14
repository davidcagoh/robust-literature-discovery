"""
Hyperparameter Sweep — Cold-Start Escape Hatch Loop

Sweeps PARETO_P × YIELD_THRESHOLD × N_ROUNDS × K_ESCAPE for each of the three
APS survey benchmarks (S1, S2, S3) and records recall + corpus size at the end
of the final round.

Fixed across all configs:
  - Seed strategy: top-k by in-degree (best-case, deterministic — no sampling noise)
  - Seed size: k=5 (canonical operating point)
  - MAX_DEPTH: 8 (safety valve, rarely binds under yield stopping)

Output:
  data/outputs/hyperparameter_sweep.csv   — one row per config × survey
  data/outputs/pub_figures/fig9_param_sweep.png  — summary heatmaps

**Traversal engine updated 2026-07-14** to call litdiscover's real production
operators (backward_traversal_operator, forward_traversal_operator) via a
ClosedCorpusSource, matching eval/03/04b/05 and sweep/04/07_rounds_sweep.py —
see wiki/litdiscover/phase-discovery-roadmap.md §1.3. Same design split as
eval/03: PARETO_P_VALS is an explicit percentile sweep, so each threshold is
computed directly (np.percentile over the frontier's own citation_count,
production's actual pre-expansion filter point) rather than through
pareto_hub_threshold()'s Gini-adaptive override, which would silently
overrule some swept values.

**Not run to completion after this migration — this is a real, not
theoretical, cost concern, flagged rather than silently attempted.** The
original runtime estimate below ("~30-60 min") was measured against the old
dict-lookup traversal. eval/03's migration (33 conditions, unfiltered
strategies included) already took ~30-40 min against the production
ThreadPoolExecutor-based operators at this corpus scale (see
wiki/litdiscover/phase-discovery-roadmap.md §1.4's "real-world performance
finding"). This script is 1980 configs (660 configs × 3 surveys) — orders of
magnitude more operator calls — and would likely take hours, not tens of
minutes, under the same engine. Code correctness was verified by matching
this script's traversal shape line-for-line against eval/04b's and eval/03's
already-validated migrations, not by re-running to completion. If this sweep
is needed again, consider adding a `pdf_workers`-style batch cap or a
non-threaded code path to backward_traversal_operator first.

Original runtime estimate (pre-migration, dict-lookup traversal): ~495
configs × 3 surveys, <5s/config, ~30-60 min.
"""
from __future__ import annotations

import json
import csv
import itertools
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))
from _corpus_loader import load_adjacency, build_closed_corpus_source  # noqa: E402

from litdiscover.discovery.traverse import (
    backward_traversal_operator, forward_traversal_operator,
)

_REPO   = Path(__file__).parent.parent.parent
OUT     = _REPO / "data" / "outputs"
FIGS    = OUT / "pub_figures"
FIGS.mkdir(parents=True, exist_ok=True)

# ── Sweep grid ────────────────────────────────────────────────────────────────
PARETO_P_VALS     = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, None]  # None = no filter
YIELD_THRESH_VALS = [0.01, 0.02, 0.05, 0.10, 0.20]
N_ROUNDS_VALS     = [1, 2, 3]
K_ESCAPE_VALS     = [5, 10, 20, 50]

# Fixed
SEED_SIZE = 5
MAX_DEPTH = 8

print(f"Sweep grid: {len(PARETO_P_VALS)} pareto × "
      f"{len(YIELD_THRESH_VALS)} yield × "
      f"{len(N_ROUNDS_VALS)} rounds × "
      f"{len(K_ESCAPE_VALS)} k_escape = "
      f"{len(PARETO_P_VALS)*len(YIELD_THRESH_VALS)*len(N_ROUNDS_VALS)*len(K_ESCAPE_VALS)} configs "
      f"× 3 surveys")

# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading APS citation graph via shared _corpus_loader...")
cites, cited_by = load_adjacency()
print(f"  {sum(len(v) for v in cites.values()):,} edges")

source, doi_to_paper = build_closed_corpus_source(cites, cited_by)

with open(OUT / "ground_truth.json") as f:
    gt = json.load(f)

all_nodes = set(cites.keys()) | set(cited_by.keys())
print(f"  {len(all_nodes):,} nodes. Done.")

# ── Seed generation (top-k, deterministic) ────────────────────────────────────
def make_seeds_top_k(gold_refs, k):
    scored = sorted(gold_refs, key=lambda x: len(cited_by.get(x, set())), reverse=True)
    return set(scored[:k])

# ── Core traversal (real litdiscover production operators) ────────────────────
def bidir_pareto_traversal(seed_set, gold_refs, visited_already=None,
                            pareto_p=80, yield_thresh=0.05, max_depth=MAX_DEPTH):
    visited  = set(visited_already) if visited_already else set()
    for s in seed_set:
        visited.add(s)
    frontier = set(seed_set) - (set(visited_already) if visited_already else set())
    if not frontier:
        frontier = set(seed_set)

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
            cit_counts = [p["citation_count"] for p in frontier_papers
                          if p.get("citation_count") is not None]
            threshold = float(np.percentile(cit_counts, pareto_p)) if cit_counts else float("inf")
        else:
            threshold = float("inf")
        fwd = forward_traversal_operator(frontier_papers, hub_threshold=threshold, source=source)

        nxt = set()
        for cand in bwd.candidates + fwd.candidates:
            nb = cand.get("doi")
            if nb and nb not in visited:
                visited.add(nb); nxt.add(nb)

        frontier  = nxt
        new_nodes = len(visited) - prev_size
        new_gold  = len(visited & gold_refs) - prev_gold
        sy        = new_gold / new_nodes if new_nodes > 0 else 0.0

        if sy < yield_thresh and d >= 2:
            stop_depth = d
            break
        if not frontier:
            stop_depth = d
            break

    return visited, stop_depth

# ── Escape Hatch loop ─────────────────────────────────────────────────────────
def escape_hatch_loop(seeds, gold_refs, n_rounds, k_escape, pareto_p, yield_thresh):
    visited       = set()
    current_seeds = set(seeds)
    round_recalls = []

    for r in range(1, n_rounds + 1):
        visited, stop_d = bidir_pareto_traversal(
            current_seeds, gold_refs,
            visited_already=visited,
            pareto_p=pareto_p,
            yield_thresh=yield_thresh,
        )

        recall = len(visited & gold_refs) / len(gold_refs)
        round_recalls.append(recall)

        if recall >= 1.0:
            break

        # Escape Hatch: neighbourhood of included papers, ranked by in-degree
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

    return recall, len(visited), round_recalls

# ── Run sweep ─────────────────────────────────────────────────────────────────
results = []
configs = list(itertools.product(PARETO_P_VALS, YIELD_THRESH_VALS,
                                  N_ROUNDS_VALS, K_ESCAPE_VALS))
total   = len(configs) * len(gt)
done    = 0
t0      = time.time()

print(f"\nRunning {len(configs)} configs × {len(gt)} surveys = {total} runs...")

for pareto_p, yield_thresh, n_rounds, k_escape in configs:
    for survey_key, info in gt.items():
        gold_refs = set(info["gold_refs"])
        seeds     = make_seeds_top_k(gold_refs, SEED_SIZE)

        recall, corpus_size, round_recalls = escape_hatch_loop(
            seeds, gold_refs,
            n_rounds=n_rounds, k_escape=k_escape,
            pareto_p=pareto_p, yield_thresh=yield_thresh,
        )

        results.append({
            "pareto_p":     pareto_p if pareto_p is not None else 999,  # 999 = no filter
            "yield_thresh": yield_thresh,
            "n_rounds":     n_rounds,
            "k_escape":     k_escape,
            "survey":       survey_key,
            "recall":       recall,
            "corpus_size":  corpus_size,
            "n_rounds_run": len(round_recalls),
            "recall_r1":    round_recalls[0] if len(round_recalls) >= 1 else None,
            "recall_r2":    round_recalls[1] if len(round_recalls) >= 2 else None,
            "recall_r3":    round_recalls[2] if len(round_recalls) >= 3 else None,
        })

        done += 1
        if done % 100 == 0:
            elapsed = time.time() - t0
            eta = elapsed / done * (total - done)
            print(f"  {done}/{total}  elapsed={elapsed:.0f}s  ETA={eta:.0f}s")

# ── Save CSV ──────────────────────────────────────────────────────────────────
csv_path = OUT / "hyperparameter_sweep.csv"
fieldnames = results[0].keys()
with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)
print(f"\nSaved {len(results)} rows to {csv_path}")

# ── Figures ───────────────────────────────────────────────────────────────────
df_r = pd.DataFrame(results)

# For plotting, use pareto_p=999 label as "None"
def pareto_label(p):
    return "None" if p == 999 else str(p)

surveys      = list(gt.keys())
survey_short = {"S1_MIT": "S1 (1998)", "S2_UCG": "S2 (2008)", "S3_TOPO": "S3 (2019)"}
COLORS       = {"S1_MIT": "#2166ac", "S2_UCG": "#d6604d", "S3_TOPO": "#4dac26"}

# ── Fig 9a: Recall heatmap — Pareto × yield_thresh, at N_ROUNDS=2, K_ESCAPE=20
# One heatmap per survey
print("Generating Fig 9a: Pareto × yield heatmap...")
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for ax, skey in zip(axes, surveys):
    sub = df_r[(df_r["survey"] == skey) &
               (df_r["n_rounds"] == 2) &
               (df_r["k_escape"] == 20)]
    pivot = sub.pivot_table(index="pareto_p", columns="yield_thresh",
                            values="recall", aggfunc="mean")
    pivot.index = [pareto_label(p) for p in pivot.index]

    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn",
                   vmin=0.7, vmax=1.0, origin="lower")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{v:.2f}" for v in pivot.columns], fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xlabel("Yield threshold")
    ax.set_ylabel("Pareto percentile")
    ax.set_title(f"{survey_short[skey]}\n(N_rounds=2, K_escape=20)", fontsize=10)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=7, color="black" if val > 0.85 else "white")

    plt.colorbar(im, ax=ax, label="Recall", fraction=0.046, pad=0.04)

fig.suptitle("Recall: Pareto Percentile × Yield Threshold\n(k=5 seeds, N_rounds=2, K_escape=20)",
             fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "fig9a_pareto_yield_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig9a_pareto_yield_heatmap.png")

# ── Fig 9b: Recall vs Pareto — line plot per yield_thresh, N_ROUNDS=2, K_ESCAPE=20
print("Generating Fig 9b: Recall vs Pareto per yield threshold...")
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
yield_colors = {0.01: "#1b7837", 0.02: "#4dac26", 0.05: "#2166ac",
                0.10: "#d6604d", 0.20: "#762a83"}

for ax, skey in zip(axes, surveys):
    sub = df_r[(df_r["survey"] == skey) &
               (df_r["n_rounds"] == 2) &
               (df_r["k_escape"] == 20)]
    for yt, color in yield_colors.items():
        s = sub[sub["yield_thresh"] == yt].sort_values("pareto_p")
        ax.plot([pareto_label(p) for p in s["pareto_p"]], s["recall"],
                marker="o", color=color, lw=2, ms=5, label=f"yield={yt:.2f}")
    ax.axhline(1.0, color="gray", lw=0.8, ls="--", alpha=0.5)
    ax.set_xlabel("Pareto percentile  (rightmost tick = no filter)")
    ax.set_ylabel("Final recall")
    ax.set_title(survey_short[skey], fontsize=10)
    ax.tick_params(axis="x", rotation=45)
    if ax == axes[0]:
        ax.legend(fontsize=8)

fig.suptitle("Recall vs Pareto Threshold by Yield Setting\n(k=5 seeds, N_rounds=2, K_escape=20)",
             fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "fig9b_recall_vs_pareto.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig9b_recall_vs_pareto.png")

# ── Fig 9c: Recall vs N_ROUNDS — at operating point Pareto=80, yield=0.05
print("Generating Fig 9c: Recall vs N_rounds...")
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
k_escape_colors = {5: "#1b7837", 10: "#2166ac", 20: "#d6604d", 50: "#762a83"}

for ax, skey in zip(axes, surveys):
    sub = df_r[(df_r["survey"] == skey) &
               (df_r["pareto_p"] == 80) &
               (df_r["yield_thresh"] == 0.05)]
    for ke, color in k_escape_colors.items():
        s = sub[sub["k_escape"] == ke].sort_values("n_rounds")
        ax.plot(s["n_rounds"], s["recall"],
                marker="o", color=color, lw=2, ms=5, label=f"K_escape={ke}")
    ax.axhline(1.0, color="gray", lw=0.8, ls="--", alpha=0.5)
    ax.set_xlabel("N_rounds")
    ax.set_ylabel("Final recall")
    ax.set_title(survey_short[skey], fontsize=10)
    ax.set_xticks(N_ROUNDS_VALS)
    if ax == axes[0]:
        ax.legend(fontsize=8)

fig.suptitle("Recall vs N_rounds by K_escape\n(k=5 seeds, Pareto=80, yield=0.05)",
             fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "fig9c_recall_vs_nrounds.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig9c_recall_vs_nrounds.png")

# ── Fig 9d: Corpus size heatmap — same slice as 9a (cost side of tradeoff)
print("Generating Fig 9d: Corpus size heatmap...")
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for ax, skey in zip(axes, surveys):
    sub = df_r[(df_r["survey"] == skey) &
               (df_r["n_rounds"] == 2) &
               (df_r["k_escape"] == 20)]
    pivot = sub.pivot_table(index="pareto_p", columns="yield_thresh",
                            values="corpus_size", aggfunc="mean")
    pivot.index = [pareto_label(p) for p in pivot.index]
    pivot_k = pivot / 1000  # display in thousands

    im = ax.imshow(pivot_k.values, aspect="auto", cmap="YlOrRd_r",
                   origin="lower")
    ax.set_xticks(range(len(pivot_k.columns)))
    ax.set_xticklabels([f"{v:.2f}" for v in pivot_k.columns], fontsize=8)
    ax.set_yticks(range(len(pivot_k.index)))
    ax.set_yticklabels(pivot_k.index, fontsize=8)
    ax.set_xlabel("Yield threshold")
    ax.set_ylabel("Pareto percentile")
    ax.set_title(f"{survey_short[skey]}\n(corpus size ×1k)", fontsize=10)

    for i in range(len(pivot_k.index)):
        for j in range(len(pivot_k.columns)):
            val = pivot_k.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.0f}k", ha="center", va="center", fontsize=7)

    plt.colorbar(im, ax=ax, label="Corpus size (×1k)", fraction=0.046, pad=0.04)

fig.suptitle("Corpus Size: Pareto Percentile × Yield Threshold\n(k=5 seeds, N_rounds=2, K_escape=20)",
             fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "fig9d_corpus_size_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig9d_corpus_size_heatmap.png")

# ── Summary: print operating point comparison ─────────────────────────────────
print("\n── Operating point summary (k=5 seeds, N_rounds=2, K_escape=20) ──")
print(f"{'Survey':<12} {'Pareto':>8} {'Yield':>8} {'Recall':>8} {'Corpus':>10}")
for skey in surveys:
    for (pp, yt) in [(80, 0.05), (50, 0.05), (80, 0.10), (50, 0.10)]:
        row = df_r[(df_r["survey"] == skey) &
                   (df_r["pareto_p"] == pp) &
                   (df_r["yield_thresh"] == yt) &
                   (df_r["n_rounds"] == 2) &
                   (df_r["k_escape"] == 20)]
        if not row.empty:
            r = row.iloc[0]
            print(f"  {skey:<12} {pp:>8} {yt:>8.2f} {r['recall']:>8.3f} {r['corpus_size']:>10,}")

print(f"\nTotal elapsed: {time.time()-t0:.0f}s")
print("Done.")
