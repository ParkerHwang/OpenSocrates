"""Deterministic, data-driven plugin package generator.

Host packages provide only templates and ``generator.json`` metadata.  The
core generator knows how to load the canonical compiled bundle, render bounded
tokens, copy fixed launch/runtime assets, and emit a release manifest.  Adding
another host therefore does not require another host branch in this module.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

_SEMANTIC_FIELDS = (
    "content_revision",
    "method_ids",
    "methods",
    "locale_messages",
    "prompt_fragments",
    "policy_versions",
)
_TOKEN_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
_SAFE_RELATIVE_RE = re.compile(r"^[^/][^:]*$")


class PluginBuildError(ValueError):
    """Raised when a host template or compiled bundle is unsafe/incomplete."""


def semantic_projection(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Return the host-neutral bundle fields used for semantic identity."""

    if not isinstance(bundle, Mapping):
        raise PluginBuildError("semantic projection requires a bundle mapping")
    missing = [key for key in _SEMANTIC_FIELDS if key not in bundle]
    if missing:
        raise PluginBuildError(f"compiled bundle is missing semantic fields: {', '.join(missing)}")
    return {key: bundle[key] for key in _SEMANTIC_FIELDS}


def semantic_projection_hash(bundle: Mapping[str, Any]) -> str:
    """Compute the canonical runtime semantic hash without a hardcoded value."""

    try:
        from opensocrates.content.hashes import normalized_semantic_hash
    except ImportError as exc:
        raise PluginBuildError("opensocrates content hash API is unavailable") from exc
    return normalized_semantic_hash(semantic_projection(bundle))


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _ensure_relative(value: str, *, field: str) -> Path:
    if not isinstance(value, str) or not value or not _SAFE_RELATIVE_RE.fullmatch(value):
        raise PluginBuildError(f"{field} must be a relative package path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise PluginBuildError(f"{field} must not escape its root")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PluginBuildError(f"cannot read JSON metadata: {path}") from exc
    if not isinstance(value, dict):
        raise PluginBuildError(f"generator metadata must be an object: {path}")
    return value


def discover_hosts(source_root: str | Path = "plugin-src") -> tuple[str, ...]:
    """Discover hosts solely from source metadata directories."""

    root = Path(source_root)
    if not root.exists():
        return ()
    return tuple(
        sorted(path.parent.name for path in root.glob("*/generator.json") if path.is_file())
    )


def _load_builder(spec: str) -> Any:
    if not isinstance(spec, str) or ":" not in spec:
        raise PluginBuildError("builder must use module:attribute notation")
    module_name, attribute = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        value = getattr(module, attribute)
    except (ImportError, AttributeError) as exc:
        raise PluginBuildError(f"cannot load builder {spec}") from exc
    if not callable(value):
        raise PluginBuildError(f"builder is not callable: {spec}")
    return value


def _render(template: str, values: Mapping[str, str], *, source: str) -> str:
    unknown: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            unknown.add(key)
            return match.group(0)
        return values[key]

    rendered = _TOKEN_RE.sub(replace, template)
    if unknown:
        raise PluginBuildError(f"unknown template tokens in {source}: {', '.join(sorted(unknown))}")
    if _TOKEN_RE.search(rendered):
        raise PluginBuildError(f"unresolved template token in {source}")
    return rendered.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def _json_token(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _method_values(method: Mapping[str, Any], common: Mapping[str, str]) -> dict[str, str]:
    def nested(key: str, locale: str) -> str:
        value = method.get(key, {})
        return value.get(locale, "") if isinstance(value, Mapping) else ""

    values = dict(common)
    values.update(
        {
            "METHOD_ID": str(method.get("id", "")),
            "METHOD_FAMILY": str(method.get("family", "")),
            "METHOD_DISPLAY_NAME_EN": nested("display_name", "en"),
            "METHOD_DISPLAY_NAME_KO": nested("display_name", "ko"),
            "METHOD_PLAIN_ACTION_EN": nested("plain_action", "en"),
            "METHOD_PLAIN_ACTION_KO": nested("plain_action", "ko"),
            "METHOD_PROCEDURE_EN": nested("procedure", "en"),
            "METHOD_PROCEDURE_KO": nested("procedure", "ko"),
            "METHOD_COMPLEMENT_EN": nested("complement_fragment", "en"),
            "METHOD_COMPLEMENT_KO": nested("complement_fragment", "ko"),
            "METHOD_PARTICIPATION_JSON": _json_token(method.get("participation", {})),
            "METHOD_ROUTING_JSON": _json_token(method.get("routing", {})),
            "METHOD_OUTPUT_CONTRACT_JSON": _json_token(method.get("output_contract", {})),
            "METHOD_COMPLEMENTS_JSON": _json_token(method.get("complements", {})),
        }
    )
    return values


def _method_reference_index(methods: list[Any]) -> str:
    """Render a compact, non-discoverable catalog for the single Claude skill."""

    sections: list[str] = []
    for raw in methods:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), str):
            raise PluginBuildError("compiled method has no valid id")
        method_id = raw["id"]
        display = raw.get("display_name", {})
        plain_action = raw.get("plain_action", {})
        display_en = display.get("en", method_id) if isinstance(display, Mapping) else method_id
        display_ko = display.get("ko", "") if isinstance(display, Mapping) else ""
        action_en = plain_action.get("en", "") if isinstance(plain_action, Mapping) else ""
        action_ko = plain_action.get("ko", "") if isinstance(plain_action, Mapping) else ""
        sections.extend(
            [
                f"## `{method_id}` — {display_en}",
                "",
                f"- Korean name: {display_ko}",
                f"- Family: `{raw.get('family', '')}`",
                f"- Use for: {action_en}",
                f"- 한국어: {action_ko}",
                f"- Routing metadata: `{_json_token(raw.get('routing', {}))}`",
                f"- Procedure: [methods/{method_id}.md](methods/{method_id}.md)",
                "",
            ]
        )
    return "\n".join(sections).rstrip()


