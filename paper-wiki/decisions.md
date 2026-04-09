# Design Decisions

Choices that have already been made and why. Read this before changing any parameter.

---

## Algorithm Parameters

### N_ROUNDS = 2 (not 4)
**Decision date:** ~2026-04-06
**Why:** N_ROUNDS_Extension.md shows round 1 does 85–98% of the work; round 2 adds 1–7pp depending on survey age. Rounds 3–4 add <0.5pp. Two rounds is the honest stopping point and makes the "cheap insurance" narrative credible.
**Implication:** Script 04b (k=1–5,10) is the canonical experiment, not script 04 (k=5/10/20/50).

### PARETO_P = 80 (suppress top 20% out-degree in forward traversal — simulation only)
**Decision date:** Set in original architecture.
**Why:** Empirically chosen. Conservative — preserves most forward candidates while cutting the biggest hubs. Script 08 hyperparameter sweep (1980 rows, completed) provides post-hoc justification.
**Implication:** This choice is asserted, not derived. The sweep covers the full grid and confirms Pareto-80 is a safe default.

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

## Naming

### LitDiscover (not "LitReview v2")
**Decision date:** ~2026-04-06
**Why:** "LitReview" sounds like the output (a review). "LitDiscover" is the process (discovery).
**Status:** ✅ Renamed throughout — pyproject.toml, CLI, and paper draft. Title: "Robust Literature Discovery from Minimal Seeds: Validating LitDiscover on APS Citation Benchmarks and Live Surveys".
