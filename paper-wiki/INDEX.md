# LitDiscover Paper — Wiki Index

A living knowledge base for the paper. Updated by LLM; read in any order.
Each file is short by design — the goal is to hold the full argument in your head in one read.

## Files

| File | Purpose | Read when |
|---|---|---|
| [thesis.md](thesis.md) | The core argument in 400 words | Every session, first |
| [argument-map.md](argument-map.md) | Section → claim → evidence → figure | Before touching any figure or script |
| [figure-roles.md](figure-roles.md) | Per-figure: what it proves, what's broken, priority | Before running analysis scripts |
| [open-questions.md](open-questions.md) | Unresolved issues and blockers | When deciding what to work on next |
| [decisions.md](decisions.md) | Design choices made and why | Before changing any parameter |
| [simulation-vs-production.md](simulation-vs-production.md) | How APS simulation relates to production system | Before framing paper claims or touching production code |

## One-line status

- **Thesis**: defined ✅
- **Paper name**: LitDiscover ✅ — title: "Robust Literature Discovery from Minimal Seeds: Validating LitDiscover on APS Citation Benchmarks and Live Surveys"
- **APS validation (Figs 1–8)**: generated; Fig 4 title fixed; script 08 sweep complete (1980 rows) ⚠️ remaining figure fixes needed
- **Filter direction (scripts 03/05/08)**: out-degree on forward candidates — finalized ✅
- **Live experiment K17-RGC (Kahle 2017)**: ✅ COMPLETE — 100% recall (56/56), depth 2, round 1
- **Live experiment Ge21-HSS (Galesic 2021)**: 🔄 in progress (202 gold papers)
- **Live experiment Le25-GLLM**: ⏳ seeds added, not yet run
- **Paper text**: needs full rewrite ❌
