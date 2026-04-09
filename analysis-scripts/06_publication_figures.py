"""
Publication-quality figures for the academic paper.
All figures use a consistent, clean style with clear visual cues.

Figure list:
  Fig 1: APS corpus overview — degree distribution (in + out) with power-law fits + Lorenz curve
  Fig 2: BFS reachability curves — forward vs backward for all 3 surveys (log-scale)
  Fig 3: Traversal strategy comparison — corpus size vs recall at depth 3 (bubble chart)
  Fig 4: Screen yield collapse — yield vs BFS depth, survey-seeded
  Fig 5: Cold-start recall recovery — per-round recall for k=20, all 3 seed qualities
  Fig 6: Recall vs seed size — final recall after 4 rounds, all seed qualities
  Fig 7: Miss analysis — in-degree comparison (missed vs recovered) + BFS distance
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
from matplotlib.gridspec import GridSpec
from collections import defaultdict
from pathlib import Path
import re

# ── Style ─────────────────────────────────────────────────────────────────────
STYLE = {
    "font.family":        "DejaVu Sans",
    "font.size":          11,
    "axes.titlesize":     12,
    "axes.labelsize":     11,
    "xtick.labelsize":    10,
    "ytick.labelsize":    10,
    "legend.fontsize":    9.5,
    "figure.dpi":         150,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          True,
    "grid.alpha":         0.3,
    "grid.linestyle":     "--",
    "lines.linewidth":    2.0,
    "patch.edgecolor":    "none",
}
plt.rcParams.update(STYLE)

# Palette — accessible, print-friendly
C = {
    "S1": "#2166ac",   # blue
    "S2": "#d6604d",   # red-orange
    "S3": "#4dac26",   # green
    "bwd": "#1a1a2e",  # near-black
    "fwd": "#e63946",  # vivid red
    "bidir": "#457b9d",
    "p80": "#2a9d8f",  # teal
    "miss": "#e63946",
    "rec":  "#457b9d",
    "gray": "#adb5bd",
    "gold": "#f4a261",
}

SURVEY = {
    "S1_MIT":  {"color": C["S1"], "label": "S1: Metal-insulator transitions (1998)", "short": "S1 (1998)"},
    "S2_UCG":  {"color": C["S2"], "label": "S2: Ultracold gases (2008)",             "short": "S2 (2008)"},
    "S3_TOPO": {"color": C["S3"], "label": "S3: Topological photonics (2019)",        "short": "S3 (2019)"},
}

_REPO = Path(__file__).parent.parent
APS_CSV = _REPO / "data-aps" / "processed" / "aps-dataset-citations-2022.csv"
OUT  = _REPO / "data-aps" / "outputs"
FIGS = OUT / "pub_figures"
FIGS.mkdir(parents=True, exist_ok=True)

# ── Load data ─────────────────────────────────────────────────────────────────
print("Loading data...")
df_csv = pd.read_csv(APS_CSV)

with open(OUT / "graph_stats.json")       as f: gstats = json.load(f)
with open(OUT / "traversal_results.json") as f: trav   = json.load(f)
with open(OUT / "cold_start_results_lowseed.json") as f: cold  = json.load(f)
with open(OUT / "ground_truth.json")      as f: gt     = json.load(f)

miss = {
    "S1_MIT":  pd.read_csv(OUT / "missed_papers_S1_MIT.csv"),
    "S2_UCG":  pd.read_csv(OUT / "missed_papers_S2_UCG.csv"),
    "S3_TOPO": pd.read_csv(OUT / "missed_papers_S3_TOPO.csv"),
}

# Build degree sequences for Fig 1
print("Building degree sequences...")
cites_count    = df_csv["citing_doi"].value_counts()
cited_by_count = df_csv["cited_doi"].value_counts()
in_deg  = cited_by_count.values
out_deg = cites_count.values

# ── Helper: Lorenz curve ──────────────────────────────────────────────────────
def lorenz(vals):
    s = np.sort(vals)
    n = len(s)
    cs = np.cumsum(s)
    return np.arange(1, n+1) / n, cs / cs[-1]

# ── Helper: power-law fit (MLE for discrete) ──────────────────────────────────
def pl_fit(vals, x_min=5):
    v = vals[vals >= x_min]
    gamma = 1 + len(v) / np.sum(np.log(v / (x_min - 0.5)))
    return gamma

# ─────────────────────────────────────────────────────────────────────────────
# FIG 1: Degree distributions + Lorenz curves
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 1: Degree distributions...")
fig = plt.figure(figsize=(14, 5))
gs  = GridSpec(1, 3, figure=fig, wspace=0.38)

# Panel A: In-degree distribution
ax1 = fig.add_subplot(gs[0])
bins = np.logspace(0, 4, 50)
ax1.hist(in_deg, bins=bins, color=C["S1"], alpha=0.75, density=True, label="Empirical")
# Power-law overlay
gamma_in = gstats["in_degree_gamma"]
x_fit = np.logspace(0.7, 4, 200)
C_fit = (gamma_in - 1) * 5**(gamma_in - 1)
ax1.plot(x_fit, C_fit * x_fit**(-gamma_in), color="#d62728", lw=2,
         label=fr"Power law ($\gamma={gamma_in:.2f}$)")
ax1.set_xscale("log"); ax1.set_yscale("log")
ax1.set_xlabel("In-degree $k_{in}$ (citations received)")
ax1.set_ylabel("Probability density")
ax1.set_title("(a) In-degree distribution")
ax1.legend()
ax1.text(0.97, 0.97, f"Gini = {gstats['in_degree_gini']:.3f}",
         transform=ax1.transAxes, ha="right", va="top",
         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#aaa", alpha=0.8))

# Panel B: Out-degree distribution
ax2 = fig.add_subplot(gs[1])
bins2 = np.logspace(0, 3, 40)
ax2.hist(out_deg, bins=bins2, color=C["S3"], alpha=0.75, density=True, label="Empirical")
gamma_out = gstats["out_degree_gamma"]
x_fit2 = np.logspace(0.5, 3, 200)
C_fit2 = (gamma_out - 1) * 5**(gamma_out - 1)
ax2.plot(x_fit2, C_fit2 * x_fit2**(-gamma_out), color="#d62728", lw=2,
         label=fr"Power law ($\gamma={gamma_out:.2f}$)")
ax2.set_xscale("log"); ax2.set_yscale("log")
ax2.set_xlabel("Out-degree $k_{out}$ (references made)")
ax2.set_ylabel("Probability density")
ax2.set_title("(b) Out-degree distribution")
ax2.legend()
ax2.text(0.97, 0.97, f"Gini = {gstats['out_degree_gini']:.3f}",
         transform=ax2.transAxes, ha="right", va="top",
         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#aaa", alpha=0.8))

# Panel C: Lorenz curves
ax3 = fig.add_subplot(gs[2])
xi, yi = lorenz(in_deg)
xo, yo = lorenz(out_deg)
ax3.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="Perfect equality")
ax3.plot(xi[::500], yi[::500], color=C["S1"], lw=2, label=f"In-degree (Gini={gstats['in_degree_gini']:.3f})")
ax3.plot(xo[::500], yo[::500], color=C["S3"], lw=2, label=f"Out-degree (Gini={gstats['out_degree_gini']:.3f})")
ax3.fill_between(xi[::500], xi[::500], yi[::500], alpha=0.12, color=C["S1"])
ax3.fill_between(xo[::500], xo[::500], yo[::500], alpha=0.12, color=C["S3"])
ax3.set_xlabel("Cumulative fraction of papers")
ax3.set_ylabel("Cumulative fraction of edges")
ax3.set_title("(c) Lorenz curves")
ax3.legend(loc="upper left")

fig.suptitle("APS Citation Graph: Structural Properties (709,803 papers, 9,833,191 edges)",
             fontsize=12, y=1.01)
fig.tight_layout()
fig.savefig(FIGS / "fig1_degree_distributions.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig1_degree_distributions.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 2: BFS reachability curves
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 2: BFS overlap with gold bibliography (seed-size curves)...")
# New format: gstats["bfs_reachability"][survey_key][str(k)] = [{depth, overlap, corpus_size}]
SEED_SIZES_REACH  = [1, 5, 10, 20]
SEED_COLORS_REACH = ["#d73027", "#f46d43", "#74add1", "#313695"]

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

for ax, (key, info) in zip(axes, SURVEY.items()):
    bfs = gstats["bfs_reachability"][key]
    gold_size = len(gt[key]["gold_refs"])

    for k_s, color in zip(SEED_SIZES_REACH, SEED_COLORS_REACH):
        curve = bfs.get(str(k_s), [])
        if not curve:
            continue
        depths   = [pt["depth"]   for pt in curve]
        overlaps = [pt["overlap"] for pt in curve]
        ax.plot(depths, overlaps, "o-", color=color, lw=2, ms=5, label=f"k={k_s}")

    ax.axhline(1.0, color=C["gold"], lw=1.2, ls=":", alpha=0.9)
    ax.text(0.1, 1.02, f"Full gold set ({gold_size} papers)", color=C["gold"],
            fontsize=8, va="bottom")
    ax.set_xlabel("BFS depth")
    ax.set_ylabel("Overlap with gold bibliography")
    ax.set_title(info["label"], fontsize=10)
    ax.set_ylim(0, 1.12)
    ax.set_xticks([0, 1, 2, 3, 4, 5, 6])
    ax.legend(loc="lower right", fontsize=8, title="Seed size")

fig.suptitle(
    "BFS Overlap with Gold Bibliography vs. Depth\n"
    "(top-k seeds from gold set by citation count; bidirectional traversal)",
    fontsize=12, y=1.02)
fig.tight_layout()
fig.savefig(FIGS / "fig2_bfs_reachability.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig2_bfs_reachability.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 3: Strategy comparison — recall vs corpus size at depth 3 (bubble chart)
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 3: Strategy comparison...")
strategies = {
    "Backward":       {"key": "backward",      "color": C["bwd"],   "marker": "o"},
    "Forward":        {"key": "forward",       "color": C["fwd"],   "marker": "s"},
    "Bidirectional":  {"key": "bidir",         "color": C["bidir"], "marker": "^"},
    "Bidir+Pareto50": {"key": "bidir_pareto50","color": "#e9c46a",  "marker": "D"},
    "Bidir+Pareto80": {"key": "bidir_pareto80","color": C["p80"],   "marker": "P"},
    "Bidir+Pareto90": {"key": "bidir_pareto90","color": "#6a4c93",  "marker": "X"},
}

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
DEPTH = 3

for ax, (skey, sinfo) in zip(axes, SURVEY.items()):
    for strat_name, strat in strategies.items():
        data = trav[skey].get(strat["key"], [])
        if not data: continue
        row = next((r for r in data if r["depth"] == DEPTH), None)
        if row is None: row = data[-1]
        recall  = row["recall_refs"]
        corpus  = row["corpus_size"]
        ax.scatter(corpus / 1000, recall, s=120, color=strat["color"],
                   marker=strat["marker"], zorder=5, label=strat_name,
                   edgecolors="white", linewidths=0.8)

    ax.set_xlabel("Corpus size at depth 3 (×1,000 papers)")
    ax.set_ylabel("Recall (gold references)")
    ax.set_title(sinfo["label"], fontsize=10)
    ax.set_xlim(left=0)
    ax.set_ylim(-0.05, 1.15)
    ax.axhline(1.0, color="gray", lw=1, ls="--", alpha=0.5)

    # Annotate the Pareto80 point
    row80 = next((r for r in trav[skey].get("bidir_pareto80", []) if r["depth"] == DEPTH), None)
    if row80:
        ax.annotate("Pareto-80\n(optimal)", xy=(row80["corpus_size"]/1000, row80["recall_refs"]),
                    xytext=(row80["corpus_size"]/1000 + 15, row80["recall_refs"] - 0.12),
                    fontsize=8, color=C["p80"],
                    arrowprops=dict(arrowstyle="->", color=C["p80"], lw=1))

handles = [mpatches.Patch(color=v["color"], label=k) for k, v in strategies.items()]
axes[1].legend(handles=handles, loc="lower right", ncol=2, fontsize=8.5)

fig.suptitle("Coverage–Cost Trade-off: Recall vs Corpus Size at BFS Depth 3",
             fontsize=12, y=1.01)
fig.tight_layout()
fig.savefig(FIGS / "fig3_strategy_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig3_strategy_comparison.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 4: Screen yield collapse (survey-seeded, bidir_pareto80)
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 4: Screen yield collapse...")
# Compute yield from traversal_results: new gold / new nodes at each depth
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

for ax, (skey, sinfo) in zip(axes, SURVEY.items()):
    data = trav[skey].get("bidir_pareto80", [])
    depths, yields = [], []
    prev_corpus = 0; prev_gold = 0
    gold_size = len(gt[skey]["gold_refs"])
    for row in data:
        d = row["depth"]
        c = row["corpus_size"]
        g = row["tp_refs"]
        new_nodes = c - prev_corpus
        new_gold  = g - prev_gold
        sy = new_gold / new_nodes if new_nodes > 0 else 0
        depths.append(d); yields.append(sy)
        prev_corpus = c; prev_gold = g

    ax.bar(depths, yields, color=sinfo["color"], alpha=0.8, width=0.6, zorder=3)
    ax.axhline(0.05, color="#d62728", lw=1.8, ls="--", label="Yield threshold (0.05)")
    ax.set_xlabel("BFS depth")
    ax.set_ylabel("Screen yield (new gold / new nodes)")
    ax.set_title(sinfo["label"], fontsize=10)
    ax.set_xticks(depths)
    ax.legend()

    # Annotate depth-1 yield
    if len(yields) > 1:
        ax.text(1, yields[1] + 0.005, f"{yields[1]:.3f}", ha="center", fontsize=9,
                color=sinfo["color"], fontweight="bold")
    # Annotate depth-2 yield
    if len(yields) > 2:
        ax.text(2, yields[2] + 0.001, f"{yields[2]:.4f}", ha="center", fontsize=9,
                color=sinfo["color"])

fig.suptitle("Screen Yield per BFS Depth: Rapid Collapse Validates the Stopping Criterion\n"
             "(Strategy: Bidirectional + Pareto-80 filter, seeded from top-5 gold references)",
             fontsize=11, y=1.03)
fig.tight_layout()
fig.savefig(FIGS / "fig4_screen_yield_collapse.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig4_screen_yield_collapse.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 5: Cold-start recall recovery per round (k=20, all 3 seed qualities)
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 5: Cold-start recall per round...")
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

SEED_STYLES = {
    "top_k":       {"color": C["S1"],   "ls": "-",  "marker": "o", "label": "Top-5 by citation count\n(best-case search)"},
    "random":      {"color": C["p80"],  "ls": "--", "marker": "s", "label": "Random 5 gold refs\n(average-case search)"},
    "contaminated":{"color": C["fwd"],  "ls": ":",  "marker": "^", "label": "5 seeds, 50% irrelevant\n(noisy search)"},
}

for ax, (skey, sinfo) in zip(axes, SURVEY.items()):
    for sq, ss in SEED_STYLES.items():
        rounds_data = cold[skey].get(sq, {}).get("5", [])
        if not rounds_data: continue
        rounds  = [r["round"]  for r in rounds_data]
        recalls = [r["recall"] for r in rounds_data]
        ax.plot(rounds, recalls, color=ss["color"], ls=ss["ls"],
                marker=ss["marker"], ms=8, lw=2.2, label=ss["label"])

    ax.axhline(1.0, color="gray", lw=1, ls="--", alpha=0.5)
    ax.set_xlabel("Escape Hatch round")
    ax.set_ylabel("Recall (fraction of gold references recovered)")
    ax.set_title(sinfo["label"], fontsize=10)
    ax.set_xticks([1, 2])
    ax.set_ylim(0.75, 1.05)
    ax.legend(loc="lower right", fontsize=8.5)

fig.suptitle("Cold-Start Recall Recovery per Escape Hatch Round ($k=5$ initial seeds)",
             fontsize=12, y=1.01)
fig.tight_layout()
fig.savefig(FIGS / "fig5_cold_start_recall_per_round.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig5_cold_start_recall_per_round.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 6: Final recall vs seed size (after 4 rounds)
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 6: Recall vs seed size...")
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
K_VALS = [1, 2, 3, 4, 5, 10]

for ax, (skey, sinfo) in zip(axes, SURVEY.items()):
    for sq, ss in SEED_STYLES.items():
        recalls = []
        for k in K_VALS:
            rounds_data = cold[skey].get(sq, {}).get(str(k), [])
            if rounds_data:
                recalls.append(rounds_data[-1]["recall"])
            else:
                recalls.append(np.nan)
        ax.plot(K_VALS, recalls, color=ss["color"], ls=ss["ls"],
                marker=ss["marker"], ms=8, lw=2.2, label=ss["label"])

    ax.axhline(1.0, color="gray", lw=1, ls="--", alpha=0.5)
    ax.set_xlabel("Initial seed size $k$")
    ax.set_ylabel("Final recall (after 2 rounds)")
    ax.set_title(sinfo["label"], fontsize=10)
    ax.set_xticks(K_VALS)
    ax.set_ylim(0.75, 1.05)
    ax.legend(loc="lower right", fontsize=8.5)

fig.suptitle("Final Recall vs Initial Seed Size (After 2 Escape Hatch Rounds)",
             fontsize=12, y=1.01)
fig.tight_layout()
fig.savefig(FIGS / "fig6_recall_vs_seed_size.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig6_recall_vs_seed_size.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 7: Miss analysis — 2-panel: in-degree comparison + BFS distance
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 7: Miss analysis...")

# Read recovered paper properties from the miss CSVs and ground truth
# We need recovered paper properties — rebuild from ground truth
from collections import defaultdict as ddict
cites_cnt    = df_csv["citing_doi"].value_counts().to_dict()
cited_by_cnt = df_csv["cited_doi"].value_counts().to_dict()

def parse_doi(doi):
    m = re.search(r'10\.1103/([A-Za-z]+)\.(\d+)\.', str(doi))
    if not m: return "Unknown", None
    journal = m.group(1)
    vol = int(m.group(2))
    year_map = {
        "PhysRevB": 1970+vol-1, "PhysRevD": 1970+vol-1, "PhysRevA": 1970+vol-1,
        "PhysRevC": 1970+vol-1, "PhysRevE": 1993+vol-48,
        "PhysRevLett": 1958+vol-1, "RevModPhys": 1929+vol-1,
        "PhysRevX": 2011+vol-1, "PhysRevApplied": 2014+vol-1,
        "PhysRevMaterials": 2017+vol-1, "PhysRevFluids": 2016+vol-1,
        "PhysRevResearch": 2019+vol-1,
    }
    return journal, year_map.get(journal, None)

rec_data = {}
for key, info in gt.items():
    missed_dois = set(miss[key]["doi"].tolist()) if len(miss[key]) > 0 else set()
    recovered_dois = set(info["gold_refs"]) - missed_dois
    rows = []
    for d in recovered_dois:
        in_d  = cited_by_cnt.get(d, 0)
        out_d = cites_cnt.get(d, 0)
        _, year = parse_doi(d)
        rows.append({"doi": d, "in_deg": in_d, "out_deg": out_d, "year": year})
    rec_data[key] = pd.DataFrame(rows)

fig = plt.figure(figsize=(14, 9))
gs  = GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

for col, (key, sinfo) in enumerate(SURVEY.items()):
    dm = miss[key]
    dr = rec_data[key]

    # Top row: in-degree comparison (box plots)
    ax_top = fig.add_subplot(gs[0, col])
    if len(dm) > 0:
        data_to_plot = [dr["in_deg"].clip(upper=2000).values, dm["in_deg"].clip(upper=2000).values]
        bp = ax_top.boxplot(data_to_plot, patch_artist=True, widths=0.5,
                            medianprops=dict(color="white", lw=2.5),
                            whiskerprops=dict(lw=1.5),
                            capprops=dict(lw=1.5),
                            flierprops=dict(marker=".", ms=4, alpha=0.4))
        bp["boxes"][0].set_facecolor(sinfo["color"])
        bp["boxes"][0].set_alpha(0.75)
        bp["boxes"][1].set_facecolor(C["miss"])
        bp["boxes"][1].set_alpha(0.75)
        ax_top.set_xticks([1, 2])
        ax_top.set_xticklabels([f"Recovered\n(n={len(dr)})", f"Missed\n(n={len(dm)})"])

        # Annotate medians
        med_rec  = np.median(dr["in_deg"])
        med_miss = np.median(dm["in_deg"])
        ax_top.text(1, med_rec  + 20, f"Median: {int(med_rec)}",  ha="center", fontsize=8.5, color=sinfo["color"])
        ax_top.text(2, med_miss + 20, f"Median: {int(med_miss)}", ha="center", fontsize=8.5, color=C["miss"])
    else:
        ax_top.text(0.5, 0.5, "No missed papers\n(100% recall)", ha="center", va="center",
                    transform=ax_top.transAxes, fontsize=11, color=C["p80"],
                    bbox=dict(boxstyle="round,pad=0.5", fc="#e8f5e9", ec=C["p80"]))
        ax_top.set_xticks([])

    ax_top.set_ylabel("In-degree (citations received)")
    ax_top.set_title(f"(a{col+1}) {sinfo['short']}", fontsize=10)

    # Bottom row: BFS distance from recovered set
    ax_bot = fig.add_subplot(gs[1, col])
    if len(dm) > 0 and "bfs_dist_from_recovered" in dm.columns:
        dist_counts = dm["bfs_dist_from_recovered"].value_counts().sort_index()
        bars = ax_bot.bar(dist_counts.index.astype(int), dist_counts.values,
                          color=sinfo["color"], alpha=0.8, width=0.5, zorder=3)
        # Label each bar
        for bar, val in zip(bars, dist_counts.values):
            ax_bot.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                        str(val), ha="center", va="bottom", fontsize=10, fontweight="bold")
        ax_bot.set_xticks(dist_counts.index.astype(int))
        ax_bot.set_xlabel("BFS distance from recovered set")
        ax_bot.set_ylabel("Number of missed papers")
        ax_bot.set_title(f"(b{col+1}) {sinfo['short']}", fontsize=10)
        ax_bot.set_ylim(0, dist_counts.max() + 1.5)
    else:
        ax_bot.text(0.5, 0.5, "No missed papers", ha="center", va="center",
                    transform=ax_bot.transAxes, fontsize=11, color=C["p80"],
                    bbox=dict(boxstyle="round,pad=0.5", fc="#e8f5e9", ec=C["p80"]))
        ax_bot.set_xticks([])

fig.suptitle("Anatomy of the Residual Coverage Gap: Structural Properties of Missed Papers\n"
             "Top row: in-degree distribution (missed vs recovered). "
             "Bottom row: BFS distance from recovered set to missed papers.",
             fontsize=11, y=1.02)
fig.savefig(FIGS / "fig7_miss_analysis.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig7_miss_analysis.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 8: Efficiency frontier — Pareto filter level vs corpus reduction
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 8: Efficiency frontier...")
pareto_keys = {
    "bidir":          {"p": 100, "label": "No filter"},
    "bidir_pareto90": {"p": 90,  "label": "Pareto-90"},
    "bidir_pareto80": {"p": 80,  "label": "Pareto-80"},
    "bidir_pareto70": {"p": 70,  "label": "Pareto-70"},
    "bidir_pareto50": {"p": 50,  "label": "Pareto-50"},
}

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
DEPTH3 = 3

for ax, (skey, sinfo) in zip(axes, SURVEY.items()):
    bidir_corpus = None
    for pk, pinfo in pareto_keys.items():
        data = trav[skey].get(pk, [])
        if not data: continue
        row = next((r for r in data if r["depth"] == DEPTH3), data[-1])
        corpus  = row["corpus_size"]
        recall  = row["recall_refs"]
        if pk == "bidir": bidir_corpus = corpus
        ax.scatter(corpus / 1000, recall, s=150,
                   color=sinfo["color"], zorder=5,
                   edgecolors="white", linewidths=1.2)
        ax.text(corpus/1000 + 2, recall - 0.015, pinfo["label"], fontsize=8.5,
                color=sinfo["color"])

    if bidir_corpus:
        ax.axvline(bidir_corpus / 1000, color="gray", lw=1, ls=":", alpha=0.6)
        ax.text(bidir_corpus/1000 + 1, 0.05, "No filter", fontsize=8, color="gray", rotation=90)

    ax.set_xlabel("Corpus size at depth 3 (×1,000 papers)")
    ax.set_ylabel("Recall (gold references)")
    ax.set_title(sinfo["label"], fontsize=10)
    ax.set_ylim(-0.05, 1.15)
    ax.axhline(1.0, color="gray", lw=1, ls="--", alpha=0.5)

fig.suptitle("Efficiency Frontier: Pareto Filter Threshold vs Corpus Size at Depth 3\n"
             "(All strategies achieve 100% recall — the filter only reduces cost)",
             fontsize=11, y=1.03)
fig.tight_layout()
fig.savefig(FIGS / "fig8_efficiency_frontier.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig8_efficiency_frontier.png")

print(f"\nAll publication figures saved to {FIGS}")
print("Done.")
