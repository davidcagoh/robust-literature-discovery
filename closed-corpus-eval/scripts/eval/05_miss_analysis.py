"""
Phase 2-3: Miss Analysis

For each survey × seed condition × seed size, identify the papers that were
NOT recovered by the cold-start Escape Hatch loop (the "misses"), and
characterise their structural properties compared to the recovered papers.

Properties examined:
  1. In-degree (citations received within APS corpus)
  2. Out-degree (references made within APS corpus)
  3. Total degree (in + out)
  4. APS journal (from DOI prefix)
  5. Publication year (from DOI where parseable)
  6. Structural isolation: minimum BFS distance from any seed in the gold set
  7. Whether the miss is reachable at all from the recovered set (at any depth)

We focus on the k=20 top-k seed condition as the canonical case, but also
compare across seed conditions to see if the miss set is stable.

**Traversal engine updated 2026-07-14** to match 04b_cold_start_lowseed.py's
promotion to the production-operator engine (backward_traversal_operator /
forward_traversal_operator / pareto_hub_threshold via ClosedCorpusSource) —
per this repo's own rule that 05 must mirror 04b's stopping/filter logic
since it reconstructs the traversal from scratch rather than reading visited
sets from the (summary-only) results JSON. See
wiki/litdiscover/phase-discovery-roadmap.md §1.3.
"""

import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from collections import defaultdict, deque
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent.parent))
from _corpus_loader import load_adjacency, build_closed_corpus_source  # noqa: E402

from litdiscover.discovery.traverse import (
    backward_traversal_operator, forward_traversal_operator, pareto_hub_threshold,
)

_REPO = Path(__file__).parent.parent.parent
APS_CSV = _REPO / "data" / "processed" / "aps-dataset-citations-2022.csv"
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

# ── Helper: extract journal and year from APS DOI ─────────────────────────────
# APS DOIs look like: 10.1103/PhysRevB.52.R3412  or  10.1103/RevModPhys.70.1039
def parse_doi(doi):
    """Returns (journal, year_approx) where year is estimated from volume number."""
    doi = str(doi)
    m = re.search(r'10\.1103/([A-Za-z]+)\.(\d+)\.', doi)
    if not m:
        return "Unknown", None
    journal = m.group(1)
    vol     = int(m.group(2))
    # Approximate year from volume number for major APS journals
    # PhysRevB: vol 1 = 1970; PhysRevLett: vol 1 = 1958; RevModPhys: vol 1 = 1929
    year_map = {
        "PhysRevB":    1970 + vol - 1,
        "PhysRevD":    1970 + vol - 1,
        "PhysRevA":    1970 + vol - 1,
        "PhysRevC":    1970 + vol - 1,
        "PhysRevE":    1993 + vol - 48,   # vol 48 = 1993
        "PhysRevLett": 1958 + vol - 1,
        "RevModPhys":  1929 + vol - 1,
        "PhysRevX":    2011 + vol - 1,
        "PhysRevApplied": 2014 + vol - 1,
        "PhysRevMaterials": 2017 + vol - 1,
        "PhysRevFluids": 2016 + vol - 1,
        "PhysRevAccelBeams": 2016 + vol - 1,
        "PhysRevResearch": 2019 + vol - 1,
    }
    year = year_map.get(journal, None)
    return journal, year

# ── Reconstruct visited sets from cold-start results ─────────────────────────
# We need to re-run the traversal to get the exact visited sets.
# The cold_start_results.json only stores recall numbers, not the visited sets.
# So we re-run the canonical case: k=20, top-k seeds.

print("\nRe-running traversal to get exact visited sets (k=5 top-k, N_ROUNDS=2)...")

import random
random.seed(42)
np.random.seed(42)

PARETO_P = 80
YIELD_THRESHOLD = 0.05
MAX_DEPTH = 8
K_SEED = 5
K_ESCAPE = 20
N_ROUNDS = 2

def make_seeds_top_k(gold_refs, k, cited_by_map):
    scored = sorted(gold_refs, key=lambda x: len(cited_by_map.get(x, set())), reverse=True)
    return set(scored[:k])

