# Thesis

## The Claim

> **LitDiscover recovers near-complete literature sets (89–98% recall) from as few as 5 seed papers, using bidirectional citation traversal with a Pareto hub filter and yield-based stopping.**

Two rounds of traversal suffice. Round 1 does 85–98% of the work; round 2 is cheap insurance. What remains unreachable is structurally peripheral: rarely-cited papers that are adjacent to the core but filtered out or never seeded.

---

## Why This Is Non-Obvious

Naively, comprehensive literature discovery requires either:
- A complete database query (impossible without knowing the query terms), or
- Manual snowballing (slow, depends entirely on the reviewer's knowledge).

The insight that makes LitDiscover possible is structural: **citation graphs are power-law skewed**. A small fraction of papers accumulate most of the citations, and those hub papers act as connectors that link disparate subfields. Starting from any 5 papers in a subfield, bidirectional BFS reaches most of the connected literature within 2–3 hops.

The two practical problems that arise from naive BFS are:
1. **Forward traversal explodes** — papers that cite a hub may cite thousands of other things too, most irrelevant. The Pareto filter suppresses forward-direction nodes whose out-degree is in the top 20%.
2. **When to stop?** — the screen yield (new relevant papers / new papers seen) drops sharply as you move away from the core. Stopping when yield < 5% keeps cost manageable.

---

## The Mechanism (one paragraph)

A user provides k seed papers. LitDiscover traverses backward (papers the seeds cite) and forward (papers that cite the seeds), applying the Pareto filter to forward candidates. It stops each round when yield drops below 5%. After round 1, it picks k=20 new seeds from the neighbourhood of papers already found and repeats — this is the "Escape Hatch" for papers the first round missed. Two rounds converge in all three benchmark surveys.

---

## What This Paper Does NOT Claim

- It does not claim 100% recall in all cases. S1 (a 1998 survey in an older subfield) reaches ~89% — the gap is explained.
- It does not claim to replace human judgement on inclusion/exclusion. The system produces a candidate set; screening remains human.
- It does not claim the method works outside physics journals — the APS corpus is the validation environment; live experiments (Kahle, Galesic) extend this.

---

## The Contribution

The contribution is not a new algorithm. Bidirectional BFS and Pareto filtering are known. The contribution is:

1. **The combination**: showing that bidir BFS + Pareto filter + yield stopping + Escape Hatch, run together, achieves near-complete recall from minimal seeds.
2. **The benchmark**: three real physics survey papers as ground truth, in a 700k-paper corpus, with full closed-form validation.
3. **The structural explanation**: characterising what gets missed and why (structural peripherality, not random failure).
