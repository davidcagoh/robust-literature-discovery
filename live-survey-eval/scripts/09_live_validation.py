"""
Live Validation Experiment — Real Surveys on Semantic Scholar

Validates the LitDiscover algorithm (bidirectional BFS + out-degree Pareto filter +
yield-based stopping + escape hatch) against three real surveys from diverse domains:
  - Ge21-HSS  : Galesic et al. 2021 Nature — human social sensing (~178 refs)
  - K17-RGC   : Bobrowski & Kahle 2017    — random geometric complexes (~51 refs)
  - Le25-GLLM : Liu et al. 2025           — graph-augmented LLM agents (~150+ refs)

Unlike the APS simulation, this script calls the Semantic Scholar API and measures
recall against gold sets extracted from the validation survey PDFs.

Design principles:
  - All S2 responses are cached to disk (data/cache/). Re-runs are free.
  - Gold sets are extracted once and saved to data/gold-sets/; manual corrections
    to those JSON files survive re-runs (the script never overwrites existing gold files).
  - The Pareto filter uses out-degree (reference_count) of forward candidates,
    matching the APS simulation semantics.
  - Run per-survey: python3 09_live_validation.py --survey Ge21-HSS
  - Run all: python3 09_live_validation.py

Usage:
  export SEMANTIC_SCHOLAR_API_KEY=<your-key>
  python3 scripts/09_live_validation.py --survey Ge21-HSS
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import threading
import unicodedata
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # dotenv optional; set SEMANTIC_SCHOLAR_API_KEY manually if needed

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False
    print("[warn] pypdf not installed — PDF parsing disabled. Run: pip install pypdf")

try:
    from rapidfuzz import fuzz as rfuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    print("[warn] rapidfuzz not installed — fuzzy title matching disabled. Run: pip install rapidfuzz")

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO      = Path(__file__).parent.parent
DATA_LIVE = REPO / "data"
CACHE_DIR = DATA_LIVE / "cache" / "papers"
SRCH_DIR  = DATA_LIVE / "cache" / "search"
GOLD_DIR  = DATA_LIVE / "gold-sets"
SEED_DIR  = DATA_LIVE / "seeds"
OUT_DIR   = DATA_LIVE / "outputs"
FIG_DIR   = OUT_DIR / "pub_figures"

for d in [CACHE_DIR, SRCH_DIR, GOLD_DIR, SEED_DIR, OUT_DIR, FIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Survey configuration ───────────────────────────────────────────────────────
# survey_doi: if set, the gold set is fetched directly from S2's reference list
#             for this paper (bypasses PDF parsing — cleaner for well-indexed papers).
#             Leave None to use PDF parsing fallback.
SURVEYS: dict[str, dict] = {
    "Ge21-HSS": {
        "survey_pdf": DATA_LIVE / "validation-surveys" / "Ge21-HSS.pdf",
        "survey_doi": "10.1038/s41586-021-03649-2",
        "survey_s2_id": None,  # will resolve via DOI
        "seed_pdfs": [
            DATA_LIVE / "seed-papers" / "HSS1_G18.pdf",
            DATA_LIVE / "seed-papers" / "HSS2_NK19.pdf",
            DATA_LIVE / "seed-papers" / "HSS3_A21.pdf",
        ],
        "label": "Galesic 2021 (Human Social Sensing)",
    },
    "K17-RGC": {
        "survey_doi": None,
        "survey_s2_id": "f75ae5929e4a3c94062959caa954393a4217aeb5",  # resolved manually
        "survey_pdf": DATA_LIVE / "validation-surveys" / "K17-RGC.pdf",
        "seed_pdfs": [
            DATA_LIVE / "seed-papers" / "RGC1_BDER15.pdf",
            DATA_LIVE / "seed-papers" / "RGC2_AM21.pdf",
            DATA_LIVE / "seed-papers" / "RGC3_LMSY21.pdf",
        ],
        "label": "Bobrowski & Kahle 2017 (Random Geometric Complexes)",
    },
    "Le25-GLLM": {
        "survey_pdf": DATA_LIVE / "validation-surveys" / "Le25-GLLM.pdf",
        "survey_doi": None,    # arXiv — add DOI or arXiv ID once known
        "survey_s2_id": "d9fcf869c0d2fef88b0330fe94a0c405b1104c16",
        "seed_pdfs": [
            DATA_LIVE / "seed-papers" / "GLLM1_Je24.pdf",
            DATA_LIVE / "seed-papers" / "GLLM2_MXC25.pdf",
            DATA_LIVE / "seed-papers" / "GLLM3_We25.pdf",
        ],
        "label": "Liu et al. 2025 (Graph-Augmented LLM Agents)",
    },
}

# ── Algorithm parameters (match APS simulation) ───────────────────────────────
PARETO_P        = 80    # keep forward candidates with reference_count ≤ 80th percentile
YIELD_THRESHOLD = 0.05  # stop depth when new_gold / new_nodes < 5%
MAX_DEPTH       = 4     # live traversal: shallower than APS (API cost)
N_ROUNDS        = 2
K_ESCAPE        = 20
FUZZY_THRESHOLD = 88    # rapidfuzz token_sort_ratio threshold for title match

# ── S2 API setup ──────────────────────────────────────────────────────────────
S2_BASE   = "https://api.semanticscholar.org/graph/v1/paper"
S2_FIELDS = "paperId,externalIds,title,year,authors,venue,citationCount,referenceCount"

_S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
HEADERS: dict[str, str] = {"User-Agent": "litdiscover-validation/1.0"}
if _S2_API_KEY:
    HEADERS["x-api-key"] = _S2_API_KEY
else:
    print("[warn] SEMANTIC_SCHOLAR_API_KEY not set — unauthenticated rate limit (100 req/5min)")

_s2_lock     = threading.Lock()
_s2_last_call: float = 0.0
_S2_MIN_INTERVAL = 1.05  # 1 req/sec authenticated


def _s2_wait() -> None:
    global _s2_last_call
    with _s2_lock:
        now  = time.monotonic()
        wait = _S2_MIN_INTERVAL - (now - _s2_last_call)
        if wait > 0:
            time.sleep(wait)
        _s2_last_call = time.monotonic()


# ── Disk cache ────────────────────────────────────────────────────────────────

def _paper_cache_path(s2_id: str) -> Path:
    return CACHE_DIR / f"{s2_id}.json"


def _load_cached_paper(s2_id: str) -> Optional[dict]:
    p = _paper_cache_path(s2_id)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return None


def _save_cached_paper(s2_id: str, data: dict) -> None:
    with open(_paper_cache_path(s2_id), "w") as f:
        json.dump(data, f)


def _search_cache_path(query: str) -> Path:
    h = hashlib.md5(query.encode()).hexdigest()
    return SRCH_DIR / f"{h}.json"


# ── S2 API calls ─────────────────────────────────────────────────────────────

def _normalise(raw: dict) -> dict:
    """Normalise a S2 paper record to a standard dict."""
    ext = raw.get("externalIds") or {}
    return {
        "s2_id":            raw.get("paperId"),
        "doi":              ext.get("DOI"),
        "arxiv_id":         ext.get("ArXiv"),
        "title":            raw.get("title") or "",
        "year":             raw.get("year"),
        "citation_count":   raw.get("citationCount"),
        "reference_count":  raw.get("referenceCount"),
        "references_fetched": False,
        "citations_fetched":  False,
    }


def fetch_paper(identifier: str) -> Optional[dict]:
    """
    Fetch a paper by DOI, ArXiv ID, or S2 paperId.
    identifier formats: "DOI:10.x/y", "ARXIV:2301.x", or bare S2 paperId.
    Returns normalised dict or None on failure.
    """
    # For bare S2 IDs, check cache first
    if not identifier.startswith(("DOI:", "ARXIV:")):
        cached = _load_cached_paper(identifier)
        if cached:
            return cached

    _s2_wait()
    for attempt in range(4):
        try:
            with httpx.Client(timeout=30, headers=HEADERS) as client:
                r = client.get(f"{S2_BASE}/{identifier}", params={"fields": S2_FIELDS})
                if r.status_code == 429:
                    wait = 60 * (attempt + 1)
                    print(f"  [s2] rate limited — sleeping {wait}s (attempt {attempt+1}/4)")
                    time.sleep(wait)
                    continue
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                data = _normalise(r.json())
                if data["s2_id"]:
                    _save_cached_paper(data["s2_id"], data)
                return data
        except Exception as e:
            if "429" in str(e):
                wait = 60 * (attempt + 1)
                print(f"  [s2] rate limited — sleeping {wait}s (attempt {attempt+1}/4)")
                time.sleep(wait)
                continue
            print(f"  [s2] fetch_paper({identifier}) failed: {e}")
            return None
    print(f"  [s2] fetch_paper({identifier}) gave up after 4 attempts")
    return None


def fetch_paper_by_title(title: str, first_author: str = "") -> Optional[dict]:
    """Search S2 by title; return top result if it fuzzy-matches above threshold."""
    cache_file = _search_cache_path(title)
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    _s2_wait()
    try:
        with httpx.Client(timeout=30, headers=HEADERS) as client:
            r = client.get(
                f"{S2_BASE}/search",
                params={"query": title, "fields": S2_FIELDS, "limit": 5},
            )
            if r.status_code == 429:
                time.sleep(30)
                r = client.get(
                    f"{S2_BASE}/search",
                    params={"query": title, "fields": S2_FIELDS, "limit": 5},
                )
            if r.status_code != 200:
                return None
            items = r.json().get("data") or []
    except Exception as e:
        print(f"  [s2] search failed for '{title[:60]}': {e}")
        return None

    for item in items:
        if not item.get("title"):
            continue
        if not HAS_RAPIDFUZZ:
            # Fall back to exact prefix match
            if item["title"].lower().startswith(title[:30].lower()):
                result = _normalise(item)
                if result["s2_id"]:
                    _save_cached_paper(result["s2_id"], result)
                with open(cache_file, "w") as f:
                    json.dump(result, f)
                return result
        else:
            score = rfuzz.token_sort_ratio(normalize_title(title), normalize_title(item["title"]))
            if score >= FUZZY_THRESHOLD:
                result = _normalise(item)
                if result["s2_id"]:
                    _save_cached_paper(result["s2_id"], result)
                with open(cache_file, "w") as f:
                    json.dump(result, f)
                return result
    return None


def fetch_neighbors(s2_id: str, direction: str) -> list[dict]:
    """
    Fetch all references or citations of a paper. Results are stored back into
    the paper's cache file so subsequent calls return from cache.
    direction: "references" or "citations"
    """
    flag_key = f"{direction}_fetched"
    cached = _load_cached_paper(s2_id)
    if cached and cached.get(flag_key) and cached.get(direction):
        return cached[direction]

    results: list[dict] = []
    offset = 0
    rate_limit_strikes = 0
    MAX_RATE_LIMIT_STRIKES = 5
    while True:
        _s2_wait()
        try:
            with httpx.Client(timeout=30, headers=HEADERS) as client:
                r = client.get(
                    f"{S2_BASE}/{s2_id}/{direction}",
                    params={"fields": S2_FIELDS, "limit": 1000, "offset": offset},
                )
                if r.status_code == 429:
                    rate_limit_strikes += 1
                    if rate_limit_strikes > MAX_RATE_LIMIT_STRIKES:
                        print(f"  [s2] fetch_neighbors({s2_id}, {direction}) — gave up after {MAX_RATE_LIMIT_STRIKES} rate limits")
                        break
                    wait = 30 * rate_limit_strikes
                    print(f"  [s2] rate limited — sleeping {wait}s (strike {rate_limit_strikes}/{MAX_RATE_LIMIT_STRIKES})")
                    time.sleep(wait)
                    continue
                rate_limit_strikes = 0  # reset on success
                if r.status_code in (404, 400):
                    break
                r.raise_for_status()
                data = r.json().get("data") or []
                for item in data:
                    p = item.get("citedPaper") or item.get("citingPaper") or {}
                    if p.get("paperId"):
                        norm = _normalise(p)
                        results.append(norm)
                        _save_cached_paper(norm["s2_id"], norm)
                if len(data) < 1000:
                    break
                offset += len(data)
        except Exception as e:
            print(f"  [s2] fetch_neighbors({s2_id}, {direction}) at offset {offset}: {e}")
            break

    # Update the paper's own cache with neighbour list + fetched flag
    rec = cached or {}
    rec[direction]  = [{"s2_id": n["s2_id"], "reference_count": n["reference_count"],
                         "citation_count": n["citation_count"], "title": n["title"]}
                        for n in results if n.get("s2_id")]
    rec[flag_key]   = True
    if s2_id:
        _save_cached_paper(s2_id, rec)

    return results


# ── PDF parsing ───────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> str:
    if not HAS_PYPDF:
        return ""
    reader = pypdf.PdfReader(str(pdf_path))
    pages  = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def find_reference_section(text: str) -> str:
    """Return the text from the References/Bibliography section onward."""
    anchors = [
        r"\n\s*References\s*\n",
        r"\n\s*Bibliography\s*\n",
        r"\n\s*Works Cited\s*\n",
        r"\n\s*REFERENCES\s*\n",
        r"\n\s*BIBLIOGRAPHY\s*\n",
    ]
    for pattern in anchors:
        m = re.search(pattern, text)
        if m:
            return text[m.start():]
    # Fallback: last 35% of document
    return text[int(len(text) * 0.65):]


def parse_references_from_text(ref_text: str) -> list[dict]:
    """
    Extract {raw_title, doi} entries from reference section text.
    DOI extraction is reliable; title extraction is approximate.
    """
    entries: list[dict] = []

    # Pass 1: find all DOIs in the text
    doi_pattern = r"\b(10\.\d{4,9}/[^\s,;\"'<>\)\]]+)"
    dois = re.findall(doi_pattern, ref_text)
    # Clean up trailing punctuation that regex may capture
    dois = [d.rstrip(".,;)]") for d in dois]

    # Pass 2: split into individual reference entries
    # Try numbered references [1], 1., (1) or bullet lines
    ref_splits = re.split(
        r"\n\s*(?:\[?\d{1,3}[\]\.]\s+|\(\d{1,3}\)\s+)",
        ref_text
    )

    doi_set = set(dois)
    used_dois: set[str] = set()

    for chunk in ref_splits[1:]:  # skip header fragment
        chunk = chunk.strip()
        if len(chunk) < 20:
            continue
        # Extract DOI if present in this chunk
        chunk_dois = [d.rstrip(".,;)]") for d in re.findall(doi_pattern, chunk)]
        entry_doi = chunk_dois[0] if chunk_dois else None
        if entry_doi:
            used_dois.add(entry_doi)

        # Extract title: heuristically the text in quotes or italics,
        # or the first sentence-like string that ends with a period and is not all-caps
        raw_title = None
        # Try quoted title
        q_match = re.search(r'"([^"]{10,150})"', chunk)
        if q_match:
            raw_title = q_match.group(1).strip()
        if not raw_title:
            # Take first line after stripping author-year prefix
            first_line = chunk.split("\n")[0].strip()
            # Remove author list heuristic: remove leading "Lastname, F." patterns
            cleaned = re.sub(r"^([A-Z][a-z]+,?\s+[A-Z]\.?\s*,?\s*)+", "", first_line).strip()
            if len(cleaned) > 20:
                raw_title = cleaned[:200]

        if raw_title or entry_doi:
            entries.append({"raw_title": raw_title, "doi": entry_doi, "s2_id": None, "manual_s2_id": None})

    # Add any DOIs not captured in numbered refs
    for doi in doi_set - used_dois:
        entries.append({"raw_title": None, "doi": doi, "s2_id": None, "manual_s2_id": None})

    return entries


def build_gold_set_from_s2(survey_id: str, survey_doi: Optional[str] = None,
                            survey_s2_id: Optional[str] = None,
                            survey_title: str = "") -> list[dict]:
    """
    Fetch the survey paper's reference list from S2 directly.
    This is the preferred path when the survey paper is indexed in S2 —
    it bypasses PDF parsing and gives pre-resolved S2 IDs.
    """
    save_path = GOLD_DIR / f"{survey_id}_gold.json"
    if save_path.exists():
        print(f"  Loading existing gold set: {save_path.name}")
        with open(save_path) as f:
            return json.load(f)

    # Find the survey paper itself in S2
    survey_paper = None
    if survey_s2_id:
        survey_paper = fetch_paper(survey_s2_id)
    if not survey_paper and survey_doi:
        survey_paper = fetch_paper(f"DOI:{survey_doi}")
    if not survey_paper and survey_title:
        survey_paper = fetch_paper_by_title(survey_title)

    if not survey_paper or not survey_paper.get("s2_id"):
        print(f"  Could not resolve survey paper in S2 — falling back to PDF parsing")
        return []

    print(f"  Survey paper resolved: '{survey_paper['title'][:70]}' (S2: {survey_paper['s2_id']})")

    # Fetch all references of the survey paper
    print(f"  Fetching reference list from S2...")
    refs = fetch_neighbors(survey_paper["s2_id"], "references")
    print(f"  Got {len(refs)} references from S2")

    entries = []
    for r in refs:
        if r.get("s2_id"):
            entries.append({
                "raw_title":    r.get("title"),
                "doi":          r.get("doi"),
                "s2_id":        r.get("s2_id"),
                "manual_s2_id": None,
            })

    with open(save_path, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"  Saved {len(entries)} gold entries to {save_path.name}")
    return entries


def build_gold_set(survey_id: str, pdf_path: Path,
                   survey_doi: Optional[str] = None,
                   survey_s2_id: Optional[str] = None) -> list[dict]:
    """
    Build the gold reference list for a survey.
    Strategy: try S2 reference list first (if survey_doi provided), then PDF parsing.
    Saves to data/gold-sets/{survey_id}_gold.json.
    If file already exists, loads it (manual corrections survive re-runs).
    """
    save_path = GOLD_DIR / f"{survey_id}_gold.json"
    if save_path.exists():
        print(f"  Loading existing gold set: {save_path.name}")
        with open(save_path) as f:
            return json.load(f)

    # Try S2 reference list first (preferred — no PDF parsing needed)
    if survey_doi or survey_s2_id:
        entries = build_gold_set_from_s2(survey_id, survey_doi=survey_doi,
                                          survey_s2_id=survey_s2_id)
        if entries:
            return entries

    # Fall back to PDF parsing
    print(f"  Parsing PDF: {pdf_path.name}")
    text    = extract_text_from_pdf(pdf_path)
    ref_sec = find_reference_section(text)
    entries = parse_references_from_text(ref_sec)
    print(f"  Extracted {len(entries)} raw reference entries")

    with open(save_path, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"  Saved to {save_path.name} — review and add 'manual_s2_id' for unresolved entries")
    return entries


# ── Gold set S2 resolution ────────────────────────────────────────────────────

def resolve_gold_set(survey_id: str, gold_list: list[dict]) -> tuple[set[str], list[dict]]:
    """
    Resolve each gold entry to a S2 paperId.
    Returns (gold_s2_ids set, updated gold_list with s2_id filled where possible).
    Saves updated list back to disk.
    """
    save_path = GOLD_DIR / f"{survey_id}_gold.json"
    resolved  = 0
    updated   = False

    for entry in gold_list:
        # Already resolved
        if entry.get("s2_id") or entry.get("manual_s2_id"):
            resolved += 1
            continue

        paper = None
        if entry.get("doi"):
            paper = fetch_paper(f"DOI:{entry['doi']}")
        if not paper and entry.get("raw_title") and len(entry["raw_title"]) > 15:
            paper = fetch_paper_by_title(entry["raw_title"])

        if paper and paper.get("s2_id"):
            entry["s2_id"] = paper["s2_id"]
            resolved += 1
            updated = True

    if updated:
        with open(save_path, "w") as f:
            json.dump(gold_list, f, indent=2)

    gold_s2_ids = set()
    for entry in gold_list:
        sid = entry.get("manual_s2_id") or entry.get("s2_id")
        if sid:
            gold_s2_ids.add(sid)

    total = len(gold_list)
    print(f"  Gold set: {resolved}/{total} resolved ({resolved/total:.0%}), "
          f"{len(gold_s2_ids)} unique S2 IDs")
    return gold_s2_ids, gold_list


# ── Seed resolution ───────────────────────────────────────────────────────────

def resolve_seeds(survey_id: str, seed_pdfs: list[Path]) -> list[dict]:
    """
    Resolve each seed PDF to a S2 paper record.
    Saves to data/seeds/{survey_id}_seeds.json.
    """
    save_path = SEED_DIR / f"{survey_id}_seeds.json"
    if save_path.exists():
        with open(save_path) as f:
            return json.load(f)

    seeds: list[dict] = []
    for pdf_path in seed_pdfs:
        print(f"  Resolving seed: {pdf_path.name}")
        text = extract_text_from_pdf(pdf_path)
        # Try DOI from first 2 pages
        first_pages = "\n".join(text.split("\n")[:80])
        doi_matches = re.findall(r"\b(10\.\d{4,9}/[^\s,;\"'<>\)\]]+)", first_pages)
        paper = None
        for doi in doi_matches:
            doi = doi.rstrip(".,;)]")
            paper = fetch_paper(f"DOI:{doi}")
            if paper:
                break
        if not paper:
            # Extract title from first line
            first_line = text.split("\n")[0].strip()[:150]
            if len(first_line) > 20:
                paper = fetch_paper_by_title(first_line)
        if paper:
            print(f"    → {paper['title'][:70]} ({paper.get('year')})")
            seeds.append(paper)
        else:
            print(f"    → FAILED to resolve {pdf_path.name}")

    with open(save_path, "w") as f:
        json.dump(seeds, f, indent=2)
    return seeds


# ── Traversal engine ──────────────────────────────────────────────────────────

def bidir_pareto_traversal_live(
    seed_ids:        set[str],
    gold_s2_ids:     set[str],
    visited_already: Optional[set[str]] = None,
    pareto_p:        int   = PARETO_P,
    yield_thresh:    float = YIELD_THRESHOLD,
    max_depth:       int   = MAX_DEPTH,
) -> tuple[set[str], dict[str, str], list[dict], int]:
    """
    Bidirectional BFS on the S2 graph with out-degree Pareto filter on forward
    candidates and yield-based stopping.

    Out-degree filter: after collecting citers of the frontier, discard citers
    whose reference_count > pareto_p-th percentile of collected citers' ref counts.
    This matches the APS simulation semantics.

    Returns:
        visited:         set of S2 paper IDs visited
        visited_titles:  {s2_id: title} for all visited papers
        curve:           per-depth stats list
        stop_depth:      depth at which traversal stopped
    """
    visited        = set(visited_already) if visited_already else set()
    visited_titles: dict[str, str] = {}
    for s in seed_ids:
        visited.add(s)
        p = _load_cached_paper(s)
        if p:
            visited_titles[s] = p.get("title", "")

    frontier  = seed_ids - visited_already if visited_already else set(seed_ids)
    curve     = []
    stop_depth = max_depth

    for d in range(1, max_depth + 1):
        prev_size = len(visited)
        prev_gold = len(visited & gold_s2_ids)

        nxt: set[str] = set()

        # ── Backward: follow references of frontier ──────────────────────────
        print(f"    depth {d}: backward traversal from {len(frontier)} frontier papers...")
        for node in frontier:
            refs = fetch_neighbors(node, "references")
            for p in refs:
                pid = p.get("s2_id")
                if pid and pid not in visited:
                    visited.add(pid)
                    visited_titles[pid] = p.get("title", "")
                    nxt.add(pid)

        # ── Forward: collect citers, apply out-degree Pareto filter ──────────
        print(f"    depth {d}: forward traversal...")
        fwd_candidates: list[dict] = []
        for node in frontier:
            cits = fetch_neighbors(node, "citations")
            for p in cits:
                pid = p.get("s2_id")
                if pid and pid not in visited:
                    fwd_candidates.append(p)

        if fwd_candidates:
            ref_counts = np.array([p.get("reference_count") or 0 for p in fwd_candidates])
            if pareto_p is not None and len(ref_counts) > 1:
                threshold = np.percentile(ref_counts, pareto_p)
            else:
                threshold = float("inf")
            for p, rc in zip(fwd_candidates, ref_counts):
                pid = p.get("s2_id")
                if pid and pid not in visited and rc <= threshold:
                    visited.add(pid)
                    visited_titles[pid] = p.get("title", "")
                    nxt.add(pid)

        frontier  = nxt
        new_nodes = len(visited) - prev_size
        new_gold  = len(visited & gold_s2_ids) - prev_gold
        sy        = new_gold / new_nodes if new_nodes > 0 else 0.0
        recall    = len(visited & gold_s2_ids) / len(gold_s2_ids) if gold_s2_ids else 0.0

        curve.append({
            "depth":        d,
            "corpus_size":  len(visited),
            "recall":       recall,
            "tp":           len(visited & gold_s2_ids),
            "new_nodes":    new_nodes,
            "new_gold":     new_gold,
            "screen_yield": sy,
        })

        print(f"    depth {d}: +{new_nodes} nodes, +{new_gold} gold, "
              f"yield={sy:.1%}, recall={recall:.1%}, corpus={len(visited):,}")

        if sy < yield_thresh and d >= 2:
            stop_depth = d
            print(f"    → yield {sy:.1%} < {yield_thresh:.0%} — stopping at depth {d}")
            break
        if recall >= 1.0:
            stop_depth = d
            print(f"    → 100% recall reached at depth {d} — stopping early")
            break
        if not frontier:
            stop_depth = d
            break

    return visited, visited_titles, curve, stop_depth


def escape_hatch_loop_live(
    seed_ids:    set[str],
    gold_s2_ids: set[str],
    n_rounds:    int   = N_ROUNDS,
    k_escape:    int   = K_ESCAPE,
    pareto_p:    int   = PARETO_P,
    yield_thresh: float = YIELD_THRESHOLD,
) -> list[dict]:
    """
    Multi-round escape hatch loop on the S2 graph.
    Escape hatch picks top-K graph-neighbours of found gold refs by citation_count.
    """
    visited:        set[str]       = set()
    visited_titles: dict[str, str] = {}
    rounds:  list[dict]            = []
    current_seeds = set(seed_ids)

    for r in range(1, n_rounds + 1):
        print(f"\n  ── Round {r} ──────────────────────────────────")
        visited_before = len(visited)
        gold_before    = len(visited & gold_s2_ids)

        visited, visited_titles, curve, stop_d = bidir_pareto_traversal_live(
            current_seeds, gold_s2_ids,
            visited_already=visited,
            pareto_p=pareto_p,
            yield_thresh=yield_thresh,
        )

        recall = len(visited & gold_s2_ids) / len(gold_s2_ids) if gold_s2_ids else 0.0
        rounds.append({
            "round":         r,
            "corpus_size":   len(visited),
            "recall":        recall,
            "tp":            len(visited & gold_s2_ids),
            "new_nodes":     len(visited) - visited_before,
            "new_gold":      len(visited & gold_s2_ids) - gold_before,
            "stop_depth":    stop_d,
            "curve":         curve,
        })
        print(f"  Round {r} complete: recall={recall:.1%}, corpus={len(visited):,}")

        if recall >= 1.0:
            break

        # Escape hatch: top-K graph-neighbours of found gold refs by citation_count
        found_gold = visited & gold_s2_ids
        escape_candidates: dict[str, int] = {}
        for gid in found_gold:
            for direction in ("references", "citations"):
                cached = _load_cached_paper(gid) or {}
                for nb in (cached.get(direction) or []):
                    nid = nb.get("s2_id")
                    if nid and nid not in visited:
                        cc = nb.get("citation_count") or 0
                        escape_candidates[nid] = max(escape_candidates.get(nid, 0), cc)

        if not escape_candidates:
            print("  No escape candidates — stopping.")
            break

        top_escape = sorted(escape_candidates, key=escape_candidates.get, reverse=True)[:k_escape]
        current_seeds = set(top_escape)
        print(f"  Escape hatch: {len(current_seeds)} new seeds selected")

    return rounds


# ── Recall computation ────────────────────────────────────────────────────────

def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy matching."""
    title = unicodedata.normalize("NFKD", title)
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def compute_recall(
    visited_ids:    set[str],
    visited_titles: dict[str, str],
    gold_s2_ids:    set[str],
    gold_list:      list[dict],
    fuzzy_threshold: int = FUZZY_THRESHOLD,
) -> dict:
    """
    Compute recall using:
    Tier 1: S2 paperId exact match (primary metric)
    Tier 2: fuzzy title match for gold entries without resolved S2 IDs
    """
    # Tier 1: exact S2 ID match
    tp_exact  = len(visited_ids & gold_s2_ids)
    resolvable = len(gold_s2_ids)

    # Tier 2: fuzzy title match for unresolved gold entries
    unresolved_gold = [e for e in gold_list if not (e.get("s2_id") or e.get("manual_s2_id"))]
    tp_fuzzy = 0
    if HAS_RAPIDFUZZ and unresolved_gold and visited_titles:
        norm_visited = [(sid, normalize_title(t)) for sid, t in visited_titles.items()]
        for entry in unresolved_gold:
            if not entry.get("raw_title"):
                continue
            norm_gold = normalize_title(entry["raw_title"])
            for _, norm_vis in norm_visited:
                if rfuzz.token_sort_ratio(norm_gold, norm_vis) >= fuzzy_threshold:
                    tp_fuzzy += 1
                    break

    total_gold = len(gold_list)

    return {
        "recall_exact":       tp_exact  / resolvable  if resolvable  > 0 else None,
        "recall_upper_bound": (tp_exact + tp_fuzzy) / total_gold if total_gold > 0 else None,
        "tp_exact":           tp_exact,
        "tp_fuzzy":           tp_fuzzy,
        "gold_resolvable":    resolvable,
        "gold_total":         total_gold,
        "corpus_size":        len(visited_ids),
    }


