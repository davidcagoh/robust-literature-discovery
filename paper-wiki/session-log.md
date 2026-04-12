# Session Log

Reverse-chronological log of what was done each session. Read this at the start of every new session to resume without re-deriving state.

---

## 2026-04-12 (session 11) — Wiki relocation decision; memory architecture settled

### What was done
- Decided to move `paper-wiki/` out of `lit-review/robust-literature-discovery/` to `citation-networks/wiki/` at the repo root, since it now covers both citation-dynamics and lit-review
- Decided to `git init` at `citation-networks/` root so the shared wiki is version-controlled; nested lit-review repo stays as-is (git ignores nested repos)
- Clarified two-layer memory architecture: `citation-networks/wiki/` for human-readable between-session state; `~/.claude-shared/projects/` for Claude cross-session context (should have a pointer + key facts about this project)
- No code or wiki files changed this session — decisions only

### State at end of session
- `paper-wiki/` still at old location (`lit-review/robust-literature-discovery/paper-wiki/`) — move deferred to next session
- All prior session 10 changes committed (a114e26)

### What to do next session
1. `git init` at `citation-networks/`; move `paper-wiki/` → `citation-networks/wiki/`; update any cross-references; commit in outer repo
2. Add citation-networks project entry to `~/.claude-shared/projects/MEMORY.md` (Zeitgeist hypothesis, pipeline stages, SOTA gap question)
3. Run SOTA gap assessment for citation-dynamics (Q-SOTA in open-questions.md) — search 2024–2026 for temporal citation phase analysis and LLM-based synthesis work

---

## 2026-04-12 (session 10) — Codebase reorganized; citation-dynamics/ scoped as synthesis stage; SOTA gap surfaced

### What was done

**Explored and mapped the relationship between `thesis/` (now `citation-dynamics/`) and `lit-review/robust-literature-discovery/`:**

- Read all writings in `thesis/writings/`: abstract (Sept 2024, supervisor Xiaobai Sun), literature review (~50 papers), thesis draft outline, year-by-year notes
- The thesis project is formally titled *"Recognizing Signature Patterns and Phases of Time-Varying Networks"* with three claimed contributions: (1) time-dependent spatial embedding, (2) backward mapping for influence tracing, (3) quantitative propagation phase characterization
- The core intellectual concept is the **Zeitgeist hypothesis**: the global APS citation distribution is a mixture of subcommunity distributions, each scale-free, corresponding to distinct research generations
- The lit review (written ~2022–2024) identified Nakis et al. 2024 (Single Event Networks / Dynamic Impact Embedding) as the cutting edge — this is now ~2 years old and the field may have moved

**Reorganized the `citation-networks/` directory structure:**

- Renamed `thesis/` → `citation-dynamics/` (reflects actual research content)
- Deleted `lit-review/deps-matlab/` (gitignored, byte-for-byte copy of `citation-dynamics/deps/`)
- Replaced `data-aps/processed/` (662 MB of duplicate files) with a relative symlink → `../../../citation-dynamics/data/processed`
- Fixed `.gitignore` to cover the symlink (added `data-aps/processed` without trailing slash)
- Wrote `citation-dynamics/README.md` describing the project, data schema, and pipeline relationship

**Identified the pipeline architecture:**

```
citation-dynamics/          →   robust-literature-discovery/   →   [synthesis — planned]
Understand network              Discover papers from               Post-discovery clustering,
structure (Zeitgeist,           minimal seeds (89–99%              temporal phase analysis,
phases, embedding)              recall at k=5)                     backward influence mapping
```

The synthesis step — applying Leiden community detection, temporal window slicing, and SG-t-SNE embedding to a *discovered* paper set — is the natural next contribution and draws directly on `citation-dynamics/` methods.

### State at end of session
- `citation-dynamics/` renamed and has README; all MATLAB scripts intact
- `data-aps/processed` symlink working correctly (verified: ls resolves 4 files)
- `deps-matlab/` deleted; `.gitignore` updated
- Paper itself (lit-review) unchanged — Q1–Q11 open questions carry forward
- No analysis scripts run this session

