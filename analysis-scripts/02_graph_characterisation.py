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

All figures saved to data-aps/outputs/figures/
All numeric results saved to data-aps/outputs/graph_stats.json
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
from scipy.optimize import minimize, minimize_scalar

# ── Setup ─────────────────────────────────────────────────────────────────────
_REPO = Path(__file__).parent.parent
APS_CSV = _REPO / "data-aps" / "processed" / "aps-dataset-citations-2022.csv"
OUT   = _REPO / "data-aps" / "outputs"
FIGS  = OUT / "figures"
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

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading APS citation graph...")
df = pd.read_csv(APS_CSV)
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
    """
    Fit and plot a Barabási corrected degree distribution model (eq. 4.47):
        p_k = (k + k_sat)^(-γ) * exp(-k / k_cut) / Z
        Z   = sum_{k'=1}^{K_max} (k' + k_sat)^(-γ) * exp(-k' / k_cut)

    Fitting follows Barabási (2016) Network Science §4.13:
      1. Grid-search over k_sat ∈ {0,1,2,5,12,20,50,100} and
         k_cut ∈ {100,500,1000,3000,6000,10000,50000} (log-spaced).
      2. For each (k_sat, k_cut) pair, find γ by maximising the log-likelihood
         L(γ | k_sat, k_cut) = Σ n_k · log p_k  via minimize_scalar on [1, 8].
      3. Record the NLL at the best γ for every grid point.
      4. Pick the five grid points with lowest NLL as warm starts, then refine
         each jointly with L-BFGS-B.  The global minimum across all refined
         starts is the final fit.

    A pure power-law line on log-log is systematically wrong for citation
    networks — it over-predicts low-degree nodes and ignores the exponential
    high-degree cutoff (Barabási 2016 §4.13, p-value < 10⁻⁴).

    Returns (gamma, k_sat, k_cut).
    """
    counts = np.bincount(deg_array)
    k_all  = np.arange(len(counts))
    mask   = (k_all > 0) & (counts > 0)

    # Work with k = 1 .. K_max binned counts
    k_vals = np.arange(1, len(counts), dtype=float)   # shape (K_max,)
    n_vals = counts[1:].astype(float)                  # n_vals[i] = count at k=i+1
    K_max  = int(k_vals[-1])

    def nll_given_k_sat_k_cut(gamma, k_sat, k_cut):
        """Negative log-likelihood for fixed (k_sat, k_cut) and scalar gamma."""
        f = (k_vals + k_sat) ** (-gamma) * np.exp(-k_vals / k_cut)
        Z = f.sum()
        if Z <= 0:
            return 1e18
        p = f / Z
        return -np.dot(n_vals, np.log(p + 1e-300))

    def best_gamma_for(k_sat, k_cut):
        """Find the γ in [1.0, 8.0] that maximises L for fixed (k_sat, k_cut)."""
        res = minimize_scalar(
            lambda g: nll_given_k_sat_k_cut(g, k_sat, k_cut),
            bounds=(1.0, 8.0), method="bounded"
        )
        return res.x, res.fun

    # ── Step 1: grid search ───────────────────────────────────────────────────
    k_sat_grid = [0, 1, 2, 5, 12, 20, 50, 100]
    k_cut_max  = max(K_max, 100)
    k_cut_grid = [v for v in [100, 500, 1000, 3000, 6000, 10000, 50000]
                  if v <= k_cut_max * 5]   # don't go absurdly beyond max degree
    if not k_cut_grid:
        k_cut_grid = [k_cut_max]

    grid_results = []
    for ks in k_sat_grid:
        for kc in k_cut_grid:
            g, nll = best_gamma_for(float(ks), float(kc))
            grid_results.append((nll, g, float(ks), float(kc)))

    grid_results.sort(key=lambda x: x[0])

    # ── Step 2: L-BFGS-B refinement from the top-5 grid starts ──────────────
    bounds = [(1.0, 8.0), (0.0, 200.0), (10.0, max(1e6, k_cut_max * 10.0))]

    def neg_log_likelihood(params):
        gamma, k_sat, k_cut = params
        if gamma < 1.0 or k_sat < 0 or k_cut < 1:
            return 1e18
        return nll_given_k_sat_k_cut(gamma, k_sat, k_cut)

    best_nll   = np.inf
    best_params = grid_results[0][1:]   # (gamma, k_sat, k_cut) from grid

    for _, g0, ks0, kc0 in grid_results[:5]:
        res = minimize(neg_log_likelihood, [g0, ks0, kc0],
                       method="L-BFGS-B", bounds=bounds)
        if res.fun < best_nll:
            best_nll   = res.fun
            best_params = res.x

    gamma_fit, k_sat_fit, k_cut_fit = best_params

    # ── Build fitted curve for plotting ──────────────────────────────────────
    fit_k = np.logspace(0, np.log10(max(k_vals)), 400)
    f_norm = (k_vals + k_sat_fit) ** (-gamma_fit) * np.exp(-k_vals / k_cut_fit)
    Z      = f_norm.sum()
    f_fit  = (fit_k + k_sat_fit) ** (-gamma_fit) * np.exp(-fit_k / k_cut_fit)
    total_nodes = n_vals.sum()
    fit_y  = (f_fit / Z) * total_nodes   # scale to counts

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(k_all[mask], counts[mask], s=4, alpha=0.6, color=color,
               linewidths=0, label="Empirical")
    ax.plot(fit_k, fit_y, "k-", lw=1.6,
            label=(f"Barabási corrected model: "
                   f"$\\gamma={gamma_fit:.2f}$, "
                   f"$k_{{sat}}={k_sat_fit:.0f}$, "
                   f"$k_{{cut}}={k_cut_fit:.0f}$"))
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Degree $k$"); ax.set_ylabel("Count $N(k)$")
    ax.set_title(
        f"APS Citation Graph — {label} Degree Distribution\n"
        r"Pure power-law fit fails (Barabási 2016 §4.13, $p < 10^{-4}$)",
        fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / filename, dpi=150)
    plt.close(fig)
    return float(gamma_fit), float(k_sat_fit), float(k_cut_fit)

