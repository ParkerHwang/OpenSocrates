#!/usr/bin/env python3
"""Check production import boundaries, including the isolated Codex SDK seam."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "opensocrates"
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {
    "_ast",
    "_io",
    "typing_extensions",
}
CODEX_SDK_ADAPTERS = frozenset(
    {
        Path("selector") / "sdk.py",
        Path("selector") / "sdk_worker.py",
    }
)
CODEX_SDK_IMPORTS = frozenset({"openai_codex", "pydantic"})
FORBIDDEN_DOMAIN_MODULES = {
    "application",
    "cli",
    "content",
    "hooks",
    "hosts",
    "persistence",
    "prompting",
    "rendering",
    "verification",
}


def _root_name(module: str) -> str:
    return module.split(".", 1)[0]


def _is_allowed_external_import(relative: Path, module: str) -> bool:
    """Allow SDK typing/client imports only at the OpenSocrates selector boundary."""

    return relative in CODEX_SDK_ADAPTERS and _root_name(module) in CODEX_SDK_IMPORTS


def check() -> list[str]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    violations: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(SRC)
        is_domain = relative.parts and relative.parts[0] == "domain"
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if (
                        _root_name(module) not in STDLIB
                        and not module.startswith("opensocrates")
                        and not _is_allowed_external_import(relative, module)
                    ):
                        violations.append(f"{path}: external import {module}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level and relative.parts:
                    continue
                if (
                    _root_name(module) not in STDLIB
                    and not module.startswith("opensocrates")
                    and not _is_allowed_external_import(relative, module)
                ):
                    violations.append(f"{path}: external import {module}")
            if is_domain and module and module.startswith("opensocrates."):
                imported_root = module.split(".")[1] if len(module.split(".")) > 1 else ""
                if imported_root in FORBIDDEN_DOMAIN_MODULES:
                    violations.append(f"{path}: domain import boundary violation {module}")
    return violations


def main() -> int:
    violations = check()
    if violations:
        print("import boundary: FAIL", file=sys.stderr)
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("import boundary: PASS (Codex SDK imports isolated; domain boundaries clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
