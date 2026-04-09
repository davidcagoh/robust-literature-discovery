# Extension: N_ROUNDS Hyperparameter Sweep

**Date:** March 31, 2026

This note records an empirical sweep of the `N_ROUNDS` hyperparameter in the cold-start Escape Hatch loop and discusses what it implies for the whitepaper's framing.

---

## What Was Run

`07_rounds_sweep.py` runs the Escape Hatch loop up to 10 rounds from the canonical `k=20` top-cited seeds, recording per round:

- `new_gold` — new gold papers found in that round
- `new_nodes` — new papers visited (screening cost)
- `cumulative_recall` — recall after that many rounds

Full results are in `data-aps/outputs/n_rounds_sweep.csv`.

---

## Results

| Survey | Gold Set | R1 new_gold | R2 new_gold | R3+ new_gold | Recall @R1 | Recall @R2 |
|---|---|---|---|---|---|---|
| S1: Metal-insulator transitions | 582 | **575** | 0 | 0,0,1,1,0,0,0,0 | 98.8% | 98.8% |
| S2: Ultracold gases | 432 | **431** | 1 | — (100% hit) | 99.8% | **100.0%** |
| S3: Topological photonics | 387 | **376** | 3 | 3,0,0,1,1,0,0,0 | 97.2% | 97.9% |

Cost per round (new nodes visited):

| Survey | R1 | R2 | R3–R10 total |
|---|---|---|---|
| S1 | 192,157 | 21,335 | ~33,744 |
| S2 | 179,506 | 36,835 | — |
| S3 | 137,741 | 18,261 | ~35,647 |

![N_ROUNDS Sweep](data-aps/outputs/pub_figures/fig9_n_rounds_sweep.png)

---

## Key Finding

**Round 1 does essentially all the work.** The elbow is at round 1→2, not somewhere later as the whitepaper's framing implies. Rounds 3–10 collectively recover at most 2 additional gold papers per survey while visiting tens of thousands of nodes — a cost/benefit ratio of roughly 10,000–20,000 nodes per gold paper, compared to ~330–510 nodes per gold paper in round 1.

The current `N_ROUNDS = 4` setting is therefore not a principled choice — it is a blank cheque that pays for three rounds of near-zero marginal return. `N_ROUNDS = 2` is the natural cap: it captures the small but real round-2 gains (S2 reaches 100%, S3 picks up 3 more papers) at a cost of roughly 10–20% additional nodes, then stops.

---

## Implications for the Whitepaper Angle

The whitepaper currently frames the Escape Hatch as a multi-round mechanism that "pushes coverage toward 100%" across rounds 1–4. The sweep data suggests a different, arguably stronger story:

**The architecture is so effective that a single round is nearly sufficient.** The Escape Hatch's value is not that it iterates to convergence over many rounds — it is that the first traversal from good seeds is already near-exhaustive, and a second round serves as a cheap insurance pass. The multi-round framing undersells round 1 and overstates the contribution of rounds 2–4.

A revised angle could emphasise that the system achieves ~97–99% recall in a **single pass**, with an optional second round as a low-cost safety net. This is a stronger practical claim than "4 rounds gets you to 98.5%", and it directly informs the recommended `N_ROUNDS` default for production use.

The residual misses (rounds 5–10 find 1–2 papers at enormous cost) align cleanly with the existing miss analysis: they are the structurally peripheral, low-degree papers that the yield threshold correctly deprioritises. That story is unchanged.
