#!/usr/bin/env python3
"""Mutation checks for bounded packaged-README overclaim patterns."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from build_plugins import generate_plugin
from check_package_docs import (
    CONTENT_ONLY_HOSTS,
    NATIVE_HOSTS,
    NATIVE_TARGETS,
    _content_only_boundary_errors,
    _native_archive_boundary_errors,
    _platform_manifest_errors,
    _readme_errors,
    _semantic_overclaim_errors,
)

MUTATIONS = (
    (
        "native_readme_clean_machine_overclaim",
        "Local Windows validation proves clean-machine installation.",
    ),
    (
        "native_readme_automatic_hook_overclaim",
        "Automatic Codex CLI hook delivery is validated.",
    ),
    (
        "native_readme_public_release_overclaim",
        "This candidate is validated as a public release.",
    ),
    (
        "native_readme_signing_overclaim",
        "Package signing is verified.",
    ),
    (
        "claude_readme_universal_support_overclaim",
        "This plugin is fully validated on every Claude surface.",
    ),
    (
        "claude_readme_universal_support_overclaim",
        "The integration is supported across all Claude platforms.",
    ),
    (
        "claude_readme_universal_support_overclaim",
        "It is not shipped on Windows, but is fully validated on every Claude surface.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "The package is signed by Anthropic for production use.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "This is an Anthropic-approved integration.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "It is not signed by Apple, but it is endorsed by Anthropic.",
    ),
    (
        "claude_readme_endorsement_overclaim",
        "The release has been notarized for distribution.",
    ),
    (
        "claude_readme_managed_safety_overclaim",
        "The selector is safe on managed machines.",
    ),
    (
        "claude_readme_managed_safety_overclaim",
        "Managed policy hooks can never observe the selector prompt.",
    ),
    (
        "claude_readme_managed_safety_overclaim",
        "The sandbox guarantees complete isolation in enterprise environments.",
    ),
)

ACCURATE_LIMITATIONS = (
    "Local Windows validation does not prove clean-machine installation.",
    "Automatic Codex CLI hook delivery remains unverified.",
    "This candidate is not validated as a public release.",
    "Signing remains unvalidated.",
    "This package is not validated on all Claude surfaces.",
    "Signing and notarization are not claimed as validated.",
    "The selector is not isolated in organization-managed environments.",
    "Managed hooks can observe the selector prompt under managed policy.",
    "The package supports local Claude surfaces only where hooks are available.",
)

COMBINED_REVIEW_MUTATION = (
    "Fully validated on every Claude surface, signed by Anthropic, and safe on managed machines. "
    "Local Windows validation proves clean-machine installation. Automatic Codex CLI hook "
    "delivery is validated. This candidate is validated as a public release. Package signing "
    "is verified."
)


def _write_manifest(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _check_native_boundaries(  # noqa: C901  # Explicit bounded mutation matrix.
    root: Path, failures: list[str]
) -> tuple[int, int]:
    baselines = 0
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="opensocrates-package-boundaries-") as name:
        scratch = Path(name)
        for host in NATIVE_HOSTS:
            for target, contract in NATIVE_TARGETS.items():
                runtime_root = scratch / "runtime" / host
                runtime = runtime_root / target / "opensocrates-runtime"
                runtime.mkdir(parents=True)
                executable = runtime / (
                    "opensocrates-runtime.exe"
                    if target == "windows-x64"
                    else "opensocrates-runtime"
                )
                executable.write_bytes(b"synthetic package-boundary fixture\n")
                package = scratch / "packages" / f"{host}-{target}"
                generate_plugin(
                    root=root,
                    host=host,
                    output=package,
                    runtime_root=runtime_root,
                    target=target,
                )
                boundary_errors = _native_archive_boundary_errors(package, target)
                readme_errors = _readme_errors(package / "README.md", host, target)
                baselines += 1
                if boundary_errors:
                    failures.append(f"baseline:{host}-{target}-archive:{','.join(boundary_errors)}")
                if readme_errors:
                    failures.append(f"baseline:{host}-{target}-readme:{','.join(readme_errors)}")

                if host == "claude":
                    readme_path = package / "README.md"
                    readme = readme_path.read_text(encoding="utf-8")
                    wrong_target = str(contract["other_target"])
                    readme_path.write_text(
                        readme + f"\nContradiction: release gate on `{wrong_target}`.\n",
                        encoding="utf-8",
                    )
                    mutations += 1
                    if f"claude_readme_{target}_release_gate_target_invalid" not in _readme_errors(
                        readme_path, host, target
                    ):
                        failures.append(f"missed:{host}-{target}-readme-release-gate-target")
                    readme_path.write_text(readme, encoding="utf-8")

                original = json.loads((package / "release-manifest.json").read_text("utf-8"))
                other_target = str(contract["other_target"])
                metadata_mutations = (
                    ("missing-target", "native_release_targets_invalid", "release_targets", []),
                    (
                        "duplicate-target",
                        "native_release_targets_invalid",
                        "release_targets",
                        [target, target],
                    ),
                    (
                        "cross-target",
                        "native_release_targets_invalid",
                        "release_targets",
                        [other_target],
                    ),
                    (
                        "cross-runtime",
                        "native_runtime_targets_invalid",
                        "runtime_targets",
                        [other_target],
                    ),
                    ("missing-runtime", "native_runtime_targets_invalid", "runtime_targets", []),
                    (
                        "duplicate-runtime",
                        "native_runtime_targets_invalid",
                        "runtime_targets",
                        [target, target],
                    ),
                    ("missing-launcher", "native_launchers_invalid", "launchers", []),
                    (
                        "duplicate-launcher",
                        "native_launchers_invalid",
                        "launchers",
                        [contract["launcher"], contract["launcher"]],
                    ),
                    (
                        "cross-launcher-declaration",
                        "native_launchers_invalid",
                        "launchers",
                        [contract["other_launcher"]],
                    ),
                )
                for label, expected, field, value in metadata_mutations:
                    manifest = dict(original)
                    manifest[field] = value
                    _write_manifest(package / "release-manifest.json", manifest)
                    mutations += 1
                    if expected not in _native_archive_boundary_errors(package, target):
                        failures.append(f"missed:{host}-{target}-{label}")
                _write_manifest(package / "release-manifest.json", original)

                cross_runtime = scratch / "mutations" / f"{host}-{target}-cross-runtime-payload"
                shutil.copytree(package, cross_runtime)
                foreign_runtime = cross_runtime / "runtime" / other_target / "foreign"
                foreign_runtime.mkdir(parents=True)
                (foreign_runtime / "payload").write_bytes(b"foreign runtime\n")
                mutations += 1
                if "native_runtime_directories_invalid" not in _native_archive_boundary_errors(
                    cross_runtime, target
                ):
                    failures.append(f"missed:{host}-{target}-cross-runtime-payload")

                cross_launcher = scratch / "mutations" / f"{host}-{target}-cross-launcher"
                shutil.copytree(package, cross_launcher)
                foreign_launcher = cross_launcher / Path(str(contract["other_launcher"]))
                foreign_launcher.parent.mkdir(parents=True, exist_ok=True)
                foreign_launcher.write_text("foreign launcher\n", encoding="utf-8")
                mutations += 1
                if "native_launcher_files_invalid" not in _native_archive_boundary_errors(
                    cross_launcher, target
                ):
                    failures.append(f"missed:{host}-{target}-cross-launcher")

                helper = scratch / "mutations" / f"{host}-{target}-npm-helper"
                shutil.copytree(package, helper)
                (helper / "installer").mkdir()
                (helper / "installer" / "windows.ps1").write_text(
                    "synthetic helper\n", encoding="utf-8"
                )
                mutations += 1
                if (
                    "native_archive_contains_npm_windows_helper"
                    not in _native_archive_boundary_errors(helper, target)
                ):
                    failures.append(f"missed:{host}-{target}-npm-helper-confusion")
    return baselines, mutations


def _check_content_only_boundaries(  # noqa: C901  # Explicit bounded mutation matrix.
    root: Path, failures: list[str]
) -> tuple[int, int]:
    baselines = 0
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="opensocrates-content-only-boundaries-") as name:
        scratch = Path(name)
        for host in CONTENT_ONLY_HOSTS:
            source = root / "build" / "generated" / "plugins" / host
            if not source.is_dir():
                failures.append(f"missing:{host}-generated-package")
                continue
            baseline_errors = _content_only_boundary_errors(source)
            baselines += 1
            if baseline_errors:
                failures.append(f"baseline:{host}-content-only:{','.join(baseline_errors)}")

            declared = scratch / f"{host}-declared-target"
            shutil.copytree(source, declared)
            manifest = json.loads((declared / "release-manifest.json").read_text("utf-8"))
            manifest["release_targets"] = ["windows-x64"]
            _write_manifest(declared / "release-manifest.json", manifest)
            mutations += 1
            if "content_only_release_targets_invalid" not in _content_only_boundary_errors(
                declared
            ):
                failures.append(f"missed:{host}-content-only-declared-target")

            payload = scratch / f"{host}-runtime-payload"
            shutil.copytree(source, payload)
            runtime = payload / "runtime" / "windows-x64"
            runtime.mkdir(parents=True)
            (runtime / "foreign").write_bytes(b"foreign runtime\n")
            mutations += 1
            if "content_only_payload_present" not in _content_only_boundary_errors(payload):
                failures.append(f"missed:{host}-content-only-runtime-payload")

            hook_payload = scratch / f"{host}-hook-payload"
            shutil.copytree(source, hook_payload)
            hooks = hook_payload / "hooks"
            hooks.mkdir()
            (hooks / "hooks.json").write_text("{}\n", encoding="utf-8")
            mutations += 1
            if "content_only_payload_present" not in _content_only_boundary_errors(hook_payload):
                failures.append(f"missed:{host}-content-only-hook-payload")

            launcher_metadata = scratch / f"{host}-launcher-metadata"
            shutil.copytree(source, launcher_metadata)
            manifest = json.loads((launcher_metadata / "release-manifest.json").read_text("utf-8"))
            manifest["launchers"] = ["bin/launch.mjs"]
            _write_manifest(launcher_metadata / "release-manifest.json", manifest)
            mutations += 1
            if "content_only_launchers_invalid" not in _content_only_boundary_errors(
                launcher_metadata
            ):
                failures.append(f"missed:{host}-content-only-launcher-metadata")

            runtime_metadata = scratch / f"{host}-runtime-metadata"
            shutil.copytree(source, runtime_metadata)
            manifest = json.loads((runtime_metadata / "release-manifest.json").read_text("utf-8"))
            manifest["runtime_targets"] = ["windows-x64"]
            _write_manifest(runtime_metadata / "release-manifest.json", manifest)
            mutations += 1
            if "content_only_runtime_targets_invalid" not in _content_only_boundary_errors(
                runtime_metadata
            ):
                failures.append(f"missed:{host}-content-only-runtime-metadata")

            launcher_payload = scratch / f"{host}-launcher-payload"
            shutil.copytree(source, launcher_payload)
            launcher = launcher_payload / "bin" / "launch.mjs"
            launcher.parent.mkdir()
            launcher.write_text("synthetic launcher\n", encoding="utf-8")
            mutations += 1
            if "content_only_payload_present" not in _content_only_boundary_errors(
                launcher_payload
            ):
                failures.append(f"missed:{host}-content-only-launcher-payload")

            helper_payload = scratch / f"{host}-npm-helper"
            shutil.copytree(source, helper_payload)
            helper = helper_payload / "installer" / "windows.ps1"
            helper.parent.mkdir()
            helper.write_text("synthetic npm helper\n", encoding="utf-8")
            mutations += 1
            if "content_only_contains_npm_windows_helper" not in _content_only_boundary_errors(
                helper_payload
            ):
                failures.append(f"missed:{host}-content-only-npm-helper")
    return baselines, mutations


def main() -> int:  # noqa: C901  # One linear mutation matrix with bounded branches.
    root = Path(__file__).resolve().parent.parent
    readme = root / "build" / "generated" / "plugins" / "claude" / "README.md"
    try:
        baseline = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"package-doc-mutations: FAIL generated README unavailable: {type(exc).__name__}")
        return 1
    baseline_errors = _semantic_overclaim_errors(baseline)
    if baseline_errors:
        print(f"package-doc-mutations: FAIL baseline errors={','.join(baseline_errors)}")
        return 1
    failures: list[str] = []
    platform_mutations = 0
    platforms = json.loads((root / "packaging" / "platforms.json").read_text("utf-8"))
    for field, value, expected in (
        (
            "release_claim_status",
            "public_release_validated",
            "platform_manifest_release_claim_invalid",
        ),
        ("signing_status", "validated", "platform_manifest_signing_claim_invalid"),
    ):
        mutated_platforms = dict(platforms)
        mutated_platforms[field] = value
        platform_mutations += 1
        if expected not in _platform_manifest_errors(mutated_platforms):
            failures.append(f"missed:platform-{field}")
    for expected, mutation in MUTATIONS:
        errors = _semantic_overclaim_errors(f"{baseline}\n\n{mutation}\n")
        if expected not in errors:
            failures.append(f"missed:{expected}")
    combined_errors = set(_semantic_overclaim_errors(f"{baseline}\n\n{COMBINED_REVIEW_MUTATION}\n"))
    expected_combined = {expected for expected, _mutation in MUTATIONS}
    if combined_errors != expected_combined:
        failures.append("missed:combined-review-mutation")
    for limitation in ACCURATE_LIMITATIONS:
        errors = _semantic_overclaim_errors(f"{baseline}\n\n{limitation}\n")
        if errors:
            failures.append(f"false-positive:{','.join(errors)}")
    codex_readme = root / "build" / "generated" / "plugins" / "codex" / "README.md"
    try:
        codex_baseline = codex_readme.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        failures.append("missing:codex-generated-readme")
    else:
        if _readme_errors(codex_readme, "codex"):
            failures.append("baseline:codex-readme")
        mutated = codex_baseline.replace("one-time interactive hook approval", "hook approval", 1)
        temporary = root / "build" / "package-doc-codex-mutation.md"
        try:
            temporary.write_text(mutated, encoding="utf-8")
            if "codex_readme_hook_approval_missing" not in _readme_errors(
                temporary, "codex", "darwin-arm64"
            ):
                failures.append("missed:codex-hook-approval")
        finally:
            temporary.unlink(missing_ok=True)
    native_baselines, native_mutations = _check_native_boundaries(root, failures)
    content_baselines, content_mutations = _check_content_only_boundaries(root, failures)
    if failures:
        print("package-doc-mutations: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        "package-doc-mutations: PASS "
        f"overclaims={len(MUTATIONS)} limitations={len(ACCURATE_LIMITATIONS)} "
        f"native_boundaries={native_baselines} native_mutations={native_mutations} "
        f"platform_mutations={platform_mutations} "
        f"content_only_boundaries={content_baselines} "
        f"content_only_mutations={content_mutations}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
