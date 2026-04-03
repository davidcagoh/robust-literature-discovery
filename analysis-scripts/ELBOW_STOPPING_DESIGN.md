# Elbow Detection / Early Stopping for the Escape Hatch Loop

**Status:** Design + implementation ready. Requires `cold_start_results.json` to execute.

---

## 1. What the Current Code Does

The cold-start experiment (`04_cold_start_simulation.py`) runs the Escape Hatch loop for a **fixed `N_ROUNDS = 4`** — a blank cheque. Each round consists of:

1. A full bidirectional Pareto-80 BFS traversal from the current seed set, halted by the **within-round** yield threshold (`screen_yield < 0.05`).
2. An escape step that picks the top-20 unvisited neighbours of the recovered gold set as seeds for the next round.

The loop only exits early in two degenerate cases: perfect recall (`recall >= 1.0`) or no escape candidates remain. In practice neither fires before round 4.

The per-round statistics that are already saved to `cold_start_results.json` are:

| Field | Description |
|---|---|
| `round` | Round number (1-indexed) |
| `recall` | Cumulative recall of gold set |
| `tp` | True positives (gold papers found) |
| `new_nodes` | Papers added this round |
| `new_gold` | New gold papers found this round |
| `stop_depth` | BFS depth at which within-round yield fired |
| `curve` | Per-depth stats for this round |

**All the information needed for an elbow criterion is already being recorded.** No re-computation of the graph traversal is required.

---

## 2. Why an Elbow Exists

The whitepaper's own narrative (Section 4.1) describes the pattern:

> "While a single round of traversal typically stalls at 80–90% recall, subsequent Escape Hatch rounds push coverage toward 100%."

This implies a classic diminishing-returns curve. Round 1 does the heavy lifting; each subsequent round recovers a shrinking fraction of the remaining gap. The per-round `new_gold` sequence is monotonically decreasing in expectation, making it a natural signal for an elbow.

---

## 3. Three Candidate Stopping Criteria

All three operate on the **between-round** signal (not the within-round yield, which already governs BFS depth). They are evaluated after each round completes and before the next escape step is triggered.

### Criterion A — Marginal Recall Gain < δ

Stop after round *r* if:

```
recall[r] - recall[r-1] < δ
```

Recommended default: **δ = 0.01** (1 percentage point). This is the most interpretable criterion for a practitioner: "stop when a full round of traversal adds less than 1% more coverage."

### Criterion B — Absolute New Gold Papers < τ

Stop after round *r* if:

```
new_gold[r] < τ
```

Recommended default: **τ = 5**. This is corpus-size-independent and directly measures whether the escape hatch is still finding anything meaningful. For a gold set of ~400 papers, `τ = 5` corresponds to roughly 1.25% marginal recall.

### Criterion C — Round-Level Screen Yield < ε

Stop after round *r* if:

```
new_gold[r] / new_nodes[r] < ε
```

Recommended default: **ε = 0.01** (1%). This mirrors the existing within-round yield threshold (0.05) but applied at the coarser round level. It answers: "of all the papers we screened this round, less than 1% were relevant — is it worth another round?"

---

## 4. Where to Add the Check (Minimal Code Change)

The change is a **single `if` block** inside `escape_hatch_loop()` in `04_cold_start_simulation.py`, inserted immediately after the round stats are appended:

```python
# After appending to rounds[]:
if r >= 2:  # always complete at least 2 rounds
    marginal_recall = rounds[-1]["recall"] - rounds[-2]["recall"]
    if marginal_recall < ELBOW_DELTA:
        break  # elbow detected — stop early
```

The same pattern applies to Criteria B and C. The constants `ELBOW_DELTA`, `ELBOW_TAU`, and `ELBOW_EPSILON` can be added to the top-level constants block alongside `YIELD_THRESHOLD`.

### Full annotated diff

