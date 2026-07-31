#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_RELATIVE_PATH = Path(".agents/plugins/marketplace.json")
MANAGER_RELATIVE_PATH = Path("tools/codex_plugin.py")
MANAGED_MARKER_NAME = ".opensocrates-managed.json"
MANAGED_SCHEMA_VERSION = 1


class LifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class PluginMetadata:
    root: Path
    marketplace_file: Path
    plugin_root: Path
    plugin_relative_path: Path
    marketplace_name: str
    plugin_name: str
    version: str
    plugin_id: str


@dataclass(frozen=True)
class MarketplaceLocation:
    kind: str
    root: Path | None


def fail(message: str) -> NoReturn:
    raise LifecycleError(message)


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing required file: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read valid JSON from {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"expected a JSON object in {path}")
    return payload


def non_empty_string(payload: dict[str, Any], key: str, path: Path) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} field {key!r} must be a non-empty string")
    return value.strip()


def validate_identifier(value: str, field: str, path: Path) -> None:
    if (
        value in {".", ".."}
        or not value.isascii()
        or not all(character.isalnum() or character in "-_." for character in value)
    ):
        fail(f"{path} field {field!r} is not a safe identifier")


def load_metadata(root: Path = ROOT) -> PluginMetadata:
    root = root.resolve()
    marketplace_file = root / MARKETPLACE_RELATIVE_PATH
    marketplace = read_json_object(marketplace_file)
    marketplace_name = non_empty_string(marketplace, "name", marketplace_file)
    validate_identifier(marketplace_name, "name", marketplace_file)
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        fail(f"{marketplace_file} must contain exactly one plugin entry")
    entry = plugins[0]
    plugin_name = non_empty_string(entry, "name", marketplace_file)
    validate_identifier(plugin_name, "plugins[0].name", marketplace_file)
    source = entry.get("source")
    if not isinstance(source, dict) or source.get("source") != "local":
        fail(f"{marketplace_file} plugin source must be local")
    source_path = source.get("path")
    if not isinstance(source_path, str) or not source_path.startswith("./"):
        fail(f"{marketplace_file} local source path must start with './'")
    plugin_relative_path = Path(source_path[2:])
    if not plugin_relative_path.parts or ".." in plugin_relative_path.parts:
        fail(f"{marketplace_file} local source path must stay within the marketplace root")
    plugin_root = (root / plugin_relative_path).resolve()
    try:
        plugin_root.relative_to(root)
    except ValueError:
        fail(f"{marketplace_file} local source path escapes the marketplace root")

    plugin_manifest_file = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = read_json_object(plugin_manifest_file)
    manifest_name = non_empty_string(manifest, "name", plugin_manifest_file)
    if manifest_name != plugin_name:
        fail(f"{plugin_manifest_file} names plugin {manifest_name!r}, expected {plugin_name!r}")
    version = non_empty_string(manifest, "version", plugin_manifest_file)

    return PluginMetadata(
        root=root,
        marketplace_file=marketplace_file,
        plugin_root=plugin_root,
        plugin_relative_path=plugin_relative_path,
        marketplace_name=marketplace_name,
        plugin_name=plugin_name,
        version=version,
        plugin_id=f"{plugin_name}@{marketplace_name}",
    )


class CodexCli:
    def __init__(self) -> None:
        requested = os.environ.get("CODEX_BIN", "codex")
        executable = shutil.which(requested)
        if executable is None:
            fail(f"Codex CLI executable {requested!r} was not found; install or update Codex first")
        self.executable = executable

    def run_json(self, *args: str) -> dict[str, Any]:
        command = [self.executable, *args]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic output"
            if "unrecognized subcommand" in detail or "unexpected argument '--json'" in detail:
                fail(
                    "this Codex version does not provide the required JSON plugin CLI; "
                    f"update Codex and retry ({detail})"
                )
            fail(f"Codex command failed: {' '.join(command)}\n{detail}")
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            fail(
                f"Codex returned invalid JSON for {' '.join(command)}: {exc}\n"
                f"{completed.stdout.strip()}"
            )
        if not isinstance(payload, dict):
            fail(f"Codex returned a non-object JSON value for {' '.join(command)}")
        return payload

    def marketplaces(self) -> list[dict[str, Any]]:
        payload = self.run_json("plugin", "marketplace", "list", "--json")
        entries = payload.get("marketplaces")
        if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
            fail("Codex marketplace list returned an unexpected schema")
        return entries


