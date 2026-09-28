#!/usr/bin/env python3
"""No-model exact child-policy read canary; prints only verdicts and policy hash."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    candidate, policy = args.candidate.resolve(), args.policy.resolve()
    oracle = ROOT / "private/qualify.py"
    link = candidate / ".eval-oracle-link"
    link.symlink_to(oracle)
    tests = {
        "candidate_read_allowed": (candidate / "main.go", 0),
        "private_oracle_direct_denied": (oracle, 1),
        "private_oracle_symlink_denied": (link, 1),
    }
    results = []
    for name, (path, expected) in tests.items():
        process = subprocess.run(["/usr/bin/sandbox-exec", "-f", str(policy), "/bin/cat", str(path)], cwd=candidate, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
        results.append({"id": name, "passed": (process.returncode == 0) if expected == 0 else (process.returncode != 0), "exit_code": process.returncode})
    receipt = {"passed": all(item["passed"] for item in results), "policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(), "checks": results}
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
