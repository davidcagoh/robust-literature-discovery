# Figure Roles

Per-figure: what argumentative step it carries, what's broken, priority, and dependency status.
Each entry includes the actual filename in `pub_figures/` so this file is self-sufficient.

**Last updated:** 2026-04-10 (full audit from visual review; filenames added)

---

## Dependency chain — read before touching anything

The figures have a logical ordering. Changing upstream defaults breaks downstream figures:

```
fig3 (pareto threshold) ──► fig4 (uses pareto default)
                         ──► fig8 (pareto sweep — need lower range)

fig6 (k analysis)        ──► fig5 (uses k=5)
```

Note: fig9a–d are DROPPED (2026-04-10) — dependency chain entries for them removed.

**Priority order (as of 2026-04-10 session 4):**
1. Review fig3 — confirm "operational default" annotation is correctly worded
2. Review fig4 — yield collapse story with cold-start seeding
3. Review fig5 — cold-start recall per round
4. ~~Add S1 non-monotonicity explanation to fig6 caption~~ ✅ DONE
5. Generate fig8b depth×pareto heatmap (new script 03b — in progress)
6. §6 — restructure around live experiment results (Kahle done, Galesic/Le25 pending)

---

## Fig 1 — Degree distributions + Lorenz curves
**File:** `pub_figures/fig1_degree_distributions.png`

**Proves:** Citation graphs are heavy-tailed → top 20% papers hold most citations → Pareto filter is structurally justified.
**Used in:** §4 Structural Motivation
**Status:** ✅ FIXED — Barabási MLE fit applied, log-scale histogram in place. Re-run script 02 then 06 to regenerate.

**What was fixed:** Script 02 previously fit a pure `k^(−γ)` straight line on log-log. Now uses Barabási (2016) corrected form `p_k ~ (k + k_sat)^(−γ) · exp(−k / k_cut)` fitted via MLE. Corrected model gives γ ≈ 3.03, p-value = 0.69. Figure switched to log-scale histogram.

**Priority:** Done ✅

---

## Fig 2 — BFS reachability vs depth
**File:** `pub_figures/fig2_bfs_reachability.png`

**Proves:** Bidirectional traversal is necessary — backward-only misses recent work, forward-only misses foundational work.
**Used in:** §4 Structural Motivation
**Status:** ✅ FIXED — bidirectional direction comparison implemented. Re-run script 02 then 06 to regenerate.

**What was fixed:** Script 02 previously only ran bidirectional BFS, duplicating the fig6 seed-size story. Now compares backward-only, forward-only, and bidirectional from the same fixed seeds (k=5 top-k gold refs). Y-axis: overlap vs BFS depth.

**Note:** §4 paper text also needs updating to match new fig2 directionality story (see open-questions.md Q14).

**Priority:** Done ✅

---

## Fig 3 — Strategy comparison (bidirectional vs alternatives)
**File:** `pub_figures/fig3_strategy_comparison.png`

**Proves:** Pareto filter reduces screening cost with no recall penalty at the correct depth.
**Used in:** §5 Structural Motivation
**Status:** ✅ FIXED — annotation reads "Pareto-80 (operational default; see §6 for yield-stopped cold-start results)". Cross-reference updated from §5 → §6 (2026-04-11).

**Priority:** Done ✅

---

## Fig 4 — Screen yield collapse
**File:** `pub_figures/fig4_screen_yield_collapse.png`

**Proves:** Depth 2 does most of the discovery work (72%/66%/54% of gold set for S1/S2/S3); round 2 adds negligible yield (1–4%). Stacked bars make both stories visible simultaneously.
**Used in:** §4 Structural Motivation
**Status:** ✅ FIXED — redesigned as stacked bar chart (x-axis = BFS depth pass, stack layers = Round 1 (solid) + Round 2 (lighter), annotated % of gold set per portion).

**Design:** x-axis = Depth 1 / Depth 2 BFS passes. Each bar stacks Round 1 contribution (solid) on top of Round 2 contribution (lighter shade). Bars annotated with % of gold set.

**Key numbers:**
- S1: R1/D2 = 417 (72%), R2/D2 = 24 (4%)
- S2: R1/D2 = 287 (66%), R2/D2 = 3 (1%)
- S3: R1/D2 = 209 (54%), R2/D2 = 8 (2%)

**History:** Original plotted `screen_yield` (new_gold/new_nodes) — always <1%, never showed a collapse, was misleading. First redesign used side-by-side bars by depth — round 2 bars so small they looked like missing data. Current stacked design is the final version.

**Priority:** Done ✅

---

## Fig 5 — Cold-start recall per round (k=5)
**File:** `pub_figures/fig5_cold_start_recall_per_round.png`

**Proves:** Even 50% off-topic (contaminated) seeds recover to ≥90% recall by round 2. Two Discovery rounds are sufficient for all seed types.
**Used in:** §5 Main Results
**Status:** ✅ FIXED — y-axis corrected to 0–1.08 (was hardcoded 0.75–1.05, cutting off contaminated seed lines). Label "Escape Hatch" renamed to "Discovery round" throughout. Seed labels simplified to "High-quality / Random / Noisy seeds".

**Key numbers visible after fix:**
- S2 contaminated R1 = 0.27, S1 contaminated R1 = 0.44 — both previously cut off
- All seed types converge to ≥90% by round 2

**Priority:** Done ✅

---

## Fig 6 — Final recall vs seed size (k=1–10)
**File:** `pub_figures/fig6_recall_vs_seed_size.png`

**Proves:** Recall is robust across seed sizes; system works from k=1 upward.
**Used in:** §5 Main Results
**Status:** ✅ Fixed — y-axis 0–100%, non-monotonicity subtitle (2 sentences), labels plain. Fig6 PNG regenerated.

