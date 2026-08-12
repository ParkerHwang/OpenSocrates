"""Production command dispatcher for the packaged OpenSocrates runtime."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from typing import Any, TextIO

from ..application.diagnose import build_diagnose
from ..domain.validation import canonical_json
from ..version import PRODUCT_VERSION, version_info
from .capabilities import probe_capabilities, show_capabilities
from .diagnose import render_diagnose
from .integrity import verify_runtime_integrity
from .metrics import export_metrics, reset_metrics, show_metrics
from .settings import handle_rigor_get, handle_rigor_reset, handle_rigor_set


class CliCommandError(ValueError):
    """Raised for a composition error that must become a bounded CLI result."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opensocrates")
    sub = parser.add_subparsers(dest="command", required=True)

    control = sub.add_parser("control", help="apply one bounded host control")
    control_sub = control.add_subparsers(dest="control_command", required=True)
    apply = control_sub.add_parser("apply", help="apply a typed control from stdin")
    apply.add_argument("--host", choices=("claude", "codex"), required=True)

    diagnose = sub.add_parser("diagnose", help="show safe runtime aggregates")
    diagnose.add_argument("--host", choices=("antigravity", "claude", "codex", "prompt_only"))
    output = diagnose.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_const", const="json", dest="output")
    output.add_argument("--markdown", action="store_const", const="markdown", dest="output")

    rigor = sub.add_parser("rigor", help="read or change the rigor preference")
    rigor_sub = rigor.add_subparsers(dest="rigor_command", required=True)
    rigor_sub.add_parser("get")
    rigor_set = rigor_sub.add_parser("set")
    rigor_set.add_argument("level", choices=("quiet", "together", "strict"))
    rigor_set.add_argument("--once", action="store_true")
    rigor_sub.add_parser("reset")

    trace = sub.add_parser("trace", help="list, show, or export a public trace")
    trace_sub = trace.add_subparsers(dest="trace_command", required=True)
    trace_sub.add_parser("list")
    trace_show = trace_sub.add_parser("show")
    trace_show.add_argument("selector", nargs="?")
    trace_export = trace_sub.add_parser("export")
    trace_export.add_argument("destination")
    trace_export.add_argument("selector", nargs="?")
    trace_export.add_argument("--overwrite", action="store_true")

    records = sub.add_parser("records", help="list or manage local public records")
    records_sub = records.add_subparsers(dest="records_command", required=True)
    records_sub.add_parser("list")
    records_delete = records_sub.add_parser("delete")
    target = records_delete.add_mutually_exclusive_group(required=True)
    target.add_argument("--id", dest="public_short_id")
    target.add_argument("--all", action="store_true", dest="all_records")
    records_delete.add_argument("--confirm")
    records_delete.add_argument("--include-quarantine", action="store_true")
    prune = records_sub.add_parser("prune")
    prune.add_argument("--apply", action="store_true")

    capabilities = sub.add_parser("capabilities", help="show capability contract status")
    capabilities_sub = capabilities.add_subparsers(dest="capabilities_command", required=True)
    for name in ("probe", "show"):
        command = capabilities_sub.add_parser(name)
        command.add_argument(
            "--host",
            choices=("antigravity", "claude", "codex", "prompt_only"),
            required=True,
        )

    metrics = sub.add_parser("metrics", help="show or export local aggregate metrics")
    metrics_sub = metrics.add_subparsers(dest="metrics_command", required=True)
    metrics_sub.add_parser("show")
    metrics_export = metrics_sub.add_parser("export")
    metrics_export.add_argument("destination")
    metrics_export.add_argument("--overwrite", action="store_true")
    metrics_sub.add_parser("reset")

    version = sub.add_parser("version", help="show release and contract identities")
    version.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _normalize_control(argv: list[str]) -> list[str]:
    if not argv or argv[0] != "control":
        return argv
    if len(argv) >= 2 and argv[1] in {"claude", "codex"}:
        return ["control", "apply", "--host", argv[1], *argv[2:]]
    if len(argv) >= 3 and argv[1] == "--host" and argv[2] in {"claude", "codex"}:
        return ["control", "apply", "--host", argv[2], *argv[3:]]
    return argv


def _emit(value: object, stdout: TextIO) -> None:
    if isinstance(value, str):
        stdout.write(value if value.endswith("\n") else value + "\n")
        return
    stdout.write(canonical_json(value))


def _unavailable(code: str = "runtime_unavailable") -> dict[str, object]:
    return {"status": "unavailable", "error_code": code}


def _services_for(services: Any | None, *, host: str | None = None) -> Any:
    if services is not None:
        return services
    from .runtime import build_runtime_services

    return build_runtime_services(host=host)


def _diagnose(services: Any, host: str | None) -> object:
    profiles = getattr(services, "capability_profiles", None) or {}
    if host:
        selected = profiles.get(host) if isinstance(profiles, dict) else None
        profiles = {host: selected} if selected is not None else {}
    selector_outcome_reader = getattr(services, "selector_outcome_counts", None)
    selector_outcomes = selector_outcome_reader() if callable(selector_outcome_reader) else {}
    integrity = verify_runtime_integrity(host=host)
    snapshot = build_diagnose(
        profiles=profiles,
        bundle=getattr(services, "bundle", None),
        health=getattr(services, "health", None),
        manifest_status=integrity.manifest_status,
        manifest_version=integrity.manifest_version,
        checksum_status=integrity.checksum_status,
        platform_name=platform.system(),
        architecture=platform.machine(),
        selector_outcomes=selector_outcomes,
        selector_outcomes_available=selector_outcomes is not None,
    )
    return snapshot


