# robust-literature-discovery

This repository contains the analysis, figures, and reproducibility materials for the paper project currently titled **Robust Literature Discovery from Minimal Seeds**.

## Scope

The contents here are intended to support the paper's empirical claims and reproducibility workflow. In particular, this repository contains the APS benchmark analysis scripts, figure-generation scripts, paper-facing notes, and selected reproducibility materials used to generate the manuscript's results.

## Relationship to `automated-lit-reviews-v2`

This repository is intentionally separate from **`automated-lit-reviews-v2`**.

| Repository | Role |
|---|---|
| `robust-literature-discovery` | Paper and reproducibility repository for the APS benchmark, analysis pipeline, and manuscript-facing artifacts |
| `automated-lit-reviews-v2` | Broader application repository containing the deployed system, application logic, database integrations, and operational workflows |

The paper repository may include limited exported artifacts or summaries derived from the application where they are relevant to validation, but it is designed so that a reader can understand and reproduce the paper-facing benchmark results **without needing the full application repository**.

## Manuscript handling

Current white papers and manuscript drafts are intentionally excluded from version control until they have been manually vetted.

## Main directories

| Path | Purpose |
|---|---|
| `analysis-scripts/` | Core APS benchmark and figure-generation scripts |
| `data-aps/outputs/pub_figures/` | Generated publication figures |
| `data-aps/outputs/` | All JSON/CSV artifacts and intermediate figures |
| `app-validation-data/` | Exported supporting validation summaries |
| `validation-surveys/` | Reference PDFs for live experiment ground truth |
| `seed-papers/` | Seed paper PDFs |
