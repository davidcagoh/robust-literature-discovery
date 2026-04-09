# Analysis Scripts: LitReview v2 Coverage Validation

These scripts reproduce all empirical results and figures in `LitReview_v2_Whitepaper.md`. They are designed to be run in order on the APS citation dataset.

## Prerequisites

Python 3.11+ with the following packages:

```
pip install pandas numpy matplotlib scipy networkx
```

The APS citation CSV must be present at `data-aps/processed/aps-dataset-citations-2022.csv` (relative to the repo root). Scripts resolve this path automatically via `Path(__file__).parent.parent`. The file is available from the APS Data Sets for Research portal at https://journals.aps.org/datasets.

## Script Pipeline

| Script | Description | Output |
|---|---|---|
| `01_extract_ground_truth.py` | Extracts the reference lists of the three chosen RevModPhys survey papers from the APS corpus. Defines the gold sets used in all subsequent experiments. | `ground_truth.json` |
| `02_graph_characterisation.py` | Computes global structural properties of the APS graph: degree distributions, Gini coefficients, power-law exponents, connected components, and BFS reachability curves for all three surveys. | `graph_stats.json`, `corpus_stats.json` |
| `03_traversal_simulation.py` | Simulates five traversal strategies (backward, forward, bidirectional, Pareto-50/70/80/90) from each survey paper. Measures recall of the gold set and corpus size at each BFS depth. | `traversal_results.json` |
| `04_cold_start_simulation.py` | Simulates the cold-start Escape Hatch loop. Seeds the traversal from $k \in \{5, 10, 20, 50\}$ papers sampled from the gold set under three noise conditions (top-k, random, contaminated). Runs 4 rounds of bidirectional Pareto-80 traversal with yield-based stopping. | `cold_start_results.json` |
| `05_miss_analysis.py` | Identifies the exact papers missed by the canonical $k=5$ top-k cold-start run (N_ROUNDS=2). Computes structural properties (in-degree, out-degree, BFS distance from recovered set) for missed vs. recovered papers. | `missed_papers_S1_MIT.csv`, `missed_papers_S2_UCG.csv`, `missed_papers_S3_TOPO.csv` |
| `06_publication_figures.py` | Generates all 8 publication-quality figures using the JSON/CSV outputs of the previous scripts. Reads `cold_start_results_lowseed.json`. | `pub_figures/fig1_*.png` through `pub_figures/fig8_*.png` |
| `07_elbow_analysis.py` | Post-processes `cold_start_results.json` (from script 04, not yet generated) to evaluate between-round stopping criteria. Currently inoperable until script 04 is run. | `elbow_stopping_results.csv`, `pub_figures/fig9_elbow_stopping_efficiency.png` |
| `07_rounds_sweep.py` | Sweeps N_ROUNDS (1–10) for the canonical k=20 top-k case; motivates the N_ROUNDS=2 default. | `outputs/n_rounds_sweep.csv`, `pub_figures/fig9_n_rounds_sweep.png` |

## Survey Papers Used as Ground Truth

| ID | DOI | Title | Year | Gold Refs (APS) |
|---|---|---|---|---|
| S1 | 10.1103/RevModPhys.70.1039 | Metal-insulator transitions | 1998 | 582 |
| S2 | 10.1103/RevModPhys.80.885 | Many-body physics with ultracold gases | 2008 | 432 |
| S3 | 10.1103/RevModPhys.91.015006 | Topological photonics | 2019 | 387 |

## Elbow Stopping Extension

See `ELBOW_STOPPING_DESIGN.md` for a full design document covering:
- Why an elbow exists in the per-round recall curve.
- Three candidate between-round stopping criteria (marginal recall gain, absolute new gold papers, round-level screen yield).
- The exact minimal code change to `04_cold_start_simulation.py` (one `if` block, ~15 lines).
- Downstream compatibility analysis for scripts 05 and 06.
- Recommended defaults and expected recall/cost trade-offs.

The companion script `07_elbow_analysis.py` retroactively applies all three criteria to an existing `cold_start_results.json` without re-running the simulation.

## Running the Full Pipeline

```bash
cd analysis-scripts
python3 01_extract_ground_truth.py
python3 02_graph_characterisation.py   # ~5 min on full APS corpus
python3 03_traversal_simulation.py     # ~10 min
python3 04b_cold_start_lowseed.py      # ~15 min (active canonical; k=1-5,10, N_ROUNDS=2)
python3 05_miss_analysis.py            # ~15 min
python3 06_publication_figures.py      # ~1 min
```

All JSON/CSV artifacts are written to `data-aps/outputs/` (relative to repo root). Publication figures are written to `data-aps/outputs/pub_figures/`. Intermediate diagnostic figures go to `data-aps/outputs/figures/` and `data-aps/outputs/figures_lowseed/`.
