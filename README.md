# robust-literature-discovery

This repository contains the analysis, figures, and reproducibility materials for the paper **Robust Literature Discovery from Minimal Seeds**, which validates the [LitDiscover](https://github.com/davidcagoh/automated-lit-reviews-v2) engine on the APS citation corpus.

## Scope

The contents here are intended to support the paper's empirical claims and reproducibility workflow. In particular, this repository contains the APS benchmark analysis scripts, figure-generation scripts, paper-facing notes, and selected reproducibility materials used to generate the manuscript's results.

## Relationship to LitDiscover

This repository is intentionally separate from **[LitDiscover (automated-lit-reviews-v2)](https://github.com/davidcagoh/automated-lit-reviews-v2)**.

| Repository | Role |
|---|---|
| `robust-literature-discovery` (this repo) | Paper and reproducibility repository: APS benchmark, analysis pipeline, publication figures, manuscript |
| [**LitDiscover**](https://github.com/davidcagoh/automated-lit-reviews-v2) | Deployed engine: queue loop, DB integrations, LLM screening, extraction, synthesis |

The paper repository is self-contained — you can reproduce all benchmark results without the full application.

## Manuscript

The active manuscript is at `paper-drafts/Robust_Literature_Discovery_from_Minimal_Seeds.md`. The active submission target compiles from `paper-drafts/tois-submission/litdiscover_tois.tex` (ACM TOIS). Earlier submission attempts (JCDL, JASIST) and the legacy IEEEtran draft are kept for reference in `paper-drafts/archive/`.

## Quick start (reproduce all paper figures)

```bash
pip install pandas numpy matplotlib scipy networkx

# Place the APS citation CSV at data-aps/processed/aps-dataset-citations-2022.csv
# then run the full pipeline:
cd analysis-scripts
python3 01_extract_ground_truth.py
python3 02_graph_characterisation.py
python3 03_traversal_simulation.py
python3 04b_cold_start_lowseed.py   # canonical experiment (k=1–10, 2 rounds)
python3 05_miss_analysis.py
python3 06_publication_figures.py    # writes fig1–fig7 to data-aps/outputs/pub_figures/
```

## Main directories

| Path | Purpose |
|---|---|
| `analysis-scripts/` | Core APS benchmark and figure-generation scripts |
| `data-aps/outputs/pub_figures/` | Generated publication figures (fig1–fig7) |
| `data-aps/outputs/` | All JSON/CSV artifacts and intermediate figures |
| `app-validation-data/` | Exported supporting validation summaries |
| `validation-surveys/` | Reference PDFs for live experiment ground truth |
| `seed-papers/` | Seed paper PDFs |
| `paper-drafts/` | Manuscript source. Root: prose + refs. `tois-submission/`: active LaTeX target. `archive/`: dead-end submission attempts + legacy draft |