### What to do next session
1. **SOTA gap assessment for citation-dynamics**: Do a literature search (2024–2026) for work on temporal citation network phase analysis, community detection in citation graphs, and synthesis of literature reviews. Specifically check: has SEN/Dynamic Impact Embedding (Nakis 2024) been followed up? Is there LLM-based synthesis work that makes the Zeitgeist approach redundant or complementary?
2. **Resume paper**: Q11 (PDF yellow-highlight [CITATION NEEDED] locations), venue decision (ICASR 2026 / ALTARS 2026), figure fixes Q2/Q3/Q7/Q8
3. **Scope the synthesis step concretely**: If SOTA check shows citation-dynamics is still novel, draft what a "synthesis pipeline" experiment would look like — taking robust-literature-discovery output and running it through Leiden + temporal analysis

---

## 2026-04-11 (session 9) — LaTeX compile fixed; IEEEtran structure corrected

### What was done

**`paper-drafts/litdiscover.tex` fixed and successfully compiles to PDF (9 pages).**

Five structural problems were present:

1. `\titleformat`/`\titlespacing` were called but `\usepackage{titlesec}` was commented out → removed the four dead lines.
2. `\usepackage{parskip}` conflicts with IEEEtran column layout → commented out.
3. `\usepackage{setspace}` + `\onehalfspacing` don't apply to IEEEtran → commented out.
4. Title was in a manual `\begin{center}` block and `\author{}` was orphaned in the body. Restructured to proper IEEEtran form: `\title{}` and `\author{}` in the preamble, `\maketitle` at document open.
5. `\usepackage{natbib}` was loaded without options; IEEEtran.bst uses numbered citations, causing a "Bibliography not compatible with author-year" error → changed to `\usepackage[numbers]{natbib}`.

The `\citep{}` / `\citet{}` natbib commands throughout the document are preserved and work correctly in numbered mode.

### State at end of session
- `litdiscover.tex`: ✅ compiles cleanly (pdflatex + bibtex + pdflatex × 2), 9-page PDF
- No content changes — purely structural/preamble fixes
- Open questions unchanged from session 8

### What to do next session
1. User reviews PDF for [CITATION NEEDED] yellow-highlight locations (Q11)
2. Venue decision: check ICASR 2026 and ALTARS 2026 deadlines
3. Figure fixes: Q7 (out-degree to Fig 7), Q8 (oracle label on Fig 2) — see open-questions.md for current status

---

## 2026-04-11 (session 8) — Full paper rewrite: Abstract, §1, §2, §5, §9 rewritten; Q12 and Q13 closed

### What was done

**Full rewrite pass completed:**

- **Abstract** — rewritten from 170-word hedging draft to 140-word finding-first form. Opens: "Automated literature discovery must do something retrieval cannot: recover a topic's literature from almost nothing." Leads with 89.2%/98.4%/96.9% headline numbers.
- **§1 Introduction** — para 4 and contributions rewritten. Removed apologetic "original internal validation → more consequential question" framing. Four contributions tightened to crisp action statements (structural account, minimal-seed recall, miss analysis, live yield signal).
- **§2 Related Work** — restructured with bold subheadings per area (citation-graph analysis; automated SR; graph compression). CiteAgent [21] integrated into citation-graph analysis; ASReview [23] and Wohlin [22] added to automated SR. Distinctive contribution paragraph leads: "LitDiscover formalises and automates the snowballing methodology [22]..."
- **§5 Structural Motivation** — split one overlong paragraph into two. Para 1: empirical BFS observation (backward outperforms forward, bidirectional best). Para 2: mechanistic explanation via Goldberg [20] (80% bibliographic copying → shared reference layer → why backward is efficient) feeding directly into Pareto filter rationale.
- **§9 Conclusion** — rewritten from scratch (Manus AI scaffolded version replaced). Now: (1) opens with "bounded control problem, not open-ended retrieval" framing; (2) leads APS results with k=1 (S3 91.2% from 1 seed, S2 96.8% at k=3) before k=5 headline; (3) states live results concisely in same para; (4) closes with directional-asymmetry insight as the operative principle.
- **Q12 closed:** Related work is correctly at §2 (was at §8 in original Manus draft).
- **Q13 closed:** §9 now explicitly mentions k=1 APS result and k=1 live result (K17-RGC 100%, 1 seed, 1 round).