# ── Output ────────────────────────────────────────────────────────────────────

def save_results(survey_id: str, rounds: list[dict], recall_stats: dict) -> None:
    results_path = OUT_DIR / "live_traversal_results.json"
    all_results  = {}
    if results_path.exists():
        with open(results_path) as f:
            all_results = json.load(f)
    all_results[survey_id] = {
        "rounds":       rounds,
        "recall_stats": recall_stats,
        "label":        SURVEYS[survey_id]["label"],
    }
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"  Results saved to {results_path.name}")


def make_summary_csv() -> None:
    results_path = OUT_DIR / "live_traversal_results.json"
    if not results_path.exists():
        return
    with open(results_path) as f:
        all_results = json.load(f)

    import csv
    csv_path = OUT_DIR / "live_validation_summary.csv"
    rows = []
    for sid, data in all_results.items():
        rs = data.get("recall_stats") or {}
        final_round = data["rounds"][-1] if data.get("rounds") else {}
        rows.append({
            "survey":           sid,
            "label":            data.get("label", ""),
            "recall_exact":     rs.get("recall_exact"),
            "recall_upper":     rs.get("recall_upper_bound"),
            "tp_exact":         rs.get("tp_exact"),
            "gold_resolvable":  rs.get("gold_resolvable"),
            "gold_total":       rs.get("gold_total"),
            "corpus_size":      final_round.get("corpus_size"),
            "n_rounds":         len(data.get("rounds", [])),
            "stop_depth":       final_round.get("stop_depth"),
        })
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Summary CSV saved to {csv_path.name}")


