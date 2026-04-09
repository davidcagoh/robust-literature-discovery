"""
Phase 2: Extract ground-truth reference sets for the three chosen survey papers.

Surveys:
  S1: RevModPhys.70.1039  — Metal-insulator transitions (Imada et al., 1998)
  S2: RevModPhys.80.885   — Many-body physics with ultracold gases (Bloch et al., 2008)
  S3: RevModPhys.91.015006 — Topological photonics (Ozawa et al., 2019)

For each survey we extract:
  - gold_refs:   the set of APS papers it cites (backward neighbours in the corpus)
  - gold_citers: the set of APS papers that cite it (forward neighbours)
  - combined gold set = gold_refs ∪ gold_citers  (everything 1-hop away)

We also record:
  - Total APS papers (nodes)
  - Total APS edges
  - In-degree and out-degree of each survey paper
"""

import pandas as pd
import json
from pathlib import Path

_REPO = Path(__file__).parent.parent
APS_CSV = _REPO / "data-aps" / "processed" / "aps-dataset-citations-2022.csv"
OUT = _REPO / "data-aps" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

SURVEYS = {
    "S1_MIT":   "10.1103/RevModPhys.70.1039",
    "S2_UCG":   "10.1103/RevModPhys.80.885",
    "S3_TOPO":  "10.1103/RevModPhys.91.015006",
}

SURVEY_META = {
    "S1_MIT":  {"title": "Metal-insulator transitions", "authors": "Imada, Fujimori, Tokura", "year": 1998},
    "S2_UCG":  {"title": "Many-body physics with ultracold gases", "authors": "Bloch, Dalibard, Zwerger", "year": 2008},
    "S3_TOPO": {"title": "Topological photonics", "authors": "Ozawa et al.", "year": 2019},
}

print("Loading APS citation graph...")
df = pd.read_csv(APS_CSV)
print(f"  Edges: {len(df):,}")

all_nodes = set(df["citing_doi"].unique()) | set(df["cited_doi"].unique())
print(f"  Nodes: {len(all_nodes):,}")

# Build adjacency sets for fast lookup
print("Building adjacency index...")
# cited_by[paper] = set of papers that cite it (forward neighbours)
# cites[paper]    = set of papers it cites (backward neighbours)
from collections import defaultdict
cites    = defaultdict(set)   # out-edges: paper -> what it cites
cited_by = defaultdict(set)   # in-edges:  paper -> who cites it

for row in df.itertuples(index=False):
    cites[row.citing_doi].add(row.cited_doi)
    cited_by[row.cited_doi].add(row.citing_doi)

print("Extracting ground-truth sets...")
results = {}
for key, doi in SURVEYS.items():
    gold_refs   = cites.get(doi, set())       # papers the survey cites
    gold_citers = cited_by.get(doi, set())    # papers that cite the survey
    gold_1hop   = gold_refs | gold_citers

    results[key] = {
        "doi": doi,
        **SURVEY_META[key],
        "out_degree":   len(gold_refs),
        "in_degree":    len(gold_citers),
        "gold_refs":    sorted(gold_refs),
        "gold_citers":  sorted(gold_citers),
        "gold_1hop":    sorted(gold_1hop),
    }

    print(f"\n  {key} ({doi})")
    print(f"    APS refs cited by survey (out-degree): {len(gold_refs)}")
    print(f"    APS papers citing survey (in-degree):  {len(gold_citers)}")
    print(f"    Combined 1-hop gold set:               {len(gold_1hop)}")

# Save results
out_file = OUT / "ground_truth.json"
# Convert sets to lists for JSON serialisation
with open(out_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nSaved ground truth to {out_file}")

# Also save corpus stats
corpus_stats = {
    "n_nodes": len(all_nodes),
    "n_edges": len(df),
}
with open(OUT / "corpus_stats.json", "w") as f:
    json.dump(corpus_stats, f, indent=2)

print("Done.")
