#!/usr/bin/env python3
"""Assemble the additional macOS profiles without widening Codex's legacy gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from build_content_hosts import build_content_host, verify_content_host_package
from build_plugins import generate_plugin
from release_check import _write_deterministic_zip, _write_package_checksums, _write_root_checksums


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_entry(package: Path) -> dict[str, float]:
    hooks = json.loads((package / "hooks/hooks.json").read_text())["hooks"]
    timings = {}
    for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
        hook = hooks[event][0]["hooks"][0]
        if hook["command"] != "${CLAUDE_PLUGIN_ROOT}/bin/launch.sh":
            raise ValueError("native_launcher_contract_mismatch")
        start = time.monotonic()
        payload = {"hook_event_name": event, "prompt": "PRIVATE_SENTINEL"}
        if event == "SessionStart":
            payload["source"] = "startup"
        result = subprocess.run(
            [str(package / "bin/launch.sh"), *hook["args"]],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=hook["timeout"],
            cwd=package,
        )
        timings[event] = round((time.monotonic() - start) * 1000, 2)
        if result.returncode or result.stderr or "PRIVATE_SENTINEL" in result.stdout:
            raise ValueError("native_entry_privacy_or_dispatch_failed")
        if event in {"Stop", "SessionEnd"}:
            if result.stdout:
                raise ValueError("native_noop_failed")
            continue
        output = json.loads(result.stdout)["hookSpecificOutput"]
        if output["hookEventName"] != event:
            raise ValueError("native_event_envelope_mismatch")
        context = output["additionalContext"]
        if (
            "Installed Claude controller" not in context
            or "This entry selects no method" not in context
        ):
            raise ValueError("native_entry_contract_missing")
    return timings


def merge_inventory(root: Path, version: str, artifacts: dict[str, str]) -> None:
    dist = root / "dist"
    for name in ("opensocrates.mjs", "managed-hosts.mjs"):
        shutil.copyfile(root / "installer" / name, dist / name)
    manifest_path = dist / f"opensocrates-{version}-release-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    profiles = {}
    for host in ("claude", "claude-chat", "antigravity"):
        package = dist / host
        identity_path = package / (
            "opensocrates/release-manifest.json"
            if host == "claude-chat"
            else "release-manifest.json"
        )
        identity = json.loads(identity_path.read_text())
        kind = "skills" if host == "claude-chat" else "plugin"
        archive = f"opensocrates-{version}-{host}-{kind}.zip"
        profiles[host] = {
            "archive": archive,
            "archive_sha256": artifacts[archive],
            "package_manifest": identity_path.relative_to(dist).as_posix(),
            "package_manifest_sha256": "sha256:" + digest(identity_path),
            "source_identity": identity["source_identity"]
            if "source_identity" in identity
            else {"source_tree_hash": identity["source_tree_hash"]},
            "runtime_targets": identity.get("runtime_targets", []),
            "application": "unverified",
        }
    manifest["additional_profiles"] = profiles
    manifest["installer_dependencies"] = {
        name: "sha256:" + digest(dist / name) for name in ("opensocrates.mjs", "managed-hosts.mjs")
    }
    arguments = [
        sys.executable,
        "tools/build_sbom.py",
        "--root",
        str(root),
        "--output",
        "build/evidence/sbom.spdx.json",
        "--report",
        "build/evidence/sbom.json",
    ]
    for artifact in (
        "content/compiled-content.bundle.json",
        "content/compiled-reasoning-content.bundle.json",
        "dist/runtime/codex/darwin-arm64/opensocrates-runtime/opensocrates-runtime",
        "dist/claude/runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime",
        f"dist/opensocrates-{version}-codex-plugin.zip",
        "dist/opensocrates.mjs",
        "dist/managed-hosts.mjs",
        *("dist/" + name for name in artifacts),
    ):
        arguments.extend(["--artifact", artifact])
    completed = subprocess.run(arguments, cwd=root, capture_output=True, timeout=300)
    if completed.returncode:
        raise ValueError("combined_sbom_generation_failed")
    destination = dist / f"opensocrates-{version}-sbom.spdx.json"
    shutil.copyfile(root / "build/evidence/sbom.spdx.json", destination)
    manifest["sbom"] = {"path": destination.name, "sha256": "sha256:" + digest(destination)}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    limitations_path = dist / f"opensocrates-{version}-limitations.json"
    limitations = json.loads(limitations_path.read_text())
    limitations["additional_profiles"] = {
        host: {
            "application": "unverified",
            "live_delivery": "separate bounded qualification",
            "new_windows_delivery": "not implemented",
        }
        for host in profiles
    }
    limitations_path.write_text(json.dumps(limitations, indent=2, sort_keys=True) + "\n")
    _write_root_checksums(dist, version)


def assemble(root: Path) -> dict[str, Any]:
    version = (root / "VERSION").read_text().strip()
    runtime_source = root / "dist/runtime/codex/darwin-arm64"
    if not (runtime_source / "opensocrates-runtime/opensocrates-runtime").is_file():
        raise ValueError("run the Codex macOS native release gate first")
    destination = root / "dist/runtime/claude/darwin-arm64"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(runtime_source, destination)
    native = root / "dist/claude"
    manifest = generate_plugin(root=root, host="claude", output=native)
    if manifest["runtime_targets"] != ["darwin-arm64"] or manifest["method_count"] != 48:
        raise ValueError("invalid native Claude closure")
    _write_package_checksums(native)
    timings = check_entry(native)

    artifacts: dict[str, str] = {}
    archives: list[tuple[str, Path, str]] = [("claude", native, "plugin")]
    for host in ("claude-chat", "antigravity"):
        package = root / "dist" / host
        build_content_host(root=root, host=host, output=package)
        verify_content_host_package(package, host=host)
        archives.append((host, package, "skills" if host == "claude-chat" else "plugin"))
    for host, package, kind in archives:
        archive = root / "dist" / f"opensocrates-{version}-{host}-{kind}.zip"
        _write_deterministic_zip(package, archive, content_only=host != "claude")
        hashed = digest(archive)
        archive.with_name(archive.name + ".sha256").write_text(f"{hashed}  {archive.name}\n")
        artifacts[archive.name] = "sha256:" + hashed
    merge_inventory(root, version, artifacts)
    return {
        "schema": "opensocrates.macos-host-assembly/1.0.0",
        "status": "pass",
        "product_version": version,
        "native_profile": "claude",
        "native_target": "darwin-arm64",
        "shared_runtime_source": "codex",
        "content_profiles": ["claude-chat", "antigravity"],
        "canonical_method_count": 48,
        "locale_procedure_count": 96,
        "native_entry": "emitted",
        "generated_hook_elapsed_ms": timings,
        "generated_hook_timeouts": "actual 3s entry / 1s no-op budgets",
        "combined_inventory": "additional profiles, dependency assets, SBOM and checksums",
        "application": "unverified",
        "live_host_delivery": "separate qualification",
        "windows_optimization": "next stage",
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", default="build/evidence/macos-host-assembly.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        report = assemble(root)
    except Exception as exc:
        report = {
            "status": "fail",
            "error_type": type(exc).__name__,
            "reason": "macos_profile_assembly_failed",
        }
    path = root / args.report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