def canonical_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return canonical_path(configured) if configured else (Path.home() / ".codex").resolve()


def managed_marketplace_root(metadata: PluginMetadata) -> Path:
    return codex_home() / "managed-marketplaces" / metadata.marketplace_name


def marker_payload(metadata: PluginMetadata) -> dict[str, Any]:
    return {
        "schemaVersion": MANAGED_SCHEMA_VERSION,
        "marketplaceName": metadata.marketplace_name,
        "pluginName": metadata.plugin_name,
    }


def path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def marker_matches(root: Path, metadata: PluginMetadata) -> bool:
    if root.is_symlink() or not root.is_dir():
        return False
    try:
        marker = read_json_object(root / MANAGED_MARKER_NAME)
    except LifecycleError:
        return False
    return marker == marker_payload(metadata)


def require_managed_marker(root: Path, metadata: PluginMetadata) -> None:
    if not marker_matches(root, metadata):
        fail(
            f"managed marketplace path {root} is missing a valid ownership marker; "
            "refusing to overwrite or remove it"
        )


def validate_managed_slot(root: Path, metadata: PluginMetadata) -> None:
    if path_exists(root):
        require_managed_marker(root, metadata)


def legacy_metadata(root: Path, expected: PluginMetadata) -> PluginMetadata | None:
    try:
        candidate = load_metadata(root)
    except LifecycleError:
        return None
    if (
        candidate.marketplace_name != expected.marketplace_name
        or candidate.plugin_name != expected.plugin_name
    ):
        return None
    required_paths = (
        candidate.plugin_root / "core" / "charter.md",
        candidate.plugin_root / "hooks" / "hooks.json",
        candidate.plugin_root / "skills" / "auto" / "SKILL.md",
    )
    return candidate if all(path.is_file() for path in required_paths) else None


def classify_marketplace(
    entry: dict[str, Any] | None,
    metadata: PluginMetadata,
    managed_root: Path,
) -> MarketplaceLocation:
    if entry is None:
        return MarketplaceLocation("none", None)
    configured_root = marketplace_root(entry)
    if configured_root == managed_root:
        require_managed_marker(configured_root, metadata)
        return MarketplaceLocation("managed", configured_root)
    if legacy_metadata(configured_root, metadata) is not None:
        return MarketplaceLocation("legacy", configured_root)
    fail(
        f"marketplace {metadata.marketplace_name!r} is already configured at "
        f"{configured_root}, which is not a valid OpenSocrates source; "
        "refusing to overwrite or remove it"
    )


def write_managed_marker(root: Path, metadata: PluginMetadata) -> None:
    marker = json.dumps(marker_payload(metadata), indent=2, sort_keys=True) + "\n"
    (root / MANAGED_MARKER_NAME).write_text(marker, encoding="utf-8")


def copy_bundle_to_staging(source: PluginMetadata, staging_root: Path) -> PluginMetadata:
    marketplace_destination = staging_root / MARKETPLACE_RELATIVE_PATH
    marketplace_destination.parent.mkdir(parents=True)
    shutil.copy2(source.marketplace_file, marketplace_destination)

    plugin_destination = staging_root / source.plugin_relative_path
    plugin_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source.plugin_root, plugin_destination)

    manager_source = source.root / MANAGER_RELATIVE_PATH
    if not manager_source.is_file():
        fail(f"managed bundle source is missing {manager_source}")
    manager_destination = staging_root / MANAGER_RELATIVE_PATH
    manager_destination.parent.mkdir(parents=True)
    shutil.copy2(manager_source, manager_destination)
    write_managed_marker(staging_root, source)

    staged = load_metadata(staging_root)
    if (
        staged.marketplace_name != source.marketplace_name
        or staged.plugin_name != source.plugin_name
        or staged.version != source.version
    ):
        fail("staged managed marketplace does not match the source bundle")
    return staged


def remove_marked_tree(root: Path, metadata: PluginMetadata) -> None:
    require_managed_marker(root, metadata)
    try:
        shutil.rmtree(root)
    except OSError as exc:
        fail(f"failed to remove managed marketplace tree {root}: {exc}")


