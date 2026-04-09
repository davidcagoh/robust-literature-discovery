# CLAUDE.md

This repository contains the APS-based empirical validation for **LitDiscover** (formerly "LitReview v2"), not the production application itself. The codebase is a small set of sequential Python analysis scripts that simulate the production system’s core discovery logic: **bidirectional citation traversal**, a **forward-direction Pareto hub filter**, and **screen-yield-based stopping** inside a multi-round **Escape Hatch** loop.

## What matters most

The repository is best understood as a **data pipeline with a few extension studies**, not as a package or library. Most work happens in `analysis-scripts/`, and the important cross-file dependency is the JSON/CSV artifact chain written to **`data-aps/outputs/`** (relative to the repo root). Publication-quality figures land in `data-aps/outputs/pub_figures/`.

The production-system architecture memo in `paper-wiki/Architecture Design_ LitReview v2.md` is important context: the scripts here are a closed-corpus simulation of the deployed LitDiscover state machine, where discovery producers feed a unified screening queue and **screen yield** decides whether to continue local traversal or trigger a fresh search-based escape hatch.

## Environment and prerequisites

The documented setup is Python 3.11+ with:

```bash
pip install pandas numpy matplotlib scipy networkx
```

The APS citation CSV is expected at:

```
data-aps/processed/aps-dataset-citations-2022.csv
```

All scripts resolve paths automatically via `Path(__file__).parent.parent` — no path editing is needed when running from any working directory.

## Common commands

Run commands from the repository root unless noted otherwise.

| Task | Command |
|---|---|
| Run the full main pipeline | `cd analysis-scripts && python3 01_extract_ground_truth.py && python3 02_graph_characterisation.py && python3 03_traversal_simulation.py && python3 04_cold_start_simulation.py && python3 05_miss_analysis.py && python3 06_publication_figures.py` |
| Run only ground-truth extraction | `cd analysis-scripts && python3 01_extract_ground_truth.py` |
| Run only graph characterization | `cd analysis-scripts && python3 02_graph_characterisation.py` |
| Run only traversal strategy comparison | `cd analysis-scripts && python3 03_traversal_simulation.py` |
| Run only the canonical cold-start experiment | `cd analysis-scripts && python3 04_cold_start_simulation.py` |
| Run the low-seed extension | `cd analysis-scripts && python3 04b_cold_start_lowseed.py` |
| Run miss analysis | `cd analysis-scripts && python3 05_miss_analysis.py` |
| Regenerate publication figures from prior outputs | `cd analysis-scripts && python3 06_publication_figures.py` |
| Post-process `cold_start_results.json` for elbow stopping | `cd analysis-scripts && python3 07_elbow_analysis.py` |
| Sweep `N_ROUNDS` for the canonical case | `cd analysis-scripts && python3 07_rounds_sweep.py` |
|

There is **no build system, lint configuration, or automated test suite** in the repository root, and no `pytest`/`ruff`/`Makefile`/`pyproject.toml` workflow to use. Validation in practice means rerunning the specific analysis script affected by your change and checking the downstream JSON/CSV/figure artifacts.

## Pipeline architecture

The main pipeline has a strict artifact dependency chain.

| Script | Role in pipeline | Reads | Writes |
|---|---|---|---|
| `01_extract_ground_truth.py` | Defines the three survey-based gold sets used everywhere else | APS CSV | `ground_truth.json`, `corpus_stats.json` |
| `02_graph_characterisation.py` | Computes global APS graph structure and survey-centric reachability statistics | APS CSV, `ground_truth.json` | `graph_stats.json`, figures |
| `03_traversal_simulation.py` | Compares backward, forward, bidirectional, and Pareto-filtered traversal strategies | APS CSV, `ground_truth.json` | `traversal_results.json`, figures |
| `04_cold_start_simulation.py` | Main cold-start experiment: seed generation, Pareto-filtered traversal, within-round yield stopping, multi-round escape hatch | APS CSV, `ground_truth.json` | `cold_start_results.json`, figures |
| `04b_cold_start_lowseed.py` | Low-seed extension (k=1–5,10, N_ROUNDS=2); the active canonical experiment | APS CSV, `ground_truth.json` | `cold_start_results_lowseed.json`, `figures_lowseed/` |
| `05_miss_analysis.py` | Explains what the canonical run misses structurally; reconstructs traversal from scratch | APS CSV, `ground_truth.json` | per-survey missed-paper CSVs, `figures/` |
| `06_publication_figures.py` | Assembles paper-quality figures from prior outputs | outputs from 02/03/04b/05 plus APS CSV | `pub_figures/*.png` |
| `07_elbow_analysis.py` | Post-processing of round-level outputs to test early-stop heuristics (requires `cold_start_results.json` from script 04 — not yet generated) | `cold_start_results.json` | `elbow_stopping_results.csv`, `fig9_elbow_stopping_efficiency.png` |
| `07_rounds_sweep.py` | Separate canonical-case sweep of the round cap | APS CSV, `ground_truth.json` | `outputs/n_rounds_sweep.csv`, `fig9_n_rounds_sweep.png` |
| `08_hyperparameter_sweep.py` | Full grid sweep: PARETO_P × YIELD_THRESHOLD × N_ROUNDS × K_ESCAPE. Fixed: k=5 top-k seeds, MAX_DEPTH=8. ~660 configs × 3 surveys, ~30–60 min runtime. | APS CSV, `ground_truth.json` | `hyperparameter_sweep.csv`, `pub_figures/fig9a–d_*.png` |