### State at end of session
- Sections rewritten: Abstract ✅, §1 ✅, §2 ✅, §5 ✅, §9 ✅
- §3–§8 intact (were already correct)
- Refs: 23 entries [1]–[23] ✅
- Open questions: Q12 ✅, Q13 ✅ (see open-questions.md)
- Remaining open: Q11 (PDF yellow-highlights), fig fixes Q7/Q8, venue decision

### What to do next session
1. User reviews PDF for [CITATION NEEDED] yellow-highlight locations (Q11)
2. Venue decision: check ICASR 2026 and ALTARS 2026 deadlines
3. Figure fixes: Q7 (out-degree to Fig 7), Q8 (oracle label on Fig 2)

---

## 2026-04-11 (session 7) — Inbox sweep: CiteAgent + refs.bib processed; venues ICASR/ALTARS identified; refs [20–21] added

### What was done

**Inbox processed:**
- `2511.03758v3.pdf` — CiteAgent (Ji et al., Nov 2025, arXiv): LLM agents simulate citation network *formation*. Key finding: recommendation algorithm's citation-visibility is the dominant driver of preferential attachment → directly supports Pareto filter. Added as ref [21]. Cited in §2 (citation-graph analysis) and §5 (backward traversal motivation).
- `refs.bib` — 9 scientometrics papers assessed. One added: Goldberg et al. 2015 (Scientometrics) — "~80% of references from local bibliography copying" → supports backward traversal priority. Added as ref [20], cited in §5. Others skipped (see bibliography.json `_inbox_assessed_2026-04-11`).
- `ResearchRabbit 2025 Revamp` (Aaron Tay blog, Nov 2025): Not citable as paper. Key context: RR, Connected Papers, Litmaps are all *interactive* exploration tools without automated stopping or screening — confirms LitDiscover's distinct position in §2. Connected Papers is noted as "fastest single-seed tool" — good contrast with LitDiscover's minimal-seed *automated* discovery framing.

**Paper updates:**
- §2 para 1: CiteAgent [21] added — "recommendation algorithm drives preferential attachment, not author bias"
- §5: Goldberg 2015 [20] added — "~80% of references from bibliographic copying, corroborating backward traversal priority"
- References [20] and [21] appended

**Venues updated:**
- ICASR (International Collaboration for Automation of Systematic Reviews) — ⭐⭐⭐⭐ BEST fit. Annual event; 2025 was July Potsdam. Watch for ICASR 2026 call.
- ALTARS (Workshop on AI in Technology-Assisted Review, at The Web Conference) — ⭐⭐⭐ Workshop track, April 2026 Copenhagen — check if submission window still open.
- ISPOR: health/clinical economics focus — not ideal for general-domain LitDiscover.
- ASE/AIware: software engineering focus — not relevant.

### State at end of session
- Refs 1–21: all added ✅
- §2 and §5 inline citations updated ✅
- Inbox: fully processed ✅ (can move to processed/)
- Remaining: [CITATION NEEDED] from user's PDF; full paper rewrite

### What to do next session
1. User reviews PDF yellow-highlights → [CITATION NEEDED] locations
2. Check ICASR 2026 and ALTARS 2026 deadlines → venue decision
3. Full paper rewrite

---

## 2026-04-11 (session 6) — Elicit/ResearchRabbit/ConnectedPapers citations added; inbox-papers folder created; venue analysis

### What was done

**Citations added (refs 17–19):**
- [17] Elicit (2024) — `Elicit2024` key — added to bibliography.json + paper §2 inline cite
- [18] ResearchRabbit (2025) — `ResearchRabbit2025` key — added to bibliography.json + paper §2 inline cite
- [19] Connected Papers (n.d.) — `ConnectedPapers` key — added to bibliography.json + paper §2 inline cite
- Paper §2 now reads: "Elicit [17], ResearchRabbit [18]" and "CiteSpace [15], Connected Papers [19]"
- References section updated with all three entries
- `_citation_gaps` in bibliography.json updated: Elicit/RR/CP gaps marked FILLED; remaining gap = PDF yellow-highlights (pending user PDF review)

