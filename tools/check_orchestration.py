#!/usr/bin/env python3
"""Deterministic orchestration gates. Fake model adapters are not live E2E proof."""

from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import check_project_memory as memory_checks
from opensocrates.cli.main import main
from opensocrates.cli.orchestration import run_orchestration
from opensocrates.orchestration import paths as path_module
from opensocrates.orchestration import runtime as runtime_module
from opensocrates.orchestration.adapter import CallResult, CodexAdapter, null_usage
from opensocrates.orchestration.contracts import assets_root, plan, schema
from opensocrates.orchestration.guidance import guides
from opensocrates.orchestration.memory import MemorySnapshot
from opensocrates.orchestration.paths import BoundaryError, digest, identity, read_text
from opensocrates.orchestration.runtime import Coordinator, orchestrate
from opensocrates.project_memory.contracts import validate
from opensocrates.project_memory.store import MemoryStore

ROOT = assets_root()


def unit(key="make", *, domain="software", dependencies=(), task_kind="judgment"):
    return {
        "unit_id": key,
        "domain": domain,
        "task_kind": task_kind,
        "role": "production",
        "objective": "Create the specified bounded result.",
        "owned_paths": [key + ".txt"],
        "dependencies": list(dependencies),
        "source_ids": ["seed"],
        "requirement_ids": ["contract"],
        "specialists": [],
        "obligations": [
            {
                "id": "correct",
                "requirement_id": "contract",
                "description": "Matches the independently specified value.",
                "required": True,
            }
        ],
        "checks": [
            {
                "check_id": "oracle",
                "argv": [sys.executable, "-B", "-c", "assert True"],
                "obligation_ids": ["correct"],
                "authorization_reference": "fixture:check",
                "expected_exit_code": 0,
            }
        ],
        "seed": None,
    }


def request(root, target):
    return {
        "schema": "opensocrates.orchestration.request/1.0.0",
        "operation": "run",
        "run_id": str(uuid4()),
        "task_id": str(uuid4()),
        "revision": 1,
        "authorization": {"reference": "fixture:authorized", "attribution": "operator_declared"},
        "model": {"name": "gpt-6-astra", "effort": "max"},
        "locale": "en",
        "objective": "Deliver a bounded verified candidate.",
        "required_artifacts": ["make.txt"],
        "constraints": [{"id": "contract", "text": "The exact expected value is good."}],
        "permissions": ["Produce declared candidate files and run declared checks."],
        "prohibitions": ["No existing project writes."],
        "source_root": str(root),
        "sources": [
            {
                "id": "seed",
                "path": "source.txt",
                "sha256": digest((root / "source.txt").read_bytes()),
            }
        ],
        "candidate_root": str(target),
        "client_path": "/explicit/qualified/codex",
        "repair_limit": 1,
        "memory": None,
        "handoff": ["Current plan is the complete accepted contract."],
        "units": [unit()],
    }


