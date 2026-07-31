"""Packaged command entry point with a fixed hook/CLI split."""

from __future__ import annotations

import sys
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    values = tuple(argv) if argv is not None else tuple(sys.argv[1:])
    if values and values[0] == "hook":
        from .hooks.entrypoint import main as hook_main

        return hook_main(values)
    from .cli.main import main as cli_main

    return cli_main(values)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
