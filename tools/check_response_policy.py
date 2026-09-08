"""Presentation sidecar, locale separation and protected-contract regressions."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from check_decision_points import request
from opensocrates.cli.decision import run_decision
from opensocrates.content.injection import ProjectionInstructionAssembler
from opensocrates.content.loader import load_compiled_bundle, load_reasoning_content_projections
from opensocrates.rendering.response_policy import (
    load_compiled_response_policy,
    load_response_policy,
    measure_visible_output,
    policy_identity,
    response_guidance,
    validate_response_policy,
)
from opensocrates.selector.decision import DecisionSession

ROOT = Path(__file__).resolve().parents[1]


class ResponsePolicyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_response_policy(ROOT / "content/response-policy.yaml")

    def test_all_eighteen_profiles_and_deterministic_default(self):
        seen = 0
        for locale, profile in self.policy["locales"].items():
            for shape in profile["shapes"]:
                guide = response_guidance(self.policy, locale, shape)
                self.assertEqual(guide["enforcement"], "guided")
                self.assertEqual(guide["application"], "unverified")
                self.assertIn(profile["protected_rule"], guide["instructions"])
                self.assertEqual(guide["sha256"], policy_identity(self.policy))
                seen += 1
            self.assertEqual(
                response_guidance(self.policy, locale, "unknown")["answer_shape"], "default"
            )
        self.assertEqual(seen, 18)

    def test_no_cap_or_missing_protected_contract_can_enter_policy(self):
        for mutate in (
            lambda p: p.update(max_words=80),
            lambda p: p.update(enforcement="verified"),
            lambda p: p["protected_contracts"].remove("card_sections"),
            lambda p: p["locales"]["ko"]["shapes"].pop("default"),
        ):
            candidate = deepcopy(self.policy)
            mutate(candidate)
            with self.assertRaises(ValueError):
                validate_response_policy(candidate)

    def test_locale_sources_are_separate_and_compiled_identity_matches(self):
        manifest = json.loads((ROOT / "content/response-policy.yaml").read_text())
        self.assertEqual(
            manifest["locales"], {"en": "response-policy/en.yaml", "ko": "response-policy/ko.yaml"}
        )
        self.assertEqual(
            self.policy,
            load_compiled_response_policy(ROOT / "content/compiled-response-policy.json"),
        )

    def test_selected_sidecar_does_not_change_canonical_method(self):
        bundle = load_compiled_bundle(ROOT / "content/compiled-content.bundle.json")
        assembler = ProjectionInstructionAssembler(
            load_reasoning_content_projections(
                ROOT / "content/compiled-reasoning-content.bundle.json"
            )
        )
        session = DecisionSession(bundle, assembler, response_policy=self.policy)
        for locale in ("en", "ko"):
            result = session.handle(request("deduction", locale=locale))
            self.assertEqual(
                result["methods"][0]["instructions"],
                assembler.assemble(("deduction",), requested_locale=locale).instructions,
            )
            self.assertEqual(result["presentation"]["profile_id"], f"{locale}-natural-v1")
        mechanical = session.handle(request(participation="mechanical"))
        self.assertEqual(mechanical["selected"], [])
        self.assertIsNone(mechanical["presentation"])
        out = io.StringIO()
        run_decision(io.StringIO(json.dumps(request("deduction"))), out)
        self.assertEqual(
            json.loads(out.getvalue())["presentation"]["sha256"], policy_identity(self.policy)
        )

    def test_all_six_controller_assets_bind_guided_policy(self):
        for host in ("antigravity", "claude", "codex", "cursor", "grok", "opencode"):
            root = ROOT / "build/generated/plugins" / host
            text = (root / "skills/opensocrates/SKILL.md").read_text()
            self.assertIn(policy_identity(self.policy), text)
            self.assertIn("en-natural-v1", text)
            self.assertIn("ko-natural-v1", text)
            self.assertEqual(
                load_compiled_response_policy(root / "content/compiled-response-policy.json"),
                self.policy,
            )

    def test_measurement_counts_complete_protected_artifact(self):
        for locale in ("en", "ko"):
            text = '판정: 보류\n\n`ID-04` 12 kg [source](https://example.com)\n{"ok":false}\n'
            result = measure_visible_output(text, locale)
            self.assertEqual(result["unicode_scalars"], len(text))
            self.assertEqual(result["utf8_bytes"], len(text.encode()))
            self.assertEqual(result["whitespace_units"], len(text.split()))
            self.assertEqual(result["quality_inference"], "none")
            self.assertEqual(result["scope"], "complete_public_artifact")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO")
    def test_compiled_policy_fifo_fails_without_blocking(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "compiled-response-policy.json"
            os.mkfifo(path, 0o600)
            code = "from pathlib import Path; import sys; from opensocrates.rendering.response_policy import load_compiled_response_policy; load_compiled_response_policy(Path(sys.argv[1]))"
            result = subprocess.run(
                [sys.executable, "-c", code, str(path)],
                capture_output=True,
                text=True,
                timeout=3,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(path.is_fifo())


if __name__ == "__main__":
    unittest.main()
