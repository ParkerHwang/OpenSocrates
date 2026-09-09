"""Synthetic validator regression; never a real upload receipt."""

from __future__ import annotations

import unittest
from copy import deepcopy

from claude_chat_evidence import (
    ARCHIVE_FILE_COUNTS,
    PRIVACY_KEYS,
    PROMPT4_MERGE_COMMIT,
    SCHEMA,
    _surface_expectations,
    export_only_contract,
    validation_errors,
)


def synthetic_pass(version: str, count: int) -> dict:
    """Pure fixture: deliberately impossible-looking SHA, never written as evidence."""
    return {
        "schema": SCHEMA,
        "checked_at": "2026-09-08",
        "status": "pass",
        "blocker": None,
        "product_version": version,
        "content_revision": 3 if version == "1.3.0" else 1,
        "release": {
            "tag": f"v{version}",
            "tag_available": True,
            "release_available": True,
            "release_commit": "0" * 40,
            "prompt4_merge_commit": PROMPT4_MERGE_COMMIT,
            "release_includes_prompt4": True,
            "latest_public_tag": f"v{version}",
        },
        "archive": {
            "asset_name": f"opensocrates-{version}-claude-chat-skills.zip",
            "checksum_asset_name": f"opensocrates-{version}-claude-chat-skills.zip.sha256",
            "available": True,
            "checksum_available": True,
            "sha256": "sha256:" + "0" * 64,
            "checksum_verified": True,
            "file_count": count,
        },
        "surfaces": _surface_expectations("pass", version),
        "live_probe": {
            "status": "pass",
            "attempted": True,
            "blocker": None,
            "claude_product_version": "synthetic",
            "claude_ui_version": "synthetic",
            "archive_accepted": True,
            "observed_status_version": version,
            "observed_content_revision": 3 if version == "1.3.0" else 1,
            "observed_internal_system_count": 48,
            "routing_observation": "representative_reference_routing_observed",
        },
        "support_claim": "exact_current_release_chat_upload_live_validated",
        "privacy": dict.fromkeys(PRIVACY_KEYS, False),
    }


class ArchiveIdentityChecks(unittest.TestCase):
    def check(self, report, **overrides):
        return validation_errors(
            report,
            product_version=report["product_version"],
            content_revision=report["content_revision"],
            **overrides,
        )

    def test_export_contract_never_claims_live_or_public_observations(self):
        report = export_only_contract("1.4.0", 3)
        self.assertEqual(self.check(report), ())
        for key, value in (
            ("status", "pass"),
            ("scope", "native_chat_activation"),
            ("public_provenance", "verified"),
            ("product_version", "1.2.1"),
        ):
            changed = deepcopy(report)
            changed[key] = value
            self.assertTrue(validation_errors(changed, product_version="1.4.0", content_revision=3))
        for value in (True, 1, "true"):
            changed = deepcopy(report)
            changed["live_probe"]["attempted"] = value
            self.assertTrue(self.check(changed))
        changed = deepcopy(report)
        changed["privacy"]["token_or_credential_recorded"] = True
        self.assertTrue(self.check(changed))
        changed = deepcopy(report)
        changed["live_probe"]["status"] = "pass"
        self.assertTrue(self.check(changed))
        changed = deepcopy(report)
        changed["live_probe"].update(status="pass", attempted=True)
        self.assertTrue(self.check(changed))

    def test_exact_version_inventory(self):
        for version, count in ARCHIVE_FILE_COUNTS.items():
            with self.subTest(version=version):
                report = synthetic_pass(version, count)
                self.assertEqual(self.check(report), ())
                for wrong in (0, count - 1, count + 1, True):
                    report["archive"]["file_count"] = wrong
                    self.assertIn("archive.file_count", self.check(report))

    def test_v13_rejects_legacy_and_unknown_versions(self):
        self.assertIn("archive.file_count", self.check(synthetic_pass("1.3.0", 51)))
        self.assertIn("archive.unsupported_version", self.check(synthetic_pass("9.9.9", 153)))

    def test_candidate_digest_and_count_remain_binding(self):
        report = synthetic_pass("1.3.0", 153)
        self.assertEqual(
            self.check(
                report, candidate_archive_sha256="sha256:" + "0" * 64, candidate_file_count=153
            ),
            (),
        )
        errors = self.check(
            report, candidate_archive_sha256="sha256:" + "1" * 64, candidate_file_count=152
        )
        self.assertIn("archive.candidate_sha256", errors)
        self.assertIn("archive.candidate_file_count", errors)

    def test_public_provenance_and_live_observations_still_required(self):
        report = synthetic_pass("1.3.0", 153)
        for section, key in (
            ("release", "tag_available"),
            ("release", "release_available"),
            ("release", "release_includes_prompt4"),
            ("archive", "checksum_verified"),
            ("live_probe", "archive_accepted"),
            ("live_probe", "attempted"),
        ):
            changed = deepcopy(report)
            changed[section][key] = False
            self.assertIn(f"{section}.{key}", self.check(changed))

    def test_local_artifact_cannot_masquerade_as_public_release(self):
        report = synthetic_pass("1.3.0", 153)
        report["surfaces"]["manual_chat_zip"]["provenance"] = "isolated_local_candidate_zip"
        report["release"]["release_commit"] = None
        self.assertIn("surfaces.manual_chat_zip.provenance", self.check(report))
        self.assertIn("release.release_commit", self.check(report))


if __name__ == "__main__":
    unittest.main()
