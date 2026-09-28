#!/usr/bin/env python3
"""Public, read-only structural check for bounded native obligations only."""
import json
import sys
from pathlib import Path


def main():
    mode = sys.argv[1]
    if mode == "design":
        design = json.loads(Path("design.json").read_text())
        required = {"api", "state_transitions", "ownership", "persistence", "migration", "compatibility", "examples"}
        assert required <= design.keys()
        assert all(design[key] for key in required)
        assert len(design["examples"]) >= 4
        assert len(Path("design.md").read_text().strip()) > 300
    elif mode == "implementation":
        names = ["main.go", "api.go", "store.go", "domain.go", "main_test.go", "web/app.ts", "web/api.ts", "web/view.ts", "web/index.html", "web/style.css", "RUNBOOK.md"]
        assert all(Path(name).is_file() and 0 < Path(name).stat().st_size <= 65536 for name in names)
        assert len(Path("RUNBOOK.md").read_text().strip()) > 100
    else:
        raise ValueError("unknown mode")


if __name__ == "__main__":
    main()