def materialize_managed_bundle(source: PluginMetadata) -> PluginMetadata:
    target = managed_marketplace_root(source)
    validate_managed_slot(target, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{source.marketplace_name}.staging-", dir=target.parent)
    )
    backup: Path | None = None
    try:
        copy_bundle_to_staging(source, staging)
        if path_exists(target):
            require_managed_marker(target, source)
            backup = target.parent / (f".{source.marketplace_name}.backup-{uuid.uuid4().hex}")
            os.replace(target, backup)
        os.replace(staging, target)
    except (OSError, LifecycleError) as exc:
        rollback_error: OSError | None = None
        if backup is not None and not path_exists(target) and path_exists(backup):
            try:
                os.replace(backup, target)
            except OSError as rollback_exc:
                rollback_error = rollback_exc
        if path_exists(staging):
            shutil.rmtree(staging, ignore_errors=True)
        detail = f"failed to replace managed marketplace {target}: {exc}"
        if rollback_error is not None:
            detail += f"; rollback also failed: {rollback_error}"
        fail(detail)
    if backup is not None:
        remove_marked_tree(backup, source)
    return load_metadata(target)


def named_marketplace(codex: CodexCli, metadata: PluginMetadata) -> dict[str, Any] | None:
    matches = [
        entry for entry in codex.marketplaces() if entry.get("name") == metadata.marketplace_name
    ]
    if len(matches) > 1:
        fail(f"Codex reported duplicate marketplaces named {metadata.marketplace_name!r}")
    return matches[0] if matches else None


def marketplace_root(entry: dict[str, Any]) -> Path:
    value = entry.get("root")
    if not isinstance(value, str) or not value.strip():
        fail(f"Codex marketplace entry has no usable root: {entry}")
    return canonical_path(value)


def add_marketplace(codex: CodexCli, metadata: PluginMetadata, root: Path) -> None:
    result = codex.run_json("plugin", "marketplace", "add", str(root), "--json")
    if result.get("marketplaceName") != metadata.marketplace_name:
        fail(f"Codex added an unexpected marketplace: {result.get('marketplaceName')!r}")
    entry = named_marketplace(codex, metadata)
    if entry is None:
        fail(f"Codex did not register marketplace {metadata.marketplace_name!r}")
    if marketplace_root(entry) != root.resolve():
        fail(f"Codex registered marketplace {metadata.marketplace_name!r} at the wrong root")


def remove_marketplace_registration(codex: CodexCli, metadata: PluginMetadata) -> None:
    result = codex.run_json("plugin", "marketplace", "remove", metadata.marketplace_name, "--json")
    if result.get("marketplaceName") != metadata.marketplace_name:
        fail("Codex removed an unexpected marketplace")


def switch_to_managed_marketplace(
    codex: CodexCli,
    metadata: PluginMetadata,
    location: MarketplaceLocation,
) -> None:
    managed_root = managed_marketplace_root(metadata)
    legacy_was_installed = False
    if location.kind == "legacy":
        state, _ = plugin_state(codex, metadata)
        legacy_was_installed = state == "installed"
        codex.run_json("plugin", "remove", metadata.plugin_id, "--json")
        remove_marketplace_registration(codex, metadata)
    try:
        add_marketplace(codex, metadata, managed_root)
    except LifecycleError as exc:
        if location.kind != "legacy" or location.root is None:
            raise
        rollback_errors: list[str] = []
        try:
            add_marketplace(codex, metadata, location.root)
            if legacy_was_installed:
                codex.run_json("plugin", "add", metadata.plugin_id, "--json")
        except LifecycleError as rollback_exc:
            rollback_errors.append(str(rollback_exc))
        detail = f"failed to migrate the legacy marketplace: {exc}"
        if rollback_errors:
            detail += f"; rollback also failed: {'; '.join(rollback_errors)}"
        fail(detail)
    entry = named_marketplace(codex, metadata)
    if entry is None or marketplace_root(entry) != managed_root:
        fail(f"Codex did not switch marketplace {metadata.marketplace_name!r} to managed storage")
    require_managed_marker(managed_root, metadata)


def plugin_state(codex: CodexCli, metadata: PluginMetadata) -> tuple[str, str | None]:
    payload = codex.run_json(
        "plugin",
        "list",
        "--marketplace",
        metadata.marketplace_name,
        "--available",
        "--json",
    )
    installed = payload.get("installed")
    available = payload.get("available")
    if not isinstance(installed, list) or not isinstance(available, list):
        fail("Codex plugin list returned an unexpected schema")

    installed_matches = [
        entry
        for entry in installed
        if isinstance(entry, dict) and entry.get("pluginId") == metadata.plugin_id
    ]
    available_matches = [
        entry
        for entry in available
        if isinstance(entry, dict) and entry.get("pluginId") == metadata.plugin_id
    ]
    if len(installed_matches) > 1 or len(available_matches) > 1:
        fail(f"Codex reported duplicate entries for plugin {metadata.plugin_id!r}")
    if installed_matches:
        version = installed_matches[0].get("version")
        return "installed", version if isinstance(version, str) else None
    if available_matches:
        version = available_matches[0].get("version")
        return "available", version if isinstance(version, str) else None
    return "missing", None


