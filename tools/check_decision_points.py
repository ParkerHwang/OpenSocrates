"""Synthetic behavior checks, distinct from empirical answer quality."""

from __future__ import annotations

import hashlib
import io
import json
import unittest
from pathlib import Path

from opensocrates.cli.decision import run_decision
from opensocrates.constants import PUBLIC_ATTRIBUTION_FOOTER
from opensocrates.content.injection import ProjectionInstructionAssembler
from opensocrates.content.loader import load_compiled_bundle, load_reasoning_content_projections
from opensocrates.selector.decision import FAULT_CODES, DecisionSession, RequestFault
from opensocrates.selector.entry import ENTRY_GUIDANCE, ENTRY_GUIDANCE_MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]
SELECT_FAULTS = ROOT / "evals" / "issue-124" / "select-faults.json"


def mutate(value, action, path, replacement):
    target = value
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[int(part)] if part.isdigit() else target[part]
    last = int(parts[-1]) if parts[-1].isdigit() else parts[-1]
    if action == "drop":
        del target[last]
    else:
        target[last] = replacement
    return value


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
            for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
                with self.subTest(method=method, locale=locale):
                    result = self.session.handle(request(method, locale=locale))
                    self.assertEqual(result["selected"], [method])
                    body = result["methods"][0]["instructions"]
                    self.assertEqual(
                        body,
                        self.assembler.assemble((method,), requested_locale=locale).instructions,
                    )
                    self.assertEqual(result["applied"], "unverified")
                    self.assertEqual(result["audit_if_applied"], "Powered by OpenSocrates")
                    self.assertEqual(result["audit_if_applied"], PUBLIC_ATTRIBUTION_FOOTER)
                    self.assertEqual(result["content_revision"], self.bundle.content_revision)
                    self.assertEqual(
                        result["methods"][0]["content_revision"], self.bundle.content_revision
                    )
                    self.assertEqual(
                        result["methods"][0]["sha256"],
                        "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    )

    def test_mechanical_even_explicit(self):
        result = self.session.handle(request("critical-thinking", participation="mechanical"))
        self.assertEqual(result["status"], "no_intervention")
        self.assertEqual(result["methods"], [])
        self.assertIsNone(result["audit_if_applied"])
        self.assertEqual(result["applied"], "unverified")

    def test_prescribed_step_does_not_bypass_later_reasoning(self):
        prescribed = self.session.handle(request(participation="mechanical"))
        self.assertEqual(prescribed["methods"], [])

        # Given rules can still require inference. A mechanical first segment
        # must not make the next substantive segment terminally bypassed.
        reasoning = self.session.handle(
            request(features=["explicit_rules", "explain"], decision="d2")
        )
        self.assertEqual(reasoning["selected"], ["deduction"])
        self.assertEqual(reasoning["methods"][0]["locale"], "en")
        self.assertEqual(reasoning["methods"][0]["read"], "unverified")
        self.assertEqual(reasoning["applied"], "unverified")

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
            self.assertIsNone(result["audit_if_applied"])
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
            self.session.handle(request("deduction", locale="ru"))["status"], "unavailable"
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

        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
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
        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
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
            method = self.bundle.methods[self.bundle.method_ids.index("bayesian-updating")]
            self.assertEqual(entry["use_for"], method.plain_action[locale])
            self.assertIn(
                method.procedure[locale].rstrip("\n"), result["methods"][0]["instructions"]
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

    def test_select_faults_name_closed_location_without_values(self):
        """#124: every rejection is locatable, never echoes input, never looks empty."""

        fixture = json.loads(SELECT_FAULTS.read_text(encoding="utf-8"))
        self.assertEqual(self.session.handle(fixture["valid"])["status"], "selected")
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.session.handle({"operation": "reset"})
                value = mutate(
                    json.loads(json.dumps(fixture["valid"])),
                    case["action"],
                    case["path"],
                    case["value"],
                )
                result = self.session.handle(value)
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(result["reason"], "invalid_decision_request")
                self.assertEqual((result["field"], result["error"]), (case["field"], case["error"]))
                self.assertIn(result["error"], FAULT_CODES)
                self.assertEqual(result["repair"], "correct_field_once")
                self.assertTrue(result["continue_ordinary_work"])
                self.assertTrue(result["constraints_remain_binding"])
                self.assertNotIn("selected", result)
                self.assertNotIn("methods", result)
                if isinstance(case["value"], str) and len(case["value"]) >= 4:
                    self.assertNotIn(case["value"], json.dumps(result, ensure_ascii=False))
        with self.assertRaises(AssertionError):
            RequestFault("context", "free_form_detail")

    def test_repaired_request_takes_valid_selection_path(self):
        fixture = json.loads(SELECT_FAULTS.read_text(encoding="utf-8"))
        broken = json.loads(json.dumps(fixture["valid"]))
        broken["context"] = "3F2B8C1E-7D4A-4E9B-A6C2-1F0E9D8B7A6C"
        broken["decision"] = "tessellate-priority"
        first = self.session.handle(broken)
        self.assertEqual(first["field"], "context")
        broken["context"] = "3f2b8c1e7d4a4e9ba6c21f0e9d8b7a6c"
        second = self.session.handle(broken)
        self.assertEqual(second["field"], "decision")
        broken["decision"] = "tessellatepriority"
        repaired = self.session.handle(broken)
        self.assertEqual(repaired["status"], "selected")
        self.assertTrue(repaired["selected"])
        method = repaired["methods"][0]
        self.assertEqual(method["locale"], "ko")
        self.assertEqual(
            method["instructions"],
            self.assembler.assemble((method["id"],), requested_locale="ko").instructions,
        )
        self.assertEqual(repaired["applied"], "unverified")

    def test_failure_states_remain_distinct(self):
        from unittest.mock import patch

        empty = self.session.handle(request(participation="mechanical"))
        self.assertEqual((empty["status"], empty["selected"]), ("no_intervention", []))
        self.assertNotIn("field", empty)

        invalid = self.session.handle(request(context="not-a-handle"))
        self.assertEqual(
            (invalid["status"], invalid["reason"]), ("unavailable", "invalid_decision_request")
        )
        self.assertEqual(invalid["field"], "context")

        unknown = self.session.handle(request("not-a-method"))
        self.assertEqual(unknown["reason"], "unknown_method")
        self.assertNotIn("field", unknown)

        # A packaged-content fault after acceptance is not mislabelled as repairable input.
        with patch.object(type(self.assembler), "assemble", side_effect=ValueError):
            runtime = self.session.handle(request("deduction", decision="d9"))
        self.assertEqual(runtime["reason"], "decision_unavailable")
        self.assertNotIn("field", runtime)
        for result in (invalid, unknown, runtime):
            self.assertTrue(result["continue_ordinary_work"])
            self.assertTrue(result["constraints_remain_binding"])

    def test_other_operations_report_closed_locations(self):
        catalog = self.session.handle({"operation": "catalog"})
        self.assertEqual((catalog["field"], catalog["error"]), ("locale", "missing_field"))
        catalog = self.session.handle({"operation": "catalog", "locale": ["ko"]})
        self.assertEqual((catalog["field"], catalog["error"]), ("locale", "invalid_value"))
        unknown = self.session.handle({"operation": "choose"})
        self.assertEqual((unknown["field"], unknown["error"]), ("operation", "unknown_operation"))
        missing = self.session.handle({"context": "a" * 32})
        self.assertEqual((missing["field"], missing["error"]), ("operation", "missing_field"))
        self.session.handle(request(epoch=2))
        stale = self.session.handle(request(epoch=1))
        self.assertEqual((stale["field"], stale["error"]), ("epoch", "stale_epoch"))

    def test_packaged_envelope_contract_matches_runtime_validation(self):
        from opensocrates.domain.enums import ClassificationConfidence, Participation
        from opensocrates.domain.models import RoutingFeatures
        from opensocrates.selector.decision import LOCALES, SELECT_KEYS

        envelope = json.loads(
            (ROOT / "plugin-src/shared/decision/features.json").read_text(encoding="utf-8")
        )["envelope"]
        packaged = json.loads(
            (ROOT / "plugin-src/shared/decision/request.json").read_text(encoding="utf-8")
        )
        self.assertEqual(tuple(envelope["required_keys"]), SELECT_KEYS)
        self.assertEqual(set(envelope["required_keys"]), set(packaged))
        self.assertEqual(set(envelope["routing_required_keys"]), set(packaged["routing"]))
        self.assertEqual(set(envelope["locale"]), LOCALES)
        self.assertEqual(set(envelope["participation"]), {p.value for p in Participation})
        self.assertEqual(
            envelope["classification_confidence"], [c.value for c in ClassificationConfidence]
        )
        self.assertEqual(envelope["routing_schema"], RoutingFeatures.__schema_id__)
        self.assertEqual((envelope["strength"], envelope["max_features"]), ([1, 2, 3], 16))
        self.assertEqual(set(envelope["feature_entry_keys"]), {"key", "strength", "basis"})
        for guide in ("en", "ko"):
            text = (ROOT / f"plugin-src/shared/decision/guide.{guide}.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("invalid_decision_request", text)
            self.assertIn("envelope", text)

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
        result = json.loads(output.getvalue())
        # Malformed JSON is repairable input, not runtime unavailability (#124).
        self.assertEqual(result["reason"], "invalid_decision_request")
        self.assertEqual((result["field"], result["error"]), ("request", "invalid_json"))
        self.assertTrue(result["continue_ordinary_work"])

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

        from opensocrates.hosts.codex.adapter import CodexAdapter, CodexAdapterConfig

        for adapter_type, config_type in ((CodexAdapter, CodexAdapterConfig),):
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
            self.assertEqual(text, ENTRY_GUIDANCE)
            self.assertLessEqual(len(text.encode()), ENTRY_GUIDANCE_MAX_BYTES)
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

        for host in ("codex",):
            root = (
                ROOT / "build/generated/plugins" / host / "skills/opensocrates/references/decision"
            )
            for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
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

        for host in ("codex",):
            with (
                patch("opensocrates.cli.runtime._compose_codex_selector") as codex,
            ):
                services = build_runtime_services(host=host, include_storage=False)
                self.assertTrue(services.adapter_for(host).config.decision_point_mode)
                codex.assert_not_called()

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
                for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
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

    def test_deep_unclosed_json_is_repairable_without_ending_the_cli(self):
        import subprocess
        import sys

        from opensocrates.cli.decision import MAX_REQUEST_CHARS

        malformed = "[" * (MAX_REQUEST_CHARS - 1)
        catalog = json.dumps({"operation": "catalog", "locale": "en"}) + "\n"
        for stream in (False, True):
            with self.subTest(stream=stream):
                command = [sys.executable, "-m", "opensocrates", "decision"]
                if stream:
                    command.append("--stream")
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    input=catalog + malformed + "\n" + catalog if stream else malformed,
                    capture_output=True,
                    encoding="utf-8",
                    timeout=30,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                rows = [json.loads(line) for line in result.stdout.splitlines()]
                self.assertEqual(len(rows), 3 if stream else 1)
                fault = rows[1] if stream else rows[0]
                self.assertEqual(fault["reason"], "invalid_decision_request")
                self.assertEqual((fault["field"], fault["error"]), ("request", "invalid_json"))
                self.assertEqual(fault["repair"], "correct_field_once")
                self.assertTrue(fault["continue_ordinary_work"])
                self.assertNotIn(malformed, result.stdout)
                if stream:
                    self.assertEqual(len(rows[0]["methods"]), 48)
                    self.assertEqual(len(rows[2]["methods"]), 48)


class LocaleCompatibilityChecks(unittest.TestCase):
    def test_exported_participation_api_preserves_typed_gate_in_all_locales(self):
        from opensocrates.domain.enums import Participation, ParticipationReasonCode
        from opensocrates.domain.models import ParticipationDecision
        from opensocrates.domain.participation import validate_participation_decision
        from opensocrates.domain.validation import model_from_dict
        from opensocrates.prompting import participation_prompt
        from opensocrates.prompting.participation_prompt import (
            build_participation_prompt,
            get_participation_prompt,
        )

        english = participation_prompt("en")
        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            with self.subTest(locale=locale):
                text = participation_prompt(locale)
                self.assertEqual(build_participation_prompt(locale), text)
                self.assertEqual(get_participation_prompt(locale), text)
                if locale != "en":
                    self.assertNotEqual(text, english)
                envelopes = [json.loads(line) for line in text.splitlines() if line.startswith("{")]
                self.assertEqual(len(envelopes), 1)
                payload = envelopes[0]
                self.assertEqual(
                    set(payload),
                    {
                        "participation",
                        "reason_code",
                        "judgment_targets",
                        "mechanical_targets",
                        "confidence_basis",
                        "explicit_method",
                    },
                )
                self.assertEqual(payload["confidence_basis"], "rule_plus_model_policy")
                self.assertIsNone(payload["explicit_method"])
                self.assertEqual(payload["judgment_targets"], [])
                self.assertEqual(payload["mechanical_targets"], [])
                for code in (*Participation, *ParticipationReasonCode):
                    self.assertIn(code.value, text)
                # A named method alone remains mechanical at the typed gate in
                # every locale; the shared envelope cannot force a judgment route.
                payload.update(
                    participation="mechanical",
                    reason_code="explicit_method_without_judgment",
                    explicit_method="deduction",
                )
                decision = model_from_dict(ParticipationDecision, payload, require_schema=False)
                self.assertEqual(
                    validate_participation_decision(decision).participation,
                    Participation.MECHANICAL,
                )
        for invalid in ("ru", "ZH", "zh-CN", "", None, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    participation_prompt(invalid)

    def test_exported_routing_api_preserves_closed_payload_in_all_locales(self):
        from opensocrates.domain.routing import validate_routing_payload
        from opensocrates.prompting import routing_prompt
        from opensocrates.prompting.routing_prompt import build_routing_prompt, get_routing_prompt

        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            with self.subTest(locale=locale):
                text = routing_prompt(locale)
                self.assertEqual(build_routing_prompt(locale), text)
                self.assertEqual(get_routing_prompt(locale), text)
                envelopes = [json.loads(line) for line in text.splitlines() if line.startswith("{")]
                self.assertEqual(len(envelopes), 1)
                payload = envelopes[0]
                self.assertEqual(
                    set(payload),
                    {
                        "schema",
                        "answer_shape",
                        "features",
                        "classification_confidence",
                        "explicit_method",
                    },
                )
                self.assertEqual(payload["schema"], "opensocrates.routing-features/1.0.0")
                self.assertIsNone(payload["explicit_method"])
                payload.update(
                    answer_shape="direct_judgment",
                    classification_confidence="high",
                    features=[{"key": "judgment", "strength": 3, "basis": "task_shape"}],
                )
                parsed = validate_routing_payload(payload)
                self.assertTrue(parsed.structurally_valid)
                self.assertFalse(parsed.invalid_feature_list)
        for invalid in ("ru", "FR", "pt-BR", "th-TH", "", None, []):
            with self.assertRaises(ValueError):
                routing_prompt(invalid)

    def test_codex_adapter_rejects_unsupported_explicit_locale_before_selection(self):
        from opensocrates.hosts.codex.adapter import CodexAdapterConfig

        for locale in (None, "en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            self.assertEqual(CodexAdapterConfig(locale_preference=locale).locale_preference, locale)
        for invalid in ("ru", "ZH", "zh-CN", "", False):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    CodexAdapterConfig(locale_preference=invalid)

    def test_locale_commands_persist_without_resetting_existing_preferences(self):
        import tempfile
        from types import SimpleNamespace

        from opensocrates.application.change_settings import normalize_settings
        from opensocrates.cli.main import main
        from opensocrates.domain.enums import FeedbackOutcome, RecordingMode, Rigor
        from opensocrates.domain.models import FeedbackEntry, InterventionPreference, UserSettings
        from opensocrates.persistence.paths import DataRootLayout
        from opensocrates.persistence.settings_store import SettingsStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            layout = DataRootLayout.from_root(root)
            # This is an existing EN/KO settings shape, not a fresh-install default.
            original = UserSettings(
                locale_preference="ko",
                default_rigor=Rigor.STRICT,
                revision=7,
                recording_mode=RecordingMode.LOCAL_PUBLIC_ARTIFACTS,
                record_retention_days=37,
                onboarding_version_seen="1.5.0",
                intervention_preferences={
                    "reframe": InterventionPreference(
                        next_sequence=23,
                        recent_feedback=(
                            FeedbackEntry(
                                sequence=22, day="2026-10-01", outcome=FeedbackOutcome.DISMISSED
                            ),
                        ),
                        reduced_since_sequence=22,
                        reduced_until="2026-10-20",
                    )
                },
            )
            layout.settings_file.write_text(original.to_json())
            layout.settings_file.chmod(0o600)
            store = SettingsStore(layout)
            runtime = SimpleNamespace(settings_store=store)
            for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th", "follow"):
                before = store.load()
                output = io.StringIO()
                self.assertEqual(
                    main(["locale", "set", locale], services=runtime, stdout=output), 0
                )
                self.assertEqual(json.loads(output.getvalue())["locale"], locale)
                current = SettingsStore(layout).load()
                self.assertEqual(current.locale_preference, None if locale == "follow" else locale)
                self.assertEqual(current.default_rigor, Rigor.STRICT)
                self.assertEqual(current.recording_mode, original.recording_mode)
                self.assertEqual(
                    current.intervention_preferences,
                    normalize_settings(before).intervention_preferences,
                )
                self.assertEqual(current.record_retention_days, original.record_retention_days)
                self.assertEqual(current.record_size_limit_bytes, original.record_size_limit_bytes)
                self.assertEqual(current.onboarding_version_seen, original.onboarding_version_seen)
                self.assertEqual(current.metrics_consent, original.metrics_consent)
                self.assertEqual(current.revision, before.revision + 1)
            output = io.StringIO()
            main(["locale", "get"], services=runtime, stdout=output)
            self.assertEqual(json.loads(output.getvalue())["locale"], "follow")
            main(["locale", "set", "ja"], services=runtime, stdout=io.StringIO())
            main(["locale", "reset"], services=runtime, stdout=io.StringIO())
            self.assertIsNone(store.load().locale_preference)

    def test_legacy_bundle_shape_loads_and_mixed_completeness_is_rejected(self):
        import tempfile
        from copy import deepcopy

        from opensocrates.content.hashes import normalized_semantic_hash
        from opensocrates.content.schema import validate_compiled_bundle_shape
        from opensocrates.domain.validation import canonical_json
        from opensocrates.prompting.framing_prompt import get_prompt_fragment
        from opensocrates.rendering.messages import LocaleCatalog

        legacy = json.loads((ROOT / "content/compiled-content.bundle.json").read_text())
        legacy["product_version"] = "1.5.0"
        legacy["content_revision"] = 3
        for field in ("locale_messages",):
            legacy[field] = {locale: legacy[field][locale] for locale in ("en", "ko")}
        legacy["prompt_fragments"] = {
            key: {locale: localized[locale] for locale in ("en", "ko")}
            for key, localized in legacy["prompt_fragments"].items()
        }
        for method in legacy["methods"]:
            method["content_revision"] = 3
            for field in ("procedure", "complement_fragment", "display_name", "plain_action"):
                method[field] = {locale: method[field][locale] for locale in ("en", "ko")}
        semantic_fields = (
            "content_revision",
            "method_ids",
            "methods",
            "locale_messages",
            "prompt_fragments",
            "policy_versions",
        )
        legacy["normalized_semantic_hash"] = normalized_semantic_hash(
            {key: legacy[key] for key in semantic_fields}
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.bundle.json"
            path.write_text(canonical_json(legacy))
            loaded = load_compiled_bundle(path)
            self.assertEqual(set(loaded.locale_messages), {"en", "ko"})
            self.assertEqual(loaded.content_revision, 3)
            catalog = LocaleCatalog.from_bundle(loaded)
            for locale in ("en", "ko"):
                self.assertTrue(catalog.lookup(locale, "message.status.title"))
                self.assertTrue(get_prompt_fragment(loaded, locale, "controller"))
        partial = deepcopy(legacy)
        partial["locale_messages"]["zh"] = dict(partial["locale_messages"]["en"])
        with self.assertRaises(ValueError):
            validate_compiled_bundle_shape(partial)

    def test_v151_four_locale_bundle_shape_remains_compatible(self):
        import tempfile
        from copy import deepcopy

        from opensocrates.content.hashes import normalized_semantic_hash
        from opensocrates.content.schema import validate_compiled_bundle_shape
        from opensocrates.domain.validation import canonical_json
        from opensocrates.rendering.messages import LocaleCatalog
        from opensocrates.rendering.response_policy import (
            load_compiled_response_policy,
            response_guidance,
            validate_response_policy,
        )

        four = ("en", "ko", "zh", "ja")
        legacy = json.loads((ROOT / "content/compiled-content.bundle.json").read_text())
        legacy["product_version"] = "1.5.1"
        legacy["content_revision"] = 4
        legacy["locale_messages"] = {locale: legacy["locale_messages"][locale] for locale in four}
        legacy["prompt_fragments"] = {
            key: {locale: localized[locale] for locale in four}
            for key, localized in legacy["prompt_fragments"].items()
        }
        for method in legacy["methods"]:
            method["content_revision"] = 4
            for field in ("procedure", "complement_fragment", "display_name", "plain_action"):
                method[field] = {locale: method[field][locale] for locale in four}
        semantic_fields = (
            "content_revision",
            "method_ids",
            "methods",
            "locale_messages",
            "prompt_fragments",
            "policy_versions",
        )
        legacy["normalized_semantic_hash"] = normalized_semantic_hash(
            {key: legacy[key] for key in semantic_fields}
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v151.bundle.json"
            path.write_text(canonical_json(legacy))
            loaded = load_compiled_bundle(path)
            catalog = LocaleCatalog.from_bundle(loaded)
            self.assertEqual(set(loaded.locale_messages), set(four))
            self.assertEqual(loaded.content_revision, 4)
            for locale in four:
                self.assertTrue(catalog.lookup(locale, "message.status.title"))
        policy = deepcopy(
            load_compiled_response_policy(ROOT / "content/compiled-response-policy.json")
        )
        policy["locales"] = {locale: policy["locales"][locale] for locale in four}
        validate_response_policy(policy)
        for locale in four:
            self.assertEqual(
                response_guidance(policy, locale)["profile_id"], f"{locale}-natural-v1"
            )
        for partial_locales in (
            {"en", "ko", "zh"},
            {"en", "ko", "zh", "ja", "fr"},
            {"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt"},
        ):
            partial = deepcopy(legacy)
            full = json.loads((ROOT / "content/compiled-content.bundle.json").read_text())
            partial["locale_messages"] = {
                locale: full["locale_messages"][locale] for locale in partial_locales
            }
            with self.assertRaises(ValueError):
                validate_compiled_bundle_shape(partial)

    def test_legacy_teacher_question_model_round_trip_and_cjk_completeness(self):
        from opensocrates.domain.models import TeacherQuestionLocales
        from opensocrates.errors import ValidationError

        raw = json.loads((ROOT / "content/teacher-questions.yaml").read_text())["methods"][
            "deduction"
        ]
        pair = {locale: raw[locale] for locale in ("en", "ko")}
        legacy = TeacherQuestionLocales.from_dict(pair)
        self.assertEqual(legacy.zh, ())
        self.assertEqual(legacy.ja, ())
        self.assertEqual(TeacherQuestionLocales.from_dict(legacy.to_dict()), legacy)
        full = TeacherQuestionLocales.from_dict(raw)
        self.assertEqual(len(full.zh), 3)
        self.assertEqual(len(full.ja), 3)
        four = TeacherQuestionLocales.from_dict(
            {locale: raw[locale] for locale in ("en", "ko", "zh", "ja")}
        )
        self.assertEqual(four.fr, ())
        self.assertEqual(TeacherQuestionLocales.from_dict(four.to_dict()), four)
        for locale in ("fr", "de", "it", "es", "pt", "th"):
            self.assertEqual(len(getattr(full, locale)), 3)
        with self.assertRaises(ValidationError):
            TeacherQuestionLocales.from_dict({**pair, "zh": raw["zh"]})


if __name__ == "__main__":
    unittest.main()
