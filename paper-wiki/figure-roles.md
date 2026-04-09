# Figure Roles

Per-figure: what argumentative step it carries, what's broken, and priority.

---

## Fig 1 — Degree distributions + Lorenz curves
**Proves:** Citation graphs are power-law skewed → top 20% papers hold most citations → Pareto filter is structurally justified.
**Used in:** §5 Structural Motivation
**Status:** ✅ Mostly correct.
**Issues:**
- γ ≈ 1.85/1.90 (both < 2) is unusual for citation networks. Needs acknowledgment + KS goodness-of-fit test.
- x_min = 5 is hardcoded, not estimated via Clauset method. May misstate γ.
- Out-degree power-law claim is weaker (references are bounded in practice). Consider softening.
**Priority:** Low — acknowledging in text is sufficient.

---

## Fig 2 — BFS reachability vs depth (oracle seeds)
**Proves:** Starting near the core, BFS reaches everything in ≤2 hops → graph is dense enough for traversal to work.
**Used in:** §5 Structural Motivation
**Status:** ⚠️ Valid but dangerously easy to misread.
**Issues:**
- Seeds are top-k papers from the gold bibliography (oracle). This is NOT what a real user does. Readers will confuse this with the cold-start experiment.
- MUST add a callout: "Seeds are oracle top-k gold refs — this shows structural reachability, not system performance."
- Could be cut to appendix and replaced with one paragraph in text.
**Priority:** Medium — fix framing before submission.

---

## Fig 3 — Strategy comparison (bidir vs alternatives)
**Proves:** Bidirectional traversal + Pareto filter achieves best recall/cost tradeoff at depth 3 vs backward-only, forward-only, and unfiltered bidir.
**Used in:** §5 Structural Motivation
**Status:** ✅ Mostly correct.
**Issues:**
- "Pareto-80 (optimal)" annotation needs justification — Pareto-50 achieves same recall at lower corpus size on this plot.
- Points are very clustered near recall=1.0; hard to distinguish visually.
**Priority:** Medium — fix annotation or justify choice in text.

---

## Fig 4 — Screen yield collapse
**Proves:** Yield drops rapidly with BFS depth → yield threshold is a principled stopping rule, not arbitrary.
**Used in:** §5 Structural Motivation
**Status:** ✅ Title fixed. Depth-0 annotation still recommended.
**Issues:**
- ~~Title says "seeded from survey paper"~~ → Fixed: title now says "seeded from top-5 gold references".
- Depth-0 bar at yield=1.0 is still potentially confusing: it shows seed quality, not traversal behaviour. Consider adding annotation: "depth 0 = seeds (all gold refs by construction)."
**Priority:** Low — title fix done; annotation is optional polish.

---

## Fig 5 — Cold-start recall per round (k=5)
**Proves:** Starting from k=5 seeds (best-case, average-case, noisy), 2 rounds of the Escape Hatch loop converges to near-complete recall across all three surveys.
**Used in:** §8 APS Closed-Corpus Validation (main result)
**Status:** ⚠️ Correct but needs framing fixes.
**Issues:**
- For S1, random seeds outperform top-5 by citation count at round 1 (~0.90 vs ~0.85). Counterintuitive — explain in text: top-5 most-cited gold refs are over-concentrated in one part of S1's subfield.
- Y-axis starts at 0.75, visually inflating differences. Consider starting at 0 or adding note.
- Single draw for random/contaminated — no error bars. Add disclaimer or run multiple trials.
**Priority:** Medium.

---

## Fig 6 — Final recall vs seed size (k=1–10)
**Proves:** Recall is robust across seed sizes k=1 to 10; top-k seeding is monotone; typical user (k=1–5) achieves good results.
**Used in:** §8 APS Closed-Corpus Validation
**Status:** ❌ Non-monotonicity looks like a bug.
**Issues:**
- Random and contaminated recall zigzags as k increases (e.g., recall drops from k=3 to k=4 in S3). This is real behaviour caused by yield-stopping interacting with contaminated seeds: more irrelevant seeds → lower yield → earlier stop → lower recall. This is a genuine finding about the system's failure mode, not a bug, but it looks like a bug as presented.
- Must explain in text or move contaminated condition to appendix with a note.
- Top-k line is monotone and makes the correct point on its own.
**Priority:** High — a reviewer WILL ask about this.

---

## Fig 7 — Miss analysis (in-degree + BFS distance)
**Proves:** Missed papers are not randomly distributed — they are structurally peripheral (low in-degree, adjacent to core but not visited).
**Used in:** §6 Miss Analysis (placed BEFORE §8 to prime reader)
**Status:** ⚠️ Correct but has a seed mismatch to verify.
**Issues:**
- Script 05 uses k=20 as the canonical case; paper reports k=5 results. If k=20 and k=5 give different missed sets, the figure is showing the wrong scenario. Verify that both give 519/582 for S1.
- 90%+ of misses are at BFS distance 1 (adjacent, not isolated). This means they were REACHABLE but excluded. The mechanism (Pareto filter vs yield stopping) is not identified in the figure. Add analysis: are distance-1 misses forward neighbors (Pareto-filtered) or backward neighbors?
- The in-degree comparison shows missed papers have lower in-degree, but in-degree is not what the Pareto filter acts on (it acts on out-degree of forward candidates). Add out-degree comparison for missed papers.
**Priority:** High.

---

## Fig 8 — Efficiency frontier (Pareto threshold sweep)
**Proves:** Tighter Pareto filters reduce corpus size 20–30% with no recall cost at depth 3.
**Used in:** §6 Miss Analysis + Efficiency
**Status:** ⚠️ Correct but Pareto-80 choice is unjustified.
**Issues:**
- All Pareto thresholds (50, 60, 70, 80, 90, none) achieve recall=1.0 at depth 3. Pareto-50 is cheapest. Why use Pareto-80?
- The answer is likely: "Pareto-50 may fail at shallower depth or under yield-stopping." This needs to be demonstrated, not assumed.
- Title says "All strategies achieve 100% recall — the filter only reduces cost." This is true at depth 3 but may not hold under yield-based stopping (the actual operating condition). Add caveat.
**Priority:** Medium — needs one clarifying sentence in the paper.
