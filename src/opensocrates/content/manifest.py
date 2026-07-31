"""Compiled content bundle and policy manifest construction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .hashes import canonical_json_bytes, normalized_semantic_hash, sha256_hex
from .locale import prompt_fragments, validate_locale_parity
from .schema import (
    BUNDLE_SCHEMA,
    FROZEN_METHOD_IDS,
    POLICY_IDS,
    PROMPT_FRAGMENT_IDS,
    ContentValidationError,
)


def policy_digests(policies: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    if set(policies) != set(POLICY_IDS):
        raise ContentValidationError("policies: expected participation, risk, routing, and card")
    result: dict[str, dict[str, str]] = {}
    for policy_id in POLICY_IDS:
        policy = policies[policy_id]
        version = policy.get("version")
        if not isinstance(version, str) or not version:
            raise ContentValidationError(f"policy.{policy_id}.version: required")
        result[policy_id] = {"version": version, "sha256": sha256_hex(canonical_json_bytes(policy))}
    return result


def build_content_bundle(
    *,
    product_version: str,
    content_revision: int,
    methods: Sequence[Mapping[str, Any]],
    locales: Mapping[str, Mapping[str, Any]],
    policies: Mapping[str, Mapping[str, Any]],
    source_tree_hash: str,
) -> dict[str, Any]:
    if set(locales) != {"en", "ko"}:
        raise ContentValidationError("bundle locales: expected exactly en and ko")
    validate_locale_parity(locales["en"], locales["ko"])
    ordered_methods = sorted((dict(method) for method in methods), key=lambda method: method["id"])
    method_ids = [method["id"] for method in ordered_methods]
    if method_ids != sorted(FROZEN_METHOD_IDS):
        raise ContentValidationError("bundle methods: expected sorted frozen IDs")
    fragments = prompt_fragments(locales["en"], locales["ko"])
    if set(fragments) != set(PROMPT_FRAGMENT_IDS):
        raise ContentValidationError("bundle prompt fragments: fixed set mismatch")
    policy_versions = policy_digests(policies)
    locale_messages = {locale: dict(locales[locale]["messages"]) for locale in ("en", "ko")}
    projection = {
        "content_revision": content_revision,
        "method_ids": method_ids,
        "methods": ordered_methods,
        "locale_messages": locale_messages,
        "prompt_fragments": fragments,
        "policy_versions": policy_versions,
    }
    return {
        "schema": BUNDLE_SCHEMA,
        "product_version": product_version,
        "content_revision": content_revision,
        "method_ids": method_ids,
        "methods": ordered_methods,
        "locale_messages": locale_messages,
        "prompt_fragments": fragments,
        "policy_versions": policy_versions,
        "source_tree_hash": source_tree_hash,
        "normalized_semantic_hash": normalized_semantic_hash(projection),
    }


def serialize_bundle(bundle: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(bundle)