def verify_install(codex: CodexCli, metadata: PluginMetadata, result: dict[str, Any]) -> None:
    if result.get("pluginId") != metadata.plugin_id:
        fail(f"Codex installed an unexpected plugin: {result.get('pluginId')!r}")
    if result.get("version") != metadata.version:
        fail(f"Codex installed version {result.get('version')!r}, expected {metadata.version!r}")
    installed_path = result.get("installedPath")
    if not isinstance(installed_path, str) or not installed_path.strip():
        fail("Codex did not report an installed plugin path")
    cached_manifest = read_json_object(
        canonical_path(installed_path) / ".codex-plugin" / "plugin.json"
    )
    if cached_manifest.get("name") != metadata.plugin_name:
        fail("cached plugin manifest has the wrong plugin name")
    if cached_manifest.get("version") != metadata.version:
        fail("cached plugin manifest has the wrong plugin version")

    state, installed_version = plugin_state(codex, metadata)
    if state != "installed" or installed_version != metadata.version:
        fail(f"Codex verification reported state={state!r}, version={installed_version!r}")


def install_or_update(action: str) -> None:
    source = load_metadata()
    codex = CodexCli()
    managed_root = managed_marketplace_root(source)
    validate_managed_slot(managed_root, source)
    location = classify_marketplace(named_marketplace(codex, source), source, managed_root)
    metadata = materialize_managed_bundle(source)
    switch_to_managed_marketplace(codex, metadata, location)
    result = codex.run_json("plugin", "add", metadata.plugin_id, "--json")
    verify_install(codex, metadata, result)
    verb = "installed" if action == "install" else "updated"
    print(f"OpenSocrates {metadata.version} {verb} successfully.")
    print(f"Managed marketplace: {managed_root}")
    print("Start a new Codex task to load the updated skills and hooks.")


def show_status() -> None:
    metadata = load_metadata()
    codex = CodexCli()
    managed_root = managed_marketplace_root(metadata)
    validate_managed_slot(managed_root, metadata)
    entry = named_marketplace(codex, metadata)
    if entry is None:
        print(f"OpenSocrates is not installed. Source version: {metadata.version}.")
        return
    location = classify_marketplace(entry, metadata, managed_root)
    state, installed_version = plugin_state(codex, metadata)
    if state == "installed":
        if installed_version == metadata.version:
            print(f"OpenSocrates {installed_version} is installed and current.")
        else:
            print(
                f"OpenSocrates {installed_version or 'unknown'} is installed; "
                f"source version {metadata.version} is available."
            )
        if location.kind == "legacy":
            print("Run update to migrate this legacy installation into managed storage.")
        return
    if state == "available":
        print(
            f"OpenSocrates marketplace is registered, but the plugin is not installed. "
            f"Source version: {metadata.version}."
        )
        return
    fail(
        f"marketplace {metadata.marketplace_name!r} is registered but does not expose "
        f"plugin {metadata.plugin_name!r}"
    )


def remove() -> None:
    metadata = load_metadata()
    codex = CodexCli()
    managed_root = managed_marketplace_root(metadata)
    validate_managed_slot(managed_root, metadata)
    entry = named_marketplace(codex, metadata)
    classify_marketplace(entry, metadata, managed_root)

    codex.run_json("plugin", "remove", metadata.plugin_id, "--json")
    if entry is not None:
        remove_marketplace_registration(codex, metadata)
    if named_marketplace(codex, metadata) is not None:
        fail(f"marketplace {metadata.marketplace_name!r} is still registered after removal")
    if path_exists(managed_root):
        remove_marked_tree(managed_root, metadata)
    print("OpenSocrates was removed from Codex.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install, inspect, update, or remove the OpenSocrates Codex plugin."
    )
    parser.add_argument("action", choices=("install", "status", "update", "remove"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.action in {"install", "update"}:
            install_or_update(args.action)
        elif args.action == "status":
            show_status()
        else:
            remove()
    except LifecycleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
