"""Deterministic content normalization and semantic/source hashing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

CONTENT_TREE_PREFIX = b"opensocrates-content-tree-v1\0"
SEMANTICS_PREFIX = b"opensocrates-runtime-semantics-v1\0"


def canonical_json_bytes(value: Any) -> bytes:
    """Return sorted compact UTF-8 JSON with exactly one terminal LF."""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def normalize_markdown(text: str) -> str:
    """Normalize line endings and enforce exactly one final LF without Unicode folding."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n") + "\n"


def canonical_yaml_bytes(value: Any) -> bytes:
    """Canonicalize an already parsed YAML value as JSON for hashing."""
    return canonical_json_bytes(value)


def source_tree_hash(content_root: str | Path, yaml_loader: Callable[[Path], Any]) -> str:
    """Hash sorted canonical YAML/Markdown source files under content_root."""
    root = Path(content_root)
    paths = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}
        ),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )
    digest = hashlib.sha256(CONTENT_TREE_PREFIX)
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.suffix.lower() in {".yaml", ".yml"}:
            content = canonical_yaml_bytes(yaml_loader(path))
        else:
            content = normalize_markdown(path.read_text(encoding="utf-8")).encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return sha256_hex(digest.digest())


def normalized_semantic_hash(projection: Mapping[str, Any]) -> str:
    """Hash the host-neutral runtime semantics projection."""
    return sha256_hex(SEMANTICS_PREFIX + canonical_json_bytes(projection))


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
