"""Atomically transfer never-started cells without signalling any process."""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "v2"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def exclusive_rename(source, destination):
    # macOS SDK sys/stdio.h: RENAME_EXCL=0x00000004, renamex_np since macOS 10.12.
    # A normal rename could replace an existing empty directory and race the old
    # runner's first mkdir. RENAME_EXCL cannot replace even an empty directory.
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renamex_np
    rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    result = rename(os.fsencode(source), os.fsencode(destination), 0x00000004)
    if result:
        code = ctypes.get_errno()
        if code in (errno.EEXIST, errno.ENOTEMPTY):
            return False
        raise OSError(code, os.strerror(code), str(destination))
    return True


def dispatch(storage):
    manifest = json.loads((HERE / "manifest.json").read_text())
    base = json.loads((BASE / "manifest.json").read_text())
    assert sha(BASE / "manifest.json") == manifest["base_manifest_sha256"]
    for name, digest in manifest["frozen_files"].items():
        assert sha(HERE / name) == digest, name
    assert not (HERE / "dispatch.json").exists(), "Never dispatch twice"
    cells = {c["id"]: c for c in base["cells"]}
    owned, legacy = [], []
    for identity in manifest["planned_cells"]:
        destination = BASE / "results" / identity
        if (storage / identity).exists() or destination.exists():
            legacy.append(identity)
            continue
        temporary = Path(tempfile.mkdtemp(prefix=".claim-", dir=HERE))
        marker = {
            "cell": cells[identity],
            "utc": datetime.now(timezone.utc).isoformat(),
            "call_attempted": False,
            "reason": "transferred_to_parallel_v1",
            "amendment_sha256": sha(HERE / "manifest.json"),
            "outcome_disposition": "administrative queue handoff; not a failed or skipped model outcome",
            "usage": {k: None for k in manifest["usage_fields"]},
        }
        save(temporary / "skipped.json", marker)
        if exclusive_rename(temporary, destination):
            owned.append(identity)
        else:
            # Only this newly created, never-published claim is removed.
            (temporary / "skipped.json").unlink()
            temporary.rmdir()
            legacy.append(identity)
    receipt = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "amendment_sha256": sha(HERE / "manifest.json"),
        "transferred_cells": owned,
        "retained_by_legacy_executor": legacy,
        "process_signals_sent": 0,
        "subject_restarts": 0,
        "new_executor_model_calls_before_this_receipt": 0,
        "ownership_rule": "Atomic exclusive directory publication before the legacy runner's first mkdir; never overwrite an existing cell directory.",
    }
    save(HERE / "dispatch.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage", type=Path, required=True)
    dispatch(parser.parse_args().storage)
