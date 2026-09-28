"""Load trusted packaged profile configuration without workspace or user data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .policy import OPTIONAL_COMPONENTS, TASK_ENUMS, AssistanceProfile

_PROFILE_KEYS = frozenset(
    {
        "profile_id",
        "revision",
        "state",
        "model",
        "effort",
        "client",
        "task_families",
        "observed_failure_categories",
        "raise_to_structured",
        "optional_components",
        "evaluation_reference",
        "validation_reference",
    }
)


def load_packaged_profiles() -> tuple[AssistanceProfile, ...]:
    """Return exact validated profiles; malformed or absent config is a safe fallback."""
    frozen = getattr(sys, "_MEIPASS", None)
    root = Path(frozen) if isinstance(frozen, str) else Path(__file__).resolve().parents[3]
    path = root / "plugin-src/shared/assistance/profiles.json"
    try:
        raw = path.read_bytes()
        if len(raw) > 16 * 1024:
            return ()
        value = json.loads(raw.decode("utf-8"))
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "revision", "profiles"}
            or value["schema"] != "opensocrates.assistance.profiles/1.0.0"
            or type(value["revision"]) is not int
            or value["revision"] < 1
            or not isinstance(value["profiles"], list)
            or len(value["profiles"]) > 32
        ):
            return ()
        profiles: list[AssistanceProfile] = []
        identities: set[tuple[str, int]] = set()
        for item in value["profiles"]:
            if not isinstance(item, dict) or set(item) != _PROFILE_KEYS:
                return ()
            if (
                not all(
                    isinstance(item[k], str) and item[k] and len(item[k]) <= 1024
                    for k in (
                        "profile_id",
                        "state",
                        "model",
                        "effort",
                        "client",
                        "evaluation_reference",
                    )
                )
                or item["state"] not in {"candidate", "validated", "withdrawn"}
                or type(item["revision"]) is not int
                or item["revision"] < 1
                or type(item["raise_to_structured"]) is not bool
                or not isinstance(item["task_families"], list)
                or not set(item["task_families"]) <= TASK_ENUMS["task_family"]
                or not isinstance(item["optional_components"], list)
                or not set(item["optional_components"]) <= OPTIONAL_COMPONENTS
                or len(set(item["optional_components"])) != len(item["optional_components"])
                or not isinstance(item["observed_failure_categories"], list)
                or any(
                    not isinstance(category, str) or len(category) > 1024
                    for category in item["observed_failure_categories"]
                )
            ):
                return ()
            if item["state"] == "validated" and not item["validation_reference"]:
                return ()
            if item["validation_reference"] is not None and not isinstance(
                item["validation_reference"], str
            ):
                return ()
            identity = (item["profile_id"], item["revision"])
            if identity in identities:
                return ()
            identities.add(identity)
            profiles.append(
                AssistanceProfile(
                    profile_id=item["profile_id"],
                    revision=item["revision"],
                    state=item["state"],
                    model=item["model"],
                    effort=item["effort"],
                    client=item["client"],
                    task_families=frozenset(item["task_families"]),
                    raise_to_structured=item["raise_to_structured"],
                    optional_components=tuple(item["optional_components"]),
                    validation_reference=item["validation_reference"],
                )
            )
        return tuple(profiles)
    except (OSError, UnicodeError, ValueError, TypeError):
        return ()
