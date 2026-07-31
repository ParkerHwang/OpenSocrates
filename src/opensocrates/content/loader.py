"""Production compiled-content JSON loader.

No YAML parser is imported here. Production receives only the validated compiler
bundle and exposes immutable-by-convention lookup operations.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from ..domain.models import CompiledContentBundle, ReasoningContentProjections
from ..domain.validation import model_from_json
from .hashes import canonical_json_bytes
from .schema import (
    ContentValidationError,
    validate_compiled_bundle_shape,
    validate_reasoning_content_projections_shape,
)

MAX_COMPILED_CONTENT_BYTES = 4 * 1024 * 1024


def _open_regular_json(path: str | Path, *, label: str) -> int:
    """Open the final path only when it is a regular, non-symlink JSON file."""

    source = Path(path)
    if source.suffix.lower() not in {".json", ".bundle"}:
        raise ContentValidationError(f"{label} loader accepts compiled JSON only")
    try:
        initial = source.lstat()
    except OSError as exc:
        raise ContentValidationError(f"{label} loader cannot inspect source") from exc
    if not stat.S_ISREG(initial.st_mode) or stat.S_ISLNK(initial.st_mode):
        raise ContentValidationError(f"{label} loader requires a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(source, flags)
    except OSError as exc:
        raise ContentValidationError(f"{label} loader cannot open source") from exc


def _read_bounded_regular_file(descriptor: int, *, label: str) -> bytes:
    """Read no more than the content bound from an already-opened regular file."""

    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_COMPILED_CONTENT_BYTES:
            raise ContentValidationError(f"{label} loader source is unsafe or exceeds its bound")
        chunks: list[bytes] = []
        remaining = MAX_COMPILED_CONTENT_BYTES + 1
        while remaining > 0:
            block = os.read(descriptor, min(64 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
    except OSError as exc:
        raise ContentValidationError(f"{label} loader cannot read source") from exc
    raw = b"".join(chunks)
    if len(raw) > MAX_COMPILED_CONTENT_BYTES:
        raise ContentValidationError(f"{label} loader source exceeds its bound")
    return raw


def _decode_canonical_json(raw: bytes, *, label: str) -> object:
    """Decode only one canonical, terminal-LF JSON document."""

    if not raw.endswith(b"\n"):
        raise ContentValidationError(f"{label} content must end with one LF")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContentValidationError(f"{label} content is not UTF-8 JSON: {exc}") from exc
    if raw != canonical_json_bytes(data):
        raise ContentValidationError(f"{label} content is not canonical sorted compact JSON")
    return data


def _read_canonical_json(path: str | Path, *, label: str) -> tuple[bytes, object]:
    """Read one bounded regular JSON file without following its final symlink."""

    descriptor = _open_regular_json(path, label=label)
    try:
        raw = _read_bounded_regular_file(descriptor, label=label)
    finally:
        os.close(descriptor)
    return raw, _decode_canonical_json(raw, label=label)


def load_compiled_bundle(path: str | Path) -> CompiledContentBundle:
    """Load only canonical UTF-8 JSON; reject YAML or noncanonical terminal output."""
    raw, data = _read_canonical_json(path, label="content")
    validate_compiled_bundle_shape(data)
    try:
        return model_from_json(CompiledContentBundle, raw)  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.
    except Exception as exc:  # domain validation exposes several stable exception classes
        raise ContentValidationError(f"compiled content violates domain contract: {exc}") from exc


def load_reasoning_content_projections(path: str | Path) -> ReasoningContentProjections:
    """Load the immutable OpenSocrates selector catalog/injectable-content projection."""

    raw, data = _read_canonical_json(path, label="reasoning content projections")
    validate_reasoning_content_projections_shape(data)
    try:
        return model_from_json(ReasoningContentProjections, raw)  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.
    except Exception as exc:  # domain validation exposes several stable exception classes
        raise ContentValidationError(
            f"reasoning content projections violate domain contract: {exc}"
        ) from exc


ContentLoader = load_compiled_bundle
ReasoningContentProjectionLoader = load_reasoning_content_projections
