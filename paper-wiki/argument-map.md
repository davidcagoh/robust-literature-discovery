# Argument Map

How the paper's sections form a logical chain. Each row is a step in the argument.
The right column shows what would break if this step were missing.

---

## §1 Introduction
**Claim:** Comprehensive literature discovery is expensive and current tools are incomplete.
**Evidence:** Prose, cited prior work.
**Without this:** Reader has no reason to care.

---

## §2 Related Work
**Claim:** Existing approaches (keyword search, forward citation chasing, backward reference chasing) each fail in isolation. Systematic review tools are manual-heavy.
**Evidence:** Citations to existing tools.
**Without this:** Paper looks like it ignores prior art.
**Note:** Moved up front (was §6 in Manus AI draft). This is correct — the argument depends on knowing what's already been tried.

---

## §3 Architecture
**Claim:** LitDiscover implements a specific state machine: SEED → SEARCH → SCREEN → TRAVERSE → ESCAPE HATCH → STABLE.
**Evidence:** System diagram, pseudocode, parameter table.
**Without this:** Figs 3–8 are uninterpretable because the reader doesn't know what the system actually does.

---

## §4 Benchmark Design
**Claim:** Three APS review papers with known bibliographies form a closed-corpus ground truth for recall measurement.
**Evidence:** Table of surveys (S1, S2, S3), APS corpus statistics, definition of "overlap" metric.
**Without this:** Results look circular (how do we know what we're trying to find?).
**Note:** 100% of gold refs from all three surveys are in the APS corpus (confirmed empirically). No corpus-coverage ceiling — all misses are algorithm failures.

---

## §5 Structural Motivation
**Claim:** The citation graph's structure explains why the algorithm works.
**Three sub-claims:**

| Sub-claim | Figure | What it shows |
|---|---|---|
| Citations are power-law skewed | Fig 1 | γ ≈ 1.85 in-degree; Gini = 0.69 → top 20% papers hold most citations |
| Starting near the core, BFS reaches everything in 2 hops | Fig 2 | Oracle-seeded BFS overlap vs depth (MUST label as oracle/upper bound) |
| Bidir+Pareto dominates other strategies on cost–recall | Fig 3 | Strategy scatter at depth 3 |
| Yield collapses rapidly → stopping is principled | Fig 4 | Screen yield per depth (fix: seeds are top-k gold refs, not survey DOI) |

**Without this section:** Algorithm looks arbitrary. The structural argument is what makes it convincing.

---

## §6 Miss Analysis + Efficiency
**Claim:** What the algorithm misses is not random — it is structurally peripheral. The Pareto filter dramatically cuts cost at no recall penalty.
**Evidence:**
- Fig 7: missed papers have low in-degree (median 9–29 vs 220 for recovered); 90%+ are at BFS distance 1 (adjacent but filtered)
- Fig 8: Pareto threshold sweep shows all thresholds achieve 100% recall at depth 3; cost drops 20–30% with Pareto-80 vs no filter

**Placed BEFORE main results** (per Issue 10 from original feedback) — this primes the reader to understand the residual gap before seeing the recall numbers.

**Open question:** Why Pareto-80 and not Pareto-50? Fig 8 shows both achieve 100% recall at depth 3. Need to show that Pareto-50 fails earlier (at shallower depth or under yield-stopping) or acknowledge the choice is conservative.

---

## §7 Main Results: Live Discovery (PARTIALLY COMPLETE ⚠️)
**Claim:** LitDiscover achieves high recall on real discovery tasks outside the training distribution (i.e., not APS benchmark surveys chosen post-hoc).
**Evidence:** K17-RGC (done), Ge21-HSS (in progress), Le25-GLLM (seeds added).
**Without this:** The paper is purely a closed-corpus study. It validates the algorithm in a setting where the ground truth is known in advance. Live experiments are what make the paper about a usable system.

**Status:**

| Survey | ID | Gold papers | Result |
|---|---|---|---|
| Bobrowski & Kahle 2017 (random geometric complexes) | K17-RGC | 56 | ✅ **100% recall (56/56)**, depth 2, round 1. 1 seed. Corpus 31,168. |
| Galesic et al. 2021 (human social sensing) | Ge21-HSS | 202 | 🔄 In progress |
| Le et al. 2025 (grounded LLMs) | Le25-GLLM | TBD | ⏳ Seeds added, not yet run |

K17-RGC is a strong result: 100% recall from a single seed paper, stopping at depth 2 with corpus yield = 0.16%. This validates yield-stopping fires correctly in the real system.

---

## §8 APS Closed-Corpus Validation
**Claim:** LitDiscover achieves 89–98% recall across three APS benchmark surveys using k=5 seeds and 2 rounds.
**Evidence:**
- Fig 5: Per-round recall for k=5 seeds (top-5, random, contaminated)
- Fig 6: Final recall vs seed size k=1–10

**Key numbers:**
| Survey | Recall (k=5, 2 rounds) | Gold set |
|---|---|---|
| S1 MIT 1998 | 89.2% (519/582) | 582 refs |
| S2 UCG 2008 | 98.4% (425/432) | 432 refs |
| S3 TOPO 2019 | 96.9% (375/387) | 387 refs |

**Narrative tension:** S1 underperforms vs S2/S3. The explanation is age (1998 survey — the most cited papers have very high in-degree and concentrate in a small part of the graph; random seeds sometimes outperform top-k by citation count because top-k is too concentrated). This tension is real and should be discussed, not hidden.

---

## §9 Conclusion
**Claim:** Minimal-seed literature discovery via graph traversal is practical and achieves near-complete recall. The residual gap is structural and interpretable.
**Note:** Rewrite from scratch. Manus AI draft conclusion is scaffolded.