Two practical implications follow from this layout.

First, **script 04b is the active canonical experiment** (k=1–5,10, N_ROUNDS=2). Script 04 (k=5/10/20/50, N_ROUNDS=4) exists but `cold_start_results.json` has not yet been generated — `07_elbow_analysis.py` depends on it and is currently inoperable. Second, `05_miss_analysis.py` is not a simple consumer of visited-node state; it **reconstructs the canonical traversal by rerunning the traversal logic**, because `cold_start_results_lowseed.json` stores summary statistics rather than visited sets. If you change stopping behavior or round semantics in `04b`, mirror that logic in `05_miss_analysis.py` as well.

## Core concepts encoded across multiple files

The most important big-picture idea is that the repository is modeling a **queue-driven literature discovery loop** in a closed citation graph. The production memo describes this as **SEED → SEARCH → SCREEN → TRAVERSE → ESCAPE HATCH → STABLE**, and the APS scripts approximate that behavior with explicit graph simulations rather than live APIs or databases.

Within that model, three mechanisms show up repeatedly and should be treated as the architectural constants of the repository.

| Mechanism | Where it appears | Why it matters |
|---|---|---|
| **Bidirectional traversal** | `03_traversal_simulation.py`, `04_cold_start_simulation.py`, `04b_cold_start_lowseed.py`, `05_miss_analysis.py`, `07_rounds_sweep.py` | The system explores both references and citations rather than treating the graph as one-directional |
| **Forward Pareto filter** | Especially `03` and `04` | Forward traversal is the explosion risk; citers with extreme out-degree are suppressed using a percentile threshold, typically 80th percentile |
| **Screen-yield stopping** | `04`, `04b`, extension notes | Local traversal halts when the ratio of newly found gold papers to newly visited papers drops below a threshold, typically `0.05` within a round |

The distinction between **within-round stopping** and **between-round stopping** is easy to miss but important. Script 04 already uses a within-round `screen_yield < 0.05` rule to stop BFS depth expansion. The elbow-stopping work in `ELBOW_STOPPING_DESIGN.md` and `07_elbow_analysis.py` is about a separate question: whether to stop after round 2 or 3 instead of always paying for a fixed `N_ROUNDS = 4`.

## Important extensions and current interpretation

`04b_cold_start_lowseed.py` is intentionally a near-copy of script 04 with only the seed-size regime changed. Its purpose is comparability, not abstraction. If you modify core cold-start mechanics in `04`, update `04b` as well unless the divergence is deliberate.

The repository currently contains two important interpretation notes.

`analysis-scripts/ELBOW_STOPPING_DESIGN.md` explains how to add **between-round early stopping** to `04_cold_start_simulation.py` with a small localized change inside `escape_hatch_loop()`. It also notes that `06_publication_figures.py` is already compatible with shorter round lists, while `05_miss_analysis.py` would need a mirrored change if you want miss analysis to honor the same stopping rule.

`paper-wiki/N_ROUNDS_Extension.md` records the stronger empirical claim that **round 1 does almost all the work and round 2 is mainly an inexpensive insurance pass**. If you are editing paper framing or defaults, this note matters more than the original four-round narrative.

## Repository-specific usage notes

There is already a checked-in `CLAUDE.md`; this version should stay focused on stable repository-operating knowledge rather than temporary handover items or paper-writing TODOs.

No Cursor rules, `.cursorrules`, or Copilot instruction files were found at the repository root during inspection, so there is nothing extra to merge from those sources.

`deps-matlab/` is ancillary to the Python APS analysis pipeline. It contains MATLAB/Julia dependencies for SG-t-SNE-related work and is not part of the main script chain above.

When making changes, prefer to preserve the current style of the repository: top-level constants, explicit script-local helper functions, JSON/CSV artifact handoff between phases, and reproducible random seeding in the cold-start experiments.