def _common_values(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    bundle: Mapping[str, Any], *, host: str, template_revision: str
) -> dict[str, str]:
    semantic_projection_hash = semantic_projection_hash_for_bundle(bundle)
    expected = bundle.get("normalized_semantic_hash")
    if expected != semantic_projection_hash:
        raise PluginBuildError(
            "compiled bundle semantic hash does not match its semantic projection"
        )
    methods = bundle.get("methods")
    method_ids = bundle.get("method_ids")
    if (
        not isinstance(methods, list)
        or not isinstance(method_ids, list)
        or len(methods) != 48
        or len(method_ids) != 48
    ):
        raise PluginBuildError("compiled bundle must contain exactly 48 methods")
    messages = bundle.get("locale_messages", {})
    fragments = bundle.get("prompt_fragments", {})
    policies = bundle.get("policy_versions", {})
    values = {
        "HOST": host,
        "PRODUCT_VERSION": str(bundle.get("product_version", "")),
        "CONTENT_REVISION": str(bundle.get("content_revision", "")),
        "SOURCE_TREE_HASH": str(bundle.get("source_tree_hash", "")),
        "SEMANTIC_HASH": str(expected),
        "SEMANTIC_PROJECTION_HASH": semantic_projection_hash,
        "METHOD_COUNT": str(len(methods)),
        "METHOD_IDS_JSON": _json_token(method_ids),
        "METHODS_JSON": _json_token(methods),
        "METHOD_REFERENCE_INDEX": _method_reference_index(methods),
        "LOCALE_MESSAGES_JSON": _json_token(messages),
        "PROMPT_FRAGMENTS_JSON": _json_token(fragments),
        "POLICY_VERSIONS_JSON": _json_token(policies),
        "TEMPLATE_REVISION": template_revision,
    }
    if isinstance(fragments, Mapping):
        controller = fragments.get("controller", {})
        capability_notice = fragments.get("capability_notice", {})
        if isinstance(controller, Mapping):
            values["CONTROLLER_EN"] = str(controller.get("en", ""))
            values["CONTROLLER_KO"] = str(controller.get("ko", ""))
        if isinstance(capability_notice, Mapping):
            values["CAPABILITY_NOTICE_EN"] = str(capability_notice.get("en", ""))
            values["CAPABILITY_NOTICE_KO"] = str(capability_notice.get("ko", ""))
        for key, locale_values in fragments.items():
            if isinstance(locale_values, Mapping):
                for locale in ("en", "ko"):
                    token = f"FRAGMENT_{str(key).upper()}_{locale.upper()}"
                    values[token] = str(locale_values.get(locale, ""))
    if isinstance(messages, Mapping):
        for locale in ("en", "ko"):
            locale_values = messages.get(locale, {})
            values[f"LOCALE_MESSAGES_{locale.upper()}_JSON"] = _json_token(locale_values)
    return values


def semantic_projection_hash_for_bundle(bundle: Mapping[str, Any]) -> str:
    """Compatibility alias with an explicit bundle-oriented name."""

    return semantic_projection_hash(bundle)


