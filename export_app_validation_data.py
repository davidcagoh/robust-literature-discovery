from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_DIR = Path("/Users/davidgoh/LocalFiles/2025-26-Ongoing/automated-lit-reviews-v2")
OUT_DIR = Path("/Users/davidgoh/LocalFiles/2025-26-Ongoing/comprehensive-citations/app-validation-data")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_env(path: Path) -> None:
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()


load_env(APP_DIR / ".env")
sys.path.insert(0, str(APP_DIR))

from litreview2.db.client import get_client, count_by_status  # noqa: E402

TARGET_SLUGS = [
    "automated-lit-review-methodology",
    "self-supervised-pretraining",
    "stochastic-proof-search",
    "jepa-learning-order",
    "lightroom-pal",
]


def main() -> None:
    db = get_client()
    projects = (
        db.table("projects")
        .select("id,slug,title,criteria,created_at,updated_at")
        .in_("slug", TARGET_SLUGS)
        .execute()
        .data
    ) or []

    projects = sorted(projects, key=lambda r: TARGET_SLUGS.index(r["slug"]))
    all_logs = []
    summary = []

    for p in projects:
        pid = p["id"]
        counts = count_by_status(db, pid)
        rows = (
            db.table("screening_log")
            .select("project_id,round,papers_screened,papers_included,papers_excluded,papers_uncertain,yield_rate,criteria_version,trigger,created_at")
            .eq("project_id", pid)
            .order("created_at")
            .execute()
            .data
        ) or []
        for row in rows:
            row["slug"] = p["slug"]
            row["title"] = p["title"]
        all_logs.extend(rows)
        nonzero = [r for r in rows if (r.get("papers_screened") or 0) > 0]
        summary.append(
            {
                "slug": p["slug"],
                "title": p["title"],
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
                "status_counts": counts,
                "screening_rows_total": len(rows),
                "screening_rows_nonzero": len(nonzero),
                "overall_screened": sum((r.get("papers_screened") or 0) for r in nonzero),
                "overall_included": sum((r.get("papers_included") or 0) for r in nonzero),
                "overall_batch_yield": (
                    sum((r.get("papers_included") or 0) for r in nonzero)
                    / sum((r.get("papers_screened") or 0) for r in nonzero)
                    if sum((r.get("papers_screened") or 0) for r in nonzero) > 0
                    else None
                ),
                "recent_nonzero_rows": nonzero[-10:],
            }
        )

    (OUT_DIR / "projects_summary.json").write_text(json.dumps(summary, indent=2))
    (OUT_DIR / "screening_log_selected_projects.json").write_text(json.dumps(all_logs, indent=2))
    print(f"Wrote {OUT_DIR / 'projects_summary.json'}")
    print(f"Wrote {OUT_DIR / 'screening_log_selected_projects.json'}")


if __name__ == "__main__":
    main()
