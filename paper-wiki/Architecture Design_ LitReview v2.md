# Architecture Design: LitReview v2

**Author:** Manus AI
**Date:** March 30, 2026

This document outlines the architecture for **LitReview v2**, a clean rewrite of the automated literature review engine. The redesign addresses the core bottlenecks discovered during the v1 pilot runs (rescreening loops, FUSE I/O crashes, and rigid sequential execution) by shifting to a unified queue-driven architecture with a clear "breathe in / breathe out" expansion loop.

---

## 1. The Core Loop: Breathe In, Breathe Out

The v1 architecture treated search, traversal, and PDF auditing as a rigid sequence. In v2, the architecture is re-centered around a single, unified **Screening Queue**. All discovery mechanisms (Search, Traversal, Recommendations, PDF Bibliography Extraction) are simply "producers" that dump candidate papers into this queue. The LLM Screener is the sole "consumer."

The loop is driven by **Screen Yield** (the ratio of newly included papers to total papers screened in a batch), which acts as the fruitfulness metric.

### The State Machine

1. **SEED**: The user provides an initial topic, research direction, or a few seed papers.
2. **SEARCH (Query-Driven)**: A semantic search (via Semantic Scholar / OpenAlex) is performed using the topic description to populate the initial queue.
3. **SCREEN**: The LLM screens the pending queue in batches.
   - *If Fruitful (Yield > Threshold)*: Proceed to TRAVERSE.
   - *If Stale (Yield < Threshold)*: Proceed to ESCAPE HATCH.
4. **TRAVERSE (Graph-Local)**: From the newly included papers, perform:
   - Backward Traversal (References)
   - Forward Traversal (Citations, with Pareto Filter)
   - S2 Recommendations (Semantic similarity to included set)
   - PDF Bibliography Extraction (Background worker)
   *All discovered papers are dumped into the pending queue. Loop back to SCREEN.*
5. **ESCAPE HATCH (Search)**: If traversal saturates (the citation graph neighbourhood is exhausted), perform a fresh SEARCH using the automatically refined inclusion criteria as the query to jump to a new part of the citation graph. Loop back to SCREEN.
6. **STABLE**: If both Traversal and the Escape Hatch Search return stale yields for consecutive rounds, the corpus is declared stable.
7. **SYNTHESIZE (Separate Tool)**: A final pass reads the full PDFs of the stable included corpus to extract insights and synthesize the final literature review document.

---

## 2. Key Architectural Changes from v1

### A. Unified Intake Queue
In v1, traversal only fired once because it waited for the pending queue to completely drain, which never happened due to uncertain papers. In v2, the screener doesn't care where papers came from. If a screening batch yields enough inclusions, the engine immediately triggers another traversal pass from the new frontier, while uncertain papers naturally fall to the back of the queue.

### B. PDF Reading at Intake (No FUSE Blocking)
In v1, PDF downloads were a blocking step that wrote large files to a FUSE mount, causing frequent crashes.
In v2, PDF bibliography extraction is a **background worker**. When a paper is marked `included`, its ID is sent to a worker that downloads the PDF to a local temporary directory (`/tmp`), extracts the references using an LLM or parser, pushes those references to the intake queue, and immediately deletes the PDF. No FUSE writes occur during the main discovery loop.

### C. Pareto Filter as a First-Class Citizen
Forward traversal from highly cited "hub" papers explodes the candidate pool with generic, off-topic papers. v2 implements an **Adaptive Pareto Split** for forward traversal. Before traversing, the engine calculates the Gini coefficient of the citation distribution of the included papers.
- High Gini (>0.7, power-law): Apply strict 80th percentile hub filter.
- Low Gini (<0.5, uniform): Relax to 95th percentile to avoid starving the frontier of niche topics.

### D. Automatic Criteria Refinement
After each fruitful screening round, an LLM prompt reviews the abstracts of the newly `included` and `excluded` papers to propose refinements to the inclusion criteria. This refined criteria string is used both to improve subsequent screening accuracy and as the query for the Escape Hatch search.

---

## 3. Database Schema Redesign

The Supabase schema will be streamlined to support the queue-driven model.

### `papers` Table
Stores paper metadata and current state.
- `id` (Primary Key)
- `s2_id`, `doi`, `arxiv_id` (Unique constraints)
- `title`, `abstract`, `authors`, `year`, `citation_count`
- `status`: `pending` | `included` | `excluded` | `uncertain`
- `source`: `seed` | `search` | `traverse_fwd` | `traverse_bwd` | `recommend` | `pdf_bib`
- `depth`: Integer (distance from seeds)

### `screening_log` Table (New)
Replaces the ambiguous `iterations` table to properly track the fruitfulness of each batch.
- `id` (Primary Key)
- `project_id`
- `timestamp`
- `papers_screened`: Integer
- `papers_included`: Integer
- `yield_rate`: Float (included / screened)
- `criteria_version`: Text (the criteria used for this batch)

### `edges` Table
Maintains the citation graph for visualization and traversal state.
- `source_id` (Citing paper)
- `target_id` (Cited paper)

---

## 4. Module Structure

The Python codebase will be restructured into independent, testable modules:

- `core/loop.py`: The main state machine orchestrating the Breathe In / Breathe Out cycle.
- `intake/search.py`: Semantic Scholar and OpenAlex query-based retrieval.
- `intake/traverse.py`: Graph-local traversal with the Adaptive Pareto filter.
- `intake/pdf_worker.py`: Asynchronous PDF download and bibliography extraction.
- `screen/llm.py`: Batch screening and automatic criteria refinement.
- `db/client.py`: Supabase interactions and queue management.

---

## 5. Conclusion

LitReview v2 shifts from a rigid, linear pipeline to a dynamic, queue-driven state machine. By decoupling discovery from screening, eliminating blocking FUSE I/O, and using Screen Yield as the primary control signal, the engine will converge faster, cost less in LLM tokens, and be significantly more resilient to infrastructure hiccups.
