"""Resume postprocessing without repeating or overwriting any frozen result.

Calls the unchanged frozen qualification functions. Generation never resumes here.
"""

import argparse
from pathlib import Path
import time

import runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    args = parser.parse_args()
    manifest = runner.verify(
        "8fafe6f815d30724ac4f5568cf494bcfd0a4d38dfe56de0054aebf8e3732c00e", args.packages
    )
    for cell in manifest["cells"]:
        result = runner.HERE / "results" / cell["id"]
        assert any(
            (result / name).exists()
            for name in ("call.json", "harness-failure.json", "skipped.json")
        ), "Generation must finish first"
    remaining = []
    for cell in manifest["cells"]:
        result = runner.HERE / "results" / cell["id"]
        if not (result / "call.json").exists():
            continue
        sentinel = "own-tests.json" if cell["task"] == "coding" else "office-check-command.json"
        if not (result / sentinel).exists():
            remaining.append(cell)
    runner.save(
        runner.HERE / "qualification-remaining.json",
        {
            "started_unix": time.time(),
            "cells": [cell["id"] for cell in remaining],
            "method": "Unchanged frozen runner.qualify; existing office results skipped, never overwritten; zero model calls",
        },
    )
    manifest["cells"] = remaining
    runner.qualify(manifest, args.storage)


if __name__ == "__main__":
    main()
