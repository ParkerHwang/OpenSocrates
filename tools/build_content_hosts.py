#!/usr/bin/env python3
"""Build deterministic, non-executable account and modular-workspace content."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HOSTS = ("claude-chat", "antigravity")
LAYOUTS = {
    "claude-chat": ("opensocrates", "opensocrates/release-manifest.json"),
    "antigravity": (".agents/skills/opensocrates", "release-manifest.json"),
}


class ContentHostError(ValueError):
    """Unsafe source, destination or package content."""


def _json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _read(root: Path, relative: str) -> bytes:
    path = root / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ContentHostError(f"source is not an owned regular file: {relative}")
    return path.read_bytes()


def _render(root: Path, relative: str, values: dict[str, str]) -> bytes:
    text = _read(root, relative).decode("utf-8")

    def replace(match: re.Match[str]) -> str:
        if match[1] not in values:
            raise ContentHostError(f"unknown template token {match[1]} in {relative}")
        return values[match[1]]

    return (
        re.sub(r"\{\{([A-Z][A-Z0-9_]*)\}\}", replace, text).replace("\r\n", "\n").rstrip("\n")
        + "\n"
    ).encode()


def _canonical_sources(root: Path, host: str) -> tuple[dict[str, Any], Any, dict[str, str]]:
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.build_plugins import _common_values

    from opensocrates.content.injection import ProjectionInstructionAssembler
    from opensocrates.content.loader import load_compiled_bundle, load_reasoning_content_projections
    from opensocrates.rendering.response_policy import (
        load_response_policy,
        render_response_guidance,
    )

    bundle_path = root / "content/compiled-content.bundle.json"
    load_compiled_bundle(bundle_path)
    bundle = json.loads(_read(root, "content/compiled-content.bundle.json"))
    projections = load_reasoning_content_projections(
        root / "content/compiled-reasoning-content.bundle.json"
    )
    assembler = ProjectionInstructionAssembler(projections)
    if projections.content_revision != bundle[
        "content_revision"
    ] or assembler.known_method_ids() != frozenset(bundle["method_ids"]):
        raise ContentHostError("canonical projection identity mismatch")
    values = _common_values(bundle, host=host, template_revision="1")
    policy = load_response_policy(root / "content/response-policy.yaml")
    for locale in ("en", "ko"):
        values[f"RESPONSE_POLICY_{locale.upper()}"] = render_response_guidance(policy, locale)
    return bundle, assembler, values


def _files(root: Path, host: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    bundle, assembler, values = _canonical_sources(root, host)
    skill, manifest_path = LAYOUTS[host]
    metadata = json.loads(_read(root, f"plugin-src/{host}/generator.json"))
    if metadata != {
        "host": host,
        "template_revision": "1",
        "delivery": "account-skill" if host == "claude-chat" else "modular-workspace",
        "skill_root": skill,
        "manifest_path": manifest_path,
    }:
        raise ContentHostError("content-host metadata differs from the closed layout")
    files = {
        f"{skill}/SKILL.md": _render(root, "plugin-src/claude-chat/SKILL.md.tmpl", values),
        f"{skill}/README.md": _render(root, f"plugin-src/{host}/README.md.tmpl", values),
        f"{skill}/THIRD_PARTY_NOTICES.md": _render(
            root, "plugin-src/claude-chat/THIRD_PARTY_NOTICES.md.tmpl", values
        ),
        f"{skill}/LICENSE": _read(root, "LICENSE"),
        f"{skill}/references/decision/features.json": _read(
            root, "plugin-src/shared/decision/features.json"
        ),
    }
    for locale in ("en", "ko"):
        for target, source in (("reader", "shared/reader"), ("decision", "claude-chat")):
            files[f"{skill}/references/{target}/guide.{locale}.md"] = _read(
                root, f"plugin-src/{source}/guide.{locale}.md"
            )
    canonical = []
    for locale in ("en", "ko"):
        entries = []
        for method in bundle["methods"]:
            method_id = method["id"]
            instructions = assembler.assemble(
                (method_id,), requested_locale=locale
            ).instructions.encode("utf-8")
            relative = f"methods/{locale}/{method_id}.md"
            path = f"{skill}/references/decision/{relative}"
            files[path] = instructions
            digest = _hash(instructions)
            entries.append(
                {
                    "id": method_id,
                    "use_for": method["plain_action"][locale],
                    "routing": method["routing"],
                    "sha256": digest,
                    "path": relative,
                }
            )
            canonical.append(
                {"method_id": method_id, "locale": locale, "path": path, "sha256": digest}
            )
        files[f"{skill}/references/decision/catalog.{locale}.json"] = _json(
            {
                "content_revision": bundle["content_revision"],
                "locale": locale,
                "methods": entries,
                "evidence": "metadata_only",
            }
        )
    if host == "antigravity":
        rule = _render(root, "plugin-src/antigravity/rule.md.tmpl", values)
        if len(rule) > 4096 or not rule.startswith(b"---\ntrigger: always_on\n"):
            raise ContentHostError("Antigravity entry rule is invalid or oversized")
        files[".agents/rules/opensocrates.md"] = rule
    source_paths = [
        "tools/build_content_hosts.py",
        "plugin-src/claude-chat/SKILL.md.tmpl",
        "plugin-src/claude-chat/THIRD_PARTY_NOTICES.md.tmpl",
        f"plugin-src/{host}/generator.json",
        f"plugin-src/{host}/README.md.tmpl",
        "plugin-src/shared/decision/features.json",
        "plugin-src/shared/reader/guide.en.md",
        "plugin-src/shared/reader/guide.ko.md",
        "plugin-src/claude-chat/guide.en.md",
        "plugin-src/claude-chat/guide.ko.md",
    ]
    if host == "antigravity":
        source_paths.append("plugin-src/antigravity/rule.md.tmpl")
    sources = [{"path": path, "sha256": _hash(_read(root, path))} for path in sorted(source_paths)]
    manifest = {
        "schema": "opensocrates.content-host-manifest/1.0.0",
        "host": host,
        "product_version": bundle["product_version"],
        "content_revision": bundle["content_revision"],
        "source_tree_hash": bundle["source_tree_hash"],
        "normalized_semantic_hash": bundle["normalized_semantic_hash"],
        "source_identity": {
            "canonical": bundle["source_tree_hash"],
            "templates": _hash(_json(sources)),
        },
        "template_sources": sources,
        "template_revision": "1",
        "delivery": metadata["delivery"],
        "skill_root": skill,
        "method_count": 48,
        "method_ids": bundle["method_ids"],
        "public_skills": ["opensocrates"],
        "launchers": [],
        "runtime_targets": [],
        "canonical_methods": canonical,
        "capability_evidence": {
            "status": "unknown",
            "reason": "content generation is not live host delivery or application",
        },
        "files": [{"path": path, "sha256": _hash(value)} for path, value in sorted(files.items())],
    }
    files[manifest_path] = _json(manifest)
    return files, manifest


def _verify_metadata(manifest: dict[str, Any], host: str) -> None:
    if (
        manifest.get("schema") != "opensocrates.content-host-manifest/1.0.0"
        or manifest.get("host") != host
    ):
        raise ContentHostError("unowned content output")
    method_ids = manifest.get("method_ids")
    if (
        not isinstance(method_ids, list)
        or len(method_ids) != 48
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value)
            for value in method_ids
        )
        or len(set(method_ids)) != 48
    ):
        raise ContentHostError("invalid canonical method inventory")
    if (
        manifest.get("method_count") != 48
        or manifest.get("launchers") != []
        or manifest.get("runtime_targets") != []
        or manifest.get("public_skills") != ["opensocrates"]
        or manifest.get("skill_root") != LAYOUTS[host][0]
    ):
        raise ContentHostError("invalid content-only capabilities")
    identity = manifest.get("source_identity")
    if (
        not isinstance(identity, dict)
        or identity.get("canonical") != manifest.get("source_tree_hash")
        or not isinstance(manifest.get("product_version"), str)
        or type(manifest.get("content_revision")) is not int
        or manifest["content_revision"] < 1
        or any(
            not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value)
            for value in (
                manifest.get("source_tree_hash"),
                manifest.get("normalized_semantic_hash"),
                identity.get("templates"),
            )
        )
    ):
        raise ContentHostError("invalid content source identity")


def _verify_canonical_pairs(manifest: dict[str, Any], host: str) -> None:
    canonical = manifest.get("canonical_methods")
    if not isinstance(canonical, list) or len(canonical) != 96:
        raise ContentHostError("missing bilingual canonical identities")
    identities = set()
    hashes = {item["path"]: item["sha256"] for item in manifest["files"]}
    for item in canonical:
        if not isinstance(item, dict):
            raise ContentHostError("invalid canonical identity")
        pair = (item.get("method_id"), item.get("locale"))
        relative = f"{LAYOUTS[host][0]}/references/decision/methods/{pair[1]}/{pair[0]}.md"
        if (
            pair[0] not in manifest["method_ids"]
            or pair[1] not in ("en", "ko")
            or pair in identities
            or item.get("path") != relative
            or item.get("sha256") != hashes.get(relative)
        ):
            raise ContentHostError("canonical identity does not match inventory")
        identities.add(pair)


def _actual_members(root: Path) -> set[str]:
    actual = set()
    for member in root.rglob("*"):
        if member.is_symlink():
            raise ContentHostError("linked content member")
        if member.is_file():
            actual.add(member.relative_to(root).as_posix())
        elif not member.is_dir():
            raise ContentHostError("nonregular content member")
    return actual


def _expected_members(host: str, method_ids: list[str]) -> set[str]:
    skill, manifest_path = LAYOUTS[host]
    members = {
        manifest_path,
        *(
            f"{skill}/{name}"
            for name in ("SKILL.md", "README.md", "THIRD_PARTY_NOTICES.md", "LICENSE")
        ),
        f"{skill}/references/decision/features.json",
    }
    for locale in ("en", "ko"):
        members.add(f"{skill}/references/reader/guide.{locale}.md")
        members.add(f"{skill}/references/decision/guide.{locale}.md")
        members.add(f"{skill}/references/decision/catalog.{locale}.json")
        members.update(
            f"{skill}/references/decision/methods/{locale}/{method_id}.md"
            for method_id in method_ids
        )
    if host == "antigravity":
        members.add(".agents/rules/opensocrates.md")
    return members


def verify_content_host_package(path: Path | str, *, host: str) -> dict[str, Any]:
    """Validate exact inventoried regular files before replacing build output."""
    if host not in HOSTS:
        raise ContentHostError("unsupported content host")
    root = Path(path)
    manifest_path = LAYOUTS[host][1]
    manifest = json.loads(_read(root.resolve(), manifest_path))
    if not isinstance(manifest, dict):
        raise ContentHostError("invalid content manifest")
    _verify_metadata(manifest, host)
    inventory = manifest.get("files")
    if not isinstance(inventory, list) or not inventory:
        raise ContentHostError("missing content inventory")
    seen = {manifest_path}
    for item in inventory:
        relative = item.get("path") if isinstance(item, dict) else None
        if (
            not isinstance(relative, str)
            or relative in seen
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or "\\" in relative
        ):
            raise ContentHostError("unsafe or duplicate content member")
        seen.add(relative)
        member = root / relative
        if member.stat().st_mode & 0o111 or _hash(_read(root.resolve(), relative)) != item.get(
            "sha256"
        ):
            raise ContentHostError(f"modified or executable content member: {relative}")
    actual = _actual_members(root)
    if actual != seen or actual != _expected_members(host, manifest["method_ids"]):
        raise ContentHostError("unexpected or missing content member")
    if (root / manifest_path).stat().st_mode & 0o111:
        raise ContentHostError("executable manifest")
    if any(
        part in {"hooks", "runtime", "bin", "scripts"} or part == "hooks.json"
        for relative in actual
        for part in Path(relative).parts
    ):
        raise ContentHostError("executable surface in content package")
    _verify_canonical_pairs(manifest, host)
    return manifest


def _output_path(root: Path, host: str, output: Path | str | None) -> Path:
    raw = Path(output) if output is not None else Path("build/generated/content-hosts") / host
    raw = raw if raw.is_absolute() else root / raw
    if raw.is_symlink():
        raise ContentHostError("linked output")
    destination = raw.resolve()
    if root.is_relative_to(destination) or any(
        destination.is_relative_to(root / name)
        for name in ("src", "tools", "content", "plugin-src", "schemas", ".git", "docs")
    ):
        raise ContentHostError("output overlaps repository or source")
    return destination


def build_content_host(
    *, root: Path | str = ".", host: str, output: Path | str | None = None
) -> dict[str, Any]:
    """Build one closed content layout; never remove unowned or modified output."""
    if host not in HOSTS:
        raise ContentHostError("unsupported content host")
    repository = Path(root).resolve()
    destination = _output_path(repository, host, output)
    files, manifest = _files(repository, host)
    if destination.exists():
        verify_content_host_package(destination, host=host)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{host}-content-", dir=destination.parent))
    backup = staging.with_name(staging.name + "-previous")
    try:
        for relative, value in files.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
            target.chmod(0o644)
        verify_content_host_package(staging, host=host)
        if destination.exists():
            verify_content_host_package(destination, host=host)
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except OSError:
            if backup.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=HOSTS)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    options = parser.parse_args(argv)
    try:
        manifest = build_content_host(root=options.root, host=options.host, output=options.output)
    except (ContentHostError, OSError, ValueError) as error:
        print(f"content host: FAIL ({error})", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
