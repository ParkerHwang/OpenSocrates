"""Observe one caller-named file by SHA-256 and compare an optional prior fingerprint.

The caller names a single path. One call stats and, only when that path is a
regular file, reads it to compute a fingerprint. The call does not watch a
directory, list directory entries, follow a symlink, copy or back up bytes,
store file contents, or modify the file.

``changed`` means the two SHA-256 fingerprints differ. That is evidence the
byte sequences differ. It is not a description of the difference. ``same``
means the fingerprints are equal. That is evidence the read bytes match under
SHA-256, not an absolute identity proof, and not evidence that nothing was
written in between. Neither result identifies an author or an intent, and
neither establishes that a replacement was atomic or conditional on the prior
fingerprint.

This module is a standalone standard-library API. It does not import other v2
modules, persist observations, or retain raw prompts, transcripts, workspace
contents, credentials, or hidden reasoning.
"""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

_SHA256_PREFIX: Final[str] = "sha256:"
_FINGERPRINT_LENGTH: Final[int] = len(_SHA256_PREFIX) + 64
_HEX_DIGITS: Final[frozenset[str]] = frozenset("0123456789abcdef")
_READ_CHUNK: Final[int] = 1024 * 1024
_NOT_REGULAR_ERRNOS: Final[frozenset[int]] = frozenset({errno.ELOOP, errno.EISDIR})

WITHHELD_INFERENCES: Final[tuple[str, ...]] = (
    "author",
    "intent",
    "content_difference",
    "atomic_overwrite",
)
"""Inferences a fingerprint comparison does not support."""


class FileAvailability(StrEnum):
    """Whether this call could read one regular file and hash its bytes."""

    FINGERPRINTED = "fingerprinted"
    ABSENT = "absent"
    INACCESSIBLE = "inaccessible"
    NOT_A_REGULAR_FILE = "not_a_regular_file"


class FingerprintComparison(StrEnum):
    """Relation between the fingerprint read now and a caller-supplied prior.

    ``changed`` (변경) and ``same`` (동일) compare fingerprints only.
    ``no_prior`` (이전정보없음) means a fingerprint was read and the caller
    supplied none. ``unobservable`` (관찰불가) means no fingerprint was read.
    Absence, an unread path, and a non-regular path stay in this last state
    rather than being reported as a change.
    """

    CHANGED = "changed"
    SAME = "same"
    NO_PRIOR = "no_prior"
    UNOBSERVABLE = "unobservable"


@dataclass(frozen=True, slots=True)
class FileObservation:
    """One read-only observation of a single named path.

    ``exists`` is ``True`` or ``False`` only when this call could settle
    existence, and ``None`` when it could not. ``fingerprint`` is ``sha256:``
    plus 64 lowercase hex digits of the bytes read during this call, or
    ``None``. Those bytes are not retained. ``previous_fingerprint`` is the
    caller-supplied prior after format validation, or ``None``.

    When ``availability`` is ``fingerprinted``, ``exists`` is ``True`` and
    ``comparison`` is ``changed``, ``same``, or ``no_prior``. Otherwise
    ``fingerprint`` is ``None`` and ``comparison`` is ``unobservable``.
    """

    path: str
    exists: bool | None
    availability: FileAvailability
    fingerprint: str | None
    previous_fingerprint: str | None
    comparison: FingerprintComparison


def observe_named_file(
    path: str | os.PathLike[str],
    previous_fingerprint: str | None = None,
) -> FileObservation:
    """Hash one named regular file and compare it with an optional prior fingerprint.

    ``path`` is used as given. It is not globbed, resolved through a symlink,
    or treated as a directory to list. ``previous_fingerprint`` is ``None``
    when the caller has no prior fingerprint. A supplied prior must be
    ``sha256:`` followed by 64 lowercase hex digits; any other value is a
    caller error and is not treated as an observation of the file.

    The fingerprint is the SHA-256 of the bytes successfully returned by the
    read. This is not an atomic snapshot. A concurrent writer can change the
    file during the read. If the read fails, no partial fingerprint is returned.
    """

    named = _require_path(path)
    previous = _require_previous(previous_fingerprint)
    exists, availability, fingerprint = _observe(named)
    return FileObservation(
        path=named,
        exists=exists,
        availability=availability,
        fingerprint=fingerprint,
        previous_fingerprint=previous,
        comparison=_comparison(fingerprint, previous),
    )


def _require_path(path: str | os.PathLike[str]) -> str:
    if not isinstance(path, (str, os.PathLike)):
        raise TypeError("path must be one filesystem path")
    named = os.fspath(path)
    if not isinstance(named, str) or named == "" or "\x00" in named:
        raise ValueError("path must name one file")
    return named


def _require_previous(previous: str | None) -> str | None:
    if previous is None:
        return None
    if not isinstance(previous, str):
        raise TypeError("previous_fingerprint must be a string or None")
    hex_digits = previous.removeprefix(_SHA256_PREFIX)
    if (
        len(previous) != _FINGERPRINT_LENGTH
        or not previous.startswith(_SHA256_PREFIX)
        or any(character not in _HEX_DIGITS for character in hex_digits)
    ):
        raise ValueError(
            "previous_fingerprint must be sha256: followed by 64 lowercase hex digits"
        )
    return previous


def _comparison(fingerprint: str | None, previous: str | None) -> FingerprintComparison:
    if fingerprint is None:
        return FingerprintComparison.UNOBSERVABLE
    if previous is None:
        return FingerprintComparison.NO_PRIOR
    if fingerprint == previous:
        return FingerprintComparison.SAME
    return FingerprintComparison.CHANGED


def _observe(path: str) -> tuple[bool | None, FileAvailability, str | None]:
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return False, FileAvailability.ABSENT, None
    except OSError:
        return None, FileAvailability.INACCESSIBLE, None
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        return True, FileAvailability.NOT_A_REGULAR_FILE, None
    return _read_regular_file(path)


def _read_regular_file(path: str) -> tuple[bool | None, FileAvailability, str | None]:
    try:
        fd = os.open(path, _read_flags())
    except FileNotFoundError:
        return False, FileAvailability.ABSENT, None
    except OSError as exc:
        return _open_error(exc)
    try:
        return _hash_fd(fd)
    finally:
        os.close(fd)


def _read_flags() -> int:
    flags = os.O_RDONLY
    for name in ("O_CLOEXEC", "O_NOFOLLOW"):
        value = getattr(os, name, 0)
        if isinstance(value, int):
            flags |= value
    return flags


def _open_error(exc: OSError) -> tuple[bool | None, FileAvailability, str | None]:
    if exc.errno == errno.ENOENT:
        return False, FileAvailability.ABSENT, None
    if exc.errno in _NOT_REGULAR_ERRNOS:
        return True, FileAvailability.NOT_A_REGULAR_FILE, None
    if exc.errno == errno.ENOTDIR:
        return None, FileAvailability.INACCESSIBLE, None
    return True, FileAvailability.INACCESSIBLE, None


def _hash_fd(fd: int) -> tuple[bool | None, FileAvailability, str | None]:
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return True, FileAvailability.NOT_A_REGULAR_FILE, None
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, _READ_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    except OSError:
        return True, FileAvailability.INACCESSIBLE, None
    return True, FileAvailability.FINGERPRINTED, _SHA256_PREFIX + digest.hexdigest()
