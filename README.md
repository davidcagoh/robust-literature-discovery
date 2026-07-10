# robust-literature-discovery

This repository contains the analysis, figures, and reproducibility materials for the paper **Robust Literature Discovery from Minimal Seeds**, which validates the [LitDiscover](https://github.com/davidcagoh/litdiscover) engine (private repository) on the APS citation corpus.

## Scope

The contents here are intended to support the paper's empirical claims and reproducibility workflow. In particular, this repository contains the APS benchmark analysis scripts, figure-generation scripts, paper-facing notes, and selected reproducibility materials used to generate the manuscript's results.

## Relationship to LitDiscover

This repository is intentionally separate from **[LitDiscover](https://github.com/davidcagoh/litdiscover)** (private repository).

| Repository | Role |
|---|---|
| `robust-literature-discovery` (this repo, public) | Paper and reproducibility repository: APS benchmark, analysis pipeline, publication figures, manuscript |
| [**LitDiscover**](https://github.com/davidcagoh/litdiscover) (private repository) | Deployed engine: queue loop, DB integrations, LLM screening, extraction, synthesis |

The paper repository is self-contained — you can reproduce all benchmark results without the full application.

## Manuscript

The active manuscript is at `drafts/Robust_Literature_Discovery_from_Minimal_Seeds.md`. The active submission target compiles from `drafts/ipm-submission/litdiscover_ipm.tex` (Information Processing & Management). Earlier submission attempts (JCDL, JASIST, TOIS) and the legacy IEEEtran draft are kept for reference in `drafts/archive/`.

## Quick start (reproduce all paper figures)

```bash
pip install pandas numpy matplotlib scipy networkx

# Place the APS citation CSV at closed-corpus-eval/data/processed/aps-dataset-citations-2022.csv
# then run the full pipeline:
cd closed-corpus-eval/scripts/eval
python3 01_extract_ground_truth.py
python3 02_graph_characterisation.py
python3 03_traversal_simulation.py
python3 04b_cold_start_lowseed.py   # canonical experiment (k=1–10, 2 rounds)
python3 05_miss_analysis.py
python3 06_publication_figures.py    # writes fig1–fig7 to data/outputs/pub_figures/
```

## Directory structure

This repo is two evaluation tracks plus the paper. Each track owns both its scripts and its
data — there's no shared top-level `scripts/`, because the coupling is real: the closed-corpus
scripts never touch live data and vice versa. Grouping by track (not by "kind of file") means
opening one directory gets you everything relevant to that track.

```
robust-literature-discovery/
├── closed-corpus-eval/            # closed-corpus APS benchmark
│   ├── scripts/
│   │   ├── eval/                          # the validation pipeline — produces every paper claim/figure
│   │   └── sweep/                         # parameter-justification scripts (why N_ROUNDS=2, PARETO_P=80)
│   └── data/
│       ├── processed/                     # symlink → ../../../../citation-dynamics/data/processed
│       └── outputs/                       # JSON/CSV artifacts + pub_figures/ (fig1–fig7)
├── live-survey-eval/              # live open-domain validation (Semantic Scholar API)
│   ├── scripts/                       # 09_live_validation.py
│   └── data/
│       ├── gold-sets/, seeds/             # curated per-survey ground truth (tracked in git)
│       ├── seed-papers/                   # seed PDFs for the 3 live-validation surveys (RGC/HSS/GLLM)
│       ├── validation-surveys/            # the 3 survey PDFs themselves (ground-truth bibliographies)
│       ├── outputs/                       # validated results (tracked in git)
│       └── cache/                         # API response cache (gitignored, regenerable)
└── drafts/
    ├── Robust_Literature_Discovery_from_Minimal_Seeds.md   # prose source of truth
    ├── bibliography.json, refs.bib                         # shared citation data
    ├── ipm-submission/      # ACTIVE — Information Processing & Management (elsarticle)
    └── archive/             # dead-end submission attempts, kept for reference:
        ├── jcdl-submission/     # JCDL 2026 — deadline missed, never submitted
        ├── jasist-submission/   # JASIST — superseded same-day by TOIS
        ├── tois-submission/     # TOIS — dropped over 20-page minimum, paper is 12pp
        └── litdiscover_ieeetran_legacy.tex + Whitepaper_legacy.{md,pdf}
```

| Path | Purpose |
|---|---|
| `closed-corpus-eval/scripts/eval/` | The validation pipeline — every paper-claimed number/figure |
| `closed-corpus-eval/scripts/sweep/` | Parameter-justification scripts (N_ROUNDS, PARETO_P sweeps) |
| `closed-corpus-eval/data/outputs/pub_figures/` | Generated publication figures (fig1–fig7) |
| `closed-corpus-eval/data/outputs/` | All JSON/CSV artifacts and intermediate figures |
| `live-survey-eval/scripts/` | Live Semantic Scholar validation script |
| `live-survey-eval/data/validation-surveys/` | Reference PDFs for live experiment ground truth |
| `live-survey-eval/data/seed-papers/` | Seed paper PDFs |
| `drafts/` | Manuscript source. Root: prose + refs. `ipm-submission/`: active LaTeX target. `archive/`: dead-end submission attempts + legacy draft |

## License

MIT — see [LICENSE](LICENSE). Note the third-party APS citation dataset itself is not covered
by this license and is not redistributed here; obtain it separately per APS's own terms (see
`closed-corpus-eval/data/processed/` note above).