def bidir_pareto_traversal_full(seed_set, gold_refs, visited_already=None):
    """
    Same per-depth BFS-with-yield-stopping shape as 04b_cold_start_lowseed.py's
    bidir_traversal() (must be kept in sync — see this script's module
    docstring), delegating each depth step to the real production operators
    via a ClosedCorpusSource instead of touching cites/cited_by directly.
    """
    visited  = set(visited_already) if visited_already else set()
    for s in seed_set:
        visited.add(s)
    frontier = set(seed_set) - (visited_already or set())
    if not frontier:
        frontier = set(seed_set)

    stop_depth = MAX_DEPTH
    for d in range(1, MAX_DEPTH + 1):
        prev_size = len(visited)
        prev_gold = len(visited & gold_refs)

        frontier_papers = [doi_to_paper[doi] for doi in frontier if doi in doi_to_paper]
        if not frontier_papers:
            stop_depth = d
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
            stop_depth = d; break
        if not frontier:
            stop_depth = d; break

    return visited, stop_depth

def escape_hatch_full(seed_set, gold_refs):
    visited = set()
    current_seeds = set(seed_set)
    for r in range(N_ROUNDS):
        visited, _ = bidir_pareto_traversal_full(current_seeds, gold_refs, visited_already=visited)
        if len(visited & gold_refs) >= len(gold_refs):
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
        current_seeds = set(escape_sorted[:K_ESCAPE])
    return visited

# ── BFS distance from a set of sources ───────────────────────────────────────
def bfs_distance_from_set(sources, target_set, adj_fwd, adj_bwd, max_depth=10):
    """
    Returns a dict {doi: min_distance} for each doi in target_set.
    Uses bidirectional adjacency (follows both forward and backward edges).
    """
    visited = {s: 0 for s in sources}
    queue   = deque(sources)
    result  = {}

    while queue:
        node = queue.popleft()
        d    = visited[node]
        if d >= max_depth:
            continue
        for nb in list(adj_fwd.get(node, set())) + list(adj_bwd.get(node, set())):
            if nb not in visited:
                visited[nb] = d + 1
                queue.append(nb)

    for t in target_set:
        result[t] = visited.get(t, max_depth + 1)  # +1 means unreachable within max_depth
    return result

# ── Main analysis loop ────────────────────────────────────────────────────────
all_miss_data = {}

for key, info in gt.items():
    doi       = info["doi"]
    gold_refs = set(info["gold_refs"])
    print(f"\n  {key} | gold_refs={len(gold_refs)}")

    seeds_top = make_seeds_top_k(gold_refs, K_SEED, cited_by)
    visited   = escape_hatch_full(seeds_top, gold_refs)

    recovered = visited & gold_refs
    missed    = gold_refs - visited

    print(f"    Recovered: {len(recovered)} / {len(gold_refs)} ({100*len(recovered)/len(gold_refs):.1f}%)")
    print(f"    Missed:    {len(missed)}")

    # ── Structural properties of missed vs recovered ──────────────────────────
    COLS = ["doi", "in_deg", "out_deg", "total_deg", "journal", "year"]
    def props(doi_set):
        rows = []
        for d in doi_set:
            in_d  = len(cited_by.get(d, set()))
            out_d = len(cites.get(d, set()))
            journal, year = parse_doi(d)
            rows.append({"doi": d, "in_deg": in_d, "out_deg": out_d,
                         "total_deg": in_d + out_d, "journal": journal, "year": year})
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame(columns=COLS)

    df_missed    = props(missed)
    df_recovered = props(recovered)

    # ── BFS distance from recovered set to each missed paper ─────────────────
    if len(missed) > 0:
        print(f"    Computing BFS distances from recovered set to missed papers...")
        dist_map = bfs_distance_from_set(recovered, missed, cites, cited_by, max_depth=8)
        df_missed["bfs_dist_from_recovered"] = df_missed["doi"].map(dist_map)

        # ── BFS distance from seeds to missed papers ──────────────────────────────
        dist_from_seeds = bfs_distance_from_set(seeds_top, missed, cites, cited_by, max_depth=8)
        df_missed["bfs_dist_from_seeds"] = df_missed["doi"].map(dist_from_seeds)

        # ── Is the miss reachable from the survey itself? ─────────────────────────
        dist_from_survey = bfs_distance_from_set({doi}, missed, cites, cited_by, max_depth=8)
        df_missed["bfs_dist_from_survey"] = df_missed["doi"].map(dist_from_survey)
    else:
        df_missed["bfs_dist_from_recovered"] = pd.Series(dtype=float)
        df_missed["bfs_dist_from_seeds"]     = pd.Series(dtype=float)
        df_missed["bfs_dist_from_survey"]    = pd.Series(dtype=float)

    all_miss_data[key] = {
        "missed":    df_missed,
        "recovered": df_recovered,
        "seeds":     seeds_top,
        "visited_size": len(visited),
    }

    print(f"    Missed paper degree stats:")
    print(f"      in_deg  — mean={df_missed['in_deg'].mean():.1f}, median={df_missed['in_deg'].median():.0f}, max={df_missed['in_deg'].max()}")
    print(f"      out_deg — mean={df_missed['out_deg'].mean():.1f}, median={df_missed['out_deg'].median():.0f}, max={df_missed['out_deg'].max()}")
    print(f"    Recovered paper degree stats:")
    print(f"      in_deg  — mean={df_recovered['in_deg'].mean():.1f}, median={df_recovered['in_deg'].median():.0f}, max={df_recovered['in_deg'].max()}")
    print(f"      out_deg — mean={df_recovered['out_deg'].mean():.1f}, median={df_recovered['out_deg'].median():.0f}, max={df_recovered['out_deg'].max()}")
    print(f"    BFS dist from recovered set:")
    print(f"      {df_missed['bfs_dist_from_recovered'].value_counts().sort_index().to_dict()}")
    print(f"    BFS dist from survey paper:")
    print(f"      {df_missed['bfs_dist_from_survey'].value_counts().sort_index().to_dict()}")
    print(f"    Journals of missed papers: {df_missed['journal'].value_counts().to_dict()}")

