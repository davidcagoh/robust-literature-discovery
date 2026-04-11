"""03b_depth_pareto_grid.py

Reads traversal_results.json (produced by 03_traversal_simulation.py) and
produces two figures:

fig8b — dual heatmap (recall row + corpus size row), all surveys side by side
fig8c — corpus size heatmap with iso-recall contour lines overlaid (one panel
         per survey). Shows the efficiency frontier: which (depth, pareto) pairs
         hit a recall target at minimum corpus cost.

No traversal simulation is rerun — this is a pure post-processing script.

Outputs
-------
data-aps/outputs/traversal_results_depth_pareto_grid.json
data-aps/outputs/pub_figures/fig8b_depth_pareto_heatmap.png
data-aps/outputs/pub_figures/fig8c_efficiency_frontier.png
"""

from pathlib import Path
import json

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
OUTPUTS = REPO_ROOT / "data-aps" / "outputs"
PUB_FIGURES = OUTPUTS / "pub_figures"
PUB_FIGURES.mkdir(parents=True, exist_ok=True)

TRAVERSAL_JSON = OUTPUTS / "traversal_results.json"
GRID_JSON      = OUTPUTS / "traversal_results_depth_pareto_grid.json"
FIG8B_OUT      = PUB_FIGURES / "fig8b_depth_pareto_heatmap.png"
FIG8C_OUT      = PUB_FIGURES / "fig8c_efficiency_frontier.png"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SURVEYS = ["S1_MIT", "S2_UCG", "S3_TOPO"]
SURVEY_LABELS = {
    "S1_MIT":  "S1 MIT (condensed matter)",
    "S2_UCG":  "S2 UCG (ultracold gases)",
    "S3_TOPO": "S3 TOPO (topological insulators)",
}

PARETO_KEYS = [
    "bidir_pareto10",
    "bidir_pareto20",
    "bidir_pareto30",
    "bidir_pareto40",
    "bidir_pareto50",
    "bidir_pareto70",
    "bidir_pareto80",
    "bidir_pareto90",
    "bidir",        # no filter
]
PARETO_LABELS = ["10", "20", "30", "40", "50", "70", "80", "90", "None"]

DEPTHS = [1, 2, 3, 4, 5, 6]

# Pareto-80 column index — mark with a border to highlight production default
PROD_COL = PARETO_LABELS.index("80")


# ---------------------------------------------------------------------------
# Build grids
# ---------------------------------------------------------------------------
def build_recall_grid(trav: dict, survey: str) -> np.ndarray:
    """Return (len(DEPTHS) × len(PARETO_KEYS)) recall matrix."""
    data = trav[survey]
    grid = np.full((len(DEPTHS), len(PARETO_KEYS)), np.nan)
    for col, pk in enumerate(PARETO_KEYS):
        if pk not in data:
            continue
        depth_map = {e["depth"]: e["recall_refs"] for e in data[pk]}
        for row, d in enumerate(DEPTHS):
            if d in depth_map:
                grid[row, col] = depth_map[d]
    return grid


def build_corpus_grid(trav: dict, survey: str) -> np.ndarray:
    """Return (len(DEPTHS) × len(PARETO_KEYS)) corpus-size matrix (raw counts)."""
    data = trav[survey]
    grid = np.full((len(DEPTHS), len(PARETO_KEYS)), np.nan)
    for col, pk in enumerate(PARETO_KEYS):
        if pk not in data:
            continue
        depth_map = {e["depth"]: e["corpus_size"] for e in data[pk]}
        for row, d in enumerate(DEPTHS):
            if d in depth_map:
                grid[row, col] = depth_map[d]
    return grid


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------
def _highlight_prod_col(ax, n_rows):
    """Draw a white border around the Pareto-80 (production default) column."""
    ax.add_patch(plt.Rectangle(
        (PROD_COL - 0.5, -0.5), 1, n_rows,
        fill=False, edgecolor="white", linewidth=2.5, zorder=10,
    ))


def _annotate(ax, grid, fmt_fn):
    """Write formatted cell values; auto-pick black/white text."""
    rows, cols = grid.shape
    for r in range(rows):
        for c in range(cols):
            val = grid[r, c]
            if np.isnan(val):
                continue
            text = fmt_fn(val)
            # Luminance heuristic: dark text on light cells, light on dark
            norm_val = val / np.nanmax(grid) if np.nanmax(grid) > 0 else 0
            color = "black" if norm_val < 0.65 else "white"
            ax.text(c, r, text, ha="center", va="center",
                    fontsize=7.5, color=color, fontweight="medium")


