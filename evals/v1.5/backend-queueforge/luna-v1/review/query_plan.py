"""Read-only query-plan observation after all timed loads; no candidate edit."""

import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    assert (ROOT / "evidence/execution.completed.json").exists()
    rows = []
    for arm in ("vanilla", "v1.4.0", "v1.5.0-rc"):
        path = ROOT / "evidence/performance-stage3" / arm / "seed/seed.sqlite"
        if not path.exists():
            rows.append({"arm": arm, "status": "unavailable", "reason": "no final seed database"})
            continue
        before = sha(path)
        column = "available_at_ms" if arm == "vanilla" else "available_at"
        query = f"SELECT id FROM jobs WHERE tenant=? AND queue=? AND state='ready' AND {column}<=? ORDER BY priority DESC,created_seq LIMIT 1"
        with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            plan = db.execute("EXPLAIN QUERY PLAN " + query, ("bench0", "mail", 2**60)).fetchall()
            indexes = db.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='jobs' ORDER BY name").fetchall()
        assert before == sha(path)
        rows.append({"arm": arm, "status": "observed", "query": query, "parameters": ["bench0", "mail", 2**60], "plan": plan, "indexes": indexes, "seed_sha256_unchanged": before})
    output = {"scope": "Post-outcome, post-load immutable read-only EXPLAIN; no actual query timing, candidate edits or model calls", "sqlite_engine": {"surface": "host Python sqlite3, not the measured Go process", "version": sqlite3.sqlite_version}, "rows": rows, "interpretation_limit": "Architectural aid from a separately identified SQLite planner, not proof of the measured Go driver's runtime plan or a controlled attribution of the throughput difference."}
    (ROOT / "review/query-plans.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"plans": [{"arm": r["arm"], "plan": r.get("plan")} for r in rows]}))


if __name__ == "__main__":
    main()
