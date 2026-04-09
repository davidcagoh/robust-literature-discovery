# Open Questions

Unresolved issues that block or weaken the paper. Ordered by importance.

---

## RESOLVED

### ~~MAX_DEPTH vs N_ROUNDS — are they redundant?~~
**Resolved:** Different granularities. MAX_DEPTH caps depth within one traversal call (safety valve, rarely binds). N_ROUNDS caps how many traversal-then-escape-hatch cycles run. N_ROUNDS is the operative parameter. In production there is no N_ROUNDS — the loop runs until the escape hatch mechanism is exhausted.

### ~~Is the APS simulation a valid proxy for production?~~
**Resolved:** Yes, as a conservative lower bound. Both systems implement the same core idea (expand graph, measure yield, stop when low, search for re-entry). The simulation uses weaker escape hatches (graph-only) and a fixed Pareto filter. Production is more powerful on both counts. So APS recall numbers are a floor. See simulation-vs-production.md.

### ~~Should we implement adaptive Pareto filter in the simulation?~~
**Resolved:** Not yet. Run the fixed-filter sweep first. If different surveys have different optimal thresholds, adaptive is motivated. If not, it adds complexity for nothing.

### ~~Filter direction in APS simulation — in-degree or out-degree?~~
**Resolved:** **Out-degree filter on forward candidates** is the correct semantics for the APS simulation. Scripts 03, 05, 08 have been reverted to match 04b. This is finalized. The production system (`traverse.py`) uses in-degree of frontier papers — a separate, documented implementation choice. See simulation-vs-production.md.

### ~~Script 08 hyperparameter sweep — has it been run?~~
**Resolved:** Complete. 1980 rows in `hyperparameter_sweep.csv`. Used out-degree filter (consistent with other scripts).

### ~~Fig 4 title — is it "seeded from survey paper" or "seeded from top-5 gold references"?~~
**Resolved:** Fixed. Title now says "seeded from top-5 gold references". See figure-roles.md.

---

## BLOCKERS

### Q1: Complete live experiments before submission
**Why it matters:** §7 (Main Results: Live Discovery) requires at least two live results. The paper's argument has live experiments as its centrepiece.

**Current status:**

| Survey | ID | Gold papers | Status | Result |
|---|---|---|---|---|
| Bobrowski & Kahle 2017 (random geometric complexes) | K17-RGC | 56 | ✅ Complete | **100% recall (56/56), depth 2, round 1**. Corpus 31,168. Yield at depth 2 = 0.16% (well below 5% threshold). 1 seed paper ("Topology Applied to Machine Learning"). |
| Galesic et al. 2021 (human social sensing) | Ge21-HSS | 202 | 🔄 In progress | Not yet complete. |
| Le et al. 2025 (grounded LLMs) | Le25-GLLM | TBD | ⏳ Seeds added, not yet run | — |

**K17-RGC note:** 100% recall from 1 seed stopping at depth 2 is a strong result and validates the system on a real user task. Corpus yield dropping to 0.16% confirms that the yield-stopping rule fires correctly.

**What's needed to unblock:** Complete Ge21-HSS run. Le25-GLLM is a bonus third experiment.
**Config files:** `projects/kahle-simplicial-geometry/project.toml`, `projects/galesic-human-social-sensing/project.toml`

---

## ANALYSIS GAPS

### Q2: Does Fig 7 miss analysis use k=5 or k=20 seeds?
**Why it matters:** Script 05 says "canonical case = k=20"; paper reports k=5 results. If the missed sets differ, Fig 7 is showing the wrong scenario.
**How to resolve:** Check whether `cold_start_results_lowseed.json` at k=5 gives 519/582 for S1, same as k=20 run. If different, rerun script 05 with k=5.

### Q3: Why does Fig 6 show non-monotone recall for contaminated seeds?
**Why it matters:** Recall drops at k=4 in some surveys. Reviewers will flag this as a bug.
**Probable answer:** Contaminated seeds (50% irrelevant) reduce yield faster → yield-stopping triggers earlier → less traversal → lower recall. More contaminated seeds = worse stopping.
**How to resolve:** Add one paragraph explaining this in §8. Optionally move contaminated condition to appendix.

### Q4: Why use Pareto-80 and not Pareto-50?
**Why it matters:** Fig 8 shows Pareto-50 achieves identical recall at depth 3 with lower cost. The choice of 80th percentile looks arbitrary.
**Probable answer:** Pareto-50 is more aggressive and may fail under yield-based stopping (the actual operating condition). Need to test this.
**How to resolve:** Either demonstrate that Pareto-50 fails under stopping, or acknowledge Pareto-80 is a conservative default and note Pareto-50 could work.

### Q5: For S1, why do random seeds outperform top-5-by-citation at round 1?
**Why it matters:** Top-5 is labelled "best-case" — it should not lose to random.
**Probable answer:** The 5 most-cited gold refs in S1 (a 1998 metal-insulator survey) all cluster in one corner of the graph; 5 random draws cover more diversity by chance. This is a single draw, so it may also be sampling noise.
**How to resolve:** Run multiple trials (≥5) for random seeds and report mean ± std. If mean of random < top-5, the issue goes away. If not, discuss concentration problem in text.

---

## FIGURE FIXES (not blockers but needed before submission)

### Q6: Fix Fig 4 title and depth-0 bar annotation
Seeds in Fig 4 are top-5 gold refs (not "survey paper" as stated). Depth-0 bar = seed quality, not traversal behaviour. See figure-roles.md.

### Q7: Add out-degree comparison to Fig 7
In-degree of missed papers is shown, but the Pareto filter acts on out-degree of forward candidates. Adding out-degree completes the causal chain.

### Q8: Add oracle callout to Fig 2
Seeds are top-k gold refs — this is not the cold-start scenario. Must be labelled to avoid reader confusion.

---

## LOW PRIORITY

### Q9: Should γ < 2 be flagged in Fig 1?
Both in-degree and out-degree exponents are < 2 (γ ≈ 1.85/1.90). This is unusual. A KS goodness-of-fit test would either support or qualify the power-law claim. Adding a sentence in §5 is sufficient.

### Q10: Add error bars to Figs 5–6
Random and contaminated seed conditions show results from a single draw. Multiple trials would replace the erratic zigzag with a mean + confidence interval. Improves robustness but not strictly required for the paper's argument.