def _run_trace(args: argparse.Namespace, services: Any) -> object:
    views = getattr(services, "trace_views", None)
    if args.trace_command == "list":
        count = (
            len(views) if isinstance(views, Sequence) and not isinstance(views, (str, bytes)) else 0
        )
        return {"status": "ok", "count": count}
    view = getattr(services, "trace_view", None)
    if view is None and isinstance(views, dict):
        view = views.get(args.selector)
    if view is None:
        return _unavailable("trace_projection_unavailable")
    from .trace import handle_trace

    catalog = getattr(services, "locale_catalog", None)
    renderer = getattr(services, "card_renderer", None)
    if catalog is None or not callable(renderer):
        return _unavailable("trace_renderer_unavailable")
    try:
        rendered = handle_trace(view, catalog, card_renderer=renderer)
    except Exception:
        return _unavailable("trace_render_unavailable")
    if args.trace_command == "show":
        return rendered
    from .runtime import write_safe_export

    try:
        write_safe_export(args.destination, rendered, overwrite=args.overwrite)
    except Exception:
        return {"status": "rejected", "error_code": "unsafe_export_destination"}
    return {"status": "ok", "exported": True}


def _run_records(args: argparse.Namespace, services: Any) -> object:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    store = getattr(services, "delete_store", None)
    if args.records_command == "list":
        if store is None or not callable(getattr(store, "list_records", None)):
            return _unavailable("records_store_unavailable")
        try:
            handles = tuple(store.list_records())
            return {"status": "ok", "count": len(handles)}
        except Exception:
            return _unavailable("records_store_unavailable")
    if args.records_command == "delete":
        from ..application.delete_records import DeleteRequest
        from .records import handle_delete

        catalog = getattr(services, "locale_catalog", None)
        if store is None or catalog is None:
            return _unavailable("records_store_unavailable")
        try:
            request = DeleteRequest(
                public_short_id=args.public_short_id,
                all_records=bool(args.all_records),
                confirmation=args.confirm,
                include_quarantine=args.include_quarantine,
            )
            return handle_delete(
                request,
                store=store,
                catalog=catalog,
                locale=getattr(services, "locale", "en"),
            )
        except Exception:
            return _unavailable("records_delete_unavailable")
    plan = getattr(services, "prune_plan", None)
    catalog = getattr(services, "locale_catalog", None)
    if plan is None or catalog is None:
        return _unavailable("records_prune_unavailable")
    try:
        if not args.apply:
            from .records import handle_prune_plan

            return handle_prune_plan(
                plan, catalog=catalog, locale=getattr(services, "locale", "en")
            )
        from .records import handle_prune_apply

        store = getattr(services, "prune_store", None)
        journal = getattr(services, "prune_journal", None)
        if store is None or journal is None:
            return _unavailable("records_prune_unavailable")
        return handle_prune_apply(
            plan,
            store=store,
            journal=journal,
            catalog=catalog,
            locale=getattr(services, "locale", "en"),
        )
    except Exception:
        return _unavailable("records_prune_unavailable")


def main(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    argv: Sequence[str] | None = None,
    *,
    services: Any | None = None,
    stdin: Any | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Dispatch one closed production command."""

    args_list = _normalize_control(list(argv) if argv is not None else sys.argv[1:])
    if args_list and args_list[0] == "hook":
        raise CliCommandError("hook is owned by the hook entrypoint")
    args = _parser().parse_args(args_list)
    output_stream = stdout or sys.stdout

    if args.command == "version":
        if args.as_json:
            output_stream.write(
                json.dumps(
                    version_info(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            )
        else:
            output_stream.write(PRODUCT_VERSION + "\n")
        return 0

    host = getattr(args, "host", None)
    runtime = _services_for(services, host=host)
    result: object

    if args.command == "control":
        application = getattr(runtime, "control_application", None)
        if application is None:
            result = _unavailable("control_application_unavailable")
        else:
            from .control import run_control

            return run_control(stdin or sys.stdin, output_stream, application)
    if args.command == "diagnose":
        result = render_diagnose(_diagnose(runtime, args.host), output=args.output or "json")  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    elif args.command == "rigor":
        repository = getattr(runtime, "settings_store", None)
        if args.rigor_command == "get":
            result = handle_rigor_get(repository)
        elif args.rigor_command == "set":
            result = handle_rigor_set(repository, args.level, once=args.once)
        else:
            result = handle_rigor_reset(repository)
    elif args.command == "capabilities":
        profiles = getattr(runtime, "capability_profiles", {}) or {}
        profile = profiles.get(args.host) if isinstance(profiles, dict) else None
        result = (
            probe_capabilities(args.host, profile=profile)
            if args.capabilities_command == "probe"
            else show_capabilities(profile)
        )
    elif args.command == "metrics":
        store = getattr(runtime, "metrics_store", None)
        if args.metrics_command == "show":
            result = show_metrics(store)
        elif args.metrics_command == "export":
            result = export_metrics(store, args.destination, overwrite=args.overwrite)
        else:
            result = reset_metrics(store)
    elif args.command == "trace":
        result = _run_trace(args, runtime)
    elif args.command == "records":
        result = _run_records(args, runtime)
    else:  # pragma: no cover - argparse closes the command union
        result = _unavailable()

    _emit(result, output_stream)
    return 0


__all__ = ["CliCommandError", "main"]
