"""Frozen preceding producer. Its output predates source_revision and factor."""
import json
from pathlib import Path
import sys


def produce(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    value = {"run_id": "legacy-1", "template_name": "alpha",
             "stages": [{"name": "old-stage", "workers": 3, "options": {"labels": ["historic"]}}],
             "total_workers": 3}
    (root / "legacy-1.json").write_text(json.dumps(value))


if __name__ == "__main__":
    produce(sys.argv[1])