# ---------------------------------------------------------------------------
# Main plot
# ---------------------------------------------------------------------------
def plot_dual_heatmaps(
    recall_grids: dict[str, np.ndarray],
    corpus_grids: dict[str, np.ndarray],
) -> plt.Figure:
    n = len(SURVEYS)
    fig, axes = plt.subplots(
        2, n,
        figsize=(5.5 * n, 9),
        constrained_layout=True,
    )

    recall_cmap = plt.get_cmap("RdYlGn")
    recall_norm = mcolors.Normalize(vmin=0.0, vmax=1.0)

    # Corpus colormap: white → deep blue (lower is cheaper/better)
    corpus_cmap = LinearSegmentedColormap.from_list(
        "corpus_cmap", ["#ffffff", "#08306b"]
    )

    # Compute global corpus max for consistent colour scale across surveys
    all_corpus = np.concatenate(
        [g.flatten() for g in corpus_grids.values()]
    )
    corpus_max = np.nanmax(all_corpus)
    corpus_norm = mcolors.Normalize(vmin=0, vmax=corpus_max)

    # ── Top row: recall ──────────────────────────────────────────────────────
    for col, survey in enumerate(SURVEYS):
        ax = axes[0, col]
        rg = recall_grids[survey]

        im_r = ax.imshow(rg, cmap=recall_cmap, norm=recall_norm,
                         aspect="auto", origin="upper", interpolation="nearest")
        _annotate(ax, rg, lambda v: f"{v:.2f}")
        _highlight_prod_col(ax, len(DEPTHS))

        ax.set_xticks(range(len(PARETO_LABELS)))
        ax.set_xticklabels(PARETO_LABELS, fontsize=9)
        ax.set_yticks(range(len(DEPTHS)))
        ax.set_yticklabels([str(d) for d in DEPTHS], fontsize=9)
        ax.set_ylabel("BFS depth", fontsize=10)
        ax.set_xlabel("Pareto threshold", fontsize=10)
        ax.set_title(SURVEY_LABELS[survey], fontsize=11, fontweight="bold", pad=6)

    fig.colorbar(im_r, ax=axes[0, :], shrink=0.6,
                 label="Recall (fraction of gold refs recovered)", pad=0.02)

    # ── Bottom row: corpus size ───────────────────────────────────────────────
    for col, survey in enumerate(SURVEYS):
        ax = axes[1, col]
        cg = corpus_grids[survey]

        im_c = ax.imshow(cg, cmap=corpus_cmap, norm=corpus_norm,
                         aspect="auto", origin="upper", interpolation="nearest")
        # Annotate in thousands
        _annotate(ax, cg, lambda v: f"{v/1000:.0f}k")
        _highlight_prod_col(ax, len(DEPTHS))

        ax.set_xticks(range(len(PARETO_LABELS)))
        ax.set_xticklabels(PARETO_LABELS, fontsize=9)
        ax.set_yticks(range(len(DEPTHS)))
        ax.set_yticklabels([str(d) for d in DEPTHS], fontsize=9)
        ax.set_ylabel("BFS depth", fontsize=10)
        ax.set_xlabel("Pareto threshold", fontsize=10)

    fig.colorbar(im_c, ax=axes[1, :], shrink=0.6,
                 label="Corpus size (papers visited)", pad=0.02)

    # Row labels on left margin
    axes[0, 0].annotate("Recall", xy=(-0.28, 0.5), xycoords="axes fraction",
                         fontsize=12, fontweight="bold", rotation=90,
                         va="center", ha="center", color="#444")
    axes[1, 0].annotate("Corpus size", xy=(-0.28, 0.5), xycoords="axes fraction",
                         fontsize=12, fontweight="bold", rotation=90,
                         va="center", ha="center", color="#444")

    fig.suptitle(
        "Depth × Pareto filter — recall and corpus size tradeoff\n"
        "White border = Pareto-80 (production default)  ·  "
        "Corpus size in thousands  ·  depth-limited traversal typical in production",
        fontsize=10,
    )

    return fig


