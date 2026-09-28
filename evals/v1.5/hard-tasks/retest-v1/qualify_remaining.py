"""Partition the frozen check commands without rerunning completed qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", type=Path, required=True)
    args = parser.parse_args()
    manifest = runner.read(runner.HERE / "manifest.json")
    pending = []
    for cell in manifest["cells"]:
        out = runner.HERE / "results" / cell["id"]
        if not (out / "call.json").exists():
            continue
        marker = "build.json" if cell["task"] == "coding" else "office-check-command.json"
        if not (out / marker).exists():
            pending.append(cell)
    runner.qualify({**manifest, "cells": pending}, args.storage)
    for cell in manifest["cells"]:
        out = runner.HERE / "results" / cell["id"]
        if (
            cell["task"] != "office"
            or not (out / "call.json").exists()
            or (out / "office-display.json").exists()
        ):
            continue
        base = args.storage / cell["id"]
        result = runner.bounded(
            [
                str(runner.PYTHON),
                str(runner.HERE / "office_display.py"),
                str(base / "workspace/output"),
                "--report",
                str(out / "office-display.json"),
            ],
            base / "workspace",
            runner.read(base / "environment.json"),
            120,
        )
        runner.save(
            out / "display-check-command.json",
            json.loads(runner.sanitize(json.dumps(result), base)),
        )
    print(
        json.dumps({"new_qualification_cells": [cell["id"] for cell in pending], "model_calls": 0})
    )


if __name__ == "__main__":
    main()
