"""Exercise the synthetic bench adapter with a fake local CLI, not a model."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools/v2_codex_bench_adapter.py"
REQUEST = {
    "schema": "opensocrates.v2-bench-request/1",
    "condition": "baseline",
    "prompt": "Draft a fictional message.",
    "materials": ["The venue is undecided."],
    "skill_text": None,
    "transport": {"instruction": "Return the requested JSON envelope."},
}


class CodexAdapterChecks(unittest.TestCase):
    def run_with_fake_cli(self, *, use_tool: bool) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "codex"
            fake.write_text(
                f"#!{sys.executable}\n"
                "import json, sys\n"
                "sys.stdin.read()\n"
                + (
                    "print(json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution'}}))\n"
                    if use_tool
                    else ""
                )
                + "payload = {'schema': 'opensocrates.v2-bench-envelope/1', "
                "'body': 'Draft', 'requester_notes': ''}\n"
                "print(json.dumps({'type': 'item.completed', 'item': "
                "{'type': 'agent_message', 'text': json.dumps(payload)}}))\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = dict(os.environ)
            env["PATH"] = directory + os.pathsep + env.get("PATH", "")
            return subprocess.run(
                [sys.executable, str(ADAPTER)],
                input=json.dumps(REQUEST),
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

    def test_fake_cli_envelope_is_passed_without_a_model_claim(self):
        result = self.run_with_fake_cli(use_tool=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["body"], "Draft")
        self.assertNotIn("model_called", json.loads(result.stdout))

    def test_observed_tool_execution_rejects_result(self):
        result = self.run_with_fake_cli(use_tool=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
