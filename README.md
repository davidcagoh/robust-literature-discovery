# robust-literature-discovery

This repository contains the analysis, figures, and reproducibility materials for the paper **Robust Literature Discovery from Minimal Seeds**, which validates the [LitDiscover](https://github.com/davidcagoh/automated-lit-reviews-v2) engine (private repository) on the APS citation corpus.

## Scope

The contents here are intended to support the paper's empirical claims and reproducibility workflow. In particular, this repository contains the APS benchmark analysis scripts, figure-generation scripts, paper-facing notes, and selected reproducibility materials used to generate the manuscript's results.

## Relationship to LitDiscover

This repository is intentionally separate from **[LitDiscover (automated-lit-reviews-v2)](https://github.com/davidcagoh/automated-lit-reviews-v2)** (private repository).

| Repository | Role |
|---|---|
| `robust-literature-discovery` (this repo, public) | Paper and reproducibility repository: APS benchmark, analysis pipeline, publication figures, manuscript |
| [**LitDiscover**](https://github.com/davidcagoh/automated-lit-reviews-v2) (private repository) | Deployed engine: queue loop, DB integrations, LLM screening, extraction, synthesis |

The paper repository is self-contained — you can reproduce all benchmark results without the full application.

## Manuscript

The active manuscript is at `paper-drafts/Robust_Literature_Discovery_from_Minimal_Seeds.md`. The active submission target compiles from `paper-drafts/ipm-submission/litdiscover_ipm.tex` (Information Processing & Management). Earlier submission attempts (JCDL, JASIST, TOIS) and the legacy IEEEtran draft are kept for reference in `paper-drafts/archive/`.

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

## Directory structure

This repo is organized around two parallel evaluation pipelines — a closed-corpus APS
benchmark (`data-aps/`) and a live open-domain validation (`data-live/`) — plus the paper
itself. The two pipelines are kept as separate top-level directories on purpose: they have
genuinely different data lifecycles (a static historical corpus vs. live-fetched API
results), so nesting them under one generic `data/` would just hide that distinction one
level deeper without simplifying anything.

```
robust-literature-discovery/
├── analysis-scripts/        # Python pipeline: ground truth → traversal sim → figures
├── paper-drafts/
│   ├── Robust_Literature_Discovery_from_Minimal_Seeds.md   # prose source of truth
│   ├── bibliography.json, refs.bib                         # shared citation data
│   ├── ipm-submission/      # ACTIVE — Information Processing & Management (elsarticle)
│   └── archive/             # dead-end submission attempts, kept for reference:
│       ├── jcdl-submission/     # JCDL 2026 — deadline missed, never submitted
│       ├── jasist-submission/   # JASIST — superseded same-day by TOIS
│       ├── tois-submission/     # TOIS — dropped over 20-page minimum, paper is 12pp
│       └── litdiscover_ieeetran_legacy.tex + Whitepaper_legacy.{md,pdf}
├── data-aps/                # closed-corpus APS benchmark
│   ├── processed/               # symlink → ../../../citation-dynamics/data/processed
│   └── outputs/                 # JSON/CSV artifacts + pub_figures/ (fig1–fig7)
├── data-live/                # live open-domain validation (Semantic Scholar API)
│   ├── gold-sets/, seeds/       # curated per-survey ground truth (tracked in git)
│   ├── outputs/                 # validated results (tracked in git)
│   └── cache/                   # API response cache (gitignored, regenerable)
├── seed-papers/              # seed PDFs for the 3 live-validation surveys (RGC/HSS/GLLM)
├── validation-surveys/       # the 3 survey PDFs themselves (ground-truth bibliographies)
├── inbox-papers/             # drop zone for related-work triage (see inbox-papers/README.md)
└── app-validation-data/      # exported summaries from the deployed LitDiscover app
```

| Path | Purpose |
|---|---|
| `analysis-scripts/` | Core APS benchmark and figure-generation scripts |
| `data-aps/outputs/pub_figures/` | Generated publication figures (fig1–fig7) |
| `data-aps/outputs/` | All JSON/CSV artifacts and intermediate figures |
| `app-validation-data/` | Exported supporting validation summaries |
| `validation-surveys/` | Reference PDFs for live experiment ground truth |
| `seed-papers/` | Seed paper PDFs |
| `paper-drafts/` | Manuscript source. Root: prose + refs. `ipm-submission/`: active LaTeX target. `archive/`: dead-end submission attempts + legacy draft |
