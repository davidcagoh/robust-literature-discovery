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

# ── Helper: Barabási corrected model curve ────────────────────────────────────
# p_k ~ (k + k_sat)^(-γ) * exp(-k / k_cut), fitted by MLE in script 02.
# Parameters are loaded from graph_stats.json (keys: *_gamma, *_k_sat, *_k_cut).
# NOTE: Fig 1 panels A and B use the corrected model overlay, NOT a straight
# power-law line — pure power-law is systematically wrong for citation networks
# (Barabási 2016 Network Science §4).  Script 02 generates the intermediate
# deg_in.png / deg_out.png figures independently; this script rebuilds the
# panel from the stored parameters to match the publication layout.
def barabasi_corrected_curve(fit_k_arr, gamma, k_sat, k_cut, total_nodes, max_k):
    """Return fitted count curve y(k) for an array of k values.

    Normalises so that sum_k p_k = 1 over k = 1..max_k, then scales by
    total_nodes to overlay on an empirical count scatter.
    """
    k_norm = np.arange(1, max_k + 1, dtype=float)
    f_norm = (k_norm + k_sat) ** (-gamma) * np.exp(-k_norm / k_cut)
    Z = f_norm.sum()
    f_fit = (fit_k_arr + k_sat) ** (-gamma) * np.exp(-fit_k_arr / k_cut)
    return (f_fit / Z) * total_nodes

# ─────────────────────────────────────────────────────────────────────────────
# FIG 1: Degree distributions + Lorenz curves
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 1: Degree distributions...")
fig = plt.figure(figsize=(14, 5))
gs  = GridSpec(1, 3, figure=fig, wspace=0.38)

# Panel A: In-degree distribution
# Uses the Barabási corrected model parameters stored in graph_stats.json by
# script 02.  The fit curve is p_k ~ (k+k_sat)^(-γ)*exp(-k/k_cut), NOT a pure
# power law — see barabasi_corrected_curve() helper above.
ax1 = fig.add_subplot(gs[0])
in_deg_counts = np.bincount(in_deg)
k_in = np.arange(len(in_deg_counts))
mask_in = (k_in > 0) & (in_deg_counts > 0)
ax1.scatter(k_in[mask_in], in_deg_counts[mask_in], s=4, alpha=0.55,
            color=C["S1"], linewidths=0, label="Empirical")
gamma_in  = gstats["in_degree_gamma"]
k_sat_in  = gstats.get("in_degree_k_sat",  1.0)
k_cut_in  = gstats.get("in_degree_k_cut",  1000.0)
x_fit_in  = np.logspace(0, np.log10(k_in[mask_in].max()), 400)
y_fit_in  = barabasi_corrected_curve(x_fit_in, gamma_in, k_sat_in, k_cut_in,
                                      in_deg_counts[mask_in].sum(),
                                      k_in[mask_in].max())
ax1.plot(x_fit_in, y_fit_in, color="#d62728", lw=2,
         label=(fr"Barabási model ($\gamma={gamma_in:.2f}$, "
                fr"$k_{{sat}}={k_sat_in:.1f}$, $k_{{cut}}={k_cut_in:.0f}$)"))