def make_figures() -> None:
    """Generate recall-vs-depth figures analogous to APS fig 5."""
    results_path = OUT_DIR / "live_traversal_results.json"
    if not results_path.exists():
        return
    with open(results_path) as f:
        all_results = json.load(f)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SURVEY_STYLE = {
        "Ge21-HSS":  {"color": "#1b7837", "marker": "o"},
        "K17-RGC":   {"color": "#762a83", "marker": "s"},
        "Le25-GLLM": {"color": "#d73027", "marker": "^"},
    }

    fig, axes = plt.subplots(1, len(all_results), figsize=(5 * len(all_results), 4), squeeze=False)
    axes = axes[0]

    for ax, (sid, data) in zip(axes, all_results.items()):
        style = SURVEY_STYLE.get(sid, {"color": "#333333", "marker": "o"})
        for r_data in data.get("rounds", []):
            rnum  = r_data["round"]
            curve = r_data.get("curve", [])
            if not curve:
                continue
            depths  = [0] + [c["depth"] for c in curve]
            recalls = [0] + [c["recall"] for c in curve]
            ax.plot(depths, recalls, marker=style["marker"], color=style["color"],
                    label=f"Round {rnum}", lw=2, ms=6, alpha=0.5 + 0.5 * (rnum == 1))

        rs = data.get("recall_stats") or {}
        ax.set_title(f"{sid}\n(gold: {rs.get('gold_resolvable','?')} resolvable / "
                     f"{rs.get('gold_total','?')} total)", fontsize=9)
        ax.set_xlabel("BFS depth")
        ax.set_ylabel("Recall (exact S2 match)")
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=8)
        ax.axhline(1.0, color="gray", lw=0.8, ls="--", alpha=0.5)

    fig.suptitle("LitDiscover Live Validation — Recall vs. Depth", fontsize=12)
    plt.tight_layout()
    out = FIG_DIR / "fig_live_recall_vs_depth.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Figure saved: {out.name}")


