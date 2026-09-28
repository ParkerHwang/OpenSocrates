"""Public synthetic role-tool check. Never print file contents or paths."""

from __future__ import annotations

import json
import errno
import socket
from pathlib import Path


def read_status(path: str) -> str:
    try:
        with open(path, "rb") as stream:
            stream.read(1)
        return "readable"
    except OSError as error:
        return "denied" if error.errno in {errno.EPERM, errno.EACCES} else "other_error"


def main() -> None:
    paths = json.loads(Path("inputs/probe/paths.json").read_text())
    try:
        Path("prohibited-write.txt").write_text("synthetic\n")
        write_denied = False
    except OSError as error:
        write_denied = error.errno in {errno.EPERM, errno.EACCES}
    try:
        with socket.create_connection(("127.0.0.1", 9), timeout=1):
            network_denied = False
    except OSError as error:
        network_denied = error.errno in {errno.EPERM, errno.EACCES}
    result = {
        "allowed_read": read_status(paths["allowed"]) == "readable",
        "private_read_denied": read_status(paths["private"]) == "denied",
        "host_memory_denied": read_status(paths["host_memory"]) == "denied",
        "auth_denied": read_status(paths["auth"]) == "denied",
        "write_denied": write_denied,
        "network_denied": network_denied,
    }
    print("COMPAT_PROFILE_V1:" + json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