ax1.set_xscale("log"); ax1.set_yscale("log")
ax1.set_ylim(bottom=0.5)   # clip y-axis: counts are integers ≥ 1
ax1.set_xlabel("In-degree $k_{in}$ (citations received)")
ax1.set_ylabel("Count $N(k)$")
ax1.set_title("(a) In-degree distribution\nPure power-law fails (Barabási 2016 §4)", fontsize=10)
ax1.legend(fontsize=8)
ax1.text(0.97, 0.97, f"Gini = {gstats['in_degree_gini']:.3f}",
         transform=ax1.transAxes, ha="right", va="top",
         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#aaa", alpha=0.8))

# Panel B: Out-degree distribution — empirical only, no model fit.
# Out-degree (bibliography length) is bounded by paper-writing conventions,
# not governed by preferential attachment.  It is NOT scale-free, so fitting
# the Barabási corrected model here would be inappropriate.
ax2 = fig.add_subplot(gs[1])
out_deg_counts = np.bincount(out_deg)
k_out = np.arange(len(out_deg_counts))
mask_out = (k_out > 0) & (out_deg_counts > 0)
ax2.scatter(k_out[mask_out], out_deg_counts[mask_out], s=4, alpha=0.55,
            color=C["S3"], linewidths=0, label="Empirical")
ax2.set_xscale("log"); ax2.set_yscale("log")
ax2.set_ylim(bottom=0.5)   # whole-number counts only; no sub-1 axis range
ax2.set_xlabel("Out-degree $k_{out}$ (references made)")
ax2.set_ylabel("Count $N(k)$")
ax2.set_title("(b) Out-degree distribution\n"
              "Bibliography length is bounded — not scale-free", fontsize=10)
ax2.text(0.97, 0.97, f"Gini = {gstats['out_degree_gini']:.3f}",
         transform=ax2.transAxes, ha="right", va="top",
         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#aaa", alpha=0.8))
ax2.text(0.05, 0.05,
         "Power-law model not appropriate:\nout-degree is constrained by\nbibliography length norms",
         transform=ax2.transAxes, ha="left", va="bottom", fontsize=8,
         color="#888", style="italic")

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
# FIG 2: BFS reachability curves by traversal direction
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 2: BFS overlap with gold bibliography (direction-comparison curves)...")
# Format: gstats["bfs_by_direction"][survey_key][direction] = [{depth, overlap, corpus_size}]
# Directions: "backward", "forward", "both"
DIRECTION_STYLES = {
    "backward":       {"color": "#2166ac", "label": "Backward only (follow reference lists)", "ls": "-"},
    "forward":        {"color": "#d6604d", "label": "Forward only (follow citers)",            "ls": "-"},
    "both":           {"color": "#1a9850", "label": "Bidirectional (unfiltered)",               "ls": "-"},
    "bidir_pareto80": {"color": C["p80"],  "label": "Bidir + Pareto-80 (operational)",         "ls": "--"},
}

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

for ax, (key, info) in zip(axes, SURVEY.items()):
    bfs_dir   = gstats["bfs_by_direction"][key]   # backward / forward / both
    bfs_trav  = trav[key]                          # bidir_pareto80 etc.
    gold_size = len(gt[key]["gold_refs"])

    for direction, dstyle in DIRECTION_STYLES.items():
        # backward/forward/both come from gstats; pareto variants from trav
        if direction in bfs_dir:
            curve = bfs_dir[direction]
            depths   = [pt["depth"]        for pt in curve]
            overlaps = [pt["overlap"]       for pt in curve]
        elif direction in bfs_trav:
            curve = bfs_trav[direction]
            depths   = [pt["depth"]        for pt in curve]
            overlaps = [pt["recall_refs"]   for pt in curve]
        else:
            continue
        ax.plot(depths, overlaps, "o", ls=dstyle["ls"],
                color=dstyle["color"], lw=2, ms=5, label=dstyle["label"])

    ax.axhline(1.0, color=C["gold"], lw=1.2, ls=":", alpha=0.9)
    ax.text(0.1, 1.02, f"Full gold set ({gold_size} papers)", color=C["gold"],
            fontsize=8, va="bottom")
    ax.set_xlabel("BFS depth")
    ax.set_ylabel("Overlap with gold bibliography")
    ax.set_title(info["label"], fontsize=10)
    ax.set_ylim(0, 1.12)
    ax.set_xticks([0, 1, 2, 3, 4, 5, 6])
    ax.legend(loc="lower right", fontsize=8.5)

fig.suptitle(
    "BFS Overlap with Gold Bibliography by Traversal Direction\n"
    "(oracle seeds: k=5 drawn from gold bibliography — upper bound on cold-start performance; dashed = Pareto-80 operational default)",
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
        ax.annotate("Pareto-80\n(operational default;\nsee §6 for yield-stopped\ncold-start results)",
                    xy=(row80["corpus_size"]/1000, row80["recall_refs"]),
                    xytext=(row80["corpus_size"]/1000 + 15, row80["recall_refs"] - 0.15),
                    fontsize=7.5, color=C["p80"],
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
# FIG 4: Stacked bars — x = BFS depth pass, stacks = Round 1 / Round 2
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 4: Stacked bars by depth pass (R1 + R2 contributions)...")
# x-axis: Depth 1 BFS Pass | Depth 2 BFS Pass
# Each bar stacked: Round 1 new gold (solid, bottom) + Round 2 new gold (lighter, top)
# Annotate % of gold set inside each portion.
GOLD_TOTALS = {k: len(v["gold_refs"]) for k, v in gt.items()}

fig, axes = plt.subplots(1, 3, figsize=(13, 5.5), sharey=False)

R1_ALPHA = 1.0
R2_ALPHA = 0.38
BAR_W    = 0.52

for ax, (skey, sinfo) in zip(axes, SURVEY.items()):
    rounds_data = cold[skey].get("top_k", {}).get("5", [])
    gold_total  = GOLD_TOTALS.get(skey, 1)
    color       = sinfo["color"]

    # Collect (depth → {r1: new_gold, r2: new_gold})
    depth_data: dict[int, dict] = {}
    for round_idx, round_label, alpha in [(0, "Round 1", R1_ALPHA), (1, "Round 2", R2_ALPHA)]:
        if round_idx >= len(rounds_data):
            continue
        for entry in rounds_data[round_idx].get("curve", []):
            d = entry["depth"]
            if d == 0:
                continue
            depth_data.setdefault(d, {})
            depth_data[d][round_label] = entry["new_gold"]

    depths_present = sorted(depth_data.keys())
    x_pos = list(range(len(depths_present)))
    x_labels = [f"BFS Depth {d}" for d in depths_present]

    r1_max = max((depth_data[d].get("Round 1", 0) for d in depths_present), default=1)

    for xi, depth in zip(x_pos, depths_present):
        r1 = depth_data[depth].get("Round 1", 0)
        r2 = depth_data[depth].get("Round 2", 0)

        # Round 1 segment (bottom)
        ax.bar(xi, r1, width=BAR_W, color=color, alpha=R1_ALPHA, zorder=3,
               label="Round 1" if xi == 0 else None)
        # Round 2 segment (top)
        ax.bar(xi, r2, width=BAR_W, bottom=r1, color=color, alpha=R2_ALPHA, zorder=3,
               label="Round 2" if xi == 0 else None)

        # Annotate Round 1 portion (centred inside segment)
        pct1 = r1 / gold_total * 100
        if r1 > r1_max * 0.08:   # only label if segment is tall enough to fit text
            ax.text(xi, r1 / 2, f"{r1}\n({pct1:.0f}%)",
                    ha="center", va="center", fontsize=8.5,
                    fontweight="bold", color="white")

        # Annotate Round 2 portion
        pct2 = r2 / gold_total * 100
        if r2 > 0:
            r2_mid = r1 + r2 / 2
            if r2 > r1_max * 0.04:
                ax.text(xi, r2_mid, f"{r2} ({pct2:.0f}%)",
                        ha="center", va="center", fontsize=8, color="#222")
            else:
                # Too small to fit inside — annotate above bar
                ax.text(xi, r1 + r2 + r1_max * 0.02,
                        f"R2: {r2} ({pct2:.0f}%)",
                        ha="center", va="bottom", fontsize=8, color="#555")

    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels, fontsize=10)
    ax.set_ylabel("New gold references found")
    ax.set_title(sinfo["label"], fontsize=10)
    ax.set_ylim(bottom=0)
    if skey == list(SURVEY.keys())[0]:
        ax.legend(fontsize=9, loc="upper left")

fig.suptitle(
    "Gold References Found per BFS Depth Pass — Round 2 Adds Negligible Yield\n"
    "(k=5 top-k seeds, Pareto-80 · solid = Round 1, faded = Round 2 · labels show count and % of gold set)",
    fontsize=11, y=1.03,
)
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
    "top_k":       {"color": C["S1"],   "ls": "-",  "marker": "o", "label": "High-quality seeds\n(top-cited papers)"},
    "random":      {"color": C["p80"],  "ls": "--", "marker": "s", "label": "Random seeds\n(typical search result)"},
    "contaminated":{"color": C["fwd"],  "ls": ":",  "marker": "^", "label": "Noisy seeds\n(50% off-topic)"},
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
    ax.set_xlabel("Discovery round")
    ax.set_ylabel("Recall (fraction of gold references recovered)")
    ax.set_title(sinfo["label"], fontsize=10)
    ax.set_xticks([1, 2])
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.legend(loc="lower right", fontsize=8.5)

fig.suptitle(
    "Recall Recovery by Discovery Round ($k=5$ initial seeds)\n"
    "Even 50% off-topic seeds recover to ≥90% recall by round 2",
    fontsize=11, y=1.03,
)
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
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.legend(loc="lower right", fontsize=8.5)

fig.suptitle(
    "Final Recall vs Initial Seed Size (after 2 discovery rounds)\n"
    "Top-k recall dips at k=2 because nearest-neighbor seeds share backward neighborhoods; "
    "contaminated recall declines with k because each off-topic seed opens a new traversal frontier. "
    "Both effects resolve by round 2.",
    fontsize=10, y=1.03,
)
fig.tight_layout()
fig.savefig(FIGS / "fig6_recall_vs_seed_size.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved fig6_recall_vs_seed_size.png")

# ─────────────────────────────────────────────────────────────────────────────
# FIG 7: Miss analysis — 2-panel redesign
#   Left:  Paired box plots — in-degree (missed vs recovered), 3 survey groups
#   Right: Horizontal stacked bars — BFS distance breakdown per survey
#
# Story: missed papers are structurally peripheral (low in-degree, not missed
# at random) and still adjacent (BFS distance 1-2 from the recovered set).
# ─────────────────────────────────────────────────────────────────────────────
print("Fig 7: Miss analysis (2-panel redesign)...")

# Build recovered-paper in-degree from ground truth minus missed sets
cites_cnt    = df_csv["citing_doi"].value_counts().to_dict()
cited_by_cnt = df_csv["cited_doi"].value_counts().to_dict()

rec_data = {}
for key, info in gt.items():
    missed_dois   = set(miss[key]["doi"].tolist()) if len(miss[key]) > 0 else set()
    recovered_dois = set(info["gold_refs"]) - missed_dois
    rows = [{"doi": d, "in_deg": cited_by_cnt.get(d, 0)} for d in recovered_dois]
    rec_data[key] = pd.DataFrame(rows)

fig, (ax_box, ax_dist) = plt.subplots(1, 2, figsize=(13, 5))

# ── Panel A: Paired box plots — in-degree (missed vs recovered) ───────────────
survey_keys   = list(SURVEY.keys())
survey_labels = [SURVEY[k]["short"] for k in survey_keys]
n_surveys     = len(survey_keys)
group_width   = 0.35   # half-width of each box pair
gap           = 1.0    # spacing between survey groups
x_centres     = np.arange(n_surveys) * (1 + gap)

bp_handles = []
for i, key in enumerate(survey_keys):
    sinfo = SURVEY[key]
    dm    = miss[key]
    dr    = rec_data[key]

    x_rec  = x_centres[i] - group_width / 2
    x_miss = x_centres[i] + group_width / 2

    rec_vals  = dr["in_deg"].clip(lower=1).values
    miss_vals = dm["in_deg"].clip(lower=1).values if len(dm) > 0 else np.array([1])

    bp_r = ax_box.boxplot(rec_vals,  positions=[x_rec],  widths=0.28,
                          patch_artist=True, sym="",
                          boxprops=dict(facecolor=sinfo["color"], alpha=0.6),
                          medianprops=dict(color="white", lw=2),
                          whiskerprops=dict(color=sinfo["color"]),
                          capprops=dict(color=sinfo["color"]))
    bp_m = ax_box.boxplot(miss_vals, positions=[x_miss], widths=0.28,
                          patch_artist=True, sym="",
                          boxprops=dict(facecolor=C["miss"], alpha=0.7),
                          medianprops=dict(color="white", lw=2),
                          whiskerprops=dict(color=C["miss"]),
                          capprops=dict(color=C["miss"]))

    # Medians are legible from box positions on log scale;
    # exact values are stated in the paper text — no annotation needed.

# Legend: survey-colored patches for Recovered + one red patch for Missed
from matplotlib.patches import Patch
bp_handles = [Patch(facecolor=SURVEY[k]["color"], alpha=0.6, label=f"Recovered ({SURVEY[k]['short']})")
              for k in survey_keys]
bp_handles.append(Patch(facecolor=C["miss"], alpha=0.7, label="Missed (all surveys)"))
ax_box.legend(handles=bp_handles, fontsize=8, loc="upper right")
ax_box.set_xticks(x_centres)
ax_box.set_xticklabels(survey_labels, fontsize=10)
ax_box.set_yscale("log")
ax_box.set_ylabel("In-degree (log scale)")
ax_box.set_title("(a) In-degree: missed vs recovered", fontsize=11)
ax_box.set_xlim(x_centres[0] - 0.7, x_centres[-1] + 0.7)

# ── Panel B: Horizontal stacked bars — BFS distance breakdown ─────────────────
dist_col = "bfs_dist_from_recovered"
bar_h    = 0.5
y_pos    = np.arange(n_surveys)
dist_colors = {1: "#4a9d8f", 2: "#e9c46a", 3: "#e76f51"}

for i, key in enumerate(reversed(survey_keys)):   # reversed so S1 is top
    sinfo = SURVEY[key]
    dm    = miss[key]
    if len(dm) == 0 or dist_col not in dm.columns:
        ax_dist.barh(y_pos[i], 0, bar_h, color=C["p80"])
        ax_dist.text(0.5, y_pos[i], "100% recall", ha="center", va="center",
                     fontsize=9, color=C["p80"])
        continue
    total     = len(dm)
    dist_cnt  = dm[dist_col].value_counts().sort_index()
    left      = 0
    for dist_val, cnt in dist_cnt.items():
        pct   = cnt / total
        color = dist_colors.get(int(dist_val), "#adb5bd")
        ax_dist.barh(y_pos[i], pct, bar_h, left=left,
                     color=color, alpha=0.85, zorder=3)
        if pct >= 0.08:   # only label if wide enough to read
            ax_dist.text(left + pct / 2, y_pos[i],
                         f"dist={int(dist_val)}\n{cnt}/{total}\n({pct:.0%})",
                         ha="center", va="center", fontsize=8, color="white",
                         fontweight="bold")
        left += pct

ax_dist.set_yticks(y_pos)
ax_dist.set_yticklabels([SURVEY[k]["short"] for k in reversed(survey_keys)], fontsize=10)
ax_dist.set_xlim(0, 1.0)
ax_dist.set_xlabel("Fraction of missed papers")
ax_dist.set_title("(b) BFS distance from recovered set", fontsize=11)
ax_dist.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax_dist.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])

# Distance legend
from matplotlib.patches import Patch as MPatch
dist_legend = [MPatch(facecolor=dist_colors[d], alpha=0.85, label=f"Distance {d}")
               for d in sorted(dist_colors)]
ax_dist.legend(handles=dist_legend, fontsize=8.5, loc="lower right")

fig.suptitle(
    "Anatomy of the Residual Coverage Gap\n"
    "Missed papers have low in-degree (rarely surfaced as candidates) "
    "and are structurally adjacent (BFS distance ≤ 2) to the recovered set.",
    fontsize=11, y=1.03)
fig.tight_layout()
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
    "bidir_pareto40": {"p": 40,  "label": "Pareto-40"},
    "bidir_pareto30": {"p": 30,  "label": "Pareto-30"},
    "bidir_pareto20": {"p": 20,  "label": "Pareto-20"},
    "bidir_pareto10": {"p": 10,  "label": "Pareto-10"},
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
