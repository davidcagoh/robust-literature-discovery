# CLAUDE.md

This repository contains the APS-based empirical validation for **LitDiscover**, a queue-driven literature discovery engine. The codebase is a set of sequential Python analysis scripts that simulate the production system's core logic: **bidirectional citation traversal**, a **forward-direction Pareto hub filter**, and **screen-yield-based stopping** inside a multi-round **Escape Hatch** loop.

The manuscript lives at `drafts/Robust_Literature_Discovery_from_Minimal_Seeds.md` (prose source of truth). `drafts/` root holds only the live prose source, `bibliography.json`, and `refs.bib`; every dead-end LaTeX target has been moved to `drafts/archive/` (2026-07-06 reorg) so the active submission is unambiguous:

| File | Format | Purpose |
|---|---|---|
| `drafts/ipm-submission/litdiscover_ipm.tex` | elsarticle `authoryear` | **Active submission target** — Information Processing & Management (rolling submission, no deadline) |
| `drafts/archive/litdiscover_ieeetran_legacy.tex` | IEEEtran (legacy) | PI annotation draft — do not delete, but not a submission target |
| `drafts/archive/tois-submission/litdiscover_tois.tex` | acmart `manuscript` mode | **Abandoned** — TOIS enforces a ~20-page minimum (excl. references); this paper is a focused 12-page contribution and doesn't meet it |
| `drafts/archive/jasist-submission/litdiscover_jasist.tex` | plain `article`, `apalike` refs | **Abandoned** — reformatted for JASIST 2026-07-06, superseded same day by TOIS (which was itself later abandoned over the page-length mismatch) |
| `drafts/archive/jcdl-submission/litdiscover_jcdl.tex` | ACM sigconf | **Abandoned** — JCDL 2026 deadline (June 30) missed, never submitted |

**IP&M submission format:** `\documentclass[authoryear,preprint,12pt]{elsarticle}` — Elsevier's journal class. **Important:** pass the `authoryear` class option and do *not* separately `\usepackage{natbib}` — elsarticle auto-loads natbib with the right settings tied to that option (omitting `authoryear` silently defaults to numeric `[1]`-style citations even with `\citet`/`\citep` in the source, which breaks any narrative citation like "Smith (2020) found..." — verified this by checking rendered PDF text, not just compile success). Bibliography style is `elsarticle-harv` (APA author-date — confirmed via IP&M's actual Guide for Authors; the generic assumption that Elsevier journals use numbered Vancouver style does *not* hold for this journal). Includes a required **CRediT authorship contribution statement** and a **Generative AI declaration** (same disclosure language as the abandoned TOIS draft) before the bibliography. `\linenumbers` active per journal review convention. Solo-authored. Compiles clean: `pdflatex && bibtex && pdflatex && pdflatex`, no errors/undefined refs, 19 pages single-column.

**TOIS submission format (archived, kept for reference):** `\documentclass[manuscript,review,anonymous]{acmart}` — single-column journal mode, ACM double-anonymous review. Uses `\acmJournal{TOIS}` instead of `\acmConference{}`. Abandoned solely over the page-length floor, not a formatting problem — the LaTeX itself compiled clean.

**JASIST submission format (archived, kept for reference):** `\documentclass[12pt]{article}` with `geometry`, `natbib`, `apalike` bibliography style, double-spaced. No ACM scaffolding. `\Description{}` kept as a no-op macro; `figure*` downgraded to plain `figure`.

**JCDL submission format (archived, kept for reference):** `\documentclass[sigconf,anonymous,review]{acmart}`. Abstract must appear **before** `\maketitle`. Do **not** add `\usepackage{caption}`, `\usepackage{subcaption}`, `\usepackage{hyperref}`, `\usepackage{natbib}`, or `\usepackage{geometry}` — acmart loads all of these and conflicts will crash the build.

**2026-07-06 repo cleanup:** `jcdl-submission/`'s LaTeX build artifacts (`.aux`/`.log`/`.bbl`/`.blg`/`.out`) were accidentally committed to git because `.gitignore`'s LaTeX-artifact patterns only matched `drafts/*.ext`, not subdirectories — fixed with recursive `drafts/**/*.ext` patterns and `git rm --cached` on the already-tracked files. Also removed: `closed-corpus-eval/data/sample/*.mat` (two orphaned MATLAB relics, referenced only by a script that itself lives under `citation-dynamics/archive/matlab-misc/` in the sibling repo — dead weight on dead weight), the empty `closed-corpus-eval/data/raw/` placeholder, empty `out/` build dirs, a stray unrelated `drafts/.claude/settings.local.json`, and the 1.2GB `live-survey-eval/data/cache/papers/` (gitignored, fully regenerable via `09_live_validation.py` — re-running it will simply re-fetch and repopulate the cache). The two later-abandoned submission folders (`jasist-submission/`, `tois-submission/`) were also folded into `drafts/archive/` once IP&M became the active target, so `drafts/` root never has more than one live LaTeX target at a time.

