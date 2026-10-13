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

    def test_all_ninety_profiles_and_deterministic_default(self):
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
        self.assertEqual(seen, 90)

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
            manifest["locales"],
            {
                locale: f"response-policy/{locale}.yaml"
                for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th")
            },
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
        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
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
        for host in ("codex",):
            root = ROOT / "build/generated/plugins" / host
            text = (root / "skills/opensocrates/SKILL.md").read_text()
            self.assertIn(policy_identity(self.policy), text)
            self.assertIn("en-natural-v1", text)
            self.assertIn("ko-natural-v1", text)
            self.assertIn("zh-natural-v1", text)
            self.assertIn("ja-natural-v1", text)
            for locale in ("fr", "de", "it", "es", "pt", "th"):
                self.assertIn(f"{locale}-natural-v1", text)
            self.assertEqual(
                load_compiled_response_policy(root / "content/compiled-response-policy.json"),
                self.policy,
            )

    def test_strict_reference_guard_precedes_instruction_without_removing_it(self):
        from opensocrates.prompting.strict_prompt import strict_second_pass_fragment

        bundle = load_compiled_bundle(ROOT / "content/compiled-content.bundle.json")
        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            raw = strict_second_pass_fragment(bundle, locale)
            guard = (ROOT / f"plugin-src/shared/rigor/activation.{locale}.md").read_text().strip()
            for host in ("codex",):
                leaf = "rigor" if host == "codex" else "opensocrates"
                text = (ROOT / f"build/generated/plugins/{host}/skills/{leaf}/SKILL.md").read_text()
                self.assertIn(guard + "\n\n" + raw, text)
        self.assertIn(
            "explicitly requested",
            (ROOT / "build/generated/plugins/codex/skills/rigor/SKILL.md").read_text(),
        )

    def test_default_vs_explicit_and_policy_required_strict_paths(self):
        from dataclasses import replace

        from compile_prompts import _method_route, _representative_request
        from opensocrates.domain.enums import Rigor, RiskFloorReason
        from opensocrates.domain.rigor import build_rigor_decision
        from opensocrates.prompting.compiler import PromptCompiler, PromptEvent

        bundle = load_compiled_bundle(ROOT / "content/compiled-content.bundle.json")
        route = _method_route(bundle, "critical-thinking", None)
        compiler = PromptCompiler(bundle)
        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            request = _representative_request(bundle, locale, PromptEvent.STOP_REPAIR, route)
            self.assertNotIn("strict_second_pass", compiler.compile(request).fragment_ids)
            explicit = build_rigor_decision(
                Rigor.TOGETHER, Rigor.STRICT, Rigor.TOGETHER, RiskFloorReason.ORDINARY_JUDGMENT
            )
            floor = build_rigor_decision(
                Rigor.TOGETHER, None, Rigor.STRICT, RiskFloorReason.IRREVERSIBLE_COMMITMENT
            )
            for rigor in (explicit, floor):
                self.assertIn(
                    "strict_second_pass",
                    compiler.compile(replace(request, rigor=rigor)).fragment_ids,
                )

    def test_all_host_decision_guides_preserve_question_scope_contract(self):
        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            source = (ROOT / f"plugin-src/shared/decision/guide.{locale}.md").read_bytes()
            for host in ("codex",):
                generated = ROOT / "build/generated/plugins" / host
                self.assertEqual(
                    (
                        generated / f"skills/opensocrates/references/decision/guide.{locale}.md"
                    ).read_bytes(),
                    source,
                )

    def test_measurement_counts_complete_protected_artifact(self):
        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            text = '판정: 보류\n\n`ID-04` 12 kg [source](https://example.com)\n{"ok":false}\n'
            result = measure_visible_output(text, locale)
            self.assertEqual(result["unicode_scalars"], len(text))
            self.assertEqual(result["utf8_bytes"], len(text.encode()))
            self.assertEqual(result["whitespace_units"], len(text.split()))
            self.assertEqual(result["quality_inference"], "none")
            self.assertEqual(result["scope"], "complete_public_artifact")

    def test_cjk_measurement_and_profile_are_distinct(self):
        for locale, text in (
            ("zh", "结论：暂缓。"),
            ("ja", "結論は保留です。"),
            ("th", "สรุปว่ายังไม่ตัดสิน"),
        ):
            result = measure_visible_output(text, locale)
            self.assertEqual(result["unit_kind"], "unicode_scalar")
            self.assertEqual(result["unicode_scalars"], len(text))
            self.assertEqual(response_guidance(self.policy, locale)["locale"], locale)

    def test_european_measurement_keeps_word_units_without_inferring_quality(self):
        for locale, text in (
            ("fr", "Conclusion : en attente."),
            ("de", "Ergebnis: offen."),
            ("it", "Conclusione: in sospeso."),
            ("es", "Conclusión: pendiente."),
            ("pt", "Conclusão: pendente."),
        ):
            measured = measure_visible_output(text, locale)
            self.assertEqual(measured["unit_kind"], "word_like")
            self.assertEqual(measured["whitespace_units"], len(text.split()))
            self.assertEqual(measured["quality_inference"], "none")

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


class PromptCompilerLocaleBudgetChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_compiled_bundle(ROOT / "content/compiled-content.bundle.json")
        cls.methods = {method.id: method for method in cls.bundle.methods}

    def test_all_new_locale_primary_and_preferred_pairs_preserve_complete_content(self):
        from dataclasses import replace

        from compile_prompts import _method_route, _representative_request
        from opensocrates.domain.enums import Rigor, RiskFloorReason
        from opensocrates.domain.rigor import build_rigor_decision
        from opensocrates.hosts.codex.capability import default_capability_profile
        from opensocrates.prompting.compiler import PromptCompiler, PromptEvent

        compiler = PromptCompiler(self.bundle)
        unavailable_profile = default_capability_profile()
        strict = build_rigor_decision(
            Rigor.TOGETHER,
            Rigor.STRICT,
            Rigor.TOGETHER,
            RiskFloorReason.ORDINARY_JUDGMENT,
        )
        locales = ("fr", "de", "it", "es", "pt", "th")
        eligible_preferred = {
            method.id: next(
                (
                    hint
                    for hint in method.complements["preferred"]
                    if hint != method.id and self.methods[hint].family != method.family
                ),
                None,
            )
            for method in self.bundle.methods
        }
        checked = 0
        for locale in locales:
            start_limit = (24 if locale == "th" else 12) * 1024
            primary_limit = 900 if locale == "th" else 1200
            for method in self.bundle.methods:
                preferred = eligible_preferred[method.id]
                secondaries = (None,) if preferred is None else (None, preferred)
                for secondary_id in secondaries:
                    route = _method_route(self.bundle, method.id, secondary_id)
                    for event in (
                        PromptEvent.START,
                        PromptEvent.TOOL_OBSERVATION,
                        PromptEvent.STOP_REPAIR,
                    ):
                        default = replace(
                            _representative_request(self.bundle, locale, event, route),
                            capability_profile=unavailable_profile,
                        )
                        for prompt_request in (default, replace(default, rigor=strict)):
                            with self.subTest(
                                locale=locale,
                                primary=method.id,
                                secondary=secondary_id,
                                event=event,
                                rigor=prompt_request.rigor.effective_rigor,
                            ):
                                result = compiler.compile(prompt_request)
                                self.assertEqual(result.locale, locale)
                                self.assertEqual(
                                    result.context_bytes, len(result.text.encode("utf-8"))
                                )
                                limit = start_limit if event is PromptEvent.START else 2 * 1024
                                self.assertEqual(result.budget.context_limit_bytes, limit)
                                self.assertLessEqual(result.context_bytes, limit)
                                self.assertLessEqual(result.estimated_tokens, 2318)
                                self.assertTrue(
                                    all(ref.locale == locale for ref in result.fragments)
                                )
                                self.assertIn("capability_notice", result.fragment_ids)
                                self.assertIn(
                                    self.bundle.prompt_fragments["capability_notice"][
                                        locale
                                    ].rstrip("\n"),
                                    result.text,
                                )
                                self.assertTrue(result.text.endswith("\n"))
                                if event is PromptEvent.START:
                                    self.assertIn(
                                        method.procedure[locale].rstrip("\n"), result.text
                                    )
                                    self.assertIn(f"procedure:{method.id}", result.fragment_ids)
                                    self.assertLessEqual(
                                        result.budget.bucket_tokens["primary_procedure"],
                                        primary_limit,
                                    )
                                    if secondary_id is not None:
                                        secondary = self.methods[secondary_id]
                                        self.assertIn(
                                            secondary.complement_fragment[locale].rstrip("\n"),
                                            result.text,
                                        )
                                        self.assertIn(
                                            f"complement:{secondary_id}", result.fragment_ids
                                        )
                                        self.assertNotIn(
                                            secondary.procedure[locale].rstrip("\n"), result.text
                                        )
                                else:
                                    self.assertNotIn(f"procedure:{method.id}", result.fragment_ids)
                                if event is PromptEvent.STOP_REPAIR:
                                    self.assertEqual(
                                        "strict_second_pass" in result.fragment_ids,
                                        prompt_request.rigor.effective_rigor is Rigor.STRICT,
                                    )
                                checked += 1
        self.assertEqual(len(self.bundle.methods), 48)
        expected_routes = len(self.bundle.methods) + sum(
            preferred is not None for preferred in eligible_preferred.values()
        )
        self.assertEqual(checked, len(locales) * expected_routes * 3 * 2)

    def test_same_family_complement_hints_are_not_simultaneous_weighted_routes(self):
        from compile_prompts import _method_route
        from opensocrates.errors import ValidationError

        same_family_hints = [
            (method.id, hint)
            for method in self.bundle.methods
            for hint in method.complements["preferred"]
            if hint != method.id and self.methods[hint].family == method.family
        ]
        self.assertTrue(same_family_hints)
        for primary, secondary in same_family_hints:
            with self.subTest(primary=primary, secondary=secondary):
                with self.assertRaises(ValidationError):
                    _method_route(self.bundle, primary, secondary)

    def test_legacy_and_default_start_limits_reject_unsegmented_oversize_output(self):
        from opensocrates.prompting.context_budget import ContextSizeError, enforce_context_budget

        oversize = "é" * 4097
        for kwargs in ({}, *({"locale": locale} for locale in ("en", "ko", "zh", "ja"))):
            with self.subTest(**kwargs):
                with self.assertRaises(ContextSizeError):
                    enforce_context_budget("start", (), oversize, **kwargs)
        for locale in ("fr", "de", "it", "es", "pt", "th"):
            limit = (24 if locale == "th" else 12) * 1024
            with self.assertRaises(ContextSizeError):
                enforce_context_budget("start", (), "x" * (limit + 1), locale=locale)
            for event in ("tool_observation", "stop_repair"):
                with self.assertRaises(ContextSizeError):
                    enforce_context_budget(event, (), "é" * 1025, locale=locale)

    def test_locale_primary_exception_preserves_other_group_and_total_rejections(self):
        from opensocrates.prompting.context_budget import (
            FragmentBudgetError,
            TotalPromptBudgetError,
            enforce_context_budget,
            enforce_fragment_budgets,
        )

        for locale in ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"):
            primary_limit = 1200 if locale in {"fr", "de", "it", "es", "pt"} else 900
            with self.subTest(locale=locale):
                with self.assertRaises(FragmentBudgetError):
                    enforce_fragment_budgets(
                        {"procedure:deduction": "x " * (primary_limit + 1)}, locale=locale
                    )
                with self.assertRaises(FragmentBudgetError):
                    enforce_fragment_budgets({"complement:deduction": "x " * 221}, locale=locale)
                with self.assertRaises(TotalPromptBudgetError):
                    enforce_context_budget("start", (), "x " * 2319, locale=locale)
        with self.assertRaises(FragmentBudgetError):
            enforce_fragment_budgets({"procedure:deduction": "x " * 901})

    def test_budget_helpers_and_compiler_reject_unknown_locale_without_fallback(self):
        from dataclasses import replace

        from compile_prompts import _method_route, _representative_request
        from opensocrates.prompting.compiler import MissingLocaleError, PromptCompiler, PromptEvent
        from opensocrates.prompting.context_budget import (
            context_limit,
            enforce_context_budget,
            enforce_fragment_budgets,
        )

        route = _method_route(self.bundle, "critical-thinking", None)
        original = _representative_request(self.bundle, "en", PromptEvent.START, route)
        compiler = PromptCompiler(self.bundle)
        for locale in ("ru", "FR", "fr-FR", "th-TH", "", "PRIVATE_LOCALE_SENTINEL"):
            with self.subTest(locale=locale):
                with self.assertRaises(ValueError) as error:
                    context_limit("start", locale=locale)
                self.assertNotIn("PRIVATE_LOCALE_SENTINEL", str(error.exception))
                with self.assertRaises(ValueError):
                    enforce_fragment_budgets({}, locale=locale)
                with self.assertRaises(ValueError):
                    enforce_context_budget("start", (), "", locale=locale)
                with self.assertRaises(MissingLocaleError) as error:
                    compiler.compile(replace(original, locale=locale))
                self.assertNotIn("PRIVATE_LOCALE_SENTINEL", str(error.exception))


if __name__ == "__main__":
    unittest.main()