def _copy_path(source: Path, destination: Path) -> None:
    def copy_file(source_file: Path, destination_file: Path) -> None:
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        destination_file.write_bytes(source_file.read_bytes())
        shutil.copymode(source_file, destination_file)

    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(
            source.rglob("*"), key=lambda item: item.relative_to(source).as_posix().encode("utf-8")
        ):
            relative = child.relative_to(source)
            target = destination / relative
            if child.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif child.is_file():
                copy_file(child, target)
    elif source.is_file():
        copy_file(source, destination)
    else:
        raise PluginBuildError(f"copy source is missing: {source}")


def _safe_remove_output(output: Path, root: Path) -> None:
    resolved_output = output.resolve()
    resolved_root = root.resolve()
    if resolved_output == resolved_root or resolved_output == Path("/"):
        raise PluginBuildError("refusing to remove the repository root")
    if output.exists():
        if output.is_dir():
            shutil.rmtree(output)
        else:
            output.unlink()


def _runtime_targets(output: Path, runtime_output: Path) -> list[str]:
    if not runtime_output.exists():
        return []
    return sorted(
        child.name
        for child in runtime_output.iterdir()
        if child.is_dir() and any(path.is_file() for path in child.rglob("*"))
    )


def generate_plugin(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    *,
    root: str | Path = ".",
    host: str,
    output: str | Path | None = None,
    source_root: str | Path = "plugin-src",
    bundle_path: str | Path = "content/compiled-content.bundle.json",
    runtime_root: str | Path = "dist/runtime",
) -> dict[str, Any]:
    """Generate one host package and return its deterministic release manifest."""

    repository = Path(root).resolve()
    _prepare_import_path(repository)
    source_base = Path(source_root)
    if not source_base.is_absolute():
        source_base = repository / source_base
    host_source = source_base / host
    metadata_path = host_source / "generator.json"
    metadata = _read_json(metadata_path)
    if metadata.get("host") != host:
        raise PluginBuildError("generator metadata host does not match requested host")
    template_revision = str(metadata.get("template_revision", "1"))
    bundle_file = Path(bundle_path)
    if not bundle_file.is_absolute():
        bundle_file = repository / bundle_file
    try:
        raw_bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PluginBuildError("compiled content bundle is not readable JSON") from exc
    if not isinstance(raw_bundle, dict):
        raise PluginBuildError("compiled content bundle must be an object")
    try:
        from opensocrates.content.loader import load_compiled_bundle

        load_compiled_bundle(bundle_file)
    except ImportError as exc:
        raise PluginBuildError("opensocrates content loader is unavailable") from exc
    except Exception as exc:
        raise PluginBuildError(
            "compiled content bundle failed canonical/domain validation"
        ) from exc
    values = _common_values(raw_bundle, host=host, template_revision=template_revision)
    output_path = Path(output) if output is not None else Path("build/generated/plugins") / host
    if not output_path.is_absolute():
        output_path = repository / output_path
    _safe_remove_output(output_path, repository)
    output_path.mkdir(parents=True, exist_ok=True)

    def template_text(relative: str) -> str:
        source = host_source / _ensure_relative(relative, field="template")
        try:
            return source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PluginBuildError(f"cannot read template: {source}") from exc

    hooks_builder = metadata.get("hooks_builder")
    if isinstance(hooks_builder, str):
        values["HOOKS_JSON"] = _json_token(_load_builder(hooks_builder)())
    else:
        values["HOOKS_JSON"] = "{}"

    def render_to(template: str, destination: str, local_values: Mapping[str, str]) -> None:
        destination_path = output_path / _ensure_relative(destination, field="output")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            _render(template_text(template), local_values, source=template), encoding="utf-8"
        )

    manifest_template = metadata.get("manifest_template")
    manifest_output = metadata.get("manifest_output")
    if isinstance(manifest_template, str) and isinstance(manifest_output, str):
        render_to(manifest_template, manifest_output, values)
    else:
        raise PluginBuildError("manifest_template and manifest_output are required")
    hooks_template = metadata.get("hooks_template")
    hooks_output = metadata.get("hooks_output")
    if hooks_template is not None or hooks_output is not None:
        if not isinstance(hooks_template, str) or not isinstance(hooks_output, str):
            raise PluginBuildError("hooks_template and hooks_output must be provided together")
        render_to(hooks_template, hooks_output, values)

    for item in metadata.get("shared_templates", []):
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("template"), str)
            or not isinstance(item.get("output"), str)
        ):
            raise PluginBuildError("shared_templates entries require template/output")
        render_to(item["template"], item["output"], values)

    method_template = metadata.get("method_template")
    method_output = metadata.get("method_output")
    methods = raw_bundle.get("methods", [])
    if not isinstance(method_template, str) or not isinstance(method_output, str):
        raise PluginBuildError("method_template and method_output are required")
    for method in methods:
        if not isinstance(method, Mapping) or not isinstance(method.get("id"), str):
            raise PluginBuildError("compiled method has no valid id")
        method_values = _method_values(method, values)
        destination = method_output.replace("{method_id}", str(method["id"]))
        render_to(method_template, destination, method_values)

    for item in metadata.get("command_templates", []):
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("template"), str)
            or not isinstance(item.get("output"), str)
        ):
            raise PluginBuildError("command_templates entries require template/output")
        render_to(item["template"], item["output"], values)

    for item in metadata.get("copy_files", []):
        if (
            not isinstance(item, Mapping)
            or not isinstance(item.get("source"), str)
            or not isinstance(item.get("output"), str)
        ):
            raise PluginBuildError("copy_files entries require source/output")
        source = repository / _ensure_relative(item["source"], field="copy source")
        destination = output_path / _ensure_relative(item["output"], field="copy output")
        _copy_path(source, destination)

    bundle_destination = output_path / _ensure_relative(
        str(metadata.get("bundle_output", "content/compiled-content.bundle.json")),
        field="bundle_output",
    )
    bundle_destination.parent.mkdir(parents=True, exist_ok=True)
    bundle_destination.write_bytes(_canonical_json(raw_bundle))

    runtime_root_path = Path(runtime_root)
    if not runtime_root_path.is_absolute():
        runtime_root_path = repository / runtime_root_path
    runtime_output_name = metadata.get("runtime_output", "runtime")
    runtime_output = output_path / _ensure_relative(
        str(runtime_output_name), field="runtime_output"
    )
    if runtime_root_path.exists():
        _copy_path(runtime_root_path, runtime_output)
        # S09's onedir runtime carries a content copy for standalone launch.
        # Replace that generated copy with the exact canonical bundle selected
        # for this package so every runtime content surface has one identity.
        for embedded_bundle in runtime_output.rglob("compiled-content.bundle.json"):
            if embedded_bundle.is_file() and embedded_bundle.parent.name == "content":
                embedded_bundle.write_bytes(_canonical_json(raw_bundle))

    files: list[dict[str, str]] = []
    for path in sorted(
        (candidate for candidate in output_path.rglob("*") if candidate.is_file()),
        key=lambda item: item.relative_to(output_path).as_posix().encode("utf-8"),
    ):
        relative = path.relative_to(output_path).as_posix()
        files.append({"path": relative, "sha256": _sha256(path.read_bytes())})
    runtime_targets = _runtime_targets(output_path, runtime_output)
    release = {
        "schema": "opensocrates.plugin-release-manifest/1.0.0",
        "host": host,
        "launcher_host": metadata.get("launcher_host", host),
        "release_targets": metadata.get("release_targets", []),
        "launchers": metadata.get("launchers", []),
        "product_version": raw_bundle.get("product_version"),
        "content_revision": raw_bundle.get("content_revision"),
        "source_tree_hash": raw_bundle.get("source_tree_hash"),
        "normalized_semantic_hash": raw_bundle.get("normalized_semantic_hash"),
        "semantic_projection_hash": values["SEMANTIC_PROJECTION_HASH"],
        "semantic_projection_fields": list(_SEMANTIC_FIELDS),
        "template_revision": template_revision,
        "method_count": len(methods),
        "method_ids": raw_bundle.get("method_ids"),
        "runtime_targets": runtime_targets,
        "capability_evidence": {
            "status": "unknown",
            "reason": "package generation has no live exact host probe",
        },
        "files": files,
    }
    (output_path / "release-manifest.json").write_bytes(_canonical_json(release))
    return release


def _prepare_import_path(root: Path) -> None:
    source = root / "src"
    if source.is_dir() and str(source) not in sys.path:
        sys.path.insert(0, str(source))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--host", default="codex")
    parser.add_argument("--source-root", default="plugin-src")
    parser.add_argument("--bundle", default="content/compiled-content.bundle.json")
    parser.add_argument("--runtime-root", default="dist/runtime")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    _prepare_import_path(root)
    try:
        release = generate_plugin(
            root=root,
            host=args.host,
            output=args.output,
            source_root=args.source_root,
            bundle_path=args.bundle,
            runtime_root=args.runtime_root,
        )
    except PluginBuildError as exc:
        parser.error(str(exc))
    print(json.dumps(release, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
