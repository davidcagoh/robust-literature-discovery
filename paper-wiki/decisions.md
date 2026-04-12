# Design Decisions

Choices that have already been made and why. Read this before changing any parameter.

---

## Wiki lives at `citation-networks/wiki/` (top-level), not inside lit-review
**Decision date:** 2026-04-12
**Why:** The wiki covers both citation-dynamics and robust-literature-discovery. Keeping it inside `lit-review/robust-literature-discovery/paper-wiki/` implies wrong ownership and buries shared decisions inside one sub-project. Top-level placement is neutral and discoverable. Version control is preserved by `git init`-ing at `citation-networks/` root; the nested lit-review `.git` is unaffected (git doesn't recurse into nested repos). The `~/.claude-shared/projects/` memory system handles Claude cross-session context; the wiki handles human-readable state.
**Implication:** Next session: move `paper-wiki/` → `citation-networks/wiki/`, init outer git, update any cross-references inside wiki files.

## Project Architecture (2026-04-12)

### `thesis/` renamed to `citation-dynamics/`; positioned as synthesis stage
**Decision date:** 2026-04-12
**Why:** The thesis project is formally titled *"Recognizing Signature Patterns and Phases of Time-Varying Networks"* — it is about characterizing temporal propagation dynamics (emergence, growth, persistence, decay, transition) in citation graphs, not just exploratory statistics. The name `citation-dynamics/` is accurate and discoverable. The pipeline is: citation-dynamics (understand structure) → robust-literature-discovery (discover papers) → synthesis (apply citation-dynamics methods to discovered paper sets to produce structured lit reviews). This positions the two projects as adjacent stages rather than independent workstreams.
**Implication:** The synthesis step — running Leiden community detection, temporal window slicing, and SG-t-SNE embedding on the *output* of a discovery run — is the planned next research contribution. All methods already exist in `citation-dynamics/`; they need to be applied to discovered sets rather than the full APS corpus.

### Canonical data lives in `citation-dynamics/data/processed/`; lit-review symlinks there
**Decision date:** 2026-04-12
**Why:** The APS .mat files (662 MB) were duplicated verbatim across both projects. Keeping one canonical copy in `citation-dynamics/` (the older project that originally compiled them) and symlinking from `data-aps/processed/` eliminates 662 MB of duplication without changing any script paths. The symlink is gitignored in the lit-review repo.
**Implication:** If the APS dataset is updated, update `citation-dynamics/data/processed/` only — the lit-review project will automatically see the change.

---

## Algorithm Parameters

### N_ROUNDS = 2 (not 4)
**Decision date:** ~2026-04-06. Reviewed 2026-04-10.
**Why:** N_ROUNDS_Extension.md shows round 1 does 85–98% of the work; round 2 adds modest insurance. The hyperparameter sweep (script 08, k_escape=5, yield=0.05, pareto80) shows:

| n_rounds | S1     | S2     | S3     |
|----------|--------|--------|--------|
| 1        | 84.9%  | 97.7%  | 94.3%  |
| 2        | 86.9%  | 98.1%  | 95.3%  |
| 3        | 89.3%  | 98.1%  | 95.6%  |

Round 3 adds 2.4pp for S1 but negligible for S2/S3. The "cheap insurance" story holds for n_rounds=2. Adding round 3 would improve S1 from ~87% to ~89% at modest additional cost (~6% more corpus). This is a marginal gain.

**Decision:** Keep n_rounds=2 as the canonical setting. S1's residual gap at 89% (cold_start 04b) is explained by structural miss analysis (§6), not insufficient rounds.

**Open question:** Should we add n_rounds=3 as an optional robustness sweep? This would not change the main result but would show S1 can reach ~90-92%.
**Implication:** Script 04b (k=1–5,10) is the canonical experiment, not script 04 (k=5/10/20/50).

### PARETO_P = 80 (suppress top 20% out-degree in forward traversal — simulation only)
**Decision date:** Set in original architecture. Confirmed 2026-04-10.
**Why:** The full hyperparameter sweep (script 08) shows that under yield stopping (the actual operating condition), Pareto threshold significantly affects recall:

| pareto_p | S1 r2  | S2 r2  | S3 r2  |
|----------|--------|--------|--------|
| 50       | 80.4%  | 93.5%  | 91.5%  |
| 70       | 86.6%  | 96.8%  | 94.6%  |
| 80       | 86.9%  | 98.1%  | 95.3%  |
| 90       | 89.0%  | 98.1%  | 96.4%  |
| 95       | 89.7%  | 98.6%  | 96.4%  |
| none     | 100%   | 100%   | 100%   |

(k_escape=5, yield=0.05, n_rounds=2)

Pareto-80 is the chosen operating point: meaningful corpus reduction vs pareto-none, while maintaining good recall. Pareto-50 is significantly worse for S1 (80.4% vs 86.9%). This is because with yield stopping, a tighter filter reduces the number of nodes explored per round, directly reducing recall.

**CRITICAL DISTINCTION:** At full depth without yield stopping (fig3), ALL pareto values reach 100% recall — the filter appears "free." This is because at depth 6, the graph is fully explored regardless. Under yield stopping (operational), the filter genuinely trades recall for corpus size. Fig3 and fig8/fig9b tell different stories and both are correct — they are showing different operating conditions. The paper must make this explicit.

**Implication:** The "Pareto-80 optimal" label in fig3 is correct but requires justification in the figure caption — it's optimal in the yield-stopped operational setting, not in the full-depth setting fig3 shows.

**IMPORTANT — what the filter actually does (SETTLED):**
- **APS simulation (scripts 03, 04b, 05, 08)**: filters FORWARD CANDIDATES (citers) by their own **out-degree** (number of papers they cite). High out-degree citer = survey-like behaviour → removed. This is the CORRECT semantics for the APS simulation and is finalized across all scripts.
- **Production (`traverse.py`)**: filters FRONTIER PAPERS by their **in-degree** (citation_count). Highly-cited frontier paper → skip forward traversal entirely for it.

These are not the same operation. The production filter matches the intuitive motivation ("don't explode through a paper cited by all of physics"). The simulation filter removes survey papers from the citer set — which is *approximately* the same effect but has a failure mode: a domain survey that cites 200 in-field papers would be *removed* by the simulation filter (high out-degree) but *allowed through* by the production filter (low citation_count if it's not widely cited).

The paper should describe the production semantics (in-degree of frontier paper) as the algorithm, and note that the APS simulation approximates it via out-degree of forward candidates. See simulation-vs-production.md for full discussion.

### YIELD_THRESHOLD = 0.05
**Decision date:** Set in original architecture.
**Why:** 5% new gold / new nodes means 95% of work is wasted. Practical stopping point.
**Implication:** The within-round stopping (yield < 5%) is separate from between-round stopping (fixed N_ROUNDS=2). Don't confuse them.

### K_ESCAPE = 20
**Decision date:** Set in original architecture.
**Why:** 20 new seeds per escape hatch round is enough to restart traversal in the missed region without exploding cost.

### SEED_SIZES = [1, 2, 3, 4, 5, 10]
**Decision date:** ~2026-04-06 (changed from [5, 10, 20, 50])
**Why:** User-facing realism. Most users provide 1–5 seeds. k=10 is the full-coverage anchor.

---

## Experiment Design

### Gold set = bibliography of the survey paper (not the survey paper itself)
**Why:** The survey DOI is the entry point, but the gold set is what the survey cites. These are different. The survey DOI is never in its own gold set.
**Implication:** tp_refs at depth 0 = 0 if seeding from survey DOI alone. The depth-0 bar in Fig 4 shows yield=1.0 because seeds are top-5 gold refs (not the survey DOI).

### Overlap metric (not "recall")
**Decision date:** ~2026-04-06
**Why:** "Recall" implies you know what you're looking for. "Overlap" (|visited ∩ gold| / |gold|) is the correct term for this setting.
**Status:** ⚠️ Scripts and figures still use "recall" everywhere. Paper text should use "overlap." Scripts can stay as-is.

### APS corpus only (no arXiv, no non-physics)
**Why:** APS provides a complete, closed citation graph. Non-APS papers would break the closed-world assumption needed for exact overlap measurement.
**Important:** 100% of gold refs for all three surveys ARE in the APS corpus. No corpus ceiling — all misses are algorithm failures.

---

## Paper Structure

### Related work moved to §2 (not §6)
**Why:** The argument depends on establishing what doesn't work before showing what does.

### Miss analysis placed BEFORE main results (§6 before §8)
**Why:** Primes the reader to understand the residual gap before seeing the 89–98% headline numbers. Avoids the impression that the miss is a disappointing surprise.

### APS validation reframed as §8, live experiments as §7
**Why:** APS is controlled benchmark (closed corpus, known gold). Live experiments (Kahle + Galesic) are the operational claim. Paper is primarily about a usable system, so live comes first.

---

## Fig9 dropped entirely (2026-04-10)
**Decision:** Remove fig9a–d from the paper. §6 space repurposed for live experiment results.
**Reasoning:**
- **fig9b (yield threshold sweep):** Vacuous. Depth-2 screen yield for these survey types is 0.3–1.5%, which falls below even the lowest tested yield threshold (1%). BFS stops at depth=2 regardless of threshold, so all sweep rows are identical. The overlap is a missing parameter region, not robustness evidence. One-sentence methods note is sufficient.
- **fig9a (Pareto×yield heatmap):** Covered by fig8c.
- **fig9c (recall vs N_rounds):** Covered by fig4 (stacked bar showing round contribution).
- **fig9d (corpus size heatmap):** Covered by fig8b (depth×pareto heatmap).

## Yield threshold = safety valve, not tuning knob (2026-04-10)
**Decision:** Yield threshold gets one sentence in methods, no standalone claim or figure.
**Wording:** "We set yield threshold at 5%; any value above ~1% produces identical results for these survey types, as depth-2 screen yield (0.3–1.5%) falls below any practical threshold."
**Rationale:** For niche/specialised topics with low screen yield, the threshold is effectively inactive — the BFS naturally terminates when the graph is exhausted. Framing it as a tunable robustness knob would be misleading given the empirical data.

## Naming

### LitDiscover (not "LitReview v2")
**Decision date:** ~2026-04-06
**Why:** "LitReview" sounds like the output (a review). "LitDiscover" is the process (discovery).
**Status:** ✅ Renamed throughout — pyproject.toml, CLI, and paper draft. Title: "Robust Literature Discovery from Minimal Seeds: Validating LitDiscover on APS Citation Benchmarks and Live Surveys".