**Zotero note clarified:** refs.bib at /Users/davidgoh/Downloads/refs.bib is the full general library — does NOT contain LitDiscover-specific entries. For a focused export: select LitDiscover collection in Zotero → right-click → Export Collection → Better BibTeX.

**inbox-papers/ folder created:** `/robust-literature-discovery/inbox-papers/` — drop new PDFs here for related-work analysis.

**Venue analysis (see INDEX.md):** Top candidates identified; JCDL or JASIST recommended as primary targets.

### State at end of session

- Refs 1–19: ✅ all added to bibliography.json and paper References section
- §2 inline citations: ✅ [17], [18], [19] inserted
- Remaining citation gaps: [CITATION NEEDED] from user's PDF yellow highlights
- Venue: not yet decided — see venue analysis in INDEX.md

### What to do next session

1. User drops papers into `inbox-papers/` → related-work sweep
2. User reviews PDF yellow-highlights → identify [CITATION NEEDED] locations
3. Venue decision
4. Full paper rewrite

---

## 2026-04-10 (session 5) — §8→§2 move, citation additions, bibliography.json

### What was done

**Section restructure:** §8 Related Work moved to §2. New order: §1 Intro → §2 Related Work → §3 Architecture → §4 Benchmark → §5 Structural Motivation → §6 Main Results → §7 Miss Analysis → §8 Live Validation → §9 Conclusion.

**Citation additions:**
- §1: [5, 9] added after "citation networks are highly asymmetric"
- §3: [5] added after "in a heavy-tailed network"
- §5: [5, 9] added after "heavy-tailed in its in-degree distribution"

**bibliography.json created** at `paper-drafts/bibliography.json`:
- 16 structured entries (refs 1–16) with keys, types, DOIs, and role notes
- Remaining gaps: Elicit, ResearchRabbit, Connected Papers (need Zotero or manual entry)
- Includes `_latex_note` with pandoc command for LaTeX transition

### State at end of session

- Paper structure: ✅ §2 = Related Work
- Citations: ✅ 3 gaps filled; 2 remaining (Elicit, ResearchRabbit, Connected Papers)
- bibliography.json: ✅ created
- Remaining: [CITATION NEEDED] from PDF yellow-highlights, full rewrite

### What to do next session

1. User to export Zotero .bib → share path for Elicit/ResearchRabbit/ConnectedPapers entries
2. Identify [CITATION NEEDED] yellow-highlight locations in PDF
3. Full paper rewrite

---

## 2026-04-10 (session 4) — Fig6 caption + paper §4/§5/§6 text complete

### What was done

**Fig6 caption updated** in `06_publication_figures.py`:
- New 2-sentence subtitle explains non-monotonicity for both top-k and contaminated seed types.
- Fig6 PNG regenerated.

**Paper text edits complete** (`paper-drafts/Robust_Literature_Discovery_from_Minimal_Seeds.md`):
- §4: fig2 paragraph rewritten — now correctly describes k=5 seed direction-comparison experiment (not oracle seeding).
- §5: non-monotonicity paragraph added after Saturation — explains k=2 dip and contaminated decline, both resolved by round 2.
- §6: fig9 references removed; fig8b/8c referenced instead; yield threshold framed as safety valve.

### State at end of session

- Fig6 caption: ✅ complete
- §4, §5, §6 paper text: ✅ complete  
- Remaining paper work: §8→§2 move, [CITATION NEEDED] locations, full rewrite
- All figures: ✅ complete

### What to do next session (in order)

1. Move related work §8 → §2
2. Add [CITATION NEEDED] at yellow-highlighted PDF locations
3. Full paper rewrite pass

---

## 2026-04-10 (session 3) — Paper text fixes: §4 fig2 paragraph, §5 non-monotonicity, §6 fig9 removal