```python
# ── Constants ─────────────────────────────────────────────────────────────────
PARETO_P        = 80
YIELD_THRESHOLD = 0.05   # within-round: stop BFS when screen yield < 5%
MAX_DEPTH       = 8
N_ROUNDS        = 8      # ← raise the ceiling; elbow will cut it off early
K_ESCAPE        = 20

# NEW: between-round elbow stopping
ELBOW_DELTA     = 0.01   # Criterion A: marginal recall gain threshold
ELBOW_TAU       = 5      # Criterion B: minimum new gold papers per round
ELBOW_EPSILON   = 0.01   # Criterion C: minimum round-level screen yield


def escape_hatch_loop(seed_set, gold_refs, all_nodes, n_rounds=N_ROUNDS,
                      k_escape=K_ESCAPE, pareto_p=PARETO_P,
                      yield_thresh=YIELD_THRESHOLD,
                      elbow_delta=ELBOW_DELTA,
                      elbow_tau=ELBOW_TAU,
                      elbow_epsilon=ELBOW_EPSILON):
    visited = set()
    rounds  = []
    current_seeds = set(seed_set)

    for r in range(1, n_rounds + 1):
        visited_before = len(visited)
        gold_before    = len(visited & gold_refs)

        visited, curve, stop_d = bidir_pareto_traversal(
            current_seeds, gold_refs,
            visited_already=visited,
            pareto_p=pareto_p,
            yield_thresh=yield_thresh,
        )

        recall    = len(visited & gold_refs) / len(gold_refs)
        new_nodes = len(visited) - visited_before
        new_gold  = len(visited & gold_refs) - gold_before
        round_yield = new_gold / new_nodes if new_nodes > 0 else 0.0

        rounds.append({
            "round":        r,
            "corpus_size":  len(visited),
            "recall":       recall,
            "tp":           len(visited & gold_refs),
            "new_nodes":    new_nodes,
            "new_gold":     new_gold,
            "round_yield":  round_yield,   # NEW field
            "stop_depth":   stop_d,
            "curve":        curve,
        })

        if recall >= 1.0:
            break

        # ── NEW: between-round elbow detection ────────────────────────────────
        if r >= 2:
            marginal_recall = rounds[-1]["recall"] - rounds[-2]["recall"]
            if (marginal_recall < elbow_delta          # Criterion A
                    or new_gold < elbow_tau             # Criterion B
                    or round_yield < elbow_epsilon):    # Criterion C
                break
        # ─────────────────────────────────────────────────────────────────────

        # Escape Hatch: find new seeds
        included = visited & gold_refs
        escape_candidates = set()
        for p in included:
            for nb in cites.get(p, set()):
                if nb not in visited:
                    escape_candidates.add(nb)
            for nb in cited_by.get(p, set()):
                if nb not in visited:
                    escape_candidates.add(nb)

        if not escape_candidates:
            break

        escape_sorted = sorted(escape_candidates,
                               key=lambda x: len(cited_by.get(x, set())), reverse=True)
        current_seeds = set(escape_sorted[:k_escape])

    return rounds
```

---

## 5. Downstream Compatibility

The change is **fully backward-compatible** with `05_miss_analysis.py` and `06_publication_figures.py`:

- `05_miss_analysis.py` re-runs the traversal from scratch and hard-codes its own `N_ROUNDS = 4`. It does not read the stopping round from the JSON. If you want it to respect the elbow, update its `escape_hatch_full()` function with the same `if r >= 2` block.
- `06_publication_figures.py` reads `cold_start_results.json` and iterates over `rounds_data` using `rounds_data[-1]` for final recall and `[r["round"] for r in rounds_data]` for x-axes. Since the list will simply be shorter when the elbow fires, both accesses remain valid with no code changes.
- The new `round_yield` field added to each round dict is additive and will be silently ignored by existing consumers.

---

## 6. Separate Analysis Script: `07_elbow_analysis.py`

A companion script (`07_elbow_analysis.py`) post-processes the existing `cold_start_results.json` to retroactively apply all three criteria and report:

- At which round each criterion would have stopped.
- The recall at that stopping point vs. the actual final recall.
- The corpus size saved.

This script requires **no re-run of the simulation** and can be run immediately after `04_cold_start_simulation.py`.

---

## 7. Recommended Defaults and Rationale

Based on the whitepaper's empirical story (round 1 → ~80–90% recall, rounds 2–4 → diminishing gains toward ~98.5%), the following defaults are recommended:

| Criterion | Default | Expected stop round | Expected recall loss |
|---|---|---|---|
| Marginal Recall < 1% (A) | δ = 0.01 | Round 2–3 | < 1% |
| New Gold < 5 (B) | τ = 5 | Round 3 | < 0.5% |
| Round Yield < 1% (C) | ε = 0.01 | Round 2–3 | < 1% |

Criterion B (`new_gold < 5`) is the most robust recommendation: it is corpus-size-independent, directly measures marginal value, and is easy to explain to practitioners ("stop when you're finding fewer than 5 new relevant papers per round").

To implement a **fixed small number of rounds** as a hard cap rather than an adaptive elbow, simply set `N_ROUNDS = 3` (or 2). The empirical data already shows that 3 rounds recovers ~97–98% recall across all conditions tested, and the elbow criteria above can serve as a soft override to stop even earlier when gains are negligible.

---

## 8. Summary of Changes Required

| File | Change | Invasiveness |
|---|---|---|
| `04_cold_start_simulation.py` | Add 3 constants + 1 `if` block in `escape_hatch_loop()` + `round_yield` field | **Minimal** (~15 lines) |
| `05_miss_analysis.py` | Optionally mirror the same `if` block in `escape_hatch_full()` | Optional |
| `06_publication_figures.py` | None | **Zero** |
| `07_elbow_analysis.py` | New standalone script | New file |
| `README.md` | Add row for script 07 | Trivial |
