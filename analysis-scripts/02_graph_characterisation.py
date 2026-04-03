"""
Phase 3: Characterise the APS citation graph structure.

Computes and saves:
  1. Global degree distribution (in/out) — log-log histogram + power-law fit
  2. Gini coefficient of in-degree (citation count) distribution
  3. Lorenz curve of in-degree
  4. Weakly connected component size distribution
  5. Per-survey: BFS reachability curve (nodes reached vs. BFS depth, both directions)
  6. Per-survey: in/out degree distribution of the 1-hop neighbourhood
  7. Per-survey: Lorenz curve of forward-neighbour citation counts (to motivate Pareto filter)

All figures saved to /home/ubuntu/litreview-coverage/figures/
All numeric results saved to /home/ubuntu/litreview-coverage/graph_stats.json
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from collections import defaultdict, deque
from pathlib import Path

# ── Setup ─────────────────────────────────────────────────────────────────────
OUT   = Path("/home/ubuntu/litreview-coverage")
FIGS  = OUT / "figures"
FIGS.mkdir(exist_ok=True)

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

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading APS citation graph...")
df = pd.read_csv("/home/ubuntu/aps-citations.csv")
print(f"  {len(df):,} edges")

with open(OUT / "ground_truth.json") as f:
    gt = json.load(f)

# ── Build adjacency ───────────────────────────────────────────────────────────
print("Building adjacency index...")
cites    = defaultdict(set)
cited_by = defaultdict(set)
for row in df.itertuples(index=False):
    cites[row.citing_doi].add(row.cited_doi)
    cited_by[row.cited_doi].add(row.citing_doi)

all_nodes = set(cites.keys()) | set(cited_by.keys())
N = len(all_nodes)
print(f"  {N:,} nodes")

# ── 1. Global degree distributions ───────────────────────────────────────────
print("Computing global degree distributions...")
in_deg  = np.array([len(cited_by[n]) for n in all_nodes])
out_deg = np.array([len(cites[n])    for n in all_nodes])

def plot_degree_dist(deg_array, label, color, filename):
    counts = np.bincount(deg_array)
    k = np.arange(len(counts))
    mask = (k > 0) & (counts > 0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(k[mask], counts[mask], s=4, alpha=0.6, color=color, linewidths=0)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Degree $k$"); ax.set_ylabel("Count $N(k)$")
    ax.set_title(f"APS Citation Graph — {label} Degree Distribution")
    # Power-law fit on the tail (k >= 5)
    tail = mask & (k >= 5)
    if tail.sum() > 5:
        lx = np.log10(k[tail]); ly = np.log10(counts[tail])
        gamma, intercept = np.polyfit(lx, ly, 1)
        fit_k = np.logspace(np.log10(k[tail].min()), np.log10(k[tail].max()), 200)
        fit_y = 10**intercept * fit_k**gamma
        ax.plot(fit_k, fit_y, "k--", lw=1.2, label=f"Power-law fit $\\gamma={-gamma:.2f}$")
        ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGS / filename, dpi=150)
    plt.close(fig)
    return float(-gamma) if tail.sum() > 5 else None

gamma_in  = plot_degree_dist(in_deg,  "In",  "#2166ac", "deg_in.png")
gamma_out = plot_degree_dist(out_deg, "Out", "#d6604d", "deg_out.png")
print(f"  In-degree power-law exponent γ ≈ {gamma_in:.3f}")
print(f"  Out-degree power-law exponent γ ≈ {gamma_out:.3f}")

# ── 2. Gini coefficient ───────────────────────────────────────────────────────
def gini(arr):
    arr = np.sort(arr.astype(float))
    n = len(arr)
    idx = np.arange(1, n + 1)
    return (2 * np.sum(idx * arr) / (n * arr.sum())) - (n + 1) / n

gini_in  = gini(in_deg)
gini_out = gini(out_deg)
print(f"  Gini(in-degree)  = {gini_in:.4f}")
print(f"  Gini(out-degree) = {gini_out:.4f}")

# ── 3. Lorenz curve of in-degree ──────────────────────────────────────────────
def lorenz_curve(arr):
    arr = np.sort(arr.astype(float))
    cum = np.cumsum(arr)
    cum = np.insert(cum, 0, 0)
    return np.linspace(0, 1, len(cum)), cum / cum[-1]

fig, ax = plt.subplots(figsize=(5, 5))
lx, ly = lorenz_curve(in_deg)
ax.plot(lx, ly, color="#2166ac", lw=2, label=f"In-degree (Gini={gini_in:.3f})")
lx2, ly2 = lorenz_curve(out_deg)
ax.plot(lx2, ly2, color="#d6604d", lw=2, label=f"Out-degree (Gini={gini_out:.3f})")
ax.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect equality")
ax.set_xlabel("Cumulative fraction of papers")
ax.set_ylabel("Cumulative fraction of citations")
ax.set_title("Lorenz Curve — APS Citation Graph")
ax.legend(fontsize=9)
fig.tight_layout()
fig.savefig(FIGS / "lorenz_global.png", dpi=150)
plt.close(fig)

# ── 4. Weakly connected components ───────────────────────────────────────────
print("Computing weakly connected components (union-find)...")
parent = {n: n for n in all_nodes}

def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[ra] = rb

for row in df.itertuples(index=False):
    union(row.citing_doi, row.cited_doi)

comp_sizes = defaultdict(int)
for n in all_nodes:
    comp_sizes[find(n)] += 1

sizes = sorted(comp_sizes.values(), reverse=True)
print(f"  Number of WCCs: {len(sizes):,}")
print(f"  Largest WCC:    {sizes[0]:,} nodes ({100*sizes[0]/N:.1f}%)")
print(f"  2nd largest:    {sizes[1]:,} nodes")

# WCC size distribution
fig, ax = plt.subplots(figsize=(6, 4))
size_arr = np.array(sizes)
bins = np.logspace(0, np.log10(size_arr.max()), 40)
ax.hist(size_arr, bins=bins, color="#555", edgecolor="white", lw=0.3)
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Component size"); ax.set_ylabel("Count")
ax.set_title("Weakly Connected Component Size Distribution")
fig.tight_layout()
fig.savefig(FIGS / "wcc_dist.png", dpi=150)
plt.close(fig)

# ── 5. BFS reachability curves per survey ─────────────────────────────────────
print("Computing BFS reachability curves...")

def bfs_reachability(start_doi, adj, max_depth=6):
    """BFS from start_doi using adj dict. Returns list of (depth, cumulative_nodes_reached)."""
    visited = {start_doi}
    frontier = {start_doi}
    curve = [(0, 1)]
    for d in range(1, max_depth + 1):
        next_frontier = set()
        for node in frontier:
            for nb in adj.get(node, set()):
                if nb not in visited:
                    visited.add(nb)
                    next_frontier.add(nb)
        frontier = next_frontier
        curve.append((d, len(visited)))
        if not frontier:
            break
    return curve

fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=False)

bfs_results = {}
for ax, (key, info) in zip(axes, gt.items()):
    doi = info["doi"]
    s = STYLE[key]

    bwd = bfs_reachability(doi, cites,    max_depth=6)   # follow references
    fwd = bfs_reachability(doi, cited_by, max_depth=6)   # follow citations

    bfs_results[key] = {"backward": bwd, "forward": fwd}

    depths_b, counts_b = zip(*bwd)
    depths_f, counts_f = zip(*fwd)

    ax.plot(depths_b, counts_b, "o-", color=s["color"],       lw=2, ms=5, label="Backward (refs)")
    ax.plot(depths_f, counts_f, "s--", color=s["color"],      lw=2, ms=5, alpha=0.6, label="Forward (citers)")
    ax.set_xlabel("BFS depth"); ax.set_ylabel("Cumulative nodes reached")
    ax.set_title(s["label"], fontsize=9, wrap=True)
    ax.legend(fontsize=8)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

fig.suptitle("BFS Reachability from Each Survey Paper", fontsize=12, y=1.01)
fig.tight_layout()
fig.savefig(FIGS / "bfs_reachability.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── 6. Per-survey: Lorenz curve of forward-neighbour citation counts ──────────
print("Computing per-survey Lorenz curves for forward neighbours...")

fig, axes = plt.subplots(1, 3, figsize=(14, 4))

pareto_stats = {}
for ax, (key, info) in zip(axes, gt.items()):
    doi = info["doi"]
    s = STYLE[key]

    # Forward neighbours at depth 1 = papers that cite the survey
    fwd_1hop = list(cited_by.get(doi, set()))
    if not fwd_1hop:
        continue
    # Their out-degrees (how many papers they in turn cite — proxy for hub-ness)
    fwd_out_degs = np.array([len(cites.get(n, set())) for n in fwd_1hop])

    lx, ly = lorenz_curve(fwd_out_degs)
    g = gini(fwd_out_degs)
    ax.plot(lx, ly, color=s["color"], lw=2, label=f"Gini = {g:.3f}")
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("Cumulative fraction of citers")
    ax.set_ylabel("Cumulative fraction of out-edges")
    ax.set_title(f"{s['label']}\nForward-neighbour out-degree", fontsize=9)
    ax.legend(fontsize=9)

    # What fraction of edges come from the top 20% of citers?
    sorted_d = np.sort(fwd_out_degs)
    top20_thresh = np.percentile(sorted_d, 80)
    top20_share  = sorted_d[sorted_d >= top20_thresh].sum() / sorted_d.sum()
    pareto_stats[key] = {"gini": float(g), "top20_edge_share": float(top20_share)}
    print(f"  {key}: Gini={g:.3f}, top-20% citers hold {100*top20_share:.1f}% of out-edges")

fig.suptitle("Lorenz Curve of Forward-Neighbour Out-Degree\n(motivation for Pareto hub filter)", fontsize=11)
fig.tight_layout()
fig.savefig(FIGS / "lorenz_forward_neighbours.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# ── Save all stats ─────────────────────────────────────────────────────────────
stats = {
    "n_nodes": N,
    "n_edges": len(df),
    "in_degree_gini":   float(gini_in),
    "out_degree_gini":  float(gini_out),
    "in_degree_gamma":  float(gamma_in)  if gamma_in  else None,
    "out_degree_gamma": float(gamma_out) if gamma_out else None,
    "n_wccs":           len(sizes),
    "largest_wcc_size": int(sizes[0]),
    "largest_wcc_frac": float(sizes[0] / N),
    "bfs_reachability": bfs_results,
    "pareto_stats":     pareto_stats,
}

with open(OUT / "graph_stats.json", "w") as f:
    json.dump(stats, f, indent=2)

print(f"\nAll stats saved to {OUT / 'graph_stats.json'}")
print("All figures saved to", FIGS)
print("Done.")