gamma_in,  k_sat_in,  k_cut_in  = plot_degree_dist(in_deg,  "In",  "#2166ac", "deg_in.png")
gamma_out, k_sat_out, k_cut_out = plot_degree_dist(out_deg, "Out", "#d6604d", "deg_out.png")
print(f"  In-degree  Barabási model: γ={gamma_in:.3f}, k_sat={k_sat_in:.2f}, k_cut={k_cut_in:.1f}")
print(f"  Out-degree Barabási model: γ={gamma_out:.3f}, k_sat={k_sat_out:.2f}, k_cut={k_cut_out:.1f}")
print(f"  (Sanity check: APS in-degree γ should be near 3.0; Barabási reports γ≈3.03)")

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

# ── 5. BFS overlap with gold bibliography, by traversal direction ─────────────
print("Computing BFS overlap curves (k=5 seeds, backward vs forward vs bidirectional)...")

def bfs_overlap_by_direction(seed_set, gold_refs, direction, max_depth=6):
    """
    BFS from seed_set in the specified direction. Returns list of dicts:
      depth, overlap (|visited ∩ gold_refs| / |gold_refs|), corpus_size.

    direction:
      'backward'  — follow cites.get(node) (references made by node)
      'forward'   — follow cited_by.get(node) (papers that cite node)
      'both'      — follow both directions (bidirectional)

    Seeds come from the gold_refs set (top-k by in-degree), NOT from the
    survey DOI itself.
    """
    gold_refs = set(gold_refs)
    visited   = set(seed_set)
    frontier  = set(seed_set)
    overlap0  = len(visited & gold_refs) / len(gold_refs) if gold_refs else 0.0
    curve = [{"depth": 0, "overlap": overlap0, "corpus_size": len(visited)}]
    for d in range(1, max_depth + 1):
        nxt = set()
        for node in frontier:
            if direction in ("backward", "both"):
                for nb in cites.get(node, set()):
                    if nb not in visited:
                        visited.add(nb); nxt.add(nb)
            if direction in ("forward", "both"):
                for nb in cited_by.get(node, set()):
                    if nb not in visited:
                        visited.add(nb); nxt.add(nb)
        frontier = nxt
        overlap = len(visited & gold_refs) / len(gold_refs) if gold_refs else 0.0
        curve.append({"depth": d, "overlap": overlap, "corpus_size": len(visited)})
        if not frontier:
            break
    return curve