### What was done

**Three targeted paper edits applied to `paper-drafts/Robust_Literature_Discovery_from_Minimal_Seeds.md`:**

1. **§4 fig2 paragraph rewritten** (oracle-seeding language removed):
   - Old text: "Backward traversal immediately covers the gold bibliography at depth 1 because the survey reference list is, by construction, the survey's backward neighborhood."
   - New text: describes k=5 top-k seeds, explains directional asymmetry, explains why bidirectional dominates, motivates Pareto filter from that observation.
   - Fig2 is now correctly described as a seed-based direction comparison, not an oracle result.

2. **§5 non-monotonicity note added** (after Saturation paragraph):
   - Top-k non-monotonicity: k=2 can be worse than k=1 due to overlapping backward neighborhoods between nearest-neighbor seeds.
   - Contaminated non-monotonicity: each additional off-topic seed opens a separate traversal frontier into unrelated graph regions.
   - Both effects are resolved by round 2.

3. **§6 fig9 references removed and replaced**:
   - Removed: "The hyperparameter sweep (Figures 9a–9b) confirms that no single threshold simultaneously maximises recall and minimises corpus size..." + `![Figure 9b: ...]` image link.
   - Replaced with: fig8b/8c references + yield threshold one-sentence explanation (yield threshold is a safety valve; depth-2 screen yield 0.3–1.5% falls below any practical threshold, so stopping is insensitive to its value).

### State at end of session

- §4: ✅ fig2 paragraph rewritten (bidirectional comparison from k=5 seeds)
- §5: ✅ non-monotonicity paragraph added
- §6: ✅ fig9 references removed; fig8b/8c referenced instead
- Paper sections still needing work: §4 text (rest of section), §8 move to §2, [CITATION NEEDED] locations
- All figures: ✅ complete

### What to do next session (in order)

