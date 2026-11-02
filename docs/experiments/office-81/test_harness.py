"""Protocol and failure tests; never invoke a real model."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("office81_run", Path(__file__).with_name("run.py"))
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


def response():
    return {"status": "ready", "answer": "A public result", "evidence_ids": ["F1"], "unknowns": [], "handoff": []}


class HarnessTests(unittest.TestCase):
    def test_rejects_invented_evidence_and_hidden_fields(self):
        value = response()
        value["evidence_ids"] = ["F999"]
        with self.assertRaises(ValueError):
            harness.validate_response(value, {"F1"})
        value = response()
        value["reasoning"] = "not a public output"
        with self.assertRaises(ValueError):
            harness.validate_response(value, {"F1"})

    def test_partial_failure_is_not_complete_execution(self):
        agents = [{"id": f"agent_{i}", "capability": f"c{i // 9}", "question": "q", "instruction": "i"} for i in range(81)]
        case = {"id": "synthetic", "task": "draft", "facts": [{"id": "F1", "text": "fiction"}], "unknowns": [], "expected": ["secret evaluator answer"]}

        def fake_call(agent_id, prompt, fact_ids, timeout):
            self.assertNotIn("secret evaluator answer", prompt)
            if agent_id == "agent_6":
                self.assertIn("worker_exception", prompt)
                self.assertIn("agent_5", prompt)
            if agent_id == "agent_5":
                raise RuntimeError("failure detail must not be persisted")
            return {"id": agent_id, "status": "completed", "response": response()}

        with contextlib.redirect_stdout(io.StringIO()):
            results = harness.run_agents(case, agents, 3, 30, call=fake_call)
        summary = harness.summarize(results)
        self.assertEqual(summary["attempted_agents"], 81)
        self.assertEqual(summary["completed_agents"], 80)
        self.assertEqual(summary["failed_agents"], 1)
        self.assertFalse(summary["complete_execution"])
        self.assertEqual([r["id"] for r in results], [a["id"] for a in agents])

    def test_tool_execution_is_rejected(self):
        self.assertTrue(harness.tool_event_seen([{"type": "item.completed", "item": {"type": "command_execution"}}]))
        self.assertFalse(harness.tool_event_seen([{"type": "item.completed", "item": {"type": "agent_message"}}]))

    def test_invocation_is_ephemeral_and_uses_isolated_cwd(self):
        captured = {}

        class FakeProcess:
            returncode = 0

            def __init__(self, command, **kwargs):
                captured["command"] = command
                captured["options"] = kwargs
                self.answer = Path(command[command.index("--output-last-message") + 1])

            def communicate(self, prompt=None, timeout=None):
                self.answer.write_text(json.dumps(response()), encoding="utf-8")
                return '{"type":"turn.completed","usage":{"input_tokens":3}}\n', "private diagnostics"

        with patch.object(harness.subprocess, "Popen", FakeProcess):
            result = harness.invoke("test", "synthetic prompt", {"F1"}, 30)
        self.assertEqual(result["status"], "completed")
        for flag in ("--ephemeral", "--ignore-user-config", "--output-schema", "--skip-git-repo-check"):
            self.assertIn(flag, captured["command"])
        self.assertEqual(captured["command"][captured["command"].index("--sandbox") + 1], "read-only")
        self.assertNotIn("shell", captured["options"])
        scratch = captured["options"]["cwd"]
        self.assertNotEqual(Path(scratch).resolve(), harness.ROOT)
        self.assertFalse(Path(scratch).exists())
        self.assertNotIn("private diagnostics", json.dumps(result))

    def test_dry_run_does_not_invoke_model(self):
        case = {"id": "synthetic"}
        agents = [{"id": f"a{i}"} for i in range(81)]
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(harness, "ROOT", Path(folder)), patch.object(harness, "load_inputs", return_value=(case, agents)), patch.object(harness, "invoke") as invoke:
                live = Path(folder) / "results/run.json"
                live.parent.mkdir()
                live.write_text("existing live result")
                with contextlib.redirect_stdout(io.StringIO()):
                    code = harness.main(["--dry-run"])
                self.assertEqual(live.read_text(), "existing live result")
                invoke.assert_not_called()
                report = json.loads((Path(folder) / "results/dry-run.json").read_text())
                self.assertEqual(code, 0)
                self.assertEqual(report["model_calls_attempted"], 0)
                self.assertFalse(report["summary"]["complete_execution"])


if __name__ == "__main__":
    unittest.main()