class FakeAdapter:
    """Controlled public behavior only; never presented as real Codex output."""

    version = "fake-deterministic-adapter"
    sha256 = digest(b"fake")

    def __init__(self, *, defect=False, fail_role=None, mutate=None):
        self.defect, self.fail_role, self.mutate = defect, fail_role, mutate
        self.assignments = []
        self.checks = []
        self.made = 0

    def probe(self):
        return None

    def invoke(self, assignment, cwd):
        self.assignments.append(copy.deepcopy(assignment))
        role = assignment["role"]
        receipt = {
            "assignment_id": assignment["assignment_id"],
            "unit_id": assignment["unit_id"],
            "role": role,
            "input_sha256": identity(assignment),
            "output_sha256": None,
            "thread_sha256": digest(assignment["assignment_id"].encode()),
            "model": assignment["model"],
            "status": "completed",
            "usage": null_usage(),
            "provider_error_events": 0,
            "failed_turn_events": 0,
            "process_exit_code": 0,
            "backend_attempts": None,
            "reason": "deterministic_fake",
        }
        if role == self.fail_role:
            receipt.update(
                status="failed", process_exit_code=1, provider_error_events=1, failed_turn_events=1
            )
            return CallResult(None, receipt)
        if role in {"production", "design"}:
            self.made += 1
            text = "bad" if self.defect and self.made == 1 else "good"
            value = {
                "schema": "opensocrates.orchestration.candidate/1.0.0",
                "assignment_id": assignment["assignment_id"],
                "files": [{"path": name, "content": text} for name in assignment["owned_paths"]],
                "blocked_reason": None,
            }
        else:
            name = assignment["owned_paths"][0]
            content = (cwd / name).read_bytes()
            bad = content != b"good"
            checks = assignment["check_receipts"]
            missing = role == "execution_verification" and not checks
            status = "unknown" if missing else "failed" if bad else "passed"
            evidence = ["artifact:" + digest(content)] + [
                "check:" + item["check_id"] for item in checks
            ]
            finding = {
                "artifact_sha256": digest(content),
                "requirement_id": "contract",
                "location": name,
                "expected": "good",
                "observed": content.decode(),
                "reproduction": "Read the exact UTF-8 file and compare with the independently specified value.",
                "impact": "Required result differs.",
                "missing_evidence": [],
                "severity": "blocking",
            }
            value = {
                "schema": "opensocrates.orchestration.assessment/1.0.0",
                "assignment_id": assignment["assignment_id"],
                "candidate_sha256": assignment["candidate_sha256"],
                "verdict": "repair_required" if bad or missing else "pass",
                "findings": [finding] if bad else [],
                "obligations": [
                    {
                        "id": item["id"],
                        "status": status,
                        "expected": "good",
                        "observed": content.decode(),
                        "reproduction": "Compare exact bytes and the declared check receipt.",
                        "evidence_ids": evidence,
                    }
                    for item in assignment["obligations"]
                ],
            }
        if self.mutate:
            self.mutate(assignment, cwd, value)
        receipt["output_sha256"] = identity(value)
        return CallResult(value, receipt)

    def check(self, check, cwd, files, candidate_sha256):
        self.checks.append((check["check_id"], candidate_sha256))
        bad = any(data == b"bad" for name, data in files.items() if not name.startswith("inputs/"))
        return {
            "check_id": check["check_id"],
            "candidate_sha256": candidate_sha256,
            "argv_sha256": identity(check["argv"]),
            "status": "failed" if bad else "passed",
            "exit_code": 1 if bad else 0,
            "stdout_sha256": digest(b""),
            "stderr_sha256": digest(b""),
            "obligation_ids": check["obligation_ids"],
            "reason": "unexpected_exit" if bad else "expected_exit",
        }


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "source"
        self.root.mkdir()
        (self.root / "source.txt").write_text("scoped source")
        self.req = request(self.root, self.base / "candidate")

    def run_plan(self, adapter=None):
        result = orchestrate(self.req, adapter=adapter or FakeAdapter())
        validate(result, schema("response"))
        return result

    def test_complete_distinct_roles_and_actual_artifact_publication(self):
        adapter = FakeAdapter()
        result = self.run_plan(adapter)
        self.assertEqual(result["status"], "integration_pending")
        self.assertEqual((self.base / "candidate/artifacts/make.txt").read_text(), "good")
        self.assertEqual((self.base / "candidate/versions/make/v1/make.txt").read_text(), "good")
        self.assertEqual(
            [item["role"] for item in adapter.assignments],
            ["production", "review", "execution_verification"],
        )
        self.assertEqual(len({item["assignment_id"] for item in adapter.assignments}), 3)
        self.assertEqual((self.root / "source.txt").read_text(), "scoped source")
        self.assertTrue(all(item["model"] == self.req["model"] for item in result["calls"]))

    def test_bounded_repair_rereviews_exact_version_then_dependent_domain(self):
        self.req["units"].append(unit("memo", domain="document", dependencies=["make"]))
        self.req["required_artifacts"].append("memo.txt")
        adapter = FakeAdapter(defect=True)
        result = self.run_plan(adapter)
        self.assertEqual(result["status"], "integration_pending")
        versions = result["units"][0]["versions"]
        self.assertEqual([item["qualified"] for item in versions], [False, True])
        self.assertNotEqual(versions[0]["candidate_sha256"], versions[1]["candidate_sha256"])
        self.assertEqual(len(adapter.checks), 3)
        dependent = [item for item in adapter.assignments if item["unit_id"] == "memo"][0]
        self.assertEqual(dependent["domain"], "document")
        self.assertEqual(
            [item["sha256"] for item in dependent["inputs"] if item["kind"] == "dependency"],
            [digest(b"good")],
        )
        self.assertTrue(adapter.assignments[3]["repair_findings"])
        for assignment in adapter.assignments:
            if assignment["role"] in {"review", "execution_verification"}:
                self.assertEqual(assignment["repair_findings"], [])
                self.assertNotIn("prior_rating", assignment)
        self.assertEqual((self.base / "candidate/versions/make/v1/make.txt").read_text(), "bad")

    def test_explicit_seed_is_never_misattributed_to_model(self):
        self.req["units"][0]["seed"] = {
            "author": "synthetic_fixture",
            "files": [{"path": "make.txt", "content": "bad"}],
        }
        result = self.run_plan()
        self.assertEqual(result["units"][0]["versions"][0]["producer_id"], "synthetic_fixture")
        self.assertEqual(
            [item["role"] for item in result["calls"]],
            ["review", "execution_verification", "production", "review", "execution_verification"],
        )
        self.assertEqual(result["status"], "integration_pending")

    def test_mechanical_skips_optional_domain_guidance_but_not_acceptance(self):
        self.req["units"][0]["task_kind"] = "mechanical"
        adapter = FakeAdapter()
        self.run_plan(adapter)
        self.assertEqual(len(adapter.assignments), 3)
        for assignment in adapter.assignments:
            self.assertFalse(
                any(item["id"].endswith("software.en.md") for item in assignment["guides"])
            )

    def test_unknown_blocks_only_dependent_units(self):
        self.req["units"] = [
            unit("unknown", domain="unknown"),
            unit("blocked", dependencies=["unknown"]),
            unit("free", domain="data"),
        ]
        self.req["required_artifacts"] = ["unknown.txt", "blocked.txt", "free.txt"]
        result = self.run_plan()
        self.assertEqual(
            [item["status"] for item in result["units"]],
            ["classification_gap", "blocked_dependency", "qualified_candidate"],
        )
        self.assertEqual(result["status"], "partial")

    def test_graph_ownership_and_unowned_required_artifact_rejected(self):
        bad_plans = []
        for name in ("missing", "make"):
            value = copy.deepcopy(self.req)
            value["units"][0]["dependencies"] = [name]
            bad_plans.append(value)
        value = copy.deepcopy(self.req)
        value["units"] += [unit("second", dependencies=["make"])]
        value["units"][0]["dependencies"] = ["second"]
        bad_plans.append(value)
        for path in ("make.txt", "MAKE.TXT", "make.txt/nested"):
            value = copy.deepcopy(self.req)
            second = unit("second")
            second["owned_paths"] = [path]
            value["units"].append(second)
            bad_plans.append(value)
        value = copy.deepcopy(self.req)
        value["required_artifacts"].append("unowned.txt")
        bad_plans.append(value)
        for value in bad_plans:
            with self.assertRaises(BoundaryError):
                plan(value)

    def test_full_guides_constraints_and_source_hashes_in_every_role(self):
        self.req["constraints"][0]["text"] = "한글 제약 " * 800
        self.req["units"][0]["specialists"] = ["contracts", "ownership"]
        self.req["locale"] = "ko"
        adapter = FakeAdapter()
        self.run_plan(adapter)
        for assignment in adapter.assignments:
            self.assertEqual(assignment["constraints"], self.req["constraints"])
            for guide in assignment["guides"]:
                expected = (ROOT / "plugin-src/shared" / guide["id"]).read_bytes()
                self.assertEqual(guide["text"].encode(), expected)
                self.assertEqual(guide["sha256"], digest(expected))
            self.assertIn(
                "coding-specialists/v0.1.1/contracts.ko.md",
                [item["id"] for item in assignment["guides"]],
            )
            self.assertEqual(assignment["inputs"][0]["sha256"], self.req["sources"][0]["sha256"])

    def test_budget_rejects_without_truncating_or_launching(self):
        self.req["constraints"][0]["text"] = "x" * 8193
        adapter = FakeAdapter()
        with self.assertRaises(ValueError):
            self.run_plan(adapter)
        self.assertEqual(adapter.assignments, [])
        self.assertFalse((self.base / "candidate").exists())

    def test_changed_source_invalidates_unit_without_stopping_unrelated_work(self):
        self.req["units"].append(unit("free", domain="document"))
        self.req["units"][1]["source_ids"] = []

        def mutation(assignment, cwd, value):
            if assignment["unit_id"] == "make":
                (self.root / "source.txt").write_text("changed")

        result = self.run_plan(FakeAdapter(mutate=mutation))
        self.assertEqual(
            [item["status"] for item in result["units"]], ["source_conflict", "qualified_candidate"]
        )
        self.assertEqual(result["calls"][0]["status"], "inputs_changed")

    def test_reviewer_cannot_patch_candidate(self):
        def mutation(assignment, cwd, value):
            if assignment["role"] == "review":
                (cwd / "make.txt").write_text("reviewer patch")

        result = self.run_plan(FakeAdapter(mutate=mutation))
        self.assertEqual(result["units"][0]["status"], "source_conflict")
        self.assertNotEqual(result["status"], "integration_pending")

    def test_old_artifact_digest_or_forged_evidence_cannot_pass(self):
        for field in ("candidate_sha256", "evidence_ids"):
            value = copy.deepcopy(self.req)
            value["candidate_root"] = str(self.base / field)

            def mutation(assignment, cwd, result, field=field):
                if assignment["role"] == "review":
                    if field == "candidate_sha256":
                        result[field] = digest(b"old")
                    else:
                        result["obligations"][0][field] = ["check:invented"]

            result = orchestrate(value, adapter=FakeAdapter(mutate=mutation))
            self.assertNotEqual(result["status"], "integration_pending")

    def test_required_unknown_or_failed_check_never_closes(self):
        self.req["units"][0]["checks"] = []
        result = self.run_plan()
        self.assertEqual(result["units"][0]["required_open"], ["correct"])
        self.assertEqual(result["units"][0]["status"], "repair_required")
        self.assertEqual(len(result["units"][0]["versions"]), 2)

    def test_failure_and_null_usage_are_retained(self):
        result = self.run_plan(FakeAdapter(fail_role="production"))
        self.assertEqual(len(result["calls"]), 1)
        call = result["calls"][0]
        self.assertEqual(call["status"], "failed")
        self.assertEqual(call["usage"], null_usage())
        self.assertEqual(call["provider_error_events"], 1)
        self.assertEqual(call["failed_turn_events"], 1)
        self.assertEqual(call["process_exit_code"], 1)
        self.assertIsNone(call["backend_attempts"])

    def test_safe_paths_symlinks_and_existing_workspace_protected(self):
        for name in (
            "../escape",
            "/absolute",
            "a\\b",
            "a/../b",
            ".codex/config",
            "inputs/collision",
            "control/schema",
        ):
            value = copy.deepcopy(self.req)
            value["units"][0]["owned_paths"] = [name]
            with self.assertRaises(ValueError):
                plan(value)
        linked = self.root / "link.txt"
        linked.symlink_to(self.root / "source.txt")
        with self.assertRaises(BoundaryError):
            read_text(self.root, "link.txt")
        self.req["candidate_root"] = str(self.root)
        with self.assertRaises(BoundaryError):
            plan(self.req)

    def test_prepare_is_stateless_zero_calls_and_cli_failure_has_no_input_echo(self):
        self.req["operation"] = "prepare"
        adapter = FakeAdapter()
        result = self.run_plan(adapter)
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(adapter.assignments, [])
        self.assertFalse((self.base / "candidate").exists())
        self.req["secret_unknown_key"] = "RAW_PROMPT_CANARY"
        output = io.StringIO()
        self.assertEqual(
            main(["orchestrate"], stdin=io.StringIO(json.dumps(self.req)), stdout=output), 2
        )
        self.assertNotIn("RAW_PROMPT_CANARY", output.getvalue())
        validate(json.loads(output.getvalue()), schema("response"))

    def test_native_adapter_argument_policy_no_resume_or_fallback(self):
        coordinator = Coordinator(self.req, adapter=FakeAdapter())
        assignment, _ = coordinator.assignment(self.req["units"][0], "production", {}, [], [])
        adapter = CodexAdapter(self.req["client_path"])
        argv = adapter._argv(assignment, self.root, self.root / "schema.json")
        for flag in (
            "--ephemeral",
            "--ignore-user-config",
            "--json",
            "read-only",
            "skip_host_skill_discovery",
            "project_doc_max_bytes=0",
            'approval_policy="never"',
            "allow_login_shell=false",
        ):
            self.assertIn(flag, argv)
        self.assertNotIn("resume", argv)
        self.assertNotIn("fork", argv)
        self.assertIn('model_reasoning_effort="max"', argv)
        sandbox = adapter._sandbox_argv(self.root, ["/bin/cat", "source.txt"])
        self.assertEqual(sandbox[1:4], ["sandbox", "-P", ":read-only"])
        self.assertNotIn("macos", sandbox)

    def test_jsonl_projection_discards_reasoning_and_tools_counts_failures(self):
        class Process:
            stdout = io.BytesIO(
                b"\n".join(
                    json.dumps(event).encode()
                    for event in [
                        {"type": "thread.started", "thread_id": "private-thread"},
                        {
                            "type": "item.completed",
                            "item": {"type": "reasoning", "text": "PRIVATE_REASONING_CANARY"},
                        },
                        {
                            "type": "item.completed",
                            "item": {
                                "type": "command_execution",
                                "aggregated_output": "RAW_TOOL_CANARY",
                            },
                        },
                        {"type": "error", "message": "PRIVATE_ERROR_CANARY"},
                        {"type": "turn.failed", "error": {"message": "PRIVATE_FAILURE_CANARY"}},
                        {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
                        {
                            "type": "turn.completed",
                            "usage": {
                                "input_tokens": 10,
                                "cache_write_input_tokens": 3,
                                "output_tokens": 2,
                            },
                        },
                    ]
                )
                + b"\n"
            )

        receipt = {
            "thread_sha256": None,
            "usage": null_usage(),
            "provider_error_events": 0,
            "failed_turn_events": 0,
        }
        final, done = CodexAdapter._events(Process(), receipt)
        self.assertEqual(final, "{}")
        self.assertTrue(done)
        self.assertEqual(receipt["provider_error_events"], 1)
        self.assertEqual(receipt["usage"]["cache_write_input_tokens"], 3)
        self.assertIsNone(receipt["usage"]["reasoning_output_tokens"])
        self.assertNotIn("CANARY", json.dumps(receipt))
        self.assertNotIn("private-thread", json.dumps(receipt))

    def test_reused_thread_identity_and_role_model_substitution_rejected(self):
        for mode in ("thread", "model"):

            class Forged(FakeAdapter):
                def invoke(self, assignment, cwd, mode=mode):
                    result = super().invoke(assignment, cwd)
                    if mode == "thread":
                        result.receipt["thread_sha256"] = digest(b"same-thread")
                    else:
                        result.receipt["model"] = {"name": "other-model", "effort": "low"}
                    return result

            value = copy.deepcopy(self.req)
            value["candidate_root"] = str(self.base / mode)
            result = orchestrate(value, adapter=Forged())
            self.assertNotEqual(result["status"], "integration_pending")
            self.assertEqual(result["units"][0]["status"], "unavailable")

    def test_failed_required_or_mismatched_execution_receipt_blocks(self):
        for mode in ("failed", "mismatch"):

            class BadCheck(FakeAdapter):
                def check(self, check, cwd, files, candidate_sha256, mode=mode):
                    result = super().check(check, cwd, files, candidate_sha256)
                    if mode == "failed":
                        result.update(status="failed", exit_code=1, reason="unexpected_exit")
                    else:
                        result["candidate_sha256"] = digest(b"old-version")
                    return result

            value = copy.deepcopy(self.req)
            value["repair_limit"] = 0
            value["candidate_root"] = str(self.base / mode)
            result = orchestrate(value, adapter=BadCheck())
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["units"][0]["required_open"], ["correct"])
            self.assertFalse(result["units"][0]["versions"][0]["qualified"])

    def test_cancellation_and_capability_unavailability_do_not_launch_followups(self):
        class Cancelled(FakeAdapter):
            def invoke(self, assignment, cwd):
                result = super().invoke(assignment, cwd)
                result.receipt.update(status="cancelled", reason="caller_cancelled")
                result.value = None
                return result

        result = self.run_plan(Cancelled())
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(len(result["calls"]), 1)

        class Unavailable(FakeAdapter):
            def probe(self):
                raise BoundaryError("sandbox_unavailable")

        result = self.run_plan(Unavailable())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["calls"], [])
        self.assertFalse((self.base / "candidate").exists())

    def test_later_source_change_invalidates_qualified_dependency_closure(self):
        self.req["units"] = [
            unit(),
            unit("child", dependencies=["make"]),
            unit("unrelated", domain="document"),
        ]
        self.req["units"][1]["source_ids"] = []
        self.req["units"][2]["source_ids"] = []

        def mutate(assignment, cwd, value):
            if (
                assignment["unit_id"] == "unrelated"
                and assignment["role"] == "execution_verification"
            ):
                (self.root / "source.txt").write_text("changed after the first qualification")

        result = self.run_plan(FakeAdapter(mutate=mutate))
        states = {item["unit_id"]: item["status"] for item in result["units"]}
        self.assertEqual(states["make"], "source_conflict")
        self.assertNotEqual(states["child"], "qualified_candidate")
        self.assertEqual(states["unrelated"], "qualified_candidate")
        self.assertFalse((self.base / "candidate/artifacts/make.txt").exists())

    def _wire(self, coordinator):
        output = io.StringIO()
        with patch(
            "opensocrates.cli.orchestration.orchestrate",
            side_effect=lambda value: coordinator.run(),
        ):
            code = run_orchestration(io.StringIO(json.dumps(coordinator.request)), output)
        result = json.loads(output.getvalue())
        validate(result, schema("response"))
        return code, result

    def _closed(self, coordinator):
        self.assertEqual(coordinator.source_binding.entries, [])
        self.assertEqual(coordinator.output_binding.entries, [])

    def test_only_known_system_aliases_are_normalized_before_binding(self):
        if str(self.root).startswith("/private/var/") and Path("/var").is_symlink():
            req = copy.deepcopy(self.req)
            req["source_root"] = req["source_root"].replace("/private/var/", "/var/", 1)
            req["candidate_root"] = str(self.base / "system-alias-candidate").replace(
                "/private/var/", "/var/", 1
            )
            self.assertEqual(
                orchestrate(req, adapter=FakeAdapter())["status"], "integration_pending"
            )
        real = self.base / "real-parent"
        real.mkdir()
        alias = self.base / "user-alias"
        alias.symlink_to(real, target_is_directory=True)
        req = copy.deepcopy(self.req)
        req["candidate_root"] = str(alias / "candidate")
        adapter = FakeAdapter()
        result = orchestrate(req, adapter=adapter)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(adapter.assignments, [])
        self.assertFalse((real / "candidate").exists())

    def test_bound_publication_rejects_replaced_source_parent_and_ancestor(self):
        for mode in ("parent", "ancestor", "source"):
            with self.subTest(mode=mode):
                base = self.base / mode
                source, ancestor = base / "source", base / "ancestor"
                source.mkdir(parents=True)
                (source / "source.txt").write_text("scoped source")
                parent = ancestor / "parent"
                parent.mkdir(parents=True)
                req = request(source, parent / "candidate")
                coordinator = Coordinator(req, adapter=FakeAdapter())
                victim = {"parent": parent, "ancestor": ancestor, "source": source}[mode]
                victim.rename(base / "original")
                victim.symlink_to(source if mode != "source" else parent, target_is_directory=True)
                result = coordinator.run()
                self.assertNotEqual(result["status"], "integration_pending")
                self.assertEqual(result["publication"]["status"], "not_started")
                self.assertFalse((source / "candidate").exists())
                self.assertFalse((source / "artifacts").exists())
                self._closed(coordinator)

    def test_publication_root_replacement_and_write_time_swap_never_follow_source(self):
        for timing in ("before_write", "during_write"):
            with self.subTest(timing=timing):
                req = copy.deepcopy(self.req)
                target = self.base / timing
                req["candidate_root"] = str(target)
                coordinator = Coordinator(req, adapter=FakeAdapter())
                swapped = False

                def swap(target=target, timing=timing):
                    nonlocal swapped
                    if not swapped:
                        target.rename(self.base / (timing + "-original"))
                        target.symlink_to(self.root, target_is_directory=True)
                        swapped = True

                write_files = runtime_module.write_bound_files
                write = os.write

                def before(root, files, guard, started, completed, write_files=write_files):
                    swap()
                    return write_files(root, files, guard, started, completed)

                def during(descriptor, data, write=write):
                    swap()
                    return write(descriptor, data)

                boundary = (
                    patch.object(runtime_module, "write_bound_files", side_effect=before)
                    if timing == "before_write"
                    else patch.object(path_module.os, "write", side_effect=during)
                )
                with boundary:
                    result = coordinator.run()
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(result["publication"]["status"], "incomplete")
                self.assertFalse(result["publication"]["location_verified"])
                self.assertFalse((self.root / "artifacts").exists())
                self.assertFalse((self.root / "versions").exists())
                self.assertEqual((self.root / "source.txt").read_text(), "scoped source")
                self._closed(coordinator)

    def test_publication_parent_swap_inside_directory_creation_cannot_redirect(self):
        parent = self.base / "owned-parent"
        parent.mkdir()
        req = copy.deepcopy(self.req)
        req["candidate_root"] = str(parent / "candidate")
        coordinator = Coordinator(req, adapter=FakeAdapter())
        mkdir = os.mkdir
        swapped = False

        def replacing(name, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if name == "candidate" and dir_fd is not None and not swapped:
                parent.rename(self.base / "held-original-parent")
                parent.symlink_to(self.root, target_is_directory=True)
                swapped = True
            return mkdir(name, mode, dir_fd=dir_fd)

        with patch.object(path_module.os, "mkdir", side_effect=replacing):
            result = coordinator.run()
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse((self.root / "candidate").exists())
        self.assertFalse(result["publication"]["location_verified"])
        self._closed(coordinator)

    def test_cancellation_or_failure_after_calls_preserves_wire_receipts(self):
        for method, failure in (
            ("_publish", KeyboardInterrupt),
            ("_validate_current", KeyboardInterrupt),
            ("_validate_current", OSError),
        ):
            with self.subTest(method=method, failure=failure):
                coordinator = Coordinator(copy.deepcopy(self.req), adapter=FakeAdapter())
                with patch.object(coordinator, method, side_effect=failure("PRIVATE_ERROR_CANARY")):
                    code, result = self._wire(coordinator)
                self.assertEqual(code, 3)
                self.assertEqual(
                    result["status"], "cancelled" if failure is KeyboardInterrupt else "unavailable"
                )
                self.assertEqual(result["run_id"], self.req["run_id"])
                self.assertEqual(len(result["calls"]), 3)
                self.assertEqual(len(result["units"][0]["versions"]), 1)
                self.assertEqual(len(result["units"][0]["versions"][0]["checks"]), 1)
                self.assertEqual(result["publication"]["status"], "not_started")
                self.assertNotIn("PRIVATE_ERROR_CANARY", json.dumps(result))
                self._closed(coordinator)

    def test_role_and_check_setup_cleanup_cancellation_retains_completed_calls(self):
        factory = tempfile.TemporaryDirectory
        for prefix, expected_calls in (("opensocrates-role-", 1), ("opensocrates-execution-", 2)):
            with self.subTest(prefix=prefix):
                coordinator = Coordinator(copy.deepcopy(self.req), adapter=FakeAdapter())

                class InterruptedCleanup:
                    def __init__(self, *args, expected_prefix=prefix, **kwargs):
                        self.inner = factory(*args, **kwargs)
                        self.interrupt = kwargs.get("prefix") == expected_prefix

                    def __enter__(self):
                        return self.inner.__enter__()

                    def __exit__(self, *args):
                        value = self.inner.__exit__(*args)
                        if self.interrupt:
                            raise KeyboardInterrupt
                        return value

                with patch.object(
                    runtime_module.tempfile, "TemporaryDirectory", InterruptedCleanup
                ):
                    code, result = self._wire(coordinator)
                self.assertEqual(code, 3)
                self.assertEqual(result["status"], "cancelled")
                self.assertEqual(len(result["calls"]), expected_calls)
                self.assertEqual(result["run_id"], self.req["run_id"])
                if expected_calls == 2:
                    self.assertEqual(len(result["units"][0]["versions"][0]["checks"]), 1)
                self._closed(coordinator)
        coordinator = Coordinator(copy.deepcopy(self.req), adapter=FakeAdapter())
        inputs = coordinator._inputs

        def setup(unit, candidate):
            if coordinator.result["calls"]:
                raise KeyboardInterrupt
            return inputs(unit, candidate)

        with patch.object(coordinator, "_inputs", side_effect=setup):
            code, result = self._wire(coordinator)
        self.assertEqual(code, 3)
        self.assertEqual(len(result["calls"]), 1)
        self.assertEqual(len(result["units"][0]["versions"]), 1)
        self._closed(coordinator)

    def test_interrupted_partial_publication_is_not_reported_as_delivery(self):
        coordinator = Coordinator(copy.deepcopy(self.req), adapter=FakeAdapter())
        write = os.write
        count = 0

        def interrupted(descriptor, data):
            nonlocal count
            count += 1
            if count == 2:
                raise KeyboardInterrupt
            return write(descriptor, data)

        with patch.object(path_module.os, "write", side_effect=interrupted):
            code, result = self._wire(coordinator)
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual(result["publication"]["status"], "incomplete")
        self.assertFalse(result["publication"]["location_verified"])
        self.assertEqual(len(result["publication"]["completed_files"]), 1)
        self.assertIsNotNone(result["publication"]["pending_path"])
        self._closed(coordinator)

    def test_directory_capabilities_close_on_initialization_and_cleanup_failure(self):
        created = []
        original_binding = runtime_module.BoundDirectory

        def binding(value):
            if created:
                raise OSError("fixture second binding failed")
            result = original_binding(value)
            created.append(result)
            return result

        with patch.object(runtime_module, "BoundDirectory", side_effect=binding):
            result = orchestrate(self.req, adapter=FakeAdapter())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(created[0].entries, [])
        coordinator = Coordinator(copy.deepcopy(self.req), adapter=FakeAdapter())
        close = coordinator.output_binding.close

        def interrupted_close():
            close()
            raise KeyboardInterrupt

        with patch.object(coordinator.output_binding, "close", side_effect=interrupted_close):
            code, result = self._wire(coordinator)
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(len(result["calls"]), 3)
        self.assertEqual(result["publication"]["status"], "complete")
        self.assertTrue(result["publication"]["location_verified"])
        self._closed(coordinator)

    def test_missing_publication_capability_prevents_calls_but_prepare_remains_usable(self):
        adapter = FakeAdapter()
        with patch.object(
            runtime_module,
            "BoundDirectory",
            side_effect=BoundaryError("directory_capability_unavailable"),
        ):
            result = orchestrate(self.req, adapter=adapter)
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(adapter.assignments, [])
            prepared = copy.deepcopy(self.req)
            prepared["operation"] = "prepare"
            self.assertEqual(orchestrate(prepared, adapter=adapter)["status"], "prepared")
        self.assertFalse((self.base / "candidate").exists())

    def test_obligation_only_feedback_reaches_repair_maker_with_exact_version(self):
        for status in ("failed", "unknown"):
            with self.subTest(status=status):
                req = copy.deepcopy(self.req)
                req["candidate_root"] = str(self.base / status)

                def obligation_only(assignment, cwd, value, status=status):
                    if (
                        assignment["role"] in {"review", "execution_verification"}
                        and (cwd / "make.txt").read_bytes() == b"bad"
                    ):
                        value["findings"] = []
                        value["obligations"][0]["status"] = status

                adapter = FakeAdapter(defect=True, mutate=obligation_only)
                result = orchestrate(req, adapter=adapter)
                self.assertEqual(result["status"], "integration_pending")
                makers = [item for item in adapter.assignments if item["role"] == "production"]
                version = result["units"][0]["versions"][0]
                self.assertEqual(makers[1]["repair_findings"], [])
                self.assertEqual(makers[1]["check_receipts"], version["checks"])
                self.assertEqual(len(makers[1]["repair_obligations"]), 2)
                for judgment in makers[1]["repair_obligations"]:
                    self.assertEqual(judgment["candidate_sha256"], version["candidate_sha256"])
                    self.assertEqual(judgment["version"], 1)
                    self.assertEqual(judgment["status"], status)
                    key = "review" if judgment["assessment_role"] == "review" else "verification"
                    self.assertEqual(judgment["assessment_id"], version[key]["assignment_id"])
                    self.assertEqual(
                        judgment["evidence_ids"], version[key]["obligations"][0]["evidence_ids"]
                    )
                for assignment in adapter.assignments:
                    if assignment["role"] in {"review", "execution_verification"}:
                        self.assertEqual(assignment["repair_obligations"], [])
                        self.assertEqual(assignment["repair_findings"], [])

    def test_old_schema_bytes_and_all_canonical_methods_unchanged(self):
        paths = subprocess.check_output(
            ["git", "ls-files", "schemas/v1", "content/methods"], cwd=ROOT, text=True
        ).splitlines()
        self.assertTrue(paths)
        for name in paths:
            # This new, unpublished schema family is revised by its own focused
            # contract tests. Preserve every pre-existing schema and method.
            if Path(name).name.startswith("orchestration-"):
                continue
            old = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
            self.assertEqual((ROOT / name).read_bytes(), old, name)
        from opensocrates.content.schema import FROZEN_METHOD_IDS

        self.assertEqual(len(FROZEN_METHOD_IDS), 48)

    def test_bilingual_complete_guides_and_package_native_assets(self):
        guide_root = ROOT / "plugin-src/shared/orchestration/v0.1.0"
        english = {path.stem.removesuffix(".en") for path in guide_root.glob("*.en.md")}
        korean = {path.stem.removesuffix(".ko") for path in guide_root.glob("*.ko.md")}
        self.assertEqual(english, korean)
        self.assertEqual(len(english), 9)
        for domain in ("software", "data", "document", "research"):
            for role in ("design", "production", "review", "execution_verification"):
                for locale in ("en", "ko"):
                    delivered = guides(unit(domain=domain), role, locale)
                    self.assertTrue(
                        all(
                            item["text"] and item["sha256"] == digest(item["text"].encode())
                            for item in delivered
                        )
                    )
        generator = json.loads((ROOT / "plugin-src/codex/generator.json").read_text())
        self.assertIn(
            {
                "source": "plugin-src/shared/orchestration",
                "output": "skills/opensocrates/references/orchestration",
            },
            generator["copy_files"],
        )
        spec = (ROOT / "packaging/pyinstaller/opensocrates-runtime.spec").read_text()
        for path in (
            "plugin-src/shared/orchestration",
            "plugin-src/shared/coding-specialists",
            "plugin-src/shared/assistance/verification.en.md",
            "plugin-src/shared/assistance/verification.ko.md",
        ):
            self.assertIn('"' + path + '"', spec)


class OrchestrationMemoryTests(unittest.TestCase):
    setUp = memory_checks.MemoryFixture.setUp
    request = memory_checks.MemoryFixture.request
    call = memory_checks.MemoryFixture.call
    enroll = memory_checks.MemoryFixture.enroll

    def orchestration_request(self):
        (self.root / "source.txt").write_text("source")
        value = request(self.root.resolve(), (self.base / "candidate").resolve())
        value["memory"] = {
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "record_ids": [],
        }
        return value

    def public_record(
        self, *, kind="decision", summary="Keep accepted intent.", source_reference=None
    ):
        result = self.call(
            "record",
            {
                "idempotency_key": str(uuid4()),
                "expected_record_version": 0,
                "kind": kind,
                "scope": {"level": "project"},
                "summary": summary,
                "rationale": None,
                "origin": {
                    "producer_kind": "agent",
                    "source_reference": source_reference,
                    "attestation": "agent_reported",
                },
                "support": "agent_reported",
                "source_refs": [],
                "snapshot_id": None,
                "revalidation": {
                    "dependency_paths": [],
                    "negative_claim": False,
                    "on_change": "refresh_or_mark_stale",
                },
                "conflict_ids": [],
            },
        )
        self.assertEqual(result["status"], "ok", result)
        return result["result"]["record"]

    def test_missing_disabled_memory_creates_nothing_and_keeps_contract(self):
        (self.root / "source.txt").write_text("source")
        req = request(self.root.resolve(), (self.base / "candidate").resolve())
        req["memory"] = {"project_id": str(uuid4()), "workspace_id": str(uuid4()), "record_ids": []}
        snapshot = MemorySnapshot(req, self.registry)
        self.assertEqual(snapshot.status, "unavailable")
        self.assertFalse(self.data.exists())
        self.enroll()
        self.call("disable", {"expected_policy_version": 1, "idempotency_key": str(uuid4())})
        req["memory"] = {
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "record_ids": [],
        }
        snapshot = MemorySnapshot(req, self.registry)
        self.assertEqual(snapshot.status, "disabled")
        coordinator = Coordinator(req, adapter=FakeAdapter(), registry=self.registry)
        assignment, _ = coordinator.assignment(req["units"][0], "production", {}, [], [])
        self.assertEqual(assignment["constraints"], req["constraints"])
        self.assertEqual(assignment["handoff"], req["handoff"])

    def test_full_accepted_intent_cannot_be_removed_by_record_selection(self):
        self.enroll()
        req = self.orchestration_request()
        record = self.public_record(summary="Preserve this complete accepted constraint. " * 90)
        accepted = self.call(
            "accept",
            {
                "record_id": record["record_id"],
                "expected_record_version": record["version"],
                "acceptance_basis": "fixture:accepted",
                "acceptance_attribution": "operator_declared",
                "idempotency_key": str(uuid4()),
            },
        )
        self.assertEqual(accepted["status"], "ok", accepted)
        other = self.public_record(kind="lesson")
        req["memory"]["record_ids"] = [other["record_id"]]
        snapshot = MemorySnapshot(req, self.registry)
        projected = snapshot.project(req["units"][0], "review")
        self.assertEqual(len(projected["records"]), 1)
        item = projected["records"][0]
        self.assertEqual(item["summary"], record["summary"])
        self.assertEqual(item["lifecycle"], "accepted")
        self.assertEqual(item["review_state"], "unknown")
        self.assertEqual(item["support"], "agent_reported")

    def test_freeze_excludes_same_attempt_and_deletion_invalidates_projection(self):
        self.enroll()
        req = self.orchestration_request()
        record = self.public_record(kind="lesson", source_reference="run:" + req["run_id"])
        snapshot = MemorySnapshot(req, self.registry)
        self.assertEqual(snapshot.project(req["units"][0], "review")["records"], [])
        self.assertEqual(len(snapshot.project(req["units"][0], "production")["records"]), 1)
        store = MemoryStore(self.registry.project_dir(self.project_id))
        store.delete_record(record["record_id"], record["version"], str(uuid4()))
        self.assertFalse(snapshot.unchanged())
        with self.assertRaises(BoundaryError):
            snapshot.project(req["units"][0], "production")
        fresh = MemorySnapshot(req, self.registry)
        self.assertEqual(fresh.project(req["units"][0], "production")["records"], [])

    def test_stale_source_remains_distinct_from_accepted_and_reviewed(self):
        self.enroll()
        req = self.orchestration_request()
        observed = self.call("observe", {"path": "source.txt", "idempotency_key": str(uuid4())})
        self.assertEqual(observed["status"], "ok", observed)
        snapshot = MemorySnapshot(req, self.registry)
        current = snapshot.project(req["units"][0], "production")["records"][0]
        self.assertEqual(current["freshness"], "current")
        (self.root / "source.txt").write_text("changed")
        stale = snapshot.project(req["units"][0], "production")["records"][0]
        self.assertEqual(stale["freshness"], "stale")
        self.assertEqual(stale["review_state"], "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
