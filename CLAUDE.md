# CLAUDE.md

This repository contains the APS-based empirical validation for **LitDiscover**, a queue-driven literature discovery engine. The codebase was a set of sequential Python analysis scripts that simulated the production system's core logic; as of 2026-07-14, `closed-corpus-eval/scripts/eval/04b_cold_start_lowseed.py` and `05_miss_analysis.py` no longer simulate it — they call the real `litdiscover.discovery.traverse` operators (`backward_traversal_operator`, `forward_traversal_operator`, `pareto_hub_threshold`) directly via a `ClosedCorpusSource` (see `closed-corpus-eval/scripts/_corpus_loader.py` and `litdiscover/litdiscover/discovery/graph_source.py`), through the same `GraphSource` abstraction the live-survey track's `10_operator_benchmark.py` already used. The rest of the pipeline (02, 03, sweep/*) is still simulation-only pending further migration — see `wiki/litdiscover/phase-discovery-roadmap.md` §1.2–1.3 in the sibling `citation-networks` repo for the full account of which scripts are migrated and why the closed-corpus and live-S2 tracks can now share code at all.

**2026-07-14 — `04b`'s canonical result changed, not just its implementation.** The original filter (archived as `04b_cold_start_lowseed_legacy.py`) discarded newly-found *candidate* papers based on the candidate's own out-degree — a real design flaw: a genuine gold paper could be excluded purely for citing a lot of things itself, unrelated to its relevance. The production-aligned filter only decides whether to expand an already-visited *frontier* paper's citers, based on that frontier paper's own citation count — it never discards a candidate on the candidate's own properties. Full 54-condition comparison (3 surveys × 3 seed strategies × k∈{1,2,3,4,5,10}): mean recall 93.5% (legacy) → **99.6%** (current canonical), mean corpus size 205,021 → **66,023** (3.1x smaller). One legible trade-off: contaminated-seed/low-k conditions saw small recall decreases (1.9–4.9pp) from less indiscriminate exploration within the fixed 2-round budget. Legacy results preserved at `data/outputs/cold_start_results_lowseed_legacy.json` and `data/outputs/figures_lowseed_legacy/`. **`05_miss_analysis.py` was re-run against the new canonical engine and now finds ZERO misses at the k=5/top-k condition** (100% recall, all 3 surveys) — meaning `06_publication_figures.py`'s Fig 7 ("miss analysis": in-degree/BFS-distance/journal/year comparison of missed vs. recovered papers) has no data left to plot at that condition. **This is flagged, not yet resolved** — `06` has not been re-run; Fig 7 needs either a re-anchor to a harder seed condition (one that still shows real misses under the corrected engine) or to be dropped, a decision intentionally left open rather than forced.

The manuscript lives at `drafts/Robust_Literature_Discovery_from_Minimal_Seeds.md` (prose source of truth). `drafts/` root holds only the live prose source, `bibliography.json`, and the canonical `refs.bib`; every dead-end LaTeX target has been moved to `drafts/archive/` (2026-07-06 reorg) so the active submission is unambiguous:

`drafts/ipm-submission/litdiscover_ipm.tex` and `litdiscover_ipm_anonymous.tex` both `\input{related-work}`, pulling from the shared `drafts/ipm-submission/related-work.tex` (single-sourced, not duplicated). `drafts/ipm-submission/refs.bib` is a **symlink** to `../refs.bib` — edit `drafts/refs.bib` only, never the symlink target directly. The full desk-rejected IP&M submission as it stood pre-redo is snapshotted at `drafts/archive/ipm-submission-rejected-2026-07-07/` — a complete, standalone copy, not touched by the ongoing redo.

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

`drafts/` root never has more than one live LaTeX target at a time — abandoned submission
attempts (`jasist-submission/`, `tois-submission/`, `jcdl-submission/`) live in `drafts/archive/`.

`closed-corpus-eval/` and `live-survey-eval/` are separate self-contained tracks, each owning its
own `scripts/` and `data/` — verified by reading every script in full: scripts 01–08 (+ 03b)
touch only APS closed-corpus data and never reference `09_live_validation.py`'s live data or vice
versa. There is deliberately no shared top-level `scripts/`.

## What matters most

The repository is a **data pipeline**, not a package. Most work happens in `closed-corpus-eval/scripts/` and `live-survey-eval/scripts/`, and the important cross-file dependency is the JSON/CSV artifact chain written to **`closed-corpus-eval/data/outputs/`**. Publication figures land in `closed-corpus-eval/data/outputs/pub_figures/`.

**Canonical experiment:** `04b_cold_start_lowseed.py` — k ∈ {1,2,3,4,5,10} seeds, N\_ROUNDS=2, PARETO\_P=80, YIELD\_THRESHOLD=0.05, traversal via real `litdiscover` production operators (see 2026-07-14 entry above). This is the paper's primary result.

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
| `03_traversal_simulation.py` | Backward / forward / bidir / Pareto-filtered strategy comparison, via real `litdiscover` operators (percentile sweep bypasses Gini calibration by design — see script docstring) | `_corpus_loader.py` (APS CSV), `ground_truth.json` | `traversal_results.json` — **migration not run to completion**, see 2026-07-14 entry above |
| **`04b_cold_start_lowseed.py`** | **Canonical experiment** (k=1–5,10, N\_ROUNDS=2), via real `litdiscover` operators + `ClosedCorpusSource` | `_corpus_loader.py` (APS CSV), `ground_truth.json` | `cold_start_results_lowseed.json` |
| `05_miss_analysis.py` | Structural analysis of unrecovered papers; reconstructs traversal from scratch via the same operators (must mirror 04b's engine — currently finds 0 misses at the canonical k=5/top-k condition, see 2026-07-14 entry above) | `_corpus_loader.py` (APS CSV), `ground_truth.json` | `missed_papers_S*.csv` |
| `06_publication_figures.py` | Generates fig1–fig7 for publication | outputs from 02/03/04b/05 + APS CSV | `pub_figures/fig1–fig7.png` |
| **`07_operator_benchmark.py`** (new 2026-07-14) | Mirrors `live-survey-eval/10_operator_benchmark.py`: real `backward_traversal_operator`/`forward_traversal_operator`/`pareto_hub_threshold` against `ClosedCorpusSource`, single-pass ablation, all 3 surveys. Author/venue expansion NOT included — the `.mat` file's author-DOI linkage is MCOS-encoded and not decodable with available tools (confirmed via `mat73`, see script docstring) | `_corpus_loader.py` (APS CSV), `ground_truth.json` | `closed_corpus_operator_benchmark_results.json` |

### `scripts/sweep/` — justifies eval/'s fixed parameters, not paper claims themselves

| Script | Role | Reads | Writes |
|---|---|---|---|
| `03b_depth_pareto_grid.py` | Depth × Pareto grid sweep (fig8b; figure dropped from paper but data kept) | APS CSV, `ground_truth.json` | `traversal_results_depth_pareto_grid.json` |
| `04_cold_start_simulation.py` | Older cold-start (k=5/10/20/50, N\_ROUNDS=4), superseded by `eval/04b`; `cold_start_results.json` not yet generated — `07_elbow_analysis.py` depends on this and is inoperable. Engine migrated to real `litdiscover` operators 2026-07-14, **not run** (see note below) | `_corpus_loader.py` (APS CSV), `ground_truth.json` | `cold_start_results.json` (not generated) |
| `07_rounds_sweep.py` | N\_ROUNDS sweep (supporting evidence; not a paper figure), via real `litdiscover` operators | `_corpus_loader.py` (APS CSV), `ground_truth.json` | `n_rounds_sweep.csv` — **migration not run to completion**, see 2026-07-14 entry above |
| `08_hyperparameter_sweep.py` | Full grid: PARETO\_P × YIELD\_THRESHOLD × N\_ROUNDS × K\_ESCAPE. **1980 rows generated pre-migration** (dict-lookup engine); engine migrated to real `litdiscover` operators 2026-07-14 but **not re-run** — at ~60x `eval/03`'s condition count, a full re-run under the production `ThreadPoolExecutor` design would likely take hours, see 2026-07-14 entry above. Figures from this sweep (fig9a–d) are dropped from the paper. | `_corpus_loader.py` (APS CSV), `ground_truth.json` | `hyperparameter_sweep.csv` |
| `07_elbow_analysis.py` | Retroactively evaluates between-round stopping criteria against `04`'s output. **Currently inoperable** — `04` hasn't been run. | `cold_start_results.json` (missing) | `elbow_stopping_results.csv` |

### `live-survey-eval/scripts/` — separate track

| Script | Role | Reads | Writes |
|---|---|---|---|
| `09_live_validation.py` | Live experiments via Semantic Scholar API (K17-RGC, Ge21-HSS, Le25-GLLM — all complete pre-migration). Traversal engine migrated to real `litdiscover` operators via `S2Source` 2026-07-14 (closes the PDF-first/Gini-calibration drift from production — see 2026-07-14 entry above), **not re-run** (spends real S2 quota) | live-survey-eval seed/gold configs, S2 API | per-survey result JSON |
| `10_operator_benchmark.py` | Runs `litdiscover`'s real production operators (imported from the `litdiscover` package, not reimplemented) against the 3 live gold-sets — baselines, marginal contribution, ablation, all derived from one pass per operator. Loaders/config/metrics extracted to `_shared.py` 2026-07-14. See `wiki/litdiscover/phase-discovery-roadmap.md` §4.3-§4.5 (⏸ paused 2026-07-14). | Existing gold-sets/seeds JSON, S2 API via the `litdiscover` package | `data/outputs/operator_benchmark_results.json` |
| `11_redundancy_check.py` | One-off sanity check: is co-citation redundant with 2-round forward traversal? (No — near-zero overlap.) Imports `_shared.py` normally as of 2026-07-14 (previously `importlib.util`-loaded `10`'s whole module body). | Existing gold-sets/seeds, S2 API | `data/outputs/redundancy_check_results.json` |
| `12_chained_composition.py` | Composition experiment (chained vs. independent-union retrieval) — H0/H1 framed. Result: chaining made both recall and precision worse in the one survey completed; paused, not fixed. See §4.6. Imports `_shared.py` normally as of 2026-07-14. | `operator_benchmark_results.json` (for the independent-union baseline), S2 API | `data/outputs/composition_experiment_results.json` |
| `_shared.py` (new 2026-07-14) | Shared config/loaders/metrics (`SURVEYS`, `_load_gold`, `_load_seed_ids`, `_fetch_full_paper`, `_recall`, `_precision`, `OPERATORS`, `MARGINAL_ORDER`) for `10`/`11`/`12` | — | — |

**2026-07-14 — gold-set data-quality fix, `data/section-ground-truth/` added:** `build_gold_set_from_s2()` (in `09_live_validation.py`) fetches each live survey's reference list from S2's own `/references` endpoint. Two of the three gold-sets (`Ge21-HSS_gold.json`, `K17-RGC_gold.json`) were found to contain a handful of entries S2 mis-links as references (a book-series name stored as a "paper," or an unrelated real paper linked entirely) — corrected by hand (Ge21-HSS 202→200, K17-RGC 56→52 entries; Le25-GLLM was already clean at 57/57). **No automated content filter was added** — two attempts (an all-caps/short-title rejection, then a series-name-phrase match) were both reverted after live testing showed they rejected far more real references than actual noise (short/all-caps titles are routine in real academic bibliographies). `FUZZY_THRESHOLD` was raised 88→92 as a generic, unrelated tightening. Any script computing recall against these two gold-sets should be re-run — the corrected (smaller) denominators mean recall is now slightly higher than previously reported. New directory `live-survey-eval/data/section-ground-truth/{Ge21-HSS,K17-RGC,Le25-GLLM}_sections.json` holds a section-level ground-truth annotation (which part of the survey each gold reference is discussed in) built for the `litdiscover` wiki's representation-learning experiment (`wiki/litdiscover/phase-representation-roadmap.md`) — not consumed by anything in this repo's own pipeline yet.

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