1. Fig6 caption — 2-sentence non-monotonicity explanation (§5 text has it; caption doesn't yet)
2. Move related work §8 → §2
3. Add [CITATION NEEDED] at yellow-highlighted locations in PDF
4. Full paper rewrite pass

---

## 2026-04-10 — Fig9 dropped; yield threshold decision; §6 restructure planned

### What was done

**Fig9 dropped entirely:**
- fig9a (Pareto×yield recall heatmap): dropped — covered by fig8c.
- fig9b (recall vs Pareto per yield threshold): dropped — vacuous sweep. Depth-2 screen yield for these survey types is 0.3–1.5%, falling below even the lowest tested threshold (1%). BFS stops at depth=2 regardless of threshold setting; all sweep rows are identical. This is a missing parameter region, not robustness evidence.
- fig9c (recall vs N_rounds): dropped — covered by fig4 (stacked bar shows round contribution directly).
- fig9d (corpus size heatmap): dropped — covered by fig8b (depth×pareto heatmap).
- §6 space freed. Will be restructured around live experiment results: Kahle 100% recall (complete), Galesic Ge21-HSS (in progress), Le25-GLLM (pending).

**Yield threshold paper treatment decided:**
- One-sentence methods note only. No figure, no standalone claim.
- Wording: "We set yield threshold at 5%; any value above ~1% produces identical results for these survey types, as depth-2 screen yield (0.3–1.5%) falls below any practical threshold."
- Framing: yield threshold is a safety valve for niche topics, not a tuning knob.

**Wiki updated:** figure-roles.md (fig9a–d marked DROPPED with per-panel reasons; dependency chain cleaned; summary table updated), decisions.md (two new entries), INDEX.md (fig9a–d struck through, next priorities reordered), session-log.md (this entry).

### State at end of session

- fig9a–d: ❌ DROPPED
- §6: to be rebuilt from live experiment results
- Next blocking items: fig6 caption (non-monotonicity), Ge21-HSS and Le25-GLLM live runs

---

## 2026-04-10 — fig8 pareto10-40 fix; fig8b depth×pareto heatmap; wiki reorganisation

### What was done

**Fig 8 — Pareto sweep extended:**
- Re-ran script 03 with PARETO_PERCENTILES extended from [50,70,80,90] to [10,20,30,40,50,70,80,90,None].
- Confirmed result: at full BFS depth (depth 6, no yield stopping), ALL pareto values 10–90 achieve 100% recall across S1, S2, S3.
- Key corpus sizes (no yield stopping): S1 pareto10=96k / pareto80=441k / unfiltered=504k. S2 pareto10=96k / pareto80=495k / unfiltered=545k. S3 pareto10=149k / pareto80=428k / unfiltered=465k.
- Fig8 story: full-depth filter is "free" — the recall vs cost tradeoff only emerges under yield-based stopping.

**Fig 8b — Depth × Pareto heatmap (in progress):**
- Designed new script `03b_depth_pareto_grid.py`: loops over MAX_DEPTH in [1,2,3,4,5,6] × PARETO_PERCENTILES in [10,20,30,40,50,70,80,90,None], stores `traversal_results_depth_pareto_grid.json`.
- Script written; figure (`fig8b_depth_pareto_heatmap.png`) generated but not yet verified visually.
- Key finding from grid: pareto80 at depth 2 already recovers 85–98%; pareto10 at depth 2 drops to 31–53%. At depth 6 all settings reach 100%.
- Figure registered in FIGURE_INDEX.md and figure-roles.md.

**Figure fixes (previously completed, confirmed this session):**
- Fig 1: Barabási MLE fit (corrected form) + log-scale histogram. Status: ✅ needs re-run of scripts 02+06.
- Fig 2: Redesigned to compare backward-only / forward-only / bidirectional from same seeds. Status: ✅ needs re-run of scripts 02+06.
- Fig 7: In-degree boxplot replaced with log-log histogram. Status: ✅ needs re-run of script 06.

**Pareto threshold decision confirmed:**
- PARETO_P=80 is confirmed as the canonical operating point (not pareto50).
- Reason: under yield-based stopping (operational condition), pareto50 gives S1=80.4% vs pareto80=86.9%. The tighter filter reduces nodes explored per round under stopping, directly lowering recall.
- Fig3 (full-depth, no stopping) shows all thresholds reach 100% — this is a different operating condition. Paper must make the distinction explicit.
- See decisions.md PARETO_P section.

**Open questions resolved this session:**
- Q4 (why pareto80 not pareto50): RESOLVED. Added to decisions.md and open-questions.md RESOLVED section.
- Q6 (fig4 title): RESOLVED. Title now reads "seeded from top-5 gold references."
- Added new open questions: Q11 (citation needed locations), Q12 (move related work to §2), Q13 (conclusion k=1 result), Q14 (§4 text update for new fig2), Q15 (§5 yield-lines-overlap note).

**Wiki reorganisation (this wiki agent session):**
- INDEX.md: added Figures section with link to FIGURE_INDEX.md and list of current pub figures; added session-log.md pointer; updated one-line status; added "Next priorities" section; added key numbers table.
- figure-roles.md: added `**File:**` field to every figure entry with actual filename in `pub_figures/`; added fig8b entry; updated summary table to reflect current statuses (fig1/2/7 now ✅ Fixed, fig8 ✅ Done, fig8b ⏳ In progress).
- session-log.md: created (this file).

### State at end of session

- fig8: ✅ done
- fig8b: ⏳ in progress (figure generated, not yet verified; needs visual check next session)
- fig1, fig2, fig7: ✅ code fixes applied; need re-run of scripts 02+06 to regenerate PNGs
- fig3: ⚠️ annotation needs visual review (is it already updated or still says "optimal"?)
- fig4: ❌ seeding still wrong (oracle seeds); blocked on fig3 annotation decision
- fig5: ⚠️ clarity issue (not urgent)
- fig6: ⚠️ S1 non-monotonicity needs caption text
- fig9a–d: ❌ HOLD (blocked on fig3 + fig6 + hyperparameter decisions)
- Live: K17-RGC ✅ complete; Ge21-HSS 🔄 in progress; Le25-GLLM ⏳ seeds added

### What to do next session (in order)

1. Visually verify `fig8b_depth_pareto_heatmap.png` — check annotations, color scale, that survey panels are labeled.
2. Visually inspect `fig3_strategy_comparison.png` — check whether "operational default" annotation is in place or still says "optimal". Fix if needed.
3. Fix fig4 seeding: change from top-5 gold refs to cold-start seeds (or clearly label as oracle baseline). This is a script 03 or 06 change.
4. Add S1 non-monotonicity explanation to fig6 caption in script 06.
5. After fig3 + fig4 are settled: rerun fig9a–d sweep with confirmed hyperparameters.
6. Re-run scripts 02 + 06 to regenerate fig1, fig2, fig7 PNGs.
7. Continue Ge21-HSS live experiment.

---

## 2026-04-10 — Fig4/Fig5 redesigns; adaptive Pareto decision; parameter confirmation

### What was done

**Fig 4 redesigned (twice, final design confirmed):**
- Original plotted `screen_yield` (new_gold/new_nodes) — always <1%, never showed a collapse, was misleading.
- First redesign: side-by-side bars by depth — round 2 bars so small they looked like missing data.
- Final design: stacked bars. x-axis = BFS depth pass (Depth 1, Depth 2). Stack layers = Round 1 (solid) + Round 2 (lighter shade). Bars annotated with % of gold set.
- Key numbers: S1 R1/D2=417 (72%), R2/D2=24 (4%). S2 R1/D2=287 (66%), R2/D2=3 (1%). S3 R1/D2=209 (54%), R2/D2=8 (2%).
- Both stories now visible: (a) depth 2 does most of the work, (b) round 2 adds negligible yield.
- Status: ✅ FIXED.

**Fig 5 fixed:**
- y-axis was hardcoded 0.75–1.05, cutting off contaminated seed lines (S2 contaminated R1=0.27, S1 contaminated R1=0.44).
- Fixed to 0–1.08 so full range is visible.
- Label "Escape Hatch" renamed to "Discovery round" throughout. Seed labels simplified to "High-quality / Random / Noisy seeds".
- Key finding now visible: even 50% off-topic seeds recover to ≥90% recall by round 2.
- Status: ✅ FIXED.

**Adaptive Pareto calibration — decision:**
- Decision: do NOT run new experiments. Calibrate from existing `hyperparameter_sweep.csv` (1980 rows) using Gini coefficient of each survey's citation distribution.
- Adaptive rule can only relax the threshold (never tighten below 80), so worst case = slightly larger corpus on niche topics — not a recall hit.
- Will be mentioned as implementation detail in the paper, not a primary paper claim.

**Parameter decisions confirmed:**
- Canonical: depth=3, PARETO_P=80 (production adaptive, hardcoded 80 in paper), N_ROUNDS=2.
- N_ROUNDS=2 validated by fig4: round 2 adds only 1–4% of gold set across all three surveys.

**Open questions:**
- Added Q16: S1 non-monotonicity in fig6 — recall drops at some seed size k then recovers. Under investigation (graph structure effect vs seeding artifact).

### State at end of session

- fig4: ✅ stacked bar redesign complete
- fig5: ✅ y-axis and label fixes complete
- fig6: ⚠️ S1 non-monotonicity needs investigation (Q16) and caption update
- fig9a–d: ❌ HOLD — pending hyperparameter finalization and fig6 resolution
- Adaptive Pareto: decided (Gini from hyperparameter_sweep.csv); implementation pending
- Live: K17-RGC ✅ complete; Ge21-HSS 🔄 in progress; Le25-GLLM ⏳ seeds added

### What to do next session (in order)

1. Investigate S1 non-monotonicity in fig6 (Q16) — check contaminated strategy for same pattern; draft caption explanation.
2. Compute Gini coefficient per survey from `hyperparameter_sweep.csv`; map to adaptive Pareto threshold table.
3. Finalize hyperparameters → rerun fig9a–d.
4. Continue Ge21-HSS live experiment; start Le25-GLLM.

---

## Sessions prior to 2026-04-10

(Session log not maintained before this date. See decisions.md and open-questions.md RESOLVED section for accumulated state.)

