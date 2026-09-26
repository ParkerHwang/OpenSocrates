"""Offline preservation and before/after request-state regression check; no models."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def aggregate(paths):
    return digest(
        "".join(f"{p}\0{digest((ROOT / p).read_bytes())}\n" for p in sorted(paths)).encode()
    )


def main():
    baseline = json.loads((HERE / "baseline.json").read_text())
    assert digest((HERE / "PLAN.md").read_bytes()) == baseline["plan_sha256"]
    paths = subprocess.check_output(["git", "ls-files", "evals/"], cwd=ROOT, text=True).splitlines()
    paths = [
        p
        for p in paths
        if p != "evals/v1.5/STATUS.md" and not p.startswith("evals/v1.5/revision-v4/")
    ]
    assert len(paths) == baseline["historical_evidence"]["file_count"]
    assert aggregate(paths) == baseline["historical_evidence"]["tree_sha256"]
    schemas = [p.relative_to(ROOT).as_posix() for p in (ROOT / "schemas/v1").glob("*.json")]
    assert len(schemas) == baseline["schema_bytes"]["count"] == 47
    assert aggregate(schemas) == baseline["schema_bytes"]["tree_sha256"]

    qualified_count = None
    validation_path = HERE / "validation.json"
    if validation_path.exists():
        validation = json.loads(validation_path.read_text())
        for group in ("runtime_input_hashes", "qualification_input_hashes"):
            for path, expected in validation[group].items():
                assert digest((ROOT / path).read_bytes()) == expected, path
        assert (
            digest((HERE / "native-release.json").read_bytes())
            == validation["native_report_sha256"]
        )
        qualified_count = len(validation["runtime_input_hashes"])
    repair_path = HERE / "ci-repair.json"
    if repair_path.exists():
        repair = json.loads(repair_path.read_text())["repair"]
        assert digest((ROOT / repair["file"]).read_bytes()) == repair["sha256"]

    import check_decision_points as fixtures
    from opensocrates.selector.decision import DecisionSession

    fixtures.DecisionChecks.setUpClass()
    old_source = subprocess.check_output(
        ["git", "show", baseline["base_commit"] + ":src/opensocrates/selector/decision.py"],
        cwd=ROOT,
        text=True,
    )
    name = "opensocrates.selector.revision_v4_baseline"
    old = types.ModuleType(name)
    old.__package__ = "opensocrates.selector"
    sys.modules[name] = old
    exec(compile(old_source, name, "exec"), old.__dict__)
    state = {}
    for label, constructor in (("before", old.DecisionSession), ("after", DecisionSession)):
        session = constructor(fixtures.DecisionChecks.bundle, fixtures.DecisionChecks.assembler)
        selected = session.handle(fixtures.request())
        session.handle(
            dict(
                operation="acknowledge",
                context="a" * 32,
                epoch=0,
                digests=[selected["methods"][0]["sha256"]],
            )
        )
        invalid = fixtures.request(context="b" * 32)
        invalid["routing"]["features"][0]["basis"] = "governing_rule"
        rejection = session.handle(invalid)
        assert rejection["status"] == "unavailable"
        state[label] = {
            "scope_preserved": session.scope == ("a" * 32, 0),
            "acknowledgment_preserved": bool(session.available),
            "diagnostic_present": "diagnostic" in rejection,
        }
    assert state["before"] == dict.fromkeys(state["before"], False)
    assert state["after"] == dict.fromkeys(state["after"], True)
    print(
        json.dumps(
            {
                "status": "pass",
                "historical_files_unchanged": len(paths),
                "schema_files_unchanged": len(schemas),
                "qualified_runtime_inputs": qualified_count,
                "decision_regression": state,
                "model_calls": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
