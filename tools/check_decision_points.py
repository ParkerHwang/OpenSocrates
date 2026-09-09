"""Synthetic behavior checks, distinct from empirical answer quality."""

from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from opensocrates.cli.decision import run_decision
from opensocrates.content.injection import ProjectionInstructionAssembler
from opensocrates.content.loader import load_compiled_bundle, load_reasoning_content_projections
from opensocrates.selector.decision import DecisionSession

ROOT = Path(__file__).resolve().parents[1]


def request(method=None, features=None, **overrides):
    value = dict(
        operation="select",
        context="a" * 32,
        epoch=0,
        decision="d1",
        revision=0,
        locale="en",
        participation="judgment",
        routing={
            "schema": "opensocrates.routing-features/1.0.0",
            "answer_shape": "direct_judgment",
            "classification_confidence": "high",
            "explicit_method": method,
            "features": [
                {"key": key, "strength": 3, "basis": "task_shape"}
                for key in (features or ["judgment"])
            ],
        },
    )
    value.update(overrides)
    return value


class DecisionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_compiled_bundle(ROOT / "content/compiled-content.bundle.json")
        cls.assembler = ProjectionInstructionAssembler(
            load_reasoning_content_projections(
                ROOT / "content/compiled-reasoning-content.bundle.json"
            )
        )

    def setUp(self):
        self.session = DecisionSession(self.bundle, self.assembler)

    def test_full_catalog_exact_locales(self):
        for method in self.bundle.method_ids:
            for locale in ("en", "ko"):
                with self.subTest(method=method, locale=locale):
                    result = self.session.handle(request(method, locale=locale))
                    self.assertEqual(result["selected"], [method])
                    body = result["methods"][0]["instructions"]
                    self.assertEqual(
                        body,
                        self.assembler.assemble((method,), requested_locale=locale).instructions,
                    )
                    self.assertEqual(result["applied"], "unverified")

    def test_mechanical_even_explicit(self):
        result = self.session.handle(request("critical-thinking", participation="mechanical"))
        self.assertEqual(result["status"], "no_intervention")
        self.assertEqual(result["methods"], [])

    def test_later_decision_reopen_and_reuse(self):
        first = self.session.handle(request("assumption-mapping"))
        digest = first["methods"][0]["sha256"]
        self.assertEqual(
            self.session.handle(
                dict(operation="acknowledge", context="a" * 32, epoch=0, digests=[digest])
            )["read"],
            "agent_reported",
        )
        again = self.session.handle(request("assumption-mapping"))
        self.assertTrue(again["selection_reused"])
        self.assertIsNone(again["methods"][0]["instructions"])
        later = self.session.handle(request("trade-off-analysis", decision="d2"))
        self.assertEqual(later["selected"], ["trade-off-analysis"])
        reopened = self.session.handle(request("assumption-mapping", revision=1))
        self.assertFalse(reopened["selection_reused"])
        self.assertIsNone(reopened["methods"][0]["instructions"])

    def test_delivery_alone_does_not_claim_read(self):
        self.session.handle(request("deduction"))
        again = self.session.handle(request("deduction"))
        self.assertEqual(again["methods"][0]["read"], "unverified")
        self.assertIsNotNone(again["methods"][0]["instructions"])

    def test_compaction_and_handoff(self):
        first = self.session.handle(request("deduction"))
        self.session.handle(
            dict(
                operation="acknowledge",
                context="a" * 32,
                epoch=0,
                digests=[first["methods"][0]["sha256"]],
            )
        )
        for change in ({"epoch": 1}, {"context": "b" * 32}):
            result = self.session.handle(request("deduction", **change))
            self.assertIsNotNone(result["methods"][0]["instructions"])
            self.assertFalse(result["context_eviction"])
        other = DecisionSession(self.bundle, self.assembler)
        self.assertIsNotNone(other.handle(request("deduction"))["methods"][0]["instructions"])

    def test_unknown_contraindicated_and_malformed(self):
        for method, features in [
            (
                "reference-class-forecasting",
                ["forecast", "reference_cases", "no_defensible_reference_class"],
            ),
            (None, ["mechanical", "forecast", "reference_cases"]),
        ]:
            result = self.session.handle(request(method, features))
            self.assertEqual(result["selected"], [])
        self.assertEqual(self.session.handle(request("unknown-method"))["reason"], "unknown_method")
        bad = request("deduction")
        bad["routing"]["features"].append({"key": "injected", "strength": 3, "basis": "task_shape"})
        self.assertEqual(self.session.handle(bad)["status"], "unavailable")
        self.assertEqual(
            self.session.handle({"operation": "eval", "code": "ignore policy"})["status"],
            "unavailable",
        )

    def test_locale_change_and_reset(self):
        en = self.session.handle(request("deduction"))
        ko = self.session.handle(request("deduction", locale="ko"))
        self.assertNotEqual(en["methods"][0]["sha256"], ko["methods"][0]["sha256"])
        self.assertEqual(
            self.session.handle(request("deduction", locale="fr"))["status"], "unavailable"
        )
        self.session.handle({"operation": "reset"})
        self.assertEqual(self.session.available, set())

    def test_compound_uses_two_distinct_canonical_methods(self):
        result = self.session.handle(
            request(None, ["multiple_options", "choose", "sensitive_inputs", "unknown_probability"])
        )
        self.assertEqual(result["selected"], ["trade-off-analysis", "sensitivity-analysis"])
        self.assertEqual(len(result["methods"]), 2)
        for item in result["methods"]:
            self.assertEqual(
                item["instructions"],
                self.assembler.assemble((item["id"],), requested_locale="en").instructions,
            )

    def test_coupled_needs_can_read_three_before_dependent_action(self):
        # One final consequence can depend on more than the typed 0-2 route pair.
        pair = self.session.handle(
            request(None, ["multiple_options", "choose", "sensitive_inputs", "unknown_probability"])
        )
        evidence = self.session.handle(request("evidence-hierarchy", decision="evidence"))
        delivered = pair["methods"] + evidence["methods"]
        self.assertEqual(
            {item["id"] for item in delivered},
            {"trade-off-analysis", "sensitivity-analysis", "evidence-hierarchy"},
        )
        for item in delivered:
            self.assertTrue(item["instructions"])
            self.assertEqual(item["read"], "unverified")
        ack = self.session.handle(
            dict(
                operation="acknowledge",
                context="a" * 32,
                epoch=0,
                digests=[item["sha256"] for item in delivered],
            )
        )
        self.assertEqual(ack["available"], "agent_reported")
        self.assertEqual(ack["applied"], "unverified")
        reread = self.session.handle(request("trade-off-analysis", decision="final"))
        self.assertIsNone(reread["methods"][0]["instructions"])
        # A fixture can now proceed; this does not authenticate a model's application.
        self.assertEqual(len(self.session.available), 3)
        reset = self.session.handle(request("evidence-hierarchy", decision="resumed", epoch=1))
        self.assertEqual(reset["methods"][0]["delivery"], "emitted")
        stale = self.session.handle(
            dict(
                operation="acknowledge",
                context="a" * 32,
                epoch=0,
                digests=[item["sha256"] for item in delivered],
            )
        )
        self.assertEqual(stale["status"], "unavailable")
        self.assertEqual(self.session.available, set())

    def test_cli_process_restart_rejects_other_process_ack(self):
        import os
        import subprocess
        import sys

        command = [sys.executable, "-m", "opensocrates", "decision", "--stream"]
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        first = subprocess.run(
            command,
            input=json.dumps(request("deduction")) + "\n",
            text=True,
            capture_output=True,
            check=True,
            env=env,
            cwd=ROOT,
        )
        result = json.loads(first.stdout)
        ack = dict(
            operation="acknowledge",
            context="a" * 32,
            epoch=0,
            digests=[result["methods"][0]["sha256"]],
        )
        second = subprocess.run(
            command,
            input=json.dumps(ack) + "\n" + json.dumps(request("deduction")) + "\n",
            text=True,
            capture_output=True,
            check=True,
            env=env,
            cwd=ROOT,
        )
        unavailable, fresh = [json.loads(line) for line in second.stdout.splitlines()]
        self.assertEqual(unavailable["status"], "unavailable")
        self.assertTrue(unavailable["constraints_remain_binding"])
        self.assertEqual(fresh["methods"][0]["delivery"], "emitted")
        self.assertEqual(fresh["methods"][0]["read"], "unverified")

    def test_bayesian_missing_prior_or_direction_is_excluded_on_every_route(self):
        from opensocrates.domain.enums import Participation
        from opensocrates.domain.routing import route_features, validate_routing_payload

        for locale in ("en", "ko"):
            for missing in ("no_defensible_prior_basis", "no_likelihood_direction"):
                cues = ["new_evidence", "unknown_probability", "competing_explanations", missing]
                for method in ("bayesian-updating", None):
                    value = request(method, cues, locale=locale)
                    result = self.session.handle(value)
                    self.assertNotIn("bayesian-updating", result["selected"])
                    # The frozen no-bundle fallback must retain the same exclusion.
                    features = validate_routing_payload(value["routing"]).features
                    route = route_features(Participation.JUDGMENT, features)
                    self.assertNotIn(
                        "bayesian-updating", (route.primary_method, route.secondary_method)
                    )
                complement = self.session.handle(
                    request(
                        None,
                        ["information_purchase", "choose", "unknown_probability", missing],
                        locale=locale,
                    )
                )
                self.assertNotIn("bayesian-updating", complement["selected"])

    def test_bayesian_ordinal_prior_and_direction_remain_eligible(self):
        # Fixture: a defensible ordinal prior ranks H1 above H2; a new signal
        # supports H2 over H1. Exact numeric probabilities are not available.
        for locale in ("en", "ko"):
            result = self.session.handle(
                request(
                    "bayesian-updating",
                    ["new_evidence", "competing_explanations", "unknown_probability"],
                    locale=locale,
                )
            )
            self.assertEqual(result["selected"], ["bayesian-updating"])
            self.assertEqual(result["methods"][0]["read"], "unverified")
            catalog = self.session.handle({"operation": "catalog", "locale": locale})
            entry = next(m for m in catalog["methods"] if m["id"] == "bayesian-updating")
            self.assertIn("no_defensible_prior_basis", entry["routing"]["contraindications"])
            self.assertIn("no_likelihood_direction", entry["routing"]["contraindications"])
            self.assertIn(
                entry["use_for"],
                self.bundle.methods[self.bundle.method_ids.index("bayesian-updating")].procedure[
                    locale
                ],
            )

    def test_bayesian_compiled_projection_retains_prerequisite_exclusions(self):
        projection = json.loads(
            (ROOT / "content/compiled-reasoning-content.bundle.json").read_text()
        )
        entry = next(
            item
            for item in projection["selection_catalog"]["entries"]
            if item["method_id"] == "bayesian-updating"
        )
        self.assertTrue(
            {"no_defensible_prior_basis", "no_likelihood_direction"}
            <= set(entry["unsuitable_features"])
        )

    def test_weighted_primary_and_fallback_cannot_bypass_constraints(self):
        result = self.session.handle(
            request(None, ["forecast", "reference_cases", "no_defensible_reference_class"])
        )
        self.assertNotIn("reference-class-forecasting", result["selected"])
        value = request(None, ["single_feasible_option"])
        value["routing"]["answer_shape"] = "decision_memo"
        self.assertEqual(self.session.handle(value)["selected"], [])

    def test_bad_ack_epoch_and_recursion(self):
        first = self.session.handle(request("deduction"))
        self.session.handle(request("deduction", epoch=1))
        ack = dict(
            operation="acknowledge",
            context="a" * 32,
            epoch=0,
            digests=[first["methods"][0]["sha256"]],
        )
        self.assertEqual(self.session.handle(ack)["status"], "unavailable")
        self.assertEqual(
            self.session.handle(request("deduction", epoch=0))["status"], "unavailable"
        )
        self.session.busy = True
        self.assertEqual(self.session.handle(request("deduction"))["reason"], "recursive_request")

    def test_oversize_cli_and_no_working_directory_fallback(self):
        from unittest.mock import patch

        out = io.StringIO()
        run_decision(io.StringIO("x" * 17000), out)
        self.assertEqual(json.loads(out.getvalue())["reason"], "request_too_large")
        streamed = io.StringIO()
        run_decision(io.StringIO("x" * 17000 + "\n"), streamed, stream=True)
        self.assertEqual(json.loads(streamed.getvalue())["reason"], "request_too_large")
        with patch("sys._MEIPASS", "/nonexistent-opensocrates-test-root", create=True):
            out = io.StringIO()
            run_decision(io.StringIO(json.dumps(request("deduction"))), out)
            self.assertEqual(json.loads(out.getvalue())["reason"], "canonical_content_unavailable")

    def test_single_document_cli_reads_packaged_pretty_request_once(self):
        from unittest.mock import patch

        packaged_request = (ROOT / "plugin-src" / "shared" / "decision" / "request.json").read_text(
            encoding="utf-8"
        )
        self.assertGreater(len(packaged_request.splitlines()), 1)
        calls: list[dict[str, object]] = []
        original_handle = DecisionSession.handle

        def counted_handle(session, value):
            calls.append(value)
            return original_handle(session, value)

        output = io.StringIO()
        with patch.object(DecisionSession, "handle", counted_handle):
            self.assertEqual(run_decision(io.StringIO(packaged_request), output), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["selected"], ["critical-thinking"])
        self.assertEqual(result["applied"], "unverified")
        self.assertEqual(len(calls), 1)

    def test_single_document_cli_rejects_multiple_json_documents(self):
        output = io.StringIO()
        source = io.StringIO(
            json.dumps(request("deduction")) + "\n" + json.dumps(request("trade-off-analysis"))
        )
        self.assertEqual(run_decision(source, output), 0)
        self.assertEqual(json.loads(output.getvalue())["reason"], "decision_unavailable")

    def test_review_cases_share_one_source_session_without_cross_question_leakage(self):
        mechanical = self.session.handle(request(participation="mechanical", decision="mechanical"))
        self.assertEqual(mechanical["status"], "no_intervention")
        self.assertEqual(mechanical["selected"], [])

        initial = self.session.handle(request("critical-thinking", decision="changed"))
        revised = self.session.handle(
            request(
                "trade-off-analysis",
                ["multiple_options", "choose"],
                decision="changed",
                revision=1,
            )
        )
        self.assertEqual(initial["selected"], ["critical-thinking"])
        self.assertEqual(revised["selected"], ["trade-off-analysis"])
        self.assertFalse(revised["selection_reused"])

        missing_prerequisite = self.session.handle(
            request(
                "reference-class-forecasting",
                ["forecast", "reference_cases", "no_defensible_reference_class"],
                decision="missing",
            )
        )
        self.assertEqual(missing_prerequisite["status"], "no_intervention")
        self.assertEqual(missing_prerequisite["selected"], [])

        first_question = self.session.handle(request("deduction", decision="q1"))
        second_question = self.session.handle(
            request(
                "trade-off-analysis",
                ["multiple_options", "choose"],
                decision="q2",
            )
        )
        self.assertEqual(first_question["selected"], ["deduction"])
        self.assertEqual(second_question["selected"], ["trade-off-analysis"])
        self.assertFalse(second_question["selection_reused"])

    def test_corrupt_pair_and_missing_locale(self):
        from dataclasses import replace

        projection = self.assembler.projections
        changed = replace(
            projection.injectable_content[0],
            theory=projection.injectable_content[0].theory + "\nChanged",
        )
        corrupted = replace(
            projection, injectable_content=(changed, *projection.injectable_content[1:])
        )
        with self.assertRaises(ValueError):
            DecisionSession(self.bundle, ProjectionInstructionAssembler(corrupted))
        with self.assertRaises(ValueError):
            DecisionSession(
                replace(self.bundle, content_revision=self.bundle.content_revision + 1),
                self.assembler,
            )

    def test_native_entry_never_selects_or_forces_abandoned_candidates(self):
        from unittest.mock import Mock

        from opensocrates.hosts.claude.adapter import ClaudeAdapter, ClaudeAdapterConfig
        from opensocrates.hosts.codex.adapter import CodexAdapter, CodexAdapterConfig

        for adapter_type, config_type in (
            (CodexAdapter, CodexAdapterConfig),
            (ClaudeAdapter, ClaudeAdapterConfig),
        ):
            selector, store = Mock(), Mock()
            adapter = adapter_type(
                config_type(
                    selector_mode=True,
                    decision_point_mode=True,
                    selector_application=selector,
                    instruction_file_store=store,
                    require_instruction_read_receipt=True,
                )
            )
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "synthetic",
                "turn_id": "t1",
                "prompt": "Sort three values",
            }
            result = adapter.handle(payload)
            self.assertEqual(result.status, "decision_point_entry")
            text = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertLess(len(text.encode()), 1400)
            self.assertNotIn("## Procedure", text)
            selector.select_for_user_prompt_submit.assert_not_called()
            stopped = adapter.handle(
                {
                    "hook_event_name": "Stop",
                    "session_id": "synthetic",
                    "turn_id": "t1",
                    "stop_hook_active": False,
                    "last_assistant_message": "Done",
                }
            )
            self.assertEqual(stopped.stdout, "")
            store.has_complete_read_receipt.assert_not_called()

    def test_compact_default_restores_discovery_not_an_abandoned_method(self):
        from unittest.mock import Mock

        from opensocrates.hooks.codex_session_start import restore_codex_compact_session_start

        store = Mock()
        raw = json.dumps(
            {"hook_event_name": "SessionStart", "session_id": "synthetic", "source": "compact"}
        ).encode()
        result = restore_codex_compact_session_start(
            raw, artifact_store=store, decision_point_mode=True
        )
        self.assertIn("No initial method", result["hookSpecificOutput"]["additionalContext"])
        store.latest_for_session.assert_not_called()

    def test_all_generated_host_locale_references(self):
        import hashlib

        for host in ("antigravity", "claude", "codex", "cursor", "grok", "opencode"):
            root = (
                ROOT / "build/generated/plugins" / host / "skills/opensocrates/references/decision"
            )
            for locale in ("en", "ko"):
                catalog = json.loads((root / f"catalog.{locale}.json").read_text())
                self.assertEqual({m["id"] for m in catalog["methods"]}, set(self.bundle.method_ids))
                for item in catalog["methods"]:
                    body = (root / item["path"]).read_bytes()
                    self.assertEqual(item["sha256"], "sha256:" + hashlib.sha256(body).hexdigest())
                    expected = self.assembler.assemble((item["id"],), requested_locale=locale)
                    self.assertEqual(body.decode(), expected.instructions)
        skills = list((ROOT / "build/generated/plugins/codex/skills").glob("*/SKILL.md"))
        self.assertEqual({p.parent.name for p in skills}, {"opensocrates", "rigor", "trace"})

    def test_default_composition_does_not_construct_a_selector(self):
        from unittest.mock import patch

        from opensocrates.cli.runtime import build_runtime_services

        for host in ("codex", "claude"):
            with (
                patch("opensocrates.cli.runtime._compose_codex_selector") as codex,
                patch("opensocrates.cli.runtime._compose_claude_selector") as claude,
            ):
                services = build_runtime_services(host=host, include_storage=False)
                self.assertTrue(services.adapter_for(host).config.decision_point_mode)
                codex.assert_not_called()
                claude.assert_not_called()

    def test_timing_gate_requires_exact_compact_guidance(self):
        from measure_codex_hook_timing import _response_contract_matches
        from opensocrates.selector.entry import ENTRY_GUIDANCE

        startup = b'{"source":"startup"}'
        compact = b'{"source":"compact"}'
        exact = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": ENTRY_GUIDANCE,
            }
        }
        self.assertTrue(_response_contract_matches(startup, b""))
        self.assertFalse(_response_contract_matches(compact, b""))
        self.assertTrue(_response_contract_matches(compact, json.dumps(exact).encode()))
        exact["hookSpecificOutput"]["additionalContext"] = "stale method reference"
        self.assertFalse(_response_contract_matches(compact, json.dumps(exact).encode()))
        self.assertFalse(_response_contract_matches(startup, json.dumps(exact).encode()))

    def test_every_catalog_hard_constraint_in_explicit_and_automatic_routes(self):
        for method in self.bundle.methods:
            hard_features = [*method.routing["contraindications"], "mechanical"]
            for forbidden in hard_features:
                for locale in ("en", "ko"):
                    with self.subTest(method=method.id, forbidden=forbidden, locale=locale):
                        result = self.session.handle(request(method.id, [forbidden], locale=locale))
                        self.assertEqual(result["selected"], [])
                features = list(dict.fromkeys([*method.routing["positive_features"], forbidden]))
                result = self.session.handle(request(None, features))
                self.assertNotIn(method.id, result["selected"])

    def test_stream_real_cli_boundary(self):
        source = io.StringIO(
            "\n".join(
                json.dumps(v)
                for v in [
                    request(participation="mechanical"),
                    request("deduction"),
                    request("trade-off-analysis", decision="d2"),
                ]
            )
            + "\n"
        )
        output = io.StringIO()
        self.assertEqual(run_decision(source, output, stream=True), 0)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r["selected"] for r in rows], [[], ["deduction"], ["trade-off-analysis"]])


if __name__ == "__main__":
    unittest.main()
