"""Presentation-only Guided policy; never rewrites or truncates public artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from ..domain.enums import AnswerShape
from .markdown import nonblank_line_count, scalar_count

SCHEMA = "opensocrates.response-policy/1.0.0"
PROTECTED = frozenset(
    {
        "authored_procedures",
        "required_public_outputs",
        "card_sections",
        "evidence_states",
        "judgment_strength",
        "stop_conditions",
        "safety_warnings",
        "legal_security_accessibility_warnings",
        "user_format",
        "numbers_units_dates",
        "identifiers",
        "citations_links",
        "code_quotes_structured_data",
    }
)
SHAPES = frozenset(shape.value for shape in AnswerShape) | {"default"}


def validate_response_policy(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "revision",
        "enforcement",
        "protected_contracts",
        "locales",
    }:
        raise ValueError("response policy fields invalid")
    if (
        value["schema"] != SCHEMA
        or type(value["revision"]) is not int
        or value["revision"] != 1
        or value["enforcement"] != "guided"
    ):
        raise ValueError("response policy identity invalid")
    if (
        not isinstance(value["protected_contracts"], list)
        or set(value["protected_contracts"]) != PROTECTED
        or len(value["protected_contracts"]) != len(PROTECTED)
    ):
        raise ValueError("response policy protected contracts invalid")
    if not isinstance(value["locales"], dict) or set(value["locales"]) != {"en", "ko"}:
        raise ValueError("response policy locales invalid")
    for locale, entry in value["locales"].items():
        _validate_profile(locale, entry)
    return value


def _validate_profile(locale: str, entry: Any) -> None:
    if not isinstance(entry, dict) or set(entry) != {
        "profile_id",
        "protected_rule",
        "rules",
        "shapes",
    }:
        raise ValueError("response profile fields invalid")
    if (
        entry["profile_id"] != f"{locale}-natural-v1"
        or not isinstance(entry["shapes"], dict)
        or set(entry["shapes"]) != SHAPES
    ):
        raise ValueError("response profile shape coverage invalid")
    if not isinstance(entry["rules"], list) or not entry["rules"]:
        raise ValueError("response profile rules invalid")
    for text in [entry["protected_rule"], *entry["rules"], *entry["shapes"].values()]:
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("response profile text invalid")


def _read_authored_json(path: Path) -> Any:
    """Build-only authoring input; use the existing bounded regular-file reader."""
    from ..content.loader import _read_bounded_regular_file

    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    try:
        raw = _read_bounded_regular_file(descriptor, label="response policy source")
    finally:
        os.close(descriptor)
    return json.loads(raw.decode("utf-8"))


def load_response_policy(path: Path) -> Mapping[str, Any]:
    """Load separate locale authoring files at build time, never host/user text."""
    manifest = _read_authored_json(path)
    expected = {locale: f"response-policy/{locale}.yaml" for locale in ("en", "ko")}
    if not isinstance(manifest, dict) or manifest.get("locales") != expected:
        raise ValueError("response policy locale source paths invalid")
    if (path.parent / "response-policy").is_symlink():
        raise ValueError("response profile source directory must not be a symlink")
    manifest["locales"] = {
        locale: _read_authored_json(path.parent / relative) for locale, relative in expected.items()
    }
    return validate_response_policy(manifest)


def load_compiled_response_policy(path: Path) -> Mapping[str, Any]:
    """Runtime consumes only the bundled canonical, bounded regular JSON asset."""
    from ..content.loader import _read_canonical_json

    _, policy = _read_canonical_json(path, label="compiled response policy")
    return validate_response_policy(policy)


def policy_identity(policy: Mapping[str, Any]) -> str:
    encoded = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def response_guidance(
    policy: Mapping[str, Any], locale: str, shape: str = "default"
) -> dict[str, Any]:
    if locale not in {"en", "ko"}:
        raise ValueError("unsupported response locale")
    selected_shape = shape if shape in SHAPES else "default"
    entry = policy["locales"][locale]
    return {
        "schema": SCHEMA,
        "revision": policy["revision"],
        "sha256": policy_identity(policy),
        "profile_id": entry["profile_id"],
        "locale": locale,
        "answer_shape": selected_shape,
        "enforcement": "guided",
        "application": "unverified",
        "instructions": "\n".join(
            [entry["protected_rule"], *entry["rules"], entry["shapes"][selected_shape]]
        ),
    }


def render_response_guidance(policy: Mapping[str, Any], locale: str) -> str:
    entry = policy["locales"][locale]
    heading = "Guided presentation policy" if locale == "en" else "작성 단계의 표현 안내"
    boundary = (
        "Guided only: no automatic rewrite, verified compliance, length cap or required-content removal."
        if locale == "en"
        else "작성 안내만 제공합니다. 자동 재작성·검증된 준수·길이 상한·필수 내용 삭제를 뜻하지 않습니다."
    )
    lines = [
        f"### {heading}",
        f"Profile: {entry['profile_id']}; revision {policy['revision']}; {policy_identity(policy)}",
        boundary,
        entry["protected_rule"],
        *entry["rules"],
    ]
    lines.extend(f"- {shape}: {entry['shapes'][shape]}" for shape in sorted(SHAPES))
    return "\n\n".join(lines)


def measure_visible_output(text: str, locale: str) -> dict[str, Any]:
    """Measure the complete public artifact, including required sections, without editing it."""
    if locale not in {"en", "ko"}:
        raise ValueError("unsupported measurement locale")
    return {
        "locale": locale,
        "unicode_scalars": scalar_count(text),
        "utf8_bytes": len(text.encode("utf-8")),
        "nonblank_lines": nonblank_line_count(text),
        "whitespace_units": len(text.split()),
        "unit_kind": "word_like" if locale == "en" else "eojeol_like",
        "scope": "complete_public_artifact",
        "quality_inference": "none",
    }