# ── Plotting ──────────────────────────────────────────────────────────────────
print("\nGenerating miss analysis figures...")

# ── Fig 1: In-degree distribution: missed vs recovered (all surveys) ──────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, data) in zip(axes, all_miss_data.items()):
    s  = SURVEY_STYLE[key]
    dm = data["missed"]
    dr = data["recovered"]
    bins = np.logspace(0, np.log10(max(dr["in_deg"].max(), 1) + 1), 30)
    ax.hist(dr["in_deg"].clip(lower=1), bins=bins, alpha=0.6,
            color=s["color"], label=f"Recovered (n={len(dr)})", density=True)
    if len(dm) > 0:
        ax.hist(dm["in_deg"].clip(lower=1), bins=bins, alpha=0.8,
                color="#d73027", label=f"Missed (n={len(dm)})", density=True)
    ax.set_xscale("log")
    ax.set_xlabel("In-degree (citations received)")
    ax.set_ylabel("Density")
    ax.set_title(s["label"], fontsize=9)
    ax.legend(fontsize=8)
fig.suptitle("In-Degree Distribution: Missed vs Recovered Papers", fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "miss_indegree_dist.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 2: Out-degree distribution: missed vs recovered ───────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, data) in zip(axes, all_miss_data.items()):
    s  = SURVEY_STYLE[key]
    dm = data["missed"]
    dr = data["recovered"]
    bins = np.linspace(0, max(dr["out_deg"].max(), dm["out_deg"].max() if len(dm) > 0 else 1) + 1, 30)
    ax.hist(dr["out_deg"], bins=bins, alpha=0.6,
            color=s["color"], label=f"Recovered (n={len(dr)})", density=True)
    if len(dm) > 0:
        ax.hist(dm["out_deg"], bins=bins, alpha=0.8,
                color="#d73027", label=f"Missed (n={len(dm)})", density=True)
    ax.set_xlabel("Out-degree (references made within APS)")
    ax.set_ylabel("Density")
    ax.set_title(s["label"], fontsize=9)
    ax.legend(fontsize=8)
fig.suptitle("Out-Degree Distribution: Missed vs Recovered Papers", fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "miss_outdegree_dist.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 3: BFS distance from recovered set to missed papers ───────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, data) in zip(axes, all_miss_data.items()):
    s  = SURVEY_STYLE[key]
    dm = data["missed"]
    if len(dm) == 0:
        ax.text(0.5, 0.5, "No missed papers", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(s["label"], fontsize=9)
        continue
    dist_counts = dm["bfs_dist_from_recovered"].value_counts().sort_index()
    ax.bar(dist_counts.index, dist_counts.values, color=s["color"], alpha=0.85)
    ax.set_xlabel("BFS distance from recovered set")
    ax.set_ylabel("Number of missed papers")
    ax.set_title(s["label"], fontsize=9)
    ax.set_xticks(sorted(dist_counts.index))
fig.suptitle("BFS Distance from Recovered Set to Missed Papers\n(How far away are the misses?)", fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "miss_bfs_distance.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 4: BFS distance from survey paper to missed papers ────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, data) in zip(axes, all_miss_data.items()):
    s  = SURVEY_STYLE[key]
    dm = data["missed"]
    if len(dm) == 0:
        ax.text(0.5, 0.5, "No missed papers", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(s["label"], fontsize=9)
        continue
    dist_counts = dm["bfs_dist_from_survey"].value_counts().sort_index()
    ax.bar(dist_counts.index, dist_counts.values, color="#762a83", alpha=0.85)
    ax.set_xlabel("BFS distance from survey paper itself")
    ax.set_ylabel("Number of missed papers")
    ax.set_title(s["label"], fontsize=9)
    ax.set_xticks(sorted(dist_counts.index))
fig.suptitle("BFS Distance from Survey Paper to Missed Papers\n(Are misses structurally far from the survey?)", fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "miss_bfs_from_survey.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 5: Journal breakdown of missed vs recovered ───────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, data) in zip(axes, all_miss_data.items()):
    s  = SURVEY_STYLE[key]
    dm = data["missed"]
    dr = data["recovered"]
    if len(dm) == 0:
        ax.text(0.5, 0.5, "No missed papers", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(s["label"], fontsize=9)
        continue

    # Normalise by total in each group
    miss_j = dm["journal"].value_counts(normalize=True)
    rec_j  = dr["journal"].value_counts(normalize=True)
    all_journals = sorted(set(miss_j.index) | set(rec_j.index))

    x = np.arange(len(all_journals))
    w = 0.35
    ax.bar(x - w/2, [rec_j.get(j, 0) for j in all_journals],  w,
           color=s["color"], alpha=0.8, label="Recovered")
    ax.bar(x + w/2, [miss_j.get(j, 0) for j in all_journals], w,
           color="#d73027", alpha=0.8, label="Missed")
    ax.set_xticks(x)
    ax.set_xticklabels(all_journals, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Fraction")
    ax.set_title(s["label"], fontsize=9)
    ax.legend(fontsize=8)
fig.suptitle("Journal Distribution: Missed vs Recovered Papers", fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "miss_journal_dist.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Fig 6: Year distribution of missed vs recovered ───────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, (key, data) in zip(axes, all_miss_data.items()):
    s  = SURVEY_STYLE[key]
    dm = data["missed"].dropna(subset=["year"])
    dr = data["recovered"].dropna(subset=["year"])
    if len(dm) == 0:
        ax.text(0.5, 0.5, "No missed papers", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(s["label"], fontsize=9)
        continue
    yr_min = min(dm["year"].min(), dr["year"].min())
    yr_max = max(dm["year"].max(), dr["year"].max())
    bins = np.arange(yr_min, yr_max + 2, 3)
    ax.hist(dr["year"], bins=bins, alpha=0.6, color=s["color"],
            label=f"Recovered (n={len(dr)})", density=True)
    ax.hist(dm["year"], bins=bins, alpha=0.8, color="#d73027",
            label=f"Missed (n={len(dm)})", density=True)
    ax.set_xlabel("Approx. publication year")
    ax.set_ylabel("Density")
    ax.set_title(s["label"], fontsize=9)
    ax.legend(fontsize=8)
fig.suptitle("Approximate Publication Year: Missed vs Recovered Papers", fontsize=12)
fig.tight_layout()
fig.savefig(FIGS / "miss_year_dist.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Save miss data to CSV for inspection ──────────────────────────────────────
for key, data in all_miss_data.items():
    data["missed"].to_csv(OUT / f"missed_papers_{key}.csv", index=False)
    print(f"  Saved missed papers for {key} to missed_papers_{key}.csv")

print(f"\nAll figures saved to {FIGS}")
print("Done.")
