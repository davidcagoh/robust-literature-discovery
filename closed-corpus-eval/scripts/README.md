# Analysis Scripts: LitReview v2 Coverage Validation

These scripts reproduce all empirical results and figures in `LitReview_v2_Whitepaper.md`, on the APS citation dataset. They split into two subdirectories by function:

- **`eval/`** — the actual validation pipeline. Run in order, this produces every number and figure the paper claims (the 89–98% recall headline, fig1–fig7).
- **`sweep/`** — parameter-justification scripts. These don't produce paper claims directly; they exist to justify *why* the fixed parameters used in `eval/` (N_ROUNDS=2, PARETO_P=80) were chosen. Some are dead weight kept for history (`04_cold_start_simulation.py`, superseded by `eval/04b_cold_start_lowseed.py`; `07_elbow_analysis.py`, currently inoperable — see below).

## Prerequisites

Python 3.11+ with the following packages:

```
pip install pandas numpy matplotlib scipy networkx
```

The APS citation CSV must be present at `closed-corpus-eval/data/processed/aps-dataset-citations-2022.csv` (relative to the repo root). Each script resolves this path automatically via `Path(__file__).parent.parent.parent`, which resolves to the `closed-corpus-eval/` track root regardless of whether the script lives in `scripts/eval/` or `scripts/sweep/`. The file is available from the APS Data Sets for Research portal at https://journals.aps.org/datasets.

## eval/ — the validation pipeline

| Script | Description | Output |
|---|---|---|
| `eval/01_extract_ground_truth.py` | Extracts the reference lists of the three chosen RevModPhys survey papers from the APS corpus. Defines the gold sets used in all subsequent experiments. | `ground_truth.json` |
| `eval/02_graph_characterisation.py` | Computes global structural properties of the APS graph: degree distributions, Gini coefficients, power-law exponents, connected components, and BFS reachability curves for all three surveys. | `graph_stats.json`, `corpus_stats.json` |
| `eval/03_traversal_simulation.py` | Simulates five traversal strategies (backward, forward, bidirectional, Pareto-50/70/80/90) from each survey paper. Measures recall of the gold set and corpus size at each BFS depth. | `traversal_results.json` |
| `eval/04b_cold_start_lowseed.py` | **Canonical experiment.** Simulates the cold-start Escape Hatch loop, seeded from k ∈ {1,2,3,4,5,10} papers under three noise conditions (top-k, random, contaminated). 2 rounds of bidirectional Pareto-80 traversal with yield-based stopping. Produces the paper's headline recall numbers. | `cold_start_results_lowseed.json` |
| `eval/05_miss_analysis.py` | Identifies the exact papers missed by the canonical k=5 top-k cold-start run (N_ROUNDS=2). Computes structural properties (in-degree, out-degree, BFS distance from recovered set) for missed vs. recovered papers. | `missed_papers_S1_MIT.csv`, `missed_papers_S2_UCG.csv`, `missed_papers_S3_TOPO.csv` |
| `eval/06_publication_figures.py` | Generates all publication-quality figures (fig1–fig8) using the JSON/CSV outputs of the previous scripts. Reads `cold_start_results_lowseed.json`. | `pub_figures/fig1_*.png` through `pub_figures/fig8_*.png` |

## sweep/ — parameter justification (not paper claims themselves)

| Script | Description | Output |
|---|---|---|
| `sweep/07_rounds_sweep.py` | Sweeps N_ROUNDS (1–10) for the canonical k=20 top-k case; motivates the N_ROUNDS=2 default used in `eval/`. | `n_rounds_sweep.csv`, `pub_figures/fig9_n_rounds_sweep.png` |
| `sweep/08_hyperparameter_sweep.py` | Full grid: PARETO_P × YIELD_THRESHOLD × N_ROUNDS × K_ESCAPE (1980 rows). Motivates PARETO_P=80. | `hyperparameter_sweep.csv`, `pub_figures/fig9a–d_*.png` |
| `sweep/03b_depth_pareto_grid.py` | Depth × Pareto grid sweep, post-processes `traversal_results.json`. Both its figures (fig8b, fig8c) were dropped from the paper — pure exploration that didn't make the final cut. | `traversal_results_depth_pareto_grid.json`, `pub_figures/fig8b_*.png`, `pub_figures/fig8c_*.png` |
| `sweep/04_cold_start_simulation.py` | **Superseded** — the old cold-start version (k=5/10/20/50, N_ROUNDS=4), replaced by `eval/04b_cold_start_lowseed.py`. Kept for history; `cold_start_results.json` is not currently generated. | `cold_start_results.json` (not generated) |
| `sweep/07_elbow_analysis.py` | Post-processes `cold_start_results.json` (from `sweep/04`, not currently generated) to evaluate between-round stopping criteria. **Currently inoperable** until `sweep/04` is run. | `elbow_stopping_results.csv`, `pub_figures/fig9_elbow_stopping_efficiency.png` |

## Survey Papers Used as Ground Truth

| ID | DOI | Title | Year | Gold Refs (APS) |
|---|---|---|---|---|
| S1 | 10.1103/RevModPhys.70.1039 | Metal-insulator transitions | 1998 | 582 |
| S2 | 10.1103/RevModPhys.80.885 | Many-body physics with ultracold gases | 2008 | 432 |
| S3 | 10.1103/RevModPhys.91.015006 | Topological photonics | 2019 | 387 |

## Elbow Stopping Extension

See `sweep/ELBOW_STOPPING_DESIGN.md` for a full design document covering:
- Why an elbow exists in the per-round recall curve.
- Three candidate between-round stopping criteria (marginal recall gain, absolute new gold papers, round-level screen yield).
- The exact minimal code change to `sweep/04_cold_start_simulation.py` (one `if` block, ~15 lines).
- Downstream compatibility analysis for `eval/05` and `eval/06`.
- Recommended defaults and expected recall/cost trade-offs.

The companion script `sweep/07_elbow_analysis.py` retroactively applies all three criteria to an existing `cold_start_results.json` without re-running the simulation.

## Running the Full Pipeline

```bash
cd closed-corpus-eval/scripts/eval
python3 01_extract_ground_truth.py
python3 02_graph_characterisation.py   # ~5 min on full APS corpus
python3 03_traversal_simulation.py     # ~10 min
python3 04b_cold_start_lowseed.py      # ~15 min (active canonical; k=1-5,10, N_ROUNDS=2)
python3 05_miss_analysis.py            # ~15 min
python3 06_publication_figures.py      # ~1 min
```

All JSON/CSV artifacts are written to `closed-corpus-eval/data/outputs/` (relative to repo root). Publication figures are written to `closed-corpus-eval/data/outputs/pub_figures/`. Intermediate diagnostic figures go to `closed-corpus-eval/data/outputs/figures/` and `closed-corpus-eval/data/outputs/figures_lowseed/`.
