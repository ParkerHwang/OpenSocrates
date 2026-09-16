"""PyInstaller entry wrapper that preserves the package import context."""

from __future__ import annotations

import sys

if __name__ == "__main__":
    # PyInstaller replaces freeze_support() with a dispatcher for both worker
    # forks and its resource-tracker/fork-server helper processes. It must run
    # before command dispatch, not only for the visible worker-fork argument.
    import multiprocessing

    multiprocessing.freeze_support()
    if sys.platform == "win32":
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            if stream is not None:
                stream.reconfigure(encoding="utf-8", newline="\n")
    arguments = tuple(sys.argv[1:])
    if arguments in {("version",), ("version", "--json")}:
        import json

        from opensocrates.version import PRODUCT_VERSION, version_info

        if arguments == ("version", "--json"):
            sys.stdout.write(
                json.dumps(
                    version_info(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            )
        else:
            sys.stdout.write(PRODUCT_VERSION + "\n")
        raise SystemExit(0)
    from opensocrates.__main__ import main

    raise SystemExit(main())
