"""Validate version-bound, privacy-safe Claude Chat release evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA = "opensocrates.claude-chat-upload-probe/2.0.0"
PROMPT4_MERGE_COMMIT = "2ced9500aea5c7672f644ecc345b58ed30a31701"
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")

TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "checked_at",
        "status",
        "blocker",
        "product_version",
        "content_revision",
        "release",
        "archive",
        "surfaces",
        "live_probe",
        "support_claim",
        "privacy",
    }
)
RELEASE_KEYS = frozenset(
    {
        "tag",
        "tag_available",
        "release_available",
        "release_commit",
        "prompt4_merge_commit",
        "release_includes_prompt4",
        "latest_public_tag",
    }
)
ARCHIVE_KEYS = frozenset(
    {
        "asset_name",
        "checksum_asset_name",
        "available",
        "checksum_available",
        "sha256",
        "checksum_verified",
        "file_count",
    }
)
SURFACE_KEYS = frozenset(
    {
        "provenance",
        "product_version",
        "evidence_state",
        "status_observation",
        "routing_observation",
        "modified_during_probe",
    }
)
LIVE_PROBE_KEYS = frozenset(
    {
        "status",
        "attempted",
        "blocker",
        "claude_product_version",
        "claude_ui_version",
        "archive_accepted",
        "observed_status_version",
        "observed_content_revision",
        "observed_internal_system_count",
        "routing_observation",
    }
)
PRIVACY_KEYS = frozenset(
    {
        "prompt_recorded",
        "conversation_recorded",
        "account_identifier_recorded",
        "local_path_recorded",
        "uploaded_file_content_recorded",
        "raw_accessibility_snapshot_recorded",
        "token_or_credential_recorded",
    }
)
SURFACE_NAMES = frozenset({"local_plugin", "manual_chat_zip", "preexisting_synced_custom_skill"})


def evidence_path(root: Path, product_version: str) -> Path:
    """Return the receipt path for the exact source product version."""

    return root / "docs" / "evidence" / f"claude-chat-upload-probe-v{product_version}.json"


def _mapping(
    value: object, expected_keys: frozenset[str], prefix: str, errors: set[str]
) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        errors.add(f"{prefix}.type")
        return None
    actual_keys = {key for key in value if isinstance(key, str)}
    if actual_keys != expected_keys or len(actual_keys) != len(value):
        errors.add(f"{prefix}.fields")
    return value


def _exact(value: object, expected: object, code: str, errors: set[str]) -> None:
    if value != expected or isinstance(value, bool) != isinstance(expected, bool):
        errors.add(code)


def _surface_expectations(status: str, product_version: str) -> dict[str, dict[str, object]]:
    pending = status == "pending"
    return {
        "local_plugin": {
            "provenance": "installer_managed_local_plugin",
            "product_version": product_version,
            "evidence_state": "historical_recorded",
            "status_observation": "version_observed",
            "routing_observation": "namespaced_status_observed",
            "modified_during_probe": False,
        },
        "manual_chat_zip": {
            "provenance": "manual_exact_release_zip_upload",
            "product_version": product_version,
            "evidence_state": (
                "pending_exact_release_artifact"
                if pending
                else "live_verified_exact_release_artifact"
            ),
            "status_observation": "not_observed" if pending else "version_observed",
            "routing_observation": (
                "not_observed" if pending else "representative_reference_routing_observed"
            ),
            "modified_during_probe": not pending,
        },
        "preexisting_synced_custom_skill": {
            "provenance": "preexisting_synced_or_custom_skill",
            "product_version": "1.1.2",
            "evidence_state": (
                "historical_recorded" if pending else "replaced_by_exact_release_artifact"
            ),
            "status_observation": "version_observed" if pending else "version_replaced",
            "routing_observation": (
                "source_not_reverified" if pending else "source_reclassified_to_manual_upload"
            ),
            "modified_during_probe": not pending,
        },
    }


def validation_errors(  # noqa: C901 - explicit evidence-state contract
    report: object,
    *,
    product_version: str,
    content_revision: int,
    candidate_archive_sha256: str | None = None,
    candidate_file_count: int | None = None,
) -> tuple[str, ...]:
    """Return stable error codes for an invalid current-version receipt."""

    errors: set[str] = set()
    document = _mapping(report, TOP_LEVEL_KEYS, "receipt", errors)
    if document is None:
        return tuple(sorted(errors))
    _exact(document.get("schema"), SCHEMA, "receipt.schema", errors)
    if (
        not isinstance(document.get("checked_at"), str)
        or DATE.fullmatch(str(document.get("checked_at"))) is None
    ):
        errors.add("receipt.checked_at")
    status = document.get("status")
    if status not in {"pending", "pass"}:
        errors.add("receipt.status")
        status = "pending"
    _exact(document.get("product_version"), product_version, "receipt.product_version", errors)
    _exact(document.get("content_revision"), content_revision, "receipt.content_revision", errors)

    release = _mapping(document.get("release"), RELEASE_KEYS, "release", errors)
    archive = _mapping(document.get("archive"), ARCHIVE_KEYS, "archive", errors)
    surfaces = _mapping(document.get("surfaces"), SURFACE_NAMES, "surfaces", errors)
    live_probe = _mapping(document.get("live_probe"), LIVE_PROBE_KEYS, "live_probe", errors)
    privacy = _mapping(document.get("privacy"), PRIVACY_KEYS, "privacy", errors)

    expected_tag = f"v{product_version}"
    expected_asset = f"opensocrates-{product_version}-claude-chat-skills.zip"
    if release is not None:
        _exact(release.get("tag"), expected_tag, "release.tag", errors)
        _exact(
            release.get("prompt4_merge_commit"),
            PROMPT4_MERGE_COMMIT,
            "release.prompt4_merge_commit",
            errors,
        )
        if not isinstance(release.get("latest_public_tag"), str):
            errors.add("release.latest_public_tag")
    if archive is not None:
        _exact(archive.get("asset_name"), expected_asset, "archive.asset_name", errors)
        _exact(
            archive.get("checksum_asset_name"),
            f"{expected_asset}.sha256",
            "archive.checksum_asset_name",
            errors,
        )

    if surfaces is not None:
        provenances: set[object] = set()
        for name, expected in _surface_expectations(str(status), product_version).items():
            surface = _mapping(surfaces.get(name), SURFACE_KEYS, f"surfaces.{name}", errors)
            if surface is None:
                continue
            provenances.add(surface.get("provenance"))
            for key, value in expected.items():
                _exact(surface.get(key), value, f"surfaces.{name}.{key}", errors)
        if len(provenances) != len(SURFACE_NAMES):
            errors.add("surfaces.provenance_distinct")

    pending = status == "pending"
    if pending:
        _exact(
            document.get("blocker"),
            "exact_public_release_artifact_unavailable",
            "receipt.blocker",
            errors,
        )
        _exact(
            document.get("support_claim"),
            f"historical_v1.1.2_only_current_v{product_version}_pending",
            "receipt.support_claim",
            errors,
        )
        if release is not None:
            for key in ("tag_available", "release_available", "release_includes_prompt4"):
                _exact(release.get(key), False, f"release.{key}", errors)
            _exact(release.get("release_commit"), None, "release.release_commit", errors)
        if archive is not None:
            for key in ("available", "checksum_available", "checksum_verified"):
                _exact(archive.get(key), False, f"archive.{key}", errors)
            _exact(archive.get("sha256"), None, "archive.sha256", errors)
            _exact(archive.get("file_count"), None, "archive.file_count", errors)
        expected_probe = {
            "status": "not_attempted",
            "attempted": False,
            "blocker": "exact_public_release_artifact_unavailable",
            "claude_product_version": None,
            "claude_ui_version": None,
            "archive_accepted": False,
            "observed_status_version": None,
            "observed_content_revision": None,
            "observed_internal_system_count": None,
            "routing_observation": "not_observed",
        }
    else:
        _exact(document.get("blocker"), None, "receipt.blocker", errors)
        _exact(
            document.get("support_claim"),
            "exact_current_release_chat_upload_live_validated",
            "receipt.support_claim",
            errors,
        )
        if release is not None:
            for key in ("tag_available", "release_available", "release_includes_prompt4"):
                _exact(release.get(key), True, f"release.{key}", errors)
            commit = release.get("release_commit")
            if not isinstance(commit, str) or COMMIT.fullmatch(commit) is None:
                errors.add("release.release_commit")
        if archive is not None:
            for key in ("available", "checksum_available", "checksum_verified"):
                _exact(archive.get(key), True, f"archive.{key}", errors)
            digest = archive.get("sha256")
            if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
                errors.add("archive.sha256")
            if not isinstance(archive.get("file_count"), int) or isinstance(
                archive.get("file_count"), bool
            ):
                errors.add("archive.file_count")
            else:
                _exact(archive.get("file_count"), 51, "archive.file_count", errors)
            if candidate_archive_sha256 is not None:
                _exact(digest, candidate_archive_sha256, "archive.candidate_sha256", errors)
            if candidate_file_count is not None:
                _exact(
                    archive.get("file_count"),
                    candidate_file_count,
                    "archive.candidate_file_count",
                    errors,
                )
        expected_probe = {
            "status": "pass",
            "attempted": True,
            "blocker": None,
            "archive_accepted": True,
            "observed_status_version": product_version,
            "observed_content_revision": content_revision,
            "observed_internal_system_count": 48,
            "routing_observation": "representative_reference_routing_observed",
        }
    if live_probe is not None:
        for key, value in expected_probe.items():
            _exact(live_probe.get(key), value, f"live_probe.{key}", errors)
        if not pending:
            for key in ("claude_product_version", "claude_ui_version"):
                if not isinstance(live_probe.get(key), str) or not live_probe.get(key):
                    errors.add(f"live_probe.{key}")
    if privacy is not None:
        for key in PRIVACY_KEYS:
            _exact(privacy.get(key), False, f"privacy.{key}", errors)
    return tuple(sorted(errors))
