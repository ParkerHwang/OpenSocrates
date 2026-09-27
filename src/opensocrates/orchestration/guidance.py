"""Complete, locale-matched trusted role/domain guidance per fresh assignment."""

from __future__ import annotations

from typing import Any

from .contracts import assets_root
from .paths import BoundaryError, digest


def guides(unit: dict[str, Any], role: str, locale: str) -> list[dict[str, str]]:
    shared = assets_root() / "plugin-src/shared"
    paths = [f"orchestration/v0.1.0/base.{locale}.md", f"orchestration/v0.1.0/{role}.{locale}.md"]
    if unit["task_kind"] != "mechanical":
        paths.append(f"orchestration/v0.1.0/{unit['domain']}.{locale}.md")
    if role in {"review", "execution_verification"} or unit["domain"] in {
        "software",
        "data",
        "document",
    }:
        paths.append(f"assistance/verification.{locale}.md")
    if unit["specialists"]:
        paths.append(f"coding-specialists/v0.1.1/router.{locale}.md")
        paths.extend(
            f"coding-specialists/v0.1.1/{name}.{locale}.md" for name in unit["specialists"]
        )
    result = []
    for path in paths:
        data = (shared / path).read_bytes()
        if len(data) > 65536:
            raise BoundaryError("guide_budget_exceeded")
        result.append({"id": path, "sha256": digest(data), "text": data.decode("utf-8")})
    return result
