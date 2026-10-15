#!/usr/bin/env python3
"""Public synthetic/mocked audit boundary regressions; no Git/model/host calls.

All filesystem fixtures are newly authored inside TemporaryDirectory. Every
source Git invocation is mocked: no executable helper or credential file is
created or accessed. Run only against the selected integrated candidate.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import swarm_study_audit as subject

SHA = "a" * 40
SENTINEL = "PUBLIC_SYNTHETIC_REJECTION_SENTINEL"


class AuditBoundaryChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="swarm-audit-public-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.candidate = self.root / "candidate"
        self.public = self.root / "public-study"
        self.outside = self.root / "other-public-fixtures"
        for directory in (self.candidate, self.public, self.outside):
            directory.mkdir()
        self.context = subject.trusted_context(self.candidate, SHA, [self.public])

    def request(self) -> dict:
        return {
            "schema_version": 1,
            "repository_root": str(self.candidate),
            "freeze_manifest": "freeze-manifest.json",
            "assignment_ledger": "assignment-ledger.json",
            "safe_results": "safe-results.jsonl",
            "intake_review": "intake-review.jsonl",
            "isolation_preflight": "isolation-preflight.json",
        }

    def freeze(self) -> dict:
        return {
            "schema_version": 1,
            "state": "FROZEN",
            "source_sha": SHA,
            "isolation_state": "VERIFIED",
            "quota": 54,
            "approved_by": "S001",
            "frozen_at": "2020-01-01T00:00:00Z",
            "input_files": [
                {"path": "evals/swarm-20261015/PROTOCOL.md", "sha256": "0" * 64, "role": "protocol"}
            ],
        }

    def put_json(self, name: str, data: object) -> Path:
        path = self.public / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def assert_no_rejected_bytes(self, audit: subject.Audit, payload: bytes) -> None:
        report = audit.report()
        encoded = json.dumps(report)
        self.assertEqual(report["reportability"], "HOLD")
        self.assertEqual(report["input_digests"], {})
        self.assertNotIn(SENTINEL, encoded)
        self.assertNotIn(hashlib.sha256(payload).hexdigest(), encoded)

    def test_request_cannot_supply_its_own_trust_context(self) -> None:
        audit = subject.Audit()
        with (
            patch.object(subject, "read_bytes") as read,
            patch.object(subject.subprocess, "run") as run,
        ):
            subject.audit_request(self.request(), self.public, audit)
        read.assert_not_called()
        run.assert_not_called()
        self.assertEqual(audit.report()["reportability"], "HOLD")

    def test_foreign_candidate_stops_before_artifacts_or_git(self) -> None:
        request = self.request()
        request["repository_root"] = str(self.outside)
        audit = subject.Audit()
        with (
            patch.object(subject, "read_bytes") as read,
            patch.object(subject.subprocess, "run") as run,
        ):
            subject.audit_request(request, self.public, audit, self.context)
        read.assert_not_called()
        run.assert_not_called()
        self.assertEqual(audit.report()["summary"], {})
        self.assertNotIn(str(self.outside), json.dumps(audit.report()))

    def test_outside_artifact_is_not_opened_or_hashed(self) -> None:
        request = {"freeze_manifest": str(self.outside / "public-example.json")}
        audit = subject.Audit()
        with patch.object(subject, "read_bytes") as read, patch.object(subject, "digest") as digest:
            value = subject.load_artifact(
                audit, request, self.public, "freeze_manifest", context=self.context
            )
        self.assertIsNone(value)
        read.assert_not_called()
        digest.assert_not_called()
        self.assertEqual(audit.report()["input_digests"], {})

    def test_any_unapproved_artifact_path_stops_before_source_helper(self) -> None:
        request = self.request()
        request["safe_results"] = str(self.outside / "public-example.jsonl")
        audit = subject.Audit()
        with (
            patch.object(subject, "read_bytes") as read,
            patch.object(subject, "check_source") as source,
        ):
            subject.audit_request(request, self.public, audit, self.context)
        read.assert_not_called()
        source.assert_not_called()
        self.assertEqual(audit.report()["reportability"], "HOLD")

    def test_traversal_and_nonpublic_basename_are_rejected_before_open(self) -> None:
        for reference in ("../other-public-fixtures/example.json", "config.toml"):
            with self.subTest(reference=reference), patch.object(subject, "read_bytes") as read:
                audit = subject.Audit()
                subject.load_artifact(
                    audit,
                    {"freeze_manifest": reference},
                    self.public,
                    "freeze_manifest",
                    context=self.context,
                )
                read.assert_not_called()
                self.assertEqual(audit.report()["reportability"], "HOLD")

    def test_linked_ancestor_is_rejected_before_open(self) -> None:
        (self.public / "linked").symlink_to(self.outside, target_is_directory=True)
        audit = subject.Audit()
        with patch.object(subject, "read_bytes") as read:
            subject.load_artifact(
                audit,
                {"freeze_manifest": "linked/example.json"},
                self.public,
                "freeze_manifest",
                context=self.context,
            )
        read.assert_not_called()
        self.assertEqual(audit.report()["reportability"], "HOLD")

    def test_final_link_is_rejected_by_descriptor_open(self) -> None:
        target = self.outside / "public-example.json"
        target.write_text("{}", encoding="utf-8")
        linked = self.public / "linked.json"
        linked.symlink_to(target)
        with self.assertRaises(OSError):
            subject.read_bytes(linked, 1024)

    def test_malformed_and_wrong_role_json_are_not_hashed(self) -> None:
        payloads = (b"{" + SENTINEL.encode(), json.dumps({"unrelated": SENTINEL}).encode())
        for payload in payloads:
            with self.subTest(kind=payload[:1]):
                (self.public / "freeze-manifest.json").write_bytes(payload)
                audit = subject.Audit()
                with patch.object(subject, "digest") as digest:
                    subject.load_artifact(
                        audit, self.request(), self.public, "freeze_manifest", context=self.context
                    )
                digest.assert_not_called()
                self.assert_no_rejected_bytes(audit, payload)

    def test_valid_public_role_can_have_a_digest(self) -> None:
        path = self.put_json("freeze-manifest.json", self.freeze())
        audit = subject.Audit()
        value = subject.load_artifact(
            audit, self.request(), self.public, "freeze_manifest", context=self.context
        )
        self.assertEqual(value, self.freeze())
        self.assertEqual(
            audit.input_digests["freeze_manifest"], hashlib.sha256(path.read_bytes()).hexdigest()
        )

    def test_rejected_freeze_never_reaches_source_helper(self) -> None:
        self.put_json("freeze-manifest.json", {"unrelated": SENTINEL})
        audit = subject.Audit()
        with (
            patch.object(subject, "check_source") as source,
            patch.object(subject.subprocess, "run") as run,
        ):
            subject.audit_request(self.request(), self.public, audit, self.context)
        source.assert_not_called()
        run.assert_not_called()
        self.assertEqual(audit.report()["input_digests"], {})

    def test_draft_or_foreign_source_or_quota_does_not_reach_source(self) -> None:
        for field, value in (("state", "DRAFT"), ("source_sha", "b" * 40), ("quota", 55)):
            with self.subTest(field=field):
                freeze = self.freeze()
                freeze[field] = value
                self.put_json("freeze-manifest.json", freeze)
                audit = subject.Audit()
                with patch.object(subject, "check_source") as source:
                    subject.audit_request(self.request(), self.public, audit, self.context)
                source.assert_not_called()
                self.assertEqual(audit.report()["reportability"], "HOLD")
                self.assertEqual(audit.report()["input_digests"], {})
                self.assertNotIn("b" * 40, json.dumps(audit.report()))

    def test_invalid_jsonl_does_not_publish_any_partial_rows_or_digest(self) -> None:
        payload = json.dumps({"unrelated": SENTINEL}).encode() + b"\n"
        (self.public / "safe-results.jsonl").write_bytes(payload)
        audit = subject.Audit()
        with patch.object(subject, "digest") as digest:
            rows = subject.load_jsonl(
                audit,
                {"safe_results": "safe-results.jsonl"},
                self.public,
                "safe_results",
                self.context,
            )
        digest.assert_not_called()
        self.assertEqual(rows, [])
        self.assert_no_rejected_bytes(audit, payload)

    def test_hold_omits_previously_accepted_input_fingerprints(self) -> None:
        audit = subject.Audit()
        audit.input_digests["safe_results"] = "1" * 64
        audit.add("blocker", "public_result_differs_from_intake_review_digest")
        self.assertEqual(audit.report()["input_digests"], {})
        self.assertTrue(audit.report()["digests_omitted_on_hold"])

    def git_context(self) -> subject.TrustedContext:
        metadata = self.candidate / ".git"
        metadata.mkdir()
        (metadata / "objects").mkdir()
        (metadata / "HEAD").write_text(SHA + "\n", encoding="ascii")
        (metadata / "index").write_bytes(b"DIRC-public-synthetic-mock-index")
        (metadata / "config").write_text("[core]\nfsmonitor = false\n", encoding="ascii")
        return subject.trusted_context(self.candidate, SHA, [self.public], metadata, metadata)

    def test_git_without_separate_metadata_context_stays_unknown(self) -> None:
        audit = subject.Audit()
        with patch.object(subject.subprocess, "run") as run:
            subject.check_source(audit, self.freeze(), self.candidate, self.context)
        run.assert_not_called()
        self.assertEqual(audit.report()["reportability"], "UNKNOWN")

    def test_git_uses_scratch_config_and_sanitized_environment_only(self) -> None:
        context = self.git_context()
        original_read = subject.read_bytes
        reads = []

        def observed_read(path, limit):
            reads.append(path)
            return original_read(path, limit)

        def observe_command(command, **options):
            self.assertEqual(command[0], "/usr/bin/git")
            self.assertIn("core.fsmonitor=false", command)
            self.assertIn("--no-ext-diff", command)
            self.assertIn("--no-textconv", command)
            self.assertIn("--ignore-submodules=all", command)
            scratch = Path(
                next(item.split("=", 1)[1] for item in command if item.startswith("--git-dir="))
            )
            self.assertNotEqual(scratch, context.git_dir)
            self.assertEqual(options["cwd"], scratch)
            self.assertEqual((scratch / "index").read_bytes(), b"DIRC-public-synthetic-mock-index")
            self.assertIn("fsmonitor = false", (scratch / "config").read_text())
            environment = options["env"]
            self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
            self.assertEqual(environment["GIT_CONFIG_SYSTEM"], os.devnull)
            self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(environment["GIT_CONFIG_COUNT"], "0")
            self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
            self.assertEqual(environment["GIT_ALLOW_PROTOCOL"], "")
            self.assertNotIn("GIT_DIR", environment)
            self.assertNotIn("GIT_CONFIG_PARAMETERS", environment)
            self.assertNotIn("SSH_AUTH_SOCK", environment)
            self.assertEqual(options["stdout"], subject.subprocess.DEVNULL)
            self.assertEqual(options["stderr"], subject.subprocess.DEVNULL)
            return SimpleNamespace(returncode=0)

        audit = subject.Audit()
        with (
            patch.object(subject, "read_bytes", side_effect=observed_read),
            patch.object(subject.subprocess, "run", side_effect=observe_command) as run,
        ):
            subject.check_source(audit, self.freeze(), self.candidate, context)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn(context.git_dir / "config", reads)
        self.assertEqual(audit.summary["audited_source_sha"], SHA)
        self.assertEqual(audit.report()["reportability"], "REPORTABLE")

    def test_dirty_or_unavailable_scratch_diff_is_not_a_pass(self) -> None:
        context = self.git_context()
        for code, state in ((1, "HOLD"), (128, "UNKNOWN")):
            with (
                self.subTest(code=code),
                patch.object(
                    subject.subprocess, "run", return_value=SimpleNamespace(returncode=code)
                ),
            ):
                audit = subject.Audit()
                subject.check_source(audit, self.freeze(), self.candidate, context)
                self.assertEqual(audit.report()["reportability"], state)

    def test_alternate_objects_or_changed_head_do_not_invoke_git(self) -> None:
        context = self.git_context()
        info = context.git_common_dir / "objects" / "info"
        info.mkdir()
        (info / "alternates").write_text("public-synthetic-unused-alternate\n", encoding="ascii")
        audit = subject.Audit()
        with patch.object(subject.subprocess, "run") as run:
            subject.check_source(audit, self.freeze(), self.candidate, context)
        run.assert_not_called()
        self.assertEqual(audit.report()["reportability"], "UNKNOWN")

    def test_source_sha_drift_does_not_run_worktree_helpers(self) -> None:
        context = self.git_context()
        (context.git_dir / "HEAD").write_text("b" * 40 + "\n", encoding="ascii")
        audit = subject.Audit()
        with patch.object(subject.subprocess, "run") as run:
            subject.check_source(audit, self.freeze(), self.candidate, context)
        run.assert_not_called()
        self.assertEqual(audit.report()["reportability"], "HOLD")

    def test_object_store_link_stays_unknown_without_git(self) -> None:
        context = self.git_context()
        (context.git_common_dir / "objects" / "linked-public-folder").symlink_to(
            self.outside, target_is_directory=True
        )
        audit = subject.Audit()
        with patch.object(subject.subprocess, "run") as run:
            subject.check_source(audit, self.freeze(), self.candidate, context)
        run.assert_not_called()
        self.assertEqual(audit.report()["reportability"], "UNKNOWN")

    def isolation(self) -> dict:
        identity = {key: None for key in subject.IDENTITY_FIELDS}
        identity["source_sha"] = SHA
        check = {
            "check": "public-summary",
            "status": "PASS",
            "reason": "public-synthetic",
            "evidence_ids": [],
        }
        return {
            "tool": "swarm-isolation-preflight",
            "status": "PASS",
            "source_identity": identity,
            "as_of": "2020-01-01T00:00:00Z",
            "isolation_blocked": False,
            "experiment_blocked": True,
            "execution_authorized": False,
            "final_study_freeze_and_lease_required": True,
            "global_checks": [check],
            "arms": [{"arm": arm, "status": "PASS", "checks": [check]} for arm in subject.ARMS],
            "blocking_checks": [],
        }

    def test_s042_isolation_pass_keeps_execution_blocked(self) -> None:
        audit = subject.Audit()
        verified = subject.check_isolation(audit, self.freeze(), self.isolation())
        self.assertIsNotNone(verified)
        self.assertEqual(audit.report()["reportability"], "REPORTABLE")
        self.assertFalse(audit.report()["execution_authorized"])

    def test_s042_flags_cannot_substitute_execution_permission(self) -> None:
        for field, value in (
            ("isolation_blocked", True),
            ("experiment_blocked", False),
            ("execution_authorized", True),
            ("final_study_freeze_and_lease_required", False),
        ):
            with self.subTest(field=field):
                isolation = self.isolation()
                isolation[field] = value
                audit = subject.Audit()
                subject.check_isolation(audit, self.freeze(), isolation)
                self.assertEqual(audit.report()["reportability"], "HOLD")
                self.assertFalse(audit.report()["execution_authorized"])

    def test_isolation_pass_does_not_replace_frozen_isolation_gate(self) -> None:
        freeze = self.freeze()
        freeze["isolation_state"] = "UNVERIFIED"
        audit = subject.Audit()
        subject.check_isolation(audit, freeze, self.isolation())
        self.assertEqual(audit.report()["reportability"], "HOLD")

    def test_cli_rejection_returns_only_safe_category(self) -> None:
        path = self.public / "request.json"
        payload = ("{" + SENTINEL).encode()
        path.write_bytes(payload)
        output = self.public / "audit.json"
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            patch.object(subject.subprocess, "run") as run,
        ):
            code = subject.main(
                [
                    "--input",
                    str(path),
                    "--output",
                    str(output),
                    "--candidate-root",
                    str(self.candidate),
                    "--candidate-sha",
                    SHA,
                    "--public-evidence-root",
                    str(self.public),
                ]
            )
        run.assert_not_called()
        self.assertEqual(code, 3)
        self.assertFalse(output.exists())
        self.assertNotIn(SENTINEL, stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(hashlib.sha256(payload).hexdigest(), stdout.getvalue() + stderr.getvalue())
        self.assertNotIn(str(path), stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
