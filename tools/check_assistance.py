"""Deterministic assistance policy and strict command contract checks."""

from __future__ import annotations

import io
import json
import unittest
from copy import deepcopy

from opensocrates.assistance import AssistanceProfile, InvalidAssistanceRequest, plan_assistance
from opensocrates.cli.assistance import run_assistance
from opensocrates.cli.main import main

REQUEST_ID = "123e4567-e89b-42d3-a456-426614174000"


def request(locale: str = "en", **task_changes: object) -> dict[str, object]:
    task = {
        "task_kind": "judgment",
        "task_family": "planning",
        "complexity": "bounded",
        "stakes": "ordinary",
        "uncertainty": "bounded",
        "context_need": "none",
        "completion": "in_progress",
        "material_change": False,
    }
    task.update(task_changes)
    return {
        "schema": "opensocrates.assistance.request/1.0.0",
        "request_id": REQUEST_ID,
        "locale": locale,
        "task": task,
        "model_context": {"model": None, "effort": None, "client": None, "attribution": "unknown"},
        "profile_override": None,
    }


def profile(state: str = "validated") -> AssistanceProfile:
    return AssistanceProfile(
        "profile-test",
        2,
        state,
        "test-model",
        "medium",
        "codex",
        frozenset(("planning",)),
        raise_to_structured=True,
        optional_components=("verification_target",),
        validation_reference="eval-1" if state == "validated" else None,
    )


class AssistanceChecks(unittest.TestCase):
    def test_precedence_and_budgets(self) -> None:
        cases = (
            (
                {"task_kind": "mechanical", "complexity": "coupled", "stakes": "consequential"},
                "none",
                "continue",
                0,
            ),
            (
                {
                    "completion": "checks_satisfied",
                    "material_change": False,
                    "context_need": "continuity",
                },
                "none",
                "finish",
                0,
            ),
            ({"completion": "checks_satisfied", "material_change": True}, "light", "continue", 0),
            (
                {"completion": "dependent_input_missing", "stakes": "consequential"},
                "structured",
                "resolve_dependency",
                0,
            ),
            (
                {"completion": "dependent_input_missing", "task_kind": "mechanical"},
                "none",
                "resolve_dependency",
                0,
            ),
            (
                {"complexity": "coupled", "context_need": "continuity"},
                "structured",
                "continue",
                24576,
            ),
            ({"context_need": "continuity"}, "light", "continue", 8192),
        )
        for changes, level, action, budget in cases:
            with self.subTest(changes=changes):
                result = plan_assistance(request(**changes))
                self.assertEqual(
                    (
                        result["assistance_level"],
                        result["next_action"],
                        result["context_pack_budget_bytes"],
                    ),
                    (level, action, budget),
                )
                self.assertEqual(result["application"], "unverified")

    def test_component_order_and_locale_equivalence(self) -> None:
        for changes in ({}, {"context_need": "current_evidence"}, {"complexity": "coupled"}):
            en, ko = (plan_assistance(request(locale, **changes)) for locale in ("en", "ko"))
            self.assertEqual(en, ko)
        self.assertEqual(
            plan_assistance(request())["guidance_components"],
            ["goal", "constraints", "completion_cue"],
        )
        self.assertEqual(
            plan_assistance(request(context_need="current_evidence"))["guidance_components"],
            ["goal", "constraints", "evidence_need", "completion_cue"],
        )
        self.assertEqual(
            plan_assistance(request(complexity="coupled"))["guidance_components"],
            [
                "goal",
                "constraints",
                "evidence_need",
                "bounded_subgoal",
                "verification_target",
                "completion_cue",
            ],
        )

    def test_profiles_are_exact_and_candidate_requires_explicit_gate(self) -> None:
        value = request()
        value["model_context"] = {
            "model": "test-model",
            "effort": "medium",
            "client": "codex",
            "attribution": "operator_declared",
        }
        result = plan_assistance(value, profiles=(profile(),))
        self.assertEqual(
            (
                result["assistance_level"],
                result["profile_evidence"],
                result["validation_reference"],
            ),
            ("structured", "validated_run", "eval-1"),
        )
        self.assertEqual(
            result["guidance_components"],
            ["goal", "constraints", "verification_target", "completion_cue"],
        )
        changed = deepcopy(value)
        changed["model_context"]["effort"] = "high"
        self.assertEqual(
            plan_assistance(changed, profiles=(profile(),))["profile_evidence"], "task_default"
        )
        self.assertEqual(
            plan_assistance(value, profiles=(profile("withdrawn"),))["profile_evidence"],
            "task_default",
        )
        self.assertEqual(
            plan_assistance(value, profiles=(profile("candidate"),))["profile_evidence"],
            "task_default",
        )
        value["profile_override"] = {
            "profile_id": "profile-test",
            "revision": 2,
            "authorization_basis": "operator evaluation run",
        }
        self.assertEqual(
            plan_assistance(value, profiles=(profile("candidate"),), candidate_enabled=True)[
                "profile_evidence"
            ],
            "candidate_evaluation",
        )
        self.assertEqual(
            plan_assistance(value, profiles=(profile("candidate"),), candidate_enabled=False)[
                "profile_evidence"
            ],
            "task_default",
        )

    def test_closed_request_rejects_bad_values(self) -> None:
        mutants = []
        for path, value in (("schema", "wrong"), ("request_id", "bad"), ("locale", "fr")):
            changed = request()
            changed[path] = value
            mutants.append(changed)
        changed = request()
        changed["extra"] = 1
        mutants.append(changed)
        changed = request()
        changed["task"]["material_change"] = 1
        mutants.append(changed)
        changed = request()
        changed["task"]["unknown"] = True
        mutants.append(changed)
        changed = request()
        changed["model_context"]["attribution"] = "trusted"
        mutants.append(changed)
        changed = request()
        changed["profile_override"] = {"profile_id": "p", "revision": 0, "authorization_basis": "x"}
        mutants.append(changed)
        for changed in mutants:
            with self.subTest(changed=changed), self.assertRaises(InvalidAssistanceRequest):
                plan_assistance(changed)

    def test_cli_byte_bound_duplicate_keys_and_dispatch_without_runtime(self) -> None:
        out = io.StringIO()
        payload = json.dumps(request(), ensure_ascii=False).encode()
        self.assertEqual(main(["assistance"], stdin=io.BytesIO(payload), stdout=out), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "ok")
        for bad in (b"{" + b'"schema":1,"schema":2}', b"x" * 16385, b"\xff", b"NaN"):
            out = io.StringIO()
            self.assertEqual(run_assistance(io.BytesIO(bad), out), 2)
            self.assertEqual(json.loads(out.getvalue())["status"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
