"""Executable completion fixtures. Observations stay separate from caller reports."""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from opensocrates.cli.assistance import run_assistance

ROOT = Path(__file__).resolve().parents[1]


def observe_fixtures() -> dict[str, bool]:
    """New disposable fixtures, never edits to frozen model-produced candidates."""
    with tempfile.TemporaryDirectory(prefix="opensocrates-verification-") as temporary:
        base = Path(temporary)
        (base / "store.py").write_text("def open_reader():\n    return 64\n", encoding="utf-8")
        test_body = "import unittest\nfrom store import open_db\nclass Caller(unittest.TestCase):\n    def test_capacity(self):\n        self.assertEqual(open_db(), 64)\n"
        (base / "test_store.py").write_text(test_body, encoding="utf-8")

        def execute(*args):
            return subprocess.run(
                [sys.executable, "-B", *args], cwd=base, capture_output=True, timeout=20
            )

        api = execute("-c", "from store import open_reader; assert open_reader() == 64")
        broken = execute("-m", "unittest", "test_store")
        assert api.returncode == 0 and broken.returncode != 0
        assert b"open_db" in broken.stderr
        (base / "store.py").write_text(
            "def open_reader():\n    return 64\ndef open_db():\n    return open_reader()\n",
            encoding="utf-8",
        )
        repaired = execute("-m", "unittest", "test_store")
        assert repaired.returncode == 0
        assert (base / "test_store.py").read_text(encoding="utf-8") == test_body

        source = {"attendees": 26, "capacity": 30, "cost": 0}
        (base / "plan.json").write_text(json.dumps(source), encoding="utf-8")
        (base / "memo.txt").write_text("Attendees: 25\n", encoding="utf-8")
        (base / "table.csv").write_text("metric,value,unit\nattendees,26,KRW\n", encoding="utf-8")
        data = json.loads((base / "plan.json").read_text(encoding="utf-8"))
        row = next(csv.DictReader(io.StringIO((base / "table.csv").read_text(encoding="utf-8"))))
        calculation = data["attendees"] <= data["capacity"] and data["cost"] == 0
        narrative = (
            int((base / "memo.txt").read_text(encoding="utf-8").split(":")[1]) == data["attendees"]
        )
        units = row["unit"] == "people" and int(row["value"]) == data["attendees"]
        assert calculation and not narrative and not units
        return {
            "api": True,
            "broken_caller": False,
            "repaired_caller": True,
            "calculation": calculation,
            "narrative": narrative,
            "units": units,
        }


def exercise(command, root=ROOT) -> dict[str, object]:
    observed = observe_fixtures()
    calls = 0

    def plan(value):
        nonlocal calls
        calls += 1
        result = command("assistance", value)
        assert result["status"] == "ok", result
        assert result["application"] == "unverified"
        return result

    def report(item, met, evidence):
        item.update(
            status="met" if met else "unmet", evidence_refs=[evidence], attribution="agent_reported"
        )

    for locale in ("en", "ko"):
        coding = json.loads(
            (root / "plugin-src/shared/assistance/verification-coding.json").read_text(
                encoding="utf-8"
            )
        )
        coding["locale"] = locale
        api, callers, tests, performance = coding["obligations"]
        report(api, observed["api"], "fixture:api")
        report(callers, observed["broken_caller"], "fixture:caller-test")
        result = plan(coding)
        assert result["next_action"] == "continue"
        assert result["obligation_summary"]["blocking_ids"] == ["callers", "tests"]
        assert result["obligation_summary"]["ready_ids"] == ["callers"]
        report(callers, observed["repaired_caller"], "fixture:caller-repair")
        report(tests, observed["repaired_caller"], "fixture:tests")
        assert plan(coding)["next_action"] == "finish", "optional performance became a prerequisite"
        performance["required"] = True
        assert plan(coding)["next_action"] == "continue", "requested performance was skipped"
        # This is a reported-state transition, not a performance benchmark.
        report(performance, True, "fixture:reported-performance")
        assert plan(coding)["next_action"] == "finish"
        tests["evidence_refs"] = []
        assert plan(coding)["next_action"] == "continue", (
            "unsubstantiated met report closed the task"
        )

        artifacts = json.loads(
            (root / "plugin-src/shared/assistance/verification-artifacts.json").read_text(
                encoding="utf-8"
            )
        )
        artifacts["locale"] = locale
        for item in artifacts["obligations"]:
            report(item, observed[item["obligation_id"]], "fixture:" + item["obligation_id"])
        result = plan(artifacts)
        assert result["next_action"] == "continue"
        assert result["obligation_summary"]["blocking_ids"] == ["narrative", "units"]
        # Do not label unseen corrections as independently observed.
        for item in artifacts["obligations"]:
            report(item, True, "fixture:reported-reconciliation")
        assert plan(artifacts)["next_action"] == "finish"
        artifacts["obligations"][1]["attribution"] = "unknown"
        assert plan(artifacts)["next_action"] == "continue"
    return {
        "status": "pass",
        "languages": ["en", "ko"],
        "command_calls": calls,
        "model_calls": 0,
        "observations": observed,
        "reported_state_is_not_native_proof": True,
    }


def main() -> int:
    def command(mode, value):
        assert mode == "assistance"
        output = io.StringIO()
        assert run_assistance(io.StringIO(json.dumps(value)), output) == 0
        return json.loads(output.getvalue())

    print(json.dumps(exercise(command), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