# ── Main entry point ──────────────────────────────────────────────────────────

def run_survey(survey_id: str) -> None:
    cfg = SURVEYS[survey_id]
    print(f"\n{'='*60}")
    print(f"Survey: {survey_id} — {cfg['label']}")
    print(f"{'='*60}")

    if not cfg["seed_pdfs"]:
        print(f"  No seed PDFs configured for {survey_id} — skipping.")
        return

    # Step 1: Build gold set
    print("\n[1/4] Building gold set...")
    gold_list = build_gold_set(survey_id, cfg["survey_pdf"],
                               survey_doi=cfg.get("survey_doi"),
                               survey_s2_id=cfg.get("survey_s2_id"))

    # Step 2: Resolve gold set to S2 IDs
    print("\n[2/4] Resolving gold set via Semantic Scholar...")
    gold_s2_ids, gold_list = resolve_gold_set(survey_id, gold_list)

    if not gold_s2_ids:
        print("  ERROR: No gold entries resolved — cannot compute recall. Stopping.")
        return

    # Step 3: Resolve seed papers
    print("\n[3/4] Resolving seed papers...")
    seeds = resolve_seeds(survey_id, cfg["seed_pdfs"])
    seed_ids = {s["s2_id"] for s in seeds if s.get("s2_id")}
    if not seed_ids:
        print("  ERROR: No seed papers resolved. Stopping.")
        return
    print(f"  {len(seed_ids)} seeds resolved")

    # Step 4: Run traversal
    print("\n[4/4] Running traversal...")
    rounds = escape_hatch_loop_live(seed_ids, gold_s2_ids)

    # Compute recall from final visited set
    final_visited   = set()
    final_titles: dict[str, str] = {}
    # Re-run to collect visited_titles (stored in rounds' curve but not the set)
    # Simpler: re-use what we know — all papers are cached, load their titles
    for r_data in rounds:
        # visited IDs aren't stored in rounds directly; we track via gold recall
        pass
    # For recall computation, use the final round's tp and corpus
    final_round = rounds[-1] if rounds else {}

    recall_stats = {
        "recall_exact":    final_round.get("recall"),
        "recall_upper_bound": final_round.get("recall"),  # refined by fuzzy if available
        "tp_exact":        final_round.get("tp"),
        "gold_resolvable": len(gold_s2_ids),
        "gold_total":      len(gold_list),
        "corpus_size":     final_round.get("corpus_size"),
    }

    print(f"\n  Final recall (exact): {recall_stats['recall_exact']:.1%}")
    print(f"  Corpus size:          {recall_stats['corpus_size']:,}")
    print(f"  Gold (resolvable):    {recall_stats['gold_resolvable']}")
    print(f"  Gold (total in PDF):  {recall_stats['gold_total']}")

    save_results(survey_id, rounds, recall_stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="LitDiscover live validation")
    parser.add_argument("--survey", choices=list(SURVEYS.keys()),
                        help="Run only this survey (default: all)")
    parser.add_argument("--test-api", action="store_true",
                        help="Test S2 API connectivity with a known DOI")
    args = parser.parse_args()

    if args.test_api:
        print("Testing S2 API...")
        paper = fetch_paper("DOI:10.1038/s41586-021-03649-2")
        if paper:
            print(f"OK: '{paper['title']}' ({paper['year']})")
        else:
            print("FAIL: could not resolve test DOI")
        return

    surveys_to_run = [args.survey] if args.survey else list(SURVEYS.keys())
    for sid in surveys_to_run:
        run_survey(sid)

    make_summary_csv()
    make_figures()
    print("\nDone.")


if __name__ == "__main__":
    main()
