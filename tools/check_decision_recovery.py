"""Replay request failures without model calls or historical artifact repairs."""

from __future__ import annotations

import copy
import io
import json
import re
import unittest

import check_decision_points as baseline
from opensocrates.cli.decision import run_decision
from opensocrates.selector.decision import DecisionSession


class RecoveryChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        baseline.DecisionChecks.setUpClass()

    def setUp(self):
        self.session = DecisionSession(
            baseline.DecisionChecks.bundle, baseline.DecisionChecks.assembler
        )

    def test_prepare_requires_real_classification_and_preserves_canonical_locales(self):
        handles = set()
        for locale in ("en", "ko"):
            prepared = self.session.handle({"operation": "prepare", "locale": locale})
            self.assertEqual(prepared["status"], "prepared")
            self.assertEqual(prepared["selector_model_calls"], 0)
            self.assertEqual(prepared["applied"], "unverified")
            self.assertNotIn("selected", prepared)
            self.assertIsNone(self.session.scope)
            draft = prepared["request"]
            self.assertTrue(re.fullmatch("[0-9a-f]{32}", draft["context"]))
            handles.add(draft["context"])
            self.assertEqual(
                self.session.handle(draft)["diagnostic"]["field_path"], "$.participation"
            )
            self.assertIsNone(self.session.scope)
            draft["participation"] = "judgment"
            self.assertEqual(
                self.session.handle(draft)["diagnostic"]["field_path"], "$.routing.answer_shape"
            )
            self.assertIsNone(self.session.scope)
            draft["routing"].update(baseline.request()["routing"])
            result = self.session.handle(draft)
            self.assertEqual(result["selected"], ["critical-thinking"])
            self.assertEqual(
                result["methods"][0]["instructions"],
                self.session.assembler.assemble(
                    ("critical-thinking",), requested_locale=locale
                ).instructions,
            )
            self.session.handle({"operation": "reset"})
        self.assertEqual(len(handles), 2)

    def test_prepare_and_rejections_preserve_acknowledged_content(self):
        original = baseline.request("critical-thinking")
        first = self.session.handle(original)
        self.session.handle(
            dict(
                operation="acknowledge",
                context=original["context"],
                epoch=0,
                digests=[first["methods"][0]["sha256"]],
            )
        )
        before = (
            self.session.scope,
            self.session.last_key,
            copy.deepcopy(self.session.delivered),
            set(self.session.available),
        )
        bad = baseline.request("critical-thinking", context="b" * 32)
        bad["routing"]["features"][0]["basis"] = "governing_rule"
        cases = [
            {"operation": "prepare", "locale": "ko"},
            bad,
            baseline.request("unknown-method", context="c" * 32),
            baseline.request(participation="invalid", epoch=2),
            {"operation": "reset", "private-canary": True},
            dict(operation="acknowledge", context="d" * 32, epoch=0, digests=[]),
        ]
        for value in cases:
            with self.subTest(operation=value["operation"]):
                self.session.handle(value)
                self.assertEqual(
                    (
                        self.session.scope,
                        self.session.last_key,
                        self.session.delivered,
                        self.session.available,
                    ),
                    before,
                )
                reused = self.session.handle(original)
                self.assertTrue(reused["selection_reused"])
                self.assertIsNone(reused["methods"][0]["instructions"])

    def test_field_diagnostics_do_not_echo_values_or_unknown_names(self):
        canary = "PRIVATE-PROMPT-/workspace/secret"
        cases = []
        for field, value, path in (
            ("context", canary, "$.context"),
            ("decision", "d-1", "$.decision"),
            ("revision", True, "$.revision"),
            ("locale", [canary], "$.locale"),
            ("participation", canary, "$.participation"),
            ("operation", canary, "$.operation"),
            ("epoch", -1, "$.epoch"),
        ):
            cases.append((baseline.request(**{field: value}), path))
        for field in ("key", "basis", "strength"):
            value = baseline.request()
            value["routing"]["features"][0][field] = canary
            cases.append((value, f"$.routing.features[0].{field}"))
        value = baseline.request()
        value["routing"][canary] = canary
        cases.append((value, "$.routing"))
        value = baseline.request()
        del value["operation"]
        cases.append((value, "$.operation"))
        for value, path in cases:
            with self.subTest(path=path):
                response = self.session.handle(value)
                self.assertEqual(response["reason"], "invalid_decision_request")
                self.assertEqual(response["diagnostic"]["field_path"], path)
                self.assertNotIn(canary, json.dumps(response))
                self.assertTrue(response["continue_ordinary_work"])
                self.assertTrue(response["constraints_remain_binding"])

    def test_basis_is_distinct_from_feature_and_repair_does_not_drop_feature(self):
        value = baseline.request(features=["governing_rule", "recurring_failure"])
        value["routing"]["features"][0]["basis"] = "governing_rule"
        response = self.session.handle(value)
        allowed = response["diagnostic"]["allowed_values"]
        self.assertNotIn("governing_rule", allowed)
        self.assertIn("learning_need", allowed)
        value["routing"]["features"][0]["basis"] = "learning_need"
        self.assertEqual(self.session.handle(value)["selected"][0], "double-loop-learning")

    def test_duplicate_feature_and_unknown_method_are_not_partial_routes(self):
        value = baseline.request(features=["judgment", "judgment"])
        self.assertEqual(self.session.handle(value)["diagnostic"]["code"], "duplicate_feature")
        result = self.session.handle(baseline.request("private-method"))
        self.assertEqual(result["reason"], "unknown_method")
        self.assertNotIn("private-method", json.dumps(result))
        self.assertIsNone(self.session.scope)

    def test_pretty_document_stream_and_transport_recovery(self):
        value = baseline.request()
        stream = io.StringIO()
        self.assertEqual(run_decision(io.StringIO(json.dumps(value, indent=2)), stream), 0)
        self.assertEqual(json.loads(stream.getvalue())["status"], "selected")
        stream = io.StringIO()
        run_decision(io.StringIO(json.dumps(value) + "\n" + json.dumps(value)), stream)
        result = json.loads(stream.getvalue())
        self.assertEqual(result["reason"], "decision_unavailable")
        self.assertEqual(result["diagnostic"]["transport"], "single_document")
        stream = io.StringIO()
        run_decision(
            io.StringIO(
                '{"PRIVATE-CANARY":\n' + json.dumps(value) + "\n" + json.dumps(value) + "\n"
            ),
            stream,
            stream=True,
        )
        results = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["diagnostic"]["transport"], "ndjson_stream")
        self.assertNotIn("PRIVATE-CANARY", json.dumps(results[0]))
        self.assertEqual(results[1]["status"], "selected")
        self.assertTrue(results[2]["selection_reused"])

    def test_ambiguous_json_is_rejected_without_echo(self):
        for payload in (
            '{"operation":"reset","operation":"PRIVATE-CANARY"}',
            '{"operation":NaN}',
            '{"operation":Infinity}',
            "[" * 2000,
        ):
            stream = io.StringIO()
            run_decision(io.StringIO(payload), stream)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["diagnostic"]["code"], "one_json_object_required")
            self.assertNotIn("PRIVATE-CANARY", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