# ---------------------------------------------------------------------------
# Fig 8c: corpus size heatmap + iso-recall contours
# ---------------------------------------------------------------------------
def plot_efficiency_frontier(
    recall_grids: dict[str, np.ndarray],
    corpus_grids: dict[str, np.ndarray],
) -> plt.Figure:
    """
    One panel per survey. Background = corpus size (white→blue).
    Overlaid contour lines at iso-recall levels so you can read off:
    "to hit X% recall, what's the cheapest (depth, pareto) combination?"
    """
    n = len(SURVEYS)
    fig, axes = plt.subplots(1, n, figsize=(5.8 * n, 5.5), constrained_layout=True)

    corpus_cmap = LinearSegmentedColormap.from_list(
        "corpus_cmap", ["#f7fbff", "#08306b"]
    )
    all_corpus = np.concatenate([g.flatten() for g in corpus_grids.values()])
    corpus_norm = mcolors.Normalize(vmin=0, vmax=np.nanmax(all_corpus))

    # Iso-recall levels and their display colours
    iso_levels  = [0.80, 0.90, 0.95, 0.99, 1.00]
    iso_colors  = ["#d62728", "#ff7f0e", "#bcbd22", "#2ca02c", "#17becf"]
    iso_lw      = [1.4,       1.4,       1.6,       1.8,       2.2      ]

    # Coordinate arrays for contour (cols=pareto index, rows=depth index)
    # imshow origin="upper" so row 0 = depth[0]=1, row 5 = depth[5]=6
    x = np.arange(len(PARETO_LABELS))   # pareto axis
    y = np.arange(len(DEPTHS))           # depth axis

    for ax, survey in zip(axes, SURVEYS):
        cg = corpus_grids[survey]
        rg = recall_grids[survey]

        im = ax.imshow(cg, cmap=corpus_cmap, norm=corpus_norm,
                       aspect="auto", origin="upper", interpolation="bilinear")

        # Corpus size labels in each cell (thousands)
        for r in range(len(DEPTHS)):
            for c in range(len(PARETO_LABELS)):
                val = cg[r, c]
                if np.isnan(val):
                    continue
                # Luminance: white text on dark cells
                norm_val = val / np.nanmax(all_corpus)
                color = "white" if norm_val > 0.45 else "#1a1a2e"
                ax.text(c, r, f"{val/1000:.0f}k",
                        ha="center", va="center",
                        fontsize=7.5, color=color, fontweight="medium")

        # Iso-recall contours — interpolate on fine grid for smooth lines
        from scipy.interpolate import RegularGridInterpolator
        interp = RegularGridInterpolator(
            (y, x), rg, method="linear", bounds_error=False, fill_value=None
        )
        yi_fine = np.linspace(0, len(DEPTHS) - 1, 300)
        xi_fine = np.linspace(0, len(PARETO_LABELS) - 1, 300)
        xi2d, yi2d = np.meshgrid(xi_fine, yi_fine)
        rg_fine = interp((yi2d, xi2d))

        cs = ax.contour(xi_fine, yi_fine, rg_fine,
                        levels=iso_levels, colors=iso_colors,
                        linewidths=iso_lw, zorder=5)
        ax.clabel(cs, fmt={lv: f"{int(lv*100)}%" for lv in iso_levels},
                  fontsize=8.5, inline=True, inline_spacing=4)

        # Production default column marker
        _highlight_prod_col(ax, len(DEPTHS))

        ax.set_xticks(range(len(PARETO_LABELS)))
        ax.set_xticklabels(PARETO_LABELS, fontsize=9)
        ax.set_xlabel("Pareto threshold", fontsize=10)
        ax.set_yticks(range(len(DEPTHS)))
        ax.set_yticklabels([str(d) for d in DEPTHS], fontsize=9)
        ax.set_ylabel("BFS depth", fontsize=10)
        ax.set_title(SURVEY_LABELS[survey], fontsize=11, fontweight="bold", pad=6)

    cb = fig.colorbar(im, ax=axes, shrink=0.65, pad=0.02)
    cb.set_label("Corpus size (papers visited)", fontsize=10)
    cb.ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{v/1000:.0f}k")
    )

    fig.suptitle(
        "Efficiency frontier: corpus cost at each (depth, pareto) combination\n"
        "Contour lines = iso-recall levels  ·  "
        "White border = Pareto-80 (production default)  ·  "
        "Cells show corpus size",
        fontsize=10,
    )
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(f"Reading {TRAVERSAL_JSON} ...")
    with open(TRAVERSAL_JSON) as f:
        trav = json.load(f)

    recall_grids: dict[str, np.ndarray] = {}
    corpus_grids: dict[str, np.ndarray] = {}
    grid_export: dict[str, dict] = {}

    for survey in SURVEYS:
        rg = build_recall_grid(trav, survey)
        cg = build_corpus_grid(trav, survey)
        recall_grids[survey] = rg
        corpus_grids[survey] = cg

        grid_export[survey] = {
            "depths": DEPTHS,
            "pareto_labels": PARETO_LABELS,
            "pareto_keys": PARETO_KEYS,
            "recall_matrix": rg.tolist(),
            "corpus_size_matrix": cg.tolist(),
        }

    with open(GRID_JSON, "w") as f:
        json.dump(grid_export, f, indent=2)
    print(f"Saved grid data -> {GRID_JSON}")

    # Quick console summary
    print("\nRecall vs corpus at depth=2 (production-relevant):")
    print(f"{'Survey':<12} {'Pareto':>7} {'Recall':>8} {'Corpus':>10}")
    print("-" * 42)
    d2 = DEPTHS.index(2)
    for survey in SURVEYS:
        for ci, label in enumerate(PARETO_LABELS):
            r = recall_grids[survey][d2, ci]
            c = corpus_grids[survey][d2, ci]
            marker = " ←" if label == "80" else ""
            print(f"{survey:<12} {label:>7} {r:>8.3f} {c:>10,.0f}{marker}")
        print()

    fig = plot_dual_heatmaps(recall_grids, corpus_grids)
    fig.savefig(FIG8B_OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved fig8b -> {FIG8B_OUT}")

    fig = plot_efficiency_frontier(recall_grids, corpus_grids)
    fig.savefig(FIG8C_OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved fig8c -> {FIG8C_OUT}")


if __name__ == "__main__":
    main()
