"""Quarantine helpers for malformed or interrupted record files."""

from __future__ import annotations

import os
import secrets
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .atomic import AtomicWriteError, atomic_replace_bytes
from .paths import secure_join


class QuarantineReason(StrEnum):
    TORN_TAIL = "torn_tail"
    MID_FILE_CORRUPTION = "mid_file_corruption"
    SEQUENCE_GAP = "sequence_gap"
    SCHEMA_MISMATCH = "schema_mismatch"
    PERMISSION_HAZARD = "permission_hazard"


class QuarantineError(OSError):
    """Raised when a record cannot be moved to quarantine safely."""


@dataclass(frozen=True, slots=True)
class QuarantineReceipt:
    original_name: str
    quarantine_name: str
    reason: QuarantineReason
    complete_line_count: int


def _safe_record_name(path: Path) -> str:
    name = path.name
    if not name.endswith(".jsonl") or name in {".jsonl", "..jsonl"}:
        raise QuarantineError("not a task record path")
    return name


def quarantine_record(
    record_path: Path,
    quarantine_dir: Path,
    *,
    reason: QuarantineReason,
    complete_line_count: int = 0,
) -> QuarantineReceipt:
    """Move a record into a non-executable owner-only quarantine directory."""

    record_path = Path(record_path)
    quarantine_dir = Path(quarantine_dir)
    original_name = _safe_record_name(record_path)
    try:
        source_info = record_path.lstat()
        directory_info = quarantine_dir.lstat()
    except OSError as error:
        raise QuarantineError("cannot inspect quarantine paths") from error
    if stat.S_ISLNK(source_info.st_mode) or stat.S_ISLNK(directory_info.st_mode):
        raise QuarantineError("symlink quarantine paths are not allowed")
    if not stat.S_ISDIR(directory_info.st_mode):
        raise QuarantineError("quarantine target is not a directory")
    tag = secrets.token_hex(8)
    quarantine_name = f"{original_name[:-6]}.{reason.value}.{tag}.jsonl"
    destination = secure_join(quarantine_dir, quarantine_name)
    try:
        os.replace(record_path, destination)
        if os.name != "nt":
            os.chmod(destination, 0o600)
    except OSError as error:
        raise QuarantineError("unable to quarantine record") from error
    return QuarantineReceipt(
        original_name=original_name,
        quarantine_name=quarantine_name,
        reason=reason,
        complete_line_count=complete_line_count,
    )


def recover_prefix(
    record_path: Path, prefix: bytes, quarantine_dir: Path, *, complete_line_count: int
) -> QuarantineReceipt:
    """Quarantine torn bytes, then restore only the validated complete prefix."""

    receipt = quarantine_record(
        record_path,
        quarantine_dir,
        reason=QuarantineReason.TORN_TAIL,
        complete_line_count=complete_line_count,
    )
    try:
        atomic_replace_bytes(record_path, prefix)
    except AtomicWriteError as error:
        raise QuarantineError("unable to restore complete record prefix") from error
    return receipt