**2026-07-10 repo restructure:** Split the former single `scripts/` + `eval/` split into two self-contained tracks, `closed-corpus-eval/` and `live-survey-eval/`, each owning both its own `scripts/` and `data/`. Verified by reading every script in full: scripts 01–08 (+ 03b) touch only APS closed-corpus data and never reference live data or vice versa for `09_live_validation.py` — there was no real shared `scripts/`, just 10 files for one track and 1 file for the other artificially combined. Also deleted `inbox-papers/` (an ad hoc related-work-triage workflow judged redundant with the systematic 366-paper sweep now tracked in the `litdiscover` repo's wiki) and `app-validation-data/` (orphaned output of an already-deleted dead script).

## What matters most

The repository is a **data pipeline**, not a package. Most work happens in `closed-corpus-eval/scripts/` and `live-survey-eval/scripts/`, and the important cross-file dependency is the JSON/CSV artifact chain written to **`closed-corpus-eval/data/outputs/`**. Publication figures land in `closed-corpus-eval/data/outputs/pub_figures/`.

**Canonical experiment:** `04b_cold_start_lowseed.py` — k ∈ {1,2,3,4,5,10} seeds, N\_ROUNDS=2, PARETO\_P=80, YIELD\_THRESHOLD=0.05. This is the paper's primary result.

**Active publication figures (fig1–fig7):** All generated by `06_publication_figures.py`. fig8/fig8b/fig8c and fig9a–d have been dropped from the paper; their PNGs are archived in `pub_figures/deprecated/`.

## Environment and prerequisites

Python 3.11+ with:

```bash
pip install pandas numpy matplotlib scipy networkx
```

The APS citation CSV is expected at:

```
closed-corpus-eval/data/processed/aps-dataset-citations-2022.csv
```

`closed-corpus-eval/data/processed/` is a symlink → `../../../../citation-dynamics/data/processed` (canonical data lives in the sibling project). Each script resolves paths automatically via `Path(__file__).parent.parent.parent` (three `.parent`s: `scripts/eval/` or `scripts/sweep/` → `scripts/` → track root), which resolves to its own track root (`closed-corpus-eval/` or `live-survey-eval/`), not the overall repo root — no path editing needed.

`closed-corpus-eval/scripts/` splits into `eval/` (the validation pipeline — produces every paper-claimed number/figure) and `sweep/` (parameter-justification scripts that motivate the fixed values `eval/` uses, not paper claims themselves — verified by reading every script in full: none of `eval/`'s 6 scripts read anything from `sweep/`'s outputs, and vice versa).

## Common commands

Run from the repository root.

| Task | Command |
|---|---|
| Full APS eval pipeline (ground truth → figures) | `cd closed-corpus-eval/scripts/eval && python3 01_extract_ground_truth.py && python3 02_graph_characterisation.py && python3 03_traversal_simulation.py && python3 04b_cold_start_lowseed.py && python3 05_miss_analysis.py && python3 06_publication_figures.py` |
| Ground-truth extraction | `cd closed-corpus-eval/scripts/eval && python3 01_extract_ground_truth.py` |
| Graph characterisation | `cd closed-corpus-eval/scripts/eval && python3 02_graph_characterisation.py` |
| Traversal strategy comparison | `cd closed-corpus-eval/scripts/eval && python3 03_traversal_simulation.py` |
| Canonical cold-start (k=1–10, 2 rounds) | `cd closed-corpus-eval/scripts/eval && python3 04b_cold_start_lowseed.py` |
| Miss analysis | `cd closed-corpus-eval/scripts/eval && python3 05_miss_analysis.py` |
| Regenerate publication figures | `cd closed-corpus-eval/scripts/eval && python3 06_publication_figures.py` |
| Hyperparameter sweep (complete, 1980 rows) | `cd closed-corpus-eval/scripts/sweep && python3 08_hyperparameter_sweep.py` |
| Live validation experiments | `cd live-survey-eval/scripts && python3 09_live_validation.py` |
| Compile active (IP&M) paper PDF | `cd drafts/ipm-submission && pdflatex litdiscover_ipm && bibtex litdiscover_ipm && pdflatex litdiscover_ipm && pdflatex litdiscover_ipm` |

## Pipeline architecture

### `scripts/eval/` — produces every paper claim

| Script | Role | Reads | Writes |
|---|---|---|---|
| `01_extract_ground_truth.py` | Defines three survey-based gold sets | APS CSV | `ground_truth.json`, `corpus_stats.json` |
| `02_graph_characterisation.py` | Global graph stats + directional BFS reachability | APS CSV, `ground_truth.json` | `graph_stats.json` |
| `03_traversal_simulation.py` | Backward / forward / bidir / Pareto-filtered strategy comparison | APS CSV, `ground_truth.json` | `traversal_results.json` |
| **`04b_cold_start_lowseed.py`** | **Canonical experiment** (k=1–5,10, N\_ROUNDS=2) | APS CSV, `ground_truth.json` | `cold_start_results_lowseed.json` |
| `05_miss_analysis.py` | Structural analysis of unrecovered papers; reconstructs traversal from scratch | APS CSV, `ground_truth.json` | `missed_papers_S*.csv` |
| `06_publication_figures.py` | Generates fig1–fig7 for publication | outputs from 02/03/04b/05 + APS CSV | `pub_figures/fig1–fig7.png` |

### `scripts/sweep/` — justifies eval/'s fixed parameters, not paper claims themselves

| Script | Role | Reads | Writes |
|---|---|---|---|
| `03b_depth_pareto_grid.py` | Depth × Pareto grid sweep (fig8b; figure dropped from paper but data kept) | APS CSV, `ground_truth.json` | `traversal_results_depth_pareto_grid.json` |
| `04_cold_start_simulation.py` | Older cold-start (k=5/10/20/50, N\_ROUNDS=4), superseded by `eval/04b`; `cold_start_results.json` not yet generated — `07_elbow_analysis.py` depends on this and is inoperable | APS CSV, `ground_truth.json` | `cold_start_results.json` (not generated) |
| `07_rounds_sweep.py` | N\_ROUNDS sweep (supporting evidence; not a paper figure) | APS CSV, `ground_truth.json` | `n_rounds_sweep.csv` |
| `08_hyperparameter_sweep.py` | Full grid: PARETO\_P × YIELD\_THRESHOLD × N\_ROUNDS × K\_ESCAPE. **Complete: 1980 rows.** Figures from this sweep (fig9a–d) are dropped from the paper. | APS CSV, `ground_truth.json` | `hyperparameter_sweep.csv` |
| `07_elbow_analysis.py` | Retroactively evaluates between-round stopping criteria against `04`'s output. **Currently inoperable** — `04` hasn't been run. | `cold_start_results.json` (missing) | `elbow_stopping_results.csv` |

### `live-survey-eval/scripts/` — separate track

| Script | Role | Reads | Writes |
|---|---|---|---|
| `09_live_validation.py` | Live experiments via Semantic Scholar API (K17-RGC, Ge21-HSS, Le25-GLLM — all complete) | live-survey-eval seed/gold configs, S2 API | per-survey result JSON |

## Core mechanisms (appear across many files)

| Mechanism | Canonical location | Notes |
|---|---|---|
| **Bidirectional traversal** | `03`, `04b`, `05` | Both references (backward) and citations (forward) explored |
| **Forward Pareto filter** | `03`, `04b` | Suppresses citers with out-degree above the 80th percentile |
| **Screen-yield stopping** | `04b` | Halts BFS depth expansion when new-gold / new-visited < 0.05 |

The distinction between **within-round stopping** (yield threshold on BFS depth) and **between-round stopping** (N\_ROUNDS cap) is important. N\_ROUNDS=2 is the canonical setting — round 1 does most of the work, round 2 is an inexpensive insurance pass.

## Key implementation notes

- **`05_miss_analysis.py` reconstructs traversal from scratch** because `cold_start_results_lowseed.json` stores summary statistics, not visited sets. If you change stopping logic in `04b`, mirror it in `05`.
- **`04b` is intentionally a near-copy of `04`** with only the seed-size regime changed. Update both if core mechanics change.
- **`07_elbow_analysis.py` is currently inoperable** — it requires `cold_start_results.json` from `04`, which has not been generated. Not a priority; the N\_ROUNDS=2 finding from `04b` supersedes the elbow analysis motivation.
- **`03b_depth_pareto_grid.py`** generates the depth × Pareto grid used in the dropped fig8b. Data is preserved in `traversal_results_depth_pareto_grid.json` for potential future use.

## Repository conventions

- Top-level constants, explicit script-local helpers, JSON/CSV artifact handoff, reproducible random seeding.
- No build system, linter, or test suite. Validation = rerunning the affected script and checking downstream artifacts.
