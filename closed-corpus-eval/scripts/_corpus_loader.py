"""
closed-corpus-eval/scripts/_corpus_loader.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shared APS closed-corpus loader. Centralises the cites/cited_by adjacency
construction that eval/01, eval/02, eval/03, eval/04b, eval/05, sweep/04,
sweep/07_rounds_sweep.py, and sweep/08 each previously re-derived
independently from the raw CSV (9 separate re-derivations of the same
~530MB, 9.8M-row parse) — see wiki/litdiscover/phase-discovery-roadmap.md
§1.2. Also builds a litdiscover.discovery.graph_source.ClosedCorpusSource so
the real production discovery operators (backward_traversal_operator,
forward_traversal_operator, pareto_hub_threshold, author_expansion_operator)
can run against this corpus instead of a hand-rolled traversal loop.

New scripts should import this module rather than rebuilding the adjacency
index inline. Existing scripts (eval/01 etc.) are migrated separately, one
at a time, per wiki/litdiscover/phase-discovery-roadmap.md §1.3's plan.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from litdiscover.discovery.graph_source import ClosedCorpusSource

_TRACK_ROOT = Path(__file__).parent.parent
APS_CSV = _TRACK_ROOT / "data" / "processed" / "aps-dataset-citations-2022.csv"


def load_adjacency(csv_path: Path = APS_CSV) -> tuple[dict[str, set], dict[str, set]]:
    """Load the APS citation CSV into (cites, cited_by) adjacency dicts.
    cites[doi] = set of DOIs it cites (out-edges); cited_by[doi] = set of
    DOIs that cite it (in-edges)."""
    df = pd.read_csv(csv_path)
    cites: dict[str, set] = defaultdict(set)
    cited_by: dict[str, set] = defaultdict(set)
    for row in df.itertuples(index=False):
        cites[row.citing_doi].add(row.cited_doi)
        cited_by[row.cited_doi].add(row.citing_doi)
    return cites, cited_by


def build_closed_corpus_source(cites: dict[str, set], cited_by: dict[str, set],
                                author_to_dois: dict[str, set] | None = None
                                ) -> tuple[ClosedCorpusSource, dict[str, dict]]:
    """
    Build a ClosedCorpusSource over the given adjacency.

    `citation_count` on emitted paper dicts = in-degree within THIS closed
    corpus (len(cited_by[doi])) — not comparable to a live S2 citation_count,
    which counts citations across all of S2's index, not just APS physics.
    See wiki/litdiscover/phase-discovery-roadmap.md §1.3's corpus-scope
    caveat: same algorithm, same code path, different population, so
    "hub-ness" is a different number even after unification.

    `title` is left as the DOI itself — this dataset (verified directly
    against aps-2022-author-doi-citation-affil.mat via h5py before this
    module was written) carries DOI, authors, affiliations, and publication
    date, but no title or abstract text anywhere.
    """
    all_dois = set(cites.keys()) | set(cited_by.keys())
    doi_to_paper = {
        doi: {"doi": doi, "title": doi, "year": None,
              "citation_count": len(cited_by.get(doi, ()))}
        for doi in all_dois
    }
    source = ClosedCorpusSource(
        cites=cites, cited_by=cited_by, doi_to_paper=doi_to_paper,
        author_to_dois=author_to_dois or {},
    )
    return source, doi_to_paper
