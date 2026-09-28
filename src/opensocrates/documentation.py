"""Stateless official-document reference prompts; metadata is not source proof."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .project_memory.contracts import ContractError, load_schema, validate

PACK_SCHEMA = "opensocrates.documentation.pack/1.0.0"
MAX_BYTES = 16 * 1024


class DocumentationUnavailable(RuntimeError):
    """Trusted installed content is absent or inconsistent, not a caller defect."""


def _installed_schema(filename: str) -> dict[str, Any]:
    try:
        return load_schema(filename)
    except (OSError, ValueError) as error:
        raise DocumentationUnavailable("installed_schema_unavailable") from error


def _assets() -> Path:
    frozen = getattr(sys, "_MEIPASS", None)
    root = Path(frozen) if isinstance(frozen, str) else Path(__file__).resolve().parents[2]
    return root / "plugin-src/shared/documentation"


def _url(value: str) -> tuple[str, str]:
    """Validate a clean reference, without resolving DNS or following redirects."""
    parsed = urlsplit(value)
    decoded = unquote(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query
        or "\\" in decoded
        or any(ord(char) < 33 or ord(char) == 127 for char in decoded)
        or not parsed.hostname.isascii()
        or any(part in (".", "..") for part in unquote(parsed.path).split("/"))
        or "%" in unquote(parsed.path)
        or re.fullmatch(r"[A-Za-z0-9_.-]*", unquote(parsed.fragment)) is None
        or re.match(
            r"(?i)(access[_-]?token|id[_-]?token|api[_-]?key|password|secret|credential)([_-]|$)",
            unquote(parsed.fragment),
        )
        is not None
    ):
        raise ValueError("invalid_reference_url")
    return parsed.hostname.lower(), unquote(parsed.path) or "/"


def _matches(url: str, roots: list[str]) -> bool:
    host, path = _url(url)
    for root in roots:
        root_host, root_path = _url(root)
        if host == root_host and (
            root_path == "/"
            or path == root_path.rstrip("/")
            or path.startswith(root_path.rstrip("/") + "/")
        ):
            return True
    return False


def _read_assets(locale: str, needed: bool) -> tuple[dict[str, Any], str]:
    try:
        catalog_bytes = (_assets() / "publishers.json").read_bytes()
        if len(catalog_bytes) > MAX_BYTES:
            raise ValueError("catalog_limit")
        catalog = json.loads(catalog_bytes)
        if (
            catalog["schema"] != "opensocrates.documentation.publishers/1.0.0"
            or type(catalog["revision"]) is not int
            or catalog["revision"] < 1
            or not isinstance(catalog["publishers"], dict)
        ):
            raise ValueError("invalid_catalog")
        for publisher_roots in catalog["publishers"].values():
            if not isinstance(publisher_roots, list) or len(publisher_roots) > 8:
                raise ValueError("invalid_roots")
            for root in publisher_roots:
                if not isinstance(root, str):
                    raise ValueError("invalid_root")
                _url(root)
        instructions = (
            (_assets() / f"prompt.{locale}.md").read_text(encoding="utf-8") if needed else ""
        )
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise DocumentationUnavailable("installed_content_unavailable") from error
    return catalog, instructions


def documentation_pack(request: Any) -> dict[str, Any]:
    """Emit fixed trusted instructions and separate bounded caller declarations."""
    validate(request, _installed_schema("documentation-request.schema.json"))
    for reference in request["references"]:
        _url(reference["url"])
        if reference["read_state"] == "reported_read" and reference["attribution"] == "unknown":
            raise ContractError("a reported read needs attribution")
    needed = request["need"] != "none" and (
        request["task_kind"] != "mechanical" or request["need"] == "official_request"
    )
    catalog, instructions = _read_assets(request["locale"], needed)
    roots = catalog["publishers"].get(request["publisher_id"], [])
    references = []
    for item in request["references"] if needed else []:
        target, version = request["target_version"], item["document_version"]
        references.append(
            {
                **item,
                "publisher_match": "catalog_match"
                if _matches(item["url"], roots)
                else "unverified",
                "version_match": "unknown"
                if target is None or version is None
                else "exact_declared"
                if target == version
                else "mismatch",
            }
        )
    if not needed:
        action = "continue"
    elif (
        not roots
        or not references
        or any(item["publisher_match"] != "catalog_match" for item in references)
    ):
        action = "find_official_source"
    elif any(item["read_state"] != "reported_read" for item in references):
        action = "read_reference"
    elif any(
        item["version_match"] == "mismatch"
        or (request["target_version"] is not None and item["version_match"] == "unknown")
        for item in references
    ):
        action = "resolve_version"
    else:
        action = "apply_with_citations"
    result = {
        "schema": PACK_SCHEMA,
        "request_id": request["request_id"],
        "status": "ok" if needed else "not_needed",
        "instructions": instructions,
        "instruction_sha256": "sha256:" + hashlib.sha256(instructions.encode("utf-8")).hexdigest()
        if needed
        else None,
        "publisher_id": request["publisher_id"],
        "catalog_revision": catalog["revision"],
        "official_roots": roots if needed else [],
        "references": references,
        "next_action": action,
        "delivery": "emitted" if needed else "not_emitted",
        "application": "unverified",
        "limitations": [
            "metadata_is_caller_reported",
            "catalog_match_not_authenticity_or_freshness",
            "no_network_or_model_calls",
            "no_document_body_retained",
            "permissions_and_behavior_checks_external",
        ],
    }
    try:
        validate(result, _installed_schema("documentation-pack.schema.json"))
    except ValueError as error:
        raise DocumentationUnavailable("invalid_installed_output") from error
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        raise DocumentationUnavailable("response_limit")
    return result