**Caption (2-sentence subtitle added):** Top-k recall dips at k=2 because nearest-neighbor seeds share backward neighborhoods; contaminated recall declines with k because each off-topic seed opens a new traversal frontier. Both effects resolve by round 2.

**See also:** Q16 in open-questions.md (RESOLVED). §5 non-monotonicity paragraph added to paper text.

**Priority:** Done ✅

---

## Fig 7 — Miss analysis (in-degree + BFS distance)
**File:** `pub_figures/fig7_miss_analysis.png`

**Proves:** Missed papers are structurally peripheral — low in-degree, adjacent to but not visited from the recovered set.
**Used in:** §6 Miss Analysis
**Status:** ✅ FIXED — switched to log-log histogram. Re-run script 06 to regenerate.

**What was fixed:** In-degree distribution changed from boxplot to log-scale histogram to correctly represent the heavy-tailed signal.

**Notes (still valid):**
- Year/journal breakdown was computed but not shown in pub figure. Fine if paper text doesn't reference them.
- BFS distance from recovered set (97% at distance 1) is a strong finding — paper text should explicitly call this out.

**Priority:** Done ✅

---

## Fig 8 — Efficiency frontier (Pareto threshold sweep)
**File:** `pub_figures/fig8_efficiency_frontier.png`
**Status:** ❌ DROPPED (2026-04-11)
**Reason:** At full depth all Pareto values reach 100% recall — the figure only shows corpus-size variation, which is not the operational regime. Creates a misleading "Pareto-10 looks equally good" impression. fig3 already covers the strategy comparison; the trade-off claim in §7 is now stated in prose.

---

## Fig 8b — Depth × Pareto grid heatmap
**File:** `pub_figures/fig8b_depth_pareto_heatmap.png`
**Status:** ❌ DROPPED (2026-04-11)
**Reason:** Key number (Pareto-80 at depth 2 = 85–98%) is already the main result stated in §6. Heatmap adds granularity without adding to the core argument. Story is complete without it.

---

## Fig 8c — Efficiency frontier (corpus cost contour)
**File:** `pub_figures/fig8c_efficiency_frontier.png`
**Status:** ❌ DROPPED (2026-04-11)
**Reason:** Most complex of the fig8 family. Covered by dropped fig8/fig8b decision; §7 trade-off claim now in prose.

---

## Fig 9a — Pareto × Yield threshold heatmap (recall)
**File:** `pub_figures/fig9a_pareto_yield_heatmap.png`

**Status:** ❌ DROPPED (2026-04-10)
**Reason:** Covered by fig8c (pareto×yield heatmap already present there). The §6 space freed by dropping fig9 will be used for live experiment results.

---

## Fig 9b — Recall vs Pareto threshold (per survey, per yield)
**File:** `pub_figures/fig9b_recall_vs_pareto.png`

**Status:** ❌ DROPPED (2026-04-10)
**Reason:** Vacuous sweep. Depth-2 screen yield (0.3–1.5%) falls below even the lowest tested yield threshold (1%), so BFS stops at depth=2 regardless of threshold setting. All sweep rows are identical — the overlap is not robustness evidence, it is a missing parameter region. Described in one sentence in methods: "We set yield threshold at 5%; any value above ~1% produces identical results for these survey types, as depth-2 screen yield (0.3–1.5%) falls below any practical threshold."

---

## Fig 9c — Recall vs N_rounds (per survey)
**File:** `pub_figures/fig9c_recall_vs_nrounds.png`

**Status:** ❌ DROPPED (2026-04-10)
**Reason:** Covered by fig4 (screen yield collapse / round contribution stacked bar). The round-saturation story is fully captured there.

---

## Fig 9d — Corpus size heatmap (Pareto × Yield)
**File:** `pub_figures/fig9d_corpus_size_heatmap.png`

**Status:** ❌ DROPPED (2026-04-10)
**Reason:** Covered by fig8b (depth×pareto heatmap). The corpus-size dimension of the tradeoff is shown there without requiring the vacuous yield-threshold axis.

---

## Summary table

| Fig | File | Status | Blocked by | Priority |
|-----|------|--------|-----------|----------|
| fig1 | `fig1_degree_distributions.png` | ✅ Fixed (needs re-run) | — | Done |
| fig2 | `fig2_bfs_reachability.png` | ✅ Fixed (needs re-run) | — | Done |
| fig3 | `fig3_strategy_comparison.png` | ⚠️ annotation needs review | — | **Review now** |
| fig4 | `fig4_screen_yield_collapse.png` | ✅ Fixed (stacked bar redesign) | — | Done |
| fig5 | `fig5_cold_start_recall_per_round.png` | ✅ Fixed (y-axis, labels) | — | Done |
| fig6 | `fig6_recall_vs_seed_size.png` | ✅ Fixed (caption updated, PNG regenerated) | — | Done |
| fig7 | `fig7_miss_analysis.png` | ✅ Fixed (needs re-run) | — | Done |
| fig8 | `fig8_efficiency_frontier.png` | ✅ Done (pareto10–90) | — | Done |
| fig8b | `fig8b_depth_pareto_heatmap.png` | ⏳ In progress | — | **Next session** |
| fig9a | `fig9a_pareto_yield_heatmap.png` | ❌ DROPPED | covered by fig8c | — |
| fig9b | `fig9b_recall_vs_pareto.png` | ❌ DROPPED | vacuous sweep (yield below any threshold) | — |
| fig9c | `fig9c_recall_vs_nrounds.png` | ❌ DROPPED | covered by fig4 | — |
| fig9d | `fig9d_corpus_size_heatmap.png` | ❌ DROPPED | covered by fig8b | — |