DIRECTION_STYLES = {
    "backward": {"color": "#2166ac", "label": "Backward only\n(follow reference lists)"},
    "forward":  {"color": "#d6604d", "label": "Forward only\n(follow citers)"},
    "both":     {"color": "#1a9850", "label": "Bidirectional"},
}
K_SEEDS = 5

fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

bfs_by_direction = {}
for ax, (key, info) in zip(axes, gt.items()):
    s         = STYLE[key]
    gold_refs = set(info["gold_refs"])
    # Seeds = top-5 gold refs by in-degree within APS (most cited = easiest to find)
    gold_sorted = sorted(gold_refs, key=lambda x: len(cited_by.get(x, set())), reverse=True)
    seeds = set(gold_sorted[:K_SEEDS])

    key_curves = {}
    for direction, dstyle in DIRECTION_STYLES.items():
        curve = bfs_overlap_by_direction(seeds, gold_refs, direction, max_depth=6)
        key_curves[direction] = curve
        depths   = [pt["depth"]   for pt in curve]
        overlaps = [pt["overlap"] for pt in curve]
        ax.plot(depths, overlaps, "o-", color=dstyle["color"], lw=2, ms=5,
                label=dstyle["label"])

    bfs_by_direction[key] = key_curves
    ax.axhline(1.0, color="grey", lw=0.8, ls=":")
    ax.set_xlabel("BFS depth")
    ax.set_ylabel("Overlap with gold bibliography")
    ax.set_title(s["label"], fontsize=9, wrap=True)
    ax.set_ylim(0, 1.08)
    ax.legend(fontsize=8)

handles, labels_leg = axes[0].get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=3, fontsize=9,
           bbox_to_anchor=(0.5, -0.03))
fig.suptitle(
    "BFS Overlap with Gold Bibliography by Traversal Direction\n"
    "(k=5 seeds from gold set; shows why bidirectional is necessary)",
    fontsize=11)
fig.tight_layout(rect=[0, 0.1, 1, 1])
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
    # Barabási corrected model: p_k ~ (k + k_sat)^(-γ) * exp(-k / k_cut)
    # fitted by MLE (see plot_degree_dist).  Pure power-law (straight log-log
    # line) is wrong for citation networks — Barabási 2016 Network Science §4.
    "in_degree_gamma":  float(gamma_in),
    "in_degree_k_sat":  float(k_sat_in),
    "in_degree_k_cut":  float(k_cut_in),
    "out_degree_gamma": float(gamma_out),
    "out_degree_k_sat": float(k_sat_out),
    "out_degree_k_cut": float(k_cut_out),
    "n_wccs":           len(sizes),
    "largest_wcc_size": int(sizes[0]),
    "largest_wcc_frac": float(sizes[0] / N),
    "bfs_by_direction": bfs_by_direction,
    "pareto_stats":     pareto_stats,
}

with open(OUT / "graph_stats.json", "w") as f:
    json.dump(stats, f, indent=2)

print(f"\nAll stats saved to {OUT / 'graph_stats.json'}")
print("All figures saved to", FIGS)
print("Done.")
