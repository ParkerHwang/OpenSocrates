#!/usr/bin/env python3
"""Evaluation-only mapping to a stricter *native* Codex permission profile.

The qualified product adapter supplies `--sandbox read-only` for role exec and
`sandbox -P :read-only` for checks. This shim maps both to a native profile
extending `:read-only` with per-episode read denials. It neither bypasses nor
replaces the pinned client. Freeze original/effective argv hashes per call.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


CLIENT = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"
MARKER = ".eval-episode"


def episode() -> Path:
    temporary = Path(os.environ["TMPDIR"]).resolve(strict=True)
    for root in (temporary, *temporary.parents):
        if (root / MARKER).is_file():
            if str(root) in {"/", "/private", "/private/tmp"}:
                break
            return root
    raise RuntimeError("marked_episode_root_unavailable")


def _configs(read_root: Path, code_home: Path | None = None) -> list[str]:
    profile = "eval"
    # More-specific read for only this role/check cwd overrides the broad host
    # deny. Prior roles, results and observations live outside this cwd.
    # The auth transport stays readable by the client parent, but not by its
    # sandboxed model-directed commands.
    auth = (code_home or Path(os.environ["CODEX_HOME"])) / "auth.json"
    filesystem = {
        "/Users": "deny", "/private/tmp": "deny",
        "/private/var/folders": "deny", str(read_root): "read",
        str(auth): "deny",
    }
    inline = "{" + ",".join(
        f"{json.dumps(path)}={json.dumps(access)}" for path, access in filesystem.items()
    ) + "}"
    mapping = [
        f'default_permissions="{profile}"',
        f'permissions.{profile}.extends=":read-only"',
        f"permissions.{profile}.filesystem={inline}",
    ]
    return [part for item in mapping for part in ("-c", item)]


def transform(argv: list[str], root: Path, code_home: Path | None = None) -> list[str]:
    if not argv:
        return argv
    if argv[0] in {"exec", "sandbox"} and "-C" in argv:
        at_cwd = argv.index("-C")
        read_root = Path(argv[at_cwd + 1]).resolve(strict=True)
        if not read_root.is_relative_to(root):
            raise RuntimeError("role_cwd_outside_marked_episode")
    else:
        read_root = root
    if argv[0] == "exec":
        if argv.count("--sandbox") != 1:
            raise RuntimeError("unexpected_role_sandbox_flag")
        at = argv.index("--sandbox")
        if argv[at + 1] != "read-only" or argv[-1] != "-":
            raise RuntimeError("unexpected_role_exec_shape")
        if "--ignore-user-config" not in argv or "--ephemeral" not in argv:
            raise RuntimeError("fresh_role_flags_missing")
        return [*argv[:at], *argv[at + 2:-1], *_configs(read_root, code_home), "-"]
    if argv[0] == "sandbox" and "-P" in argv:
        at = argv.index("-P")
        if argv[at + 1] != ":read-only":
            raise RuntimeError("unexpected_native_check_profile")
        if "--" not in argv:
            raise RuntimeError("native_check_separator_missing")
        separator = argv.index("--")
        return [*argv[:at], "-P", "eval", *argv[at + 2:separator],
                *_configs(read_root, code_home), *argv[separator:]]
    return argv


def argv_hash(args: list[str]) -> str:
    return hashlib.sha256(json.dumps(args, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    original = sys.argv[1:]
    if original and ((original[0] == "exec" and "--help" not in original)
                     or (original[0] == "sandbox" and "-P" in original)):
        root = episode()
        effective = transform(original, root)
        # A model call is never started when policy translation is unavailable.
        if original[0] == "exec" and "--sandbox" in effective:
            raise RuntimeError("legacy_sandbox_flag_retained")
        receipt = {
            "kind": original[0], "pid": os.getpid(),
            "original_argv_sha256": argv_hash([CLIENT, *original]),
            "effective_argv_sha256": argv_hash([CLIENT, *effective]),
            "profile": "eval extends :read-only",
        }
        encoded = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
        fd = os.open(root / "argv-map.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
    else:
        effective = original
    os.execv(CLIENT, [CLIENT, *effective])


if __name__ == "__main__":
    raise SystemExit(main())
