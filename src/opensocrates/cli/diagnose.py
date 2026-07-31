"""Safe JSON and Markdown rendering for the aggregate diagnose contract."""

from __future__ import annotations

from typing import TextIO

from ..application.diagnose import DiagnoseSnapshot, build_diagnose
from ..domain.validation import canonical_json


class DiagnoseCommandError(ValueError):
    """Raised when a diagnose renderer receives an invalid typed snapshot."""


def diagnose_json(snapshot: DiagnoseSnapshot) -> str:
    if not isinstance(snapshot, DiagnoseSnapshot):
        raise DiagnoseCommandError("diagnose requires a typed snapshot")
    return canonical_json(snapshot.to_dict())


def diagnose_markdown(snapshot: DiagnoseSnapshot) -> str:
    """Render only bounded aggregate fields; never render filesystem detail."""

    if not isinstance(snapshot, DiagnoseSnapshot):
        raise DiagnoseCommandError("diagnose requires a typed snapshot")
    value = snapshot.to_dict()
    versions = value["versions"]
    manifest = value["manifest"]
    health = value["health"]
    lines = [
        "# OpenSocrates diagnosis",
        "",
        f"- product: `{versions.get('product_version', 'unknown')}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- schema: `{versions.get('schema_version', 'unknown')}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- content: `{versions.get('content_revision', 'unknown')}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- manifest: `{manifest.get('status', 'unknown')}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- checksum: `{manifest.get('checksum_status', 'unknown')}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- storage: `{health.get('status', 'unknown')}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- permissions: `{health.get('permissions', 'unknown')}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- records: `{health.get('record_count', 0)}` ({health.get('record_bytes', 0)} bytes)",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- metrics: `{health.get('metric_count', 0)}` ({health.get('metric_bytes', 0)} bytes)",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- turn states: `{health.get('turn_state_count', 0)}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        f"- quarantine entries: `{health.get('quarantine_count', 0)}`",  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
    ]
    return "\n".join(lines) + "\n"


def render_diagnose(snapshot: DiagnoseSnapshot, *, output: str = "json") -> str:
    if output == "json":
        return diagnose_json(snapshot)
    if output == "markdown":
        return diagnose_markdown(snapshot)
    raise DiagnoseCommandError("diagnose output must be json or markdown")


def diagnose_main(
    snapshot: DiagnoseSnapshot | None = None,
    *,
    output: str = "json",
    stdout: TextIO | None = None,
) -> int:
    from ..cli.runtime import build_runtime_services

    selected = snapshot
    if selected is None:
        services = build_runtime_services()
        selected = build_diagnose(
            profiles=services.capability_profiles,
            bundle=services.bundle,
            health=services.health,
            manifest_status="verified" if services.bundle is not None else "unavailable",
            checksum_status="verified" if services.bundle is not None else "unavailable",
            platform_name=__import__("platform").system(),
            architecture=__import__("platform").machine(),
        )
    (stdout or __import__("sys").stdout).write(render_diagnose(selected, output=output))
    return 0


main = diagnose_main


__all__ = [
    "DiagnoseCommandError",
    "diagnose_json",
    "diagnose_main",
    "diagnose_markdown",
    "main",
    "render_diagnose",
]
