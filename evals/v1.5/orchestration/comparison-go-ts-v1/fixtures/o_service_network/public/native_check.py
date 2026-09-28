#!/usr/bin/env python3
"""Public, read-only static checks. Numeric qualification is external."""
import hashlib
import json
import re
import sys
from pathlib import Path


def main():
    mode = sys.argv[1]
    if mode == "analysis":
        metrics = json.loads(Path("metrics.json").read_text())
        sources = json.loads(Path("sources.json").read_text())
        assert {"selection", "backlog", "sla", "capacity", "part_cost", "portfolios", "sensitivity"} <= metrics.keys()
        expected = {"orders-v1": "orders.json", "events-v1": "events.json", "sla-v1": "sla_policies.json", "capacity-v1": "capacity.json", "rates-v1": "supplier_rates.json", "shared-v1": "shared_costs.json"}
        assert isinstance(sources, list) and len(sources) == len(expected)
        assert {source["id"] for source in sources} == set(expected)
        for source in sources:
            source_id, name, digest = source["id"], source["path"], source["sha256"]
            assert name == expected[source_id]
            assert re.fullmatch(r"[0-9a-f]{64}", digest)
            data = Path(f"inputs/{source_id}/{name}").read_bytes()
            assert hashlib.sha256(data).hexdigest() == digest
        assert Path("analysis.go").is_file() and Path("analysis.go").stat().st_size > 100
    elif mode == "document":
        memo = Path("memo.md").read_text()
        assert len(memo.strip()) > 300
        assert "| /" in memo and "risk" in memo.lower()
        assert Path("metrics.json").is_file()
    else:
        raise ValueError("unknown mode")


if __name__ == "__main__":
    main()
