# Simulation vs Production

The APS simulation and the production LitDiscover system implement the same core idea
with different engineering constraints. Understanding the gap is important for scoping
the paper's claims correctly.

---

## They're doing the same thing

The APS simulation:
```
traverse (BFS, depth-by-depth) → check yield per depth → stop when yield < 5%
→ escape hatch (pick top-K graph-neighbours) → repeat N_ROUNDS times
```

Production:
```
traverse (one pass over all included papers) → screen candidates → check yield per cycle
→ escape hatch (Semantic Scholar keyword search) → repeat until stable
```

Same core logic: expand the graph, measure how fruitful the expansion is, stop when it isn't,
search for a new entry point, repeat. The production system just expresses this in an
event-driven, persistent, parallelised form because it needs to run on real APIs without
ground truth.

---

## Why the simulation is cleaner for research

The production system accumulated complexity to solve deployment problems:
- Supabase persistence → restartability across crashes
- Background threads → parallelise traversal and screening
- Event-driven triggers → handle variable API latency
- Adaptive Pareto filter → handle niche topics without graph density
- Criteria refinement → adapt to what the LLM is actually finding

None of these change the research question. They're engineering concerns.

The APS simulation strips them away and asks: **does the core algorithm work?**
That's the research contribution. The live experiments validate that the engineering
wrapper doesn't break it.

---

## Key differences (what the paper needs to acknowledge)

| Dimension | APS simulation | Production |
|---|---|---|
| Traversal unit | BFS depth-by-depth | One pass over full included set |
| Traversal trigger | Fixed N_ROUNDS | Event-driven (yield ≥ 5% or queue empty) |
| Escape Hatch | Top-K graph-neighbours by in-degree | LLM-generated query → Semantic Scholar search |
| **Pareto filter target** | **Forward candidates (citers), by OUT-DEGREE** | **Frontier papers, by IN-DEGREE (citation_count)** |
| Pareto filter calibration | Fixed percentile (parameter to sweep) | Adaptive (Gini-calibrated per round) |
| Yield measured | New gold refs / new nodes at each BFS depth | Included / screened per screening cycle |
| Ground truth | Known (gold bibliography) | None — yield is proxy |
| Stopping | Fixed N_ROUNDS | Escape hatch exhausted (max 3 attempts) |

---

## What this means for the paper

**Simulation claims (§8 APS Validation):**
The fixed-parameter algorithm achieves 89–98% recall on three benchmark surveys. This is
the core algorithmic claim. N_ROUNDS, Pareto threshold, and yield threshold are hyperparameters
whose effects are characterised in the sweep (Appendix).

**Live experiment claims (§7):**
The production system, which implements the same algorithm with adaptive Pareto and
event-driven triggers, achieves comparable recall on real discovery tasks (Kahle, Galesic).
This validates that the engineering wrapper doesn't break the algorithm.

**Limitations to state explicitly:**
1. The APS escape hatch is graph-expansion (graph-neighbours by in-degree), not semantic search.
   It works because APS misses happen to be graph-adjacent (BFS distance 1). Production's
   semantic search escape hatch is stronger — it can find papers with no graph path to the
   found set.
2. All APS hyperparameters are characterised on three surveys in one corpus. Generalisation
   to other corpora is validated by live experiments, not by the APS sweep.

---

## Pareto filter direction (SETTLED)

The filter direction in the APS simulation is finalized. Scripts 03, 05, 08 have been reverted to match script 04b: **out-degree filter on forward candidates**. This is consistent across all simulation scripts and is no longer an open question.

The simulation-production gap described below is a known, documented difference — not a bug. It is acknowledged in the paper.

---

### Pareto filter direction detail

The conceptual intent is identical — "don't explode the traversal through giant hubs" — but the proxy used is different.

**Production intent and implementation:**
A highly-cited frontier paper (e.g., a foundational QFT paper cited by 50k papers) has an enormous forward neighbourhood. Following all its citers would pull in unrelated fields. So: if a frontier paper's `citation_count > Pareto threshold`, skip forward traversal for that paper entirely. The filter is on the **frontier paper's in-degree**.

**APS simulation implementation:**
After collecting citers of the frontier set, the simulation removes citers whose own reference list exceeds the Pareto percentile. The filter is on the **citer's out-degree** — treating a high-out-degree citer as "survey-like" and therefore likely to have unfocused references.

**Where they diverge:**
Suppose a domain survey cites 400 physics papers relevant to our topic and has 30 citing papers (not widely cited itself). 
- **Production**: citation_count = 30 → well below any percentile threshold → forward traversal proceeds → domain survey's 400 references enter the corpus. ✓
- **Simulation**: the *citer* of this domain survey would pass the filter (it only cites a few things), but the *domain survey itself* would be removed from the forward candidate set if its out-degree is in the top 20% — removing a paper we actually want.

In practice the failure mode is rare (the problematic citer IS a specialist paper, not a survey), which is why the simulation's recall numbers hold up. But the paper should describe the **in-degree filter on frontier papers** as the correct semantics, and note that the simulation approximates it via out-degree of forward candidates.

---

## On the adaptive Pareto filter

The production system auto-calibrates the Pareto threshold based on the Gini coefficient
of the included set's citation counts:
- High Gini (power-law, large topic) → strict 80th percentile
- Low Gini (uniform, small niche) → relaxed 90th–95th percentile

**Script 08 hyperparameter sweep is complete** (1980 rows across S1/S2/S3). The sweep covers PARETO_P × YIELD_THRESHOLD × N_ROUNDS × K_ESCAPE with k=5 top-k seeds. Whether this motivates adaptive calibration can now be read directly from the sweep results. If all three surveys share the same optimal threshold, adaptive adds no value.
