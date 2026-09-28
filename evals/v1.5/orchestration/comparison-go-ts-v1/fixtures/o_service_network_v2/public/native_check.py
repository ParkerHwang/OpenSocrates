#!/usr/bin/env python3
"""Public read-only structural checks; numeric execution is external."""
import hashlib
import json
import re
import sys
from pathlib import Path

FILES = {
    "manifest-v2": "manifest.json",
    "orders-v2": "orders.json",
    "events-initial-v2": "events_initial.json",
    "events-corrections-v2": "events_corrections.json",
    "sla-v2": "sla_policies.json",
    "rates-v2": "supplier_rates.json",
    "capacity-v2": "capacity.json",
    "shared-v2": "shared_costs.json",
    "portfolios-v2": "portfolios.json",
}


def main() -> None:
    mode = sys.argv[1]
    if mode == "analysis":
        metrics = json.loads(Path("metrics.json").read_text())
        assert {"selection", "backlog", "sla", "cost", "capacity", "portfolios", "eligible_ranking", "sensitivity"} <= metrics.keys()
        register = json.loads(Path("sources.json").read_text())
        assert isinstance(register, list) and len(register) == len(FILES)
        assert {item["id"] for item in register} == set(FILES)
        for item in register:
            source_id = item["id"]
            name = item["path"]
            digest = item["sha256"]
            assert name == FILES[source_id]
            assert re.fullmatch(r"[0-9a-f]{64}", digest)
            staged = Path("inputs") / source_id / name
            assert hashlib.sha256(staged.read_bytes()).hexdigest() == digest
        assert Path("analysis.go").is_file() and 100 < Path("analysis.go").stat().st_size <= 65536
    elif mode == "document":
        memo = Path("memo.md").read_text()
        assert len(memo.strip()) > 500
        assert "| /portfolios/" in memo
        assert re.search(r"(?m)^Recommendation:\s*\S+", memo)
        assert Path("metrics.json").is_file()
    else:
        raise ValueError("unknown mode")


if __name__ == "__main__":
    main()
