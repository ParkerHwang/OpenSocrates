#!/usr/bin/env python3
"""Check portable-lab packaging and hostile content archives, offline by default."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

_CHECKS = 0
_SENTINEL = b"PRIVATE-STUDY-CACHE-MUST-NOT-BE-PACKAGED"


def _require(condition: bool, message: str) -> None:
    global _CHECKS
    if not condition:
        raise AssertionError(message)
    _CHECKS += 1


def _reject(action: Callable[[], Any], message: str) -> None:
    try:
        action()
    except (ValueError, OSError, zipfile.BadZipFile):
        _require(True, message)
    else:
        raise AssertionError(message)


def _zip(entries: list[tuple[str, bytes, int]]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw, mode in entries:
            item = zipfile.ZipInfo(name)
            # Preserve hostile wire names even when Windows ZipInfo normalizes them.
            item.filename = name
            item.orig_filename = name
            item.create_system = 3
            item.external_attr = mode << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, raw)
    return stream.getvalue()


def _fixtures(folder: Path, hosts: Any) -> dict[str, tuple[str, str]]:
    """Test-only identities: these bytes are never called published payloads."""
    folder.mkdir()
    entries = {
        "claude_cowork": [
            (
                "opensocrates/SKILL.md",
                "# Synthetic account skill\n한국어\n".encode(),
                stat.S_IFREG | 0o644,
            ),
            (
                "opensocrates/references/method.md",
                b"Public synthetic reference\n",
                stat.S_IFREG | 0o644,
            ),
        ],
        "antigravity": [
            (
                "release-manifest.json",
                b'{"schema":"opensocrates.content-host-manifest/1.0.0","host":"antigravity","product_version":"1.5.3","source_tree_hash":"sha256:a4d9f4b70f653dee12a3ea758ef10dc391443a19536c7e7f22082962fd252e0f"}\n',
                stat.S_IFREG | 0o644,
            ),
            (
                ".agents/rules/opensocrates.md",
                b"---\ntrigger: always_on\n---\nSynthetic rule\n",
                stat.S_IFREG | 0o644,
            ),
            (
                ".agents/skills/opensocrates/SKILL.md",
                b"Synthetic workspace skill\n",
                stat.S_IFREG | 0o644,
            ),
        ],
    }
    identities = {}
    for host, members in entries.items():
        name = hosts.PAYLOADS[host][0]
        raw = _zip(members)
        (folder / name).write_bytes(raw)
        identities[host] = (name, hashlib.sha256(raw).hexdigest())
    (folder / "manifest.json").write_text(
        json.dumps({"test_fixture_only": True, "not_a_published_release": True}), encoding="utf-8"
    )
    return identities


def _check_pinning(folder: Path, hosts: Any, identities: dict[str, tuple[str, str]]) -> None:
    name = identities["antigravity"][0]
    source = folder / name
    original = source.read_bytes()
    _require(hosts.payload_bytes(folder, "antigravity") == original, "verified fixture rejected")
    source.write_bytes(original + b"tamper")
    (folder / "manifest.json").write_text(
        json.dumps(
            {"assets": [{"name": name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
        ),
        encoding="utf-8",
    )
    _reject(
        lambda: hosts.payload_bytes(folder, "antigravity"),
        "mutable manifest authorized tampered payload",
    )
    source.write_bytes(original)
    with patch.object(hosts, "MAX_ARCHIVE_BYTES", len(original) - 1):
        _reject(lambda: hosts.payload_bytes(folder, "antigravity"), "archive size cap ignored")
    other = folder / "linked-payload.zip"
    other.write_bytes(original)
    source.unlink()
    try:
        source.symlink_to(other)
    except OSError:
        print(
            "SKIP: native symlink creation unavailable; archive symlink/reparse fixtures remain covered."
        )
    else:
        _reject(lambda: hosts.payload_bytes(folder, "antigravity"), "symlink payload accepted")
        source.unlink()
    source.write_bytes(original)


def _check_archives(folder: Path, hosts: Any) -> None:
    bad_names = (
        "../escape.md",
        "/absolute.md",
        "C:/escape.md",
        ".agents/rules/../../escape.md",
        ".agents\\rules\\escape.md",
        ".agents/rules/./escape.md",
        ".agents//rules/escape.md",
        ".agents/rules/file:stream",
        "unrelated/private.md",
        ".agents/rules/CON.md",
        ".agents/rules/trailing.md.",
        ".agents/rules/hidden.md\x00ignored",
    )
    for name in bad_names:
        raw = _zip([(name, b"untrusted", stat.S_IFREG | 0o644)])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            _require(archive.infolist()[0].orig_filename == name, "hostile wire name changed")
            _reject(lambda: hosts._entries(archive, "antigravity"), "unsafe archive path accepted")
    for mode in (stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o644, stat.S_IFDIR | 0o755):
        raw = _zip([(".agents/rules/unsafe.md", b"target", mode)])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            _reject(
                lambda: hosts._entries(archive, "antigravity"), "special archive member accepted"
            )
    members = [
        (".agents/rules/a.md", b"a", stat.S_IFREG | 0o644),
        (".agents/rules/A.md", b"b", stat.S_IFREG | 0o644),
    ]
    with zipfile.ZipFile(io.BytesIO(_zip(members))) as archive:
        _reject(lambda: hosts._entries(archive, "antigravity"), "Windows case collision accepted")
    with zipfile.ZipFile(io.BytesIO(_zip(members[:1]))) as archive:
        with patch.object(hosts, "MAX_EXPANDED_BYTES", 0):
            _reject(lambda: hosts._entries(archive, "antigravity"), "expanded size cap ignored")
        with patch.object(hosts, "MAX_MEMBERS", 0):
            _reject(lambda: hosts._entries(archive, "antigravity"), "member count cap ignored")
    for raw_metadata in (
        b"not-json",
        b'{"schema":"other","host":"antigravity","product_version":"1.5.3"}',
        b'{"schema":"opensocrates.content-host-manifest/1.0.0","host":"other","product_version":"1.5.3"}',
    ):
        raw = _zip([("release-manifest.json", raw_metadata, stat.S_IFREG | 0o644)])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            _reject(
                lambda: hosts._entries(archive, "antigravity"),
                "unverified release metadata accepted",
            )
    actor = folder / "collision actor"
    actor.mkdir()
    (actor / ".agents").mkdir()
    sentinel = actor / ".agents/owner.txt"
    sentinel.write_bytes(_SENTINEL)
    with zipfile.ZipFile(io.BytesIO(_zip(members[:1]))) as archive:
        entries = hosts._entries(archive, "antigravity")
    _reject(lambda: hosts._write_new(actor, entries), "existing actor root overwritten")
    _require(sentinel.read_bytes() == _SENTINEL, "existing actor files changed after rejection")


def _check_host_bytes(actor: Path, host: str, payloads: Path, hosts: Any) -> None:
    with zipfile.ZipFile(
        payloads / hosts.PAYLOADS["claude_cowork" if host == "desktop_work" else host][0]
    ) as archive:
        for member in archive.infolist():
            if host == "antigravity" and member.filename == "release-manifest.json":
                _require(
                    not (actor / member.filename).exists(),
                    "release metadata copied into actor workspace",
                )
                continue
            destination = actor / member.filename
            if host == "desktop_work":
                destination = actor / "plugins/opensocrates-lab/skills" / member.filename
            _require(
                destination.read_bytes() == archive.read(member),
                "transport changed canonical skill bytes",
            )


def _check_host_content(folder: Path, payloads: Path, hosts: Any) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for host in ("desktop_work", "antigravity"):
        actor = folder / host
        actor.mkdir()
        guide = hosts.prepare_content(actor, host, payloads)
        _require(guide["status"] == "manual_required", "content falsely reports installed/loaded")
        _check_host_bytes(actor, host, payloads, hosts)
        if host == "desktop_work":
            manifests = list(actor.rglob("*.json"))
            _require(manifests, "Work plugin manifest absent")
            for manifest in manifests:
                parsed = json.loads(manifest.read_text(encoding="utf-8"))
                _require(
                    "hooks" not in parsed and "mcpServers" not in parsed,
                    "content-only Work adapter starts executable integrations",
                )
            _require(
                not list(actor.rglob("*.sh")) and not list(actor.rglob("*.exe")),
                "Work adapter contains native runtime",
            )
    unavailable = hosts.prepare_content(folder / "unused", "desktop_work", None)
    _require(unavailable["status"] == "unavailable", "missing payload silently falls back")
    actor = folder / "reparse actor"
    actor.mkdir()
    original_lstat = Path.lstat

    def reparse(path: Path) -> Any:
        if path == actor:
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x400)
        return original_lstat(path)

    with patch.object(Path, "lstat", reparse):
        _reject(
            lambda: hosts.prepare_content(actor, "antigravity", payloads),
            "Windows reparse actor accepted",
        )
    linked = folder / "linked actor"
    try:
        linked.symlink_to(actor, target_is_directory=True)
    except OSError:
        pass
    else:
        _reject(
            lambda: hosts.prepare_content(linked, "antigravity", payloads), "symlink actor accepted"
        )


def _copy_sources(root: Path, destination: Path, builder: Any) -> None:
    for _, source in builder._source_files():
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for relative in (
        ".git/private",
        "lab-data/state.json",
        "lab-data/approved/final.md",
        ".codex/sessions/private.jsonl",
        "src/opensocrates/evaluation/private.txt",
        "src/opensocrates/evaluation/assets/private.html",
        "evals/office-work-v1/approved/final.md",
        "tools/evaluation-lab/payloads/private.txt",
    ):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_SENTINEL)


def _check_kit_archive(output: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(output) as archive:
        prefix = "OpenSocrates-Office-Lab/"
        files = {
            item.filename.removeprefix(prefix): archive.read(item) for item in archive.infolist()
        }
        _require(
            all(item.filename.startswith(prefix) for item in archive.infolist()),
            "kit has unscoped members",
        )
        _require(
            all(_SENTINEL not in raw for raw in files.values()),
            "private source/study/cache file packaged",
        )
        manifest = json.loads(files["kit-manifest.json"])
        expected = {
            name: hashlib.sha256(raw).hexdigest()
            for name, raw in files.items()
            if name != "kit-manifest.json"
        }
        _require(manifest["files"] == expected, "portable kit file hashes incomplete or incorrect")
        _require(
            "Start Lab.command" in files and "Start Lab.cmd" in files, "platform launchers absent"
        )
        forbidden = (b"executionpolicy bypass", b"unblock-file", b"sudo ", b"pip install", b"curl ")
        launchers = files["Start Lab.command"].lower() + files["Start Lab.cmd"].lower()
        _require(
            not any(fragment in launchers for fragment in forbidden),
            "launcher bypasses trust or installs packages",
        )
        _require(
            b'"%~dp0start-lab.py"' in files["Start Lab.cmd"],
            "Windows launcher does not quote Unicode/spaced path",
        )
        modes = {
            item.filename.removeprefix(prefix): item.external_attr >> 16
            for item in archive.infolist()
        }
        _require(modes["Start Lab.command"] == stat.S_IFREG | 0o755, "Mac launcher not executable")
    return files


def _check_unpacked(output: Path, folder: Path) -> None:
    with zipfile.ZipFile(output) as archive:
        archive.extractall(folder)
    kit = folder / "OpenSocrates-Office-Lab"
    process = subprocess.run(
        [sys.executable, "-I", "-S", str(kit / "start-lab.py"), "--help"],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    _require(
        process.returncode == 0 and "--data" in process.stdout,
        "unpacked launcher fails outside repository",
    )
    script = (
        "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from opensocrates.evaluation.engine import Lab; "
        "from opensocrates.evaluation.server import _Server; "
        "from opensocrates.evaluation import hosts; "
        "lab=Lab(Path(sys.argv[2]),Path(sys.argv[3])); "
        "assert not lab.snapshot()['initialized']; print('stdlib-import-ok')"
    )
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            script,
            str(kit / "src"),
            str(folder / "fresh owned data"),
            str(kit / "evals/office-work-v1"),
        ],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    _require(
        process.returncode == 0 and process.stdout.strip() == "stdlib-import-ok",
        "unpacked lab requires non-stdlib dependencies or source checkout",
    )


def _check_build(root: Path, temporary: Path, payloads: Path, builder: Any) -> None:
    source = temporary / "isolated source — 한국어"
    _copy_sources(root, source, builder)
    output = temporary / "portable kit — 한국어.zip"
    with patch.object(builder, "ROOT", source):
        builder.build(output, payloads)
        _check_kit_archive(output)
        repeat = temporary / "portable repeat.zip"
        builder.build(repeat, payloads)
        _require(
            output.read_bytes() == repeat.read_bytes(),
            "portable kit build depends on output path or time",
        )
        original = output.read_bytes()
        _reject(lambda: builder.build(output, payloads), "existing portable archive overwritten")
        _require(output.read_bytes() == original, "rejected rebuild changed existing archive")
        target = source / "src/opensocrates/evaluation/assets/index.html"
        original_source = target.read_bytes()
        outside = temporary / "outside-private.html"
        outside.write_bytes(_SENTINEL)
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError:
            print("SKIP: native source symlink creation unavailable.")
        else:
            unsafe_output = temporary / "unsafe-source.zip"
            _reject(
                lambda: builder.build(unsafe_output, payloads),
                "linked source copied into portable archive",
            )
            _require(not unsafe_output.exists(), "rejected source left a partial kit")
            target.unlink()
        target.write_bytes(original_source)
    _check_unpacked(output, temporary / "unpacked kit — 한국어")


def check(root: Path, real_payloads: Path | None) -> int:
    global _CHECKS
    _CHECKS = 0
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "src"))
    hosts = importlib.import_module("opensocrates.evaluation.hosts")
    builder = importlib.import_module("tools.build_evaluation_lab")
    with tempfile.TemporaryDirectory(prefix="office-lab-package-") as name:
        temporary = Path(name).resolve()
        payloads = temporary / "fixture payloads — 한국어"
        identities = _fixtures(payloads, hosts)
        with (
            patch.object(hosts, "PAYLOADS", identities),
            patch.object(builder, "PAYLOADS", identities),
        ):
            _check_pinning(payloads, hosts, identities)
            _check_archives(temporary, hosts)
            _check_host_content(temporary, payloads, hosts)
            _check_build(root, temporary, payloads, builder)
        if real_payloads is None:
            print(
                "SKIP: exact public v1.5.3 payload identity/full-skill parity (provide --payloads-dir); fixture checks are offline only."
            )
        else:
            for host in hosts.PAYLOADS:
                _require(
                    bool(hosts.payload_bytes(real_payloads, host)),
                    "public pinned payload unavailable",
                )
            _check_host_content(temporary / "public content", real_payloads, hosts)
            output = temporary / "public-payload-kit.zip"
            builder.build(output, real_payloads)
            _check_kit_archive(output)
    print(
        f"Office lab packaging: {_CHECKS} checks passed (no network/model calls; native Windows launch not claimed)."
    )
    return _CHECKS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--payloads-dir", type=Path)
    args = parser.parse_args()
    check(args.root.resolve(), args.payloads_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
