#!/usr/bin/env python3
"""Check content-only layouts, canonical parity, deterministic builds and rejection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from functools import partial
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

_CHECK_COUNT = 0


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _require(condition: bool, message: str) -> None:
    global _CHECK_COUNT
    if not condition:
        raise AssertionError(message)
    _CHECK_COUNT += 1


def _reject(action: Callable[[], Any], message: str) -> None:
    global _CHECK_COUNT
    try:
        action()
    except (ValueError, OSError):
        _CHECK_COUNT += 1
        return
    raise AssertionError(message)


def _executable_stat(target: Path) -> Callable[..., os.stat_result]:
    original_stat = Path.stat

    def stat(member: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        result = original_stat(member, follow_symlinks=follow_symlinks)
        if member == target:
            result = os.stat_result((result.st_mode | 0o111, *result[1:]))
        return result

    return stat


def check(root: Path) -> int:
    global _CHECK_COUNT
    _CHECK_COUNT = 0
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "src"))
    from tools.build_content_hosts import (
        HOSTS,
        LAYOUTS,
        build_content_host,
        verify_content_host_package,
    )
    from tools.build_plugins import generate_plugin
    from tools.release_check import _write_deterministic_zip

    from opensocrates.selector.entry import ENTRY_GUIDANCE

    _require(len(ENTRY_GUIDANCE.encode("utf-8")) <= 1400, "discovery entry exceeds byte budget")
    _require(
        "references/reader/guide.en.md" in ENTRY_GUIDANCE, "discovery entry has no reader pointer"
    )
    with tempfile.TemporaryDirectory(prefix="opensocrates-content-check-") as name:
        temporary = Path(name)
        native = temporary / "native"
        generate_plugin(
            root=root, host="codex", output=native, runtime_root=temporary / "absent-runtime"
        )
        baseline = native / "skills/opensocrates/references/decision"
        for host in HOSTS:
            output = temporary / f"{host} output — 한국어"
            manifest = build_content_host(root=root, host=host, output=output)
            _require(
                manifest == verify_content_host_package(output, host=host),
                "manifest verification mismatch",
            )
            first = _tree(output)
            _require(
                build_content_host(root=root, host=host, output=output) == manifest
                and _tree(output) == first,
                "repeat build is nondeterministic",
            )
            other = temporary / f"second-{host}"
            build_content_host(root=root, host=host, output=other)
            _require(_tree(other) == first, "path-dependent package content")
            archive = temporary / f"{host}-portable.zip"
            second_archive = temporary / f"{host}-portable-second.zip"
            _write_deterministic_zip(output, archive, content_only=True)
            with patch.object(
                Path, "stat", _executable_stat(other / LAYOUTS[host][0] / "SKILL.md")
            ):
                _write_deterministic_zip(other, second_archive, content_only=True)
            _require(
                archive.read_bytes() == second_archive.read_bytes(),
                "portable ZIP depends on local file modes",
            )
            with zipfile.ZipFile(archive) as bundle:
                _require(
                    all((member.external_attr >> 16) == 0o100644 for member in bundle.infolist()),
                    "content ZIP carries an executable or platform-dependent mode",
                )
            skill = output / LAYOUTS[host][0]
            _require(
                [p.relative_to(output).as_posix() for p in output.rglob("SKILL.md")]
                == [f"{LAYOUTS[host][0]}/SKILL.md"],
                "more than one public skill",
            )
            _require(
                "control codex" not in (skill / "SKILL.md").read_text(encoding="utf-8")
                and "${PLUGIN_ROOT}" not in (skill / "SKILL.md").read_text(encoding="utf-8"),
                "portable controller has a native control command",
            )
            _require(
                len(manifest["canonical_methods"]) == 96, "bilingual procedure inventory incomplete"
            )
            for locale in ("en", "ko"):
                decision = skill / "references/decision"
                _require(
                    (decision / f"catalog.{locale}.json").read_bytes()
                    == (baseline / f"catalog.{locale}.json").read_bytes(),
                    "catalog differs from native package",
                )
                for method_id in manifest["method_ids"]:
                    relative = f"methods/{locale}/{method_id}.md"
                    actual = (decision / relative).read_bytes()
                    _require(
                        actual == (baseline / relative).read_bytes(),
                        f"canonical procedure differs: {relative}",
                    )
                _require(
                    (skill / f"references/reader/guide.{locale}.md").read_bytes()
                    == (root / f"plugin-src/shared/reader/guide.{locale}.md").read_bytes(),
                    "reader guide changed in distribution",
                )
            _require(
                (skill / "references/decision/features.json").read_bytes()
                == (root / "plugin-src/shared/decision/features.json").read_bytes(),
                "file eligibility features differ",
            )
            if host == "claude-chat":
                _require(
                    {path.name for path in output.iterdir()} == {"opensocrates"},
                    "account upload has extra root files",
                )
            else:
                rule = (output / ".agents/rules/opensocrates.md").read_bytes()
                _require(
                    len(rule) <= 4096 and rule.startswith(b"---\ntrigger: always_on\n"),
                    "invalid Antigravity rule",
                )
                _require(
                    (output / ".agents/rules" / "../skills/opensocrates/SKILL.md").resolve()
                    == (skill / "SKILL.md").resolve(),
                    "rule reference does not resolve from installed rule",
                )
            victim = skill / "references/decision/methods/en/critical-thinking.md"
            original = victim.read_bytes()
            victim.write_bytes(original + b"tampered\n")
            _reject(
                partial(verify_content_host_package, output, host=host), "tampered method accepted"
            )
            _reject(
                partial(build_content_host, root=root, host=host, output=output),
                "build overwrote modified output",
            )
            _require(
                victim.read_bytes().endswith(b"tampered\n"), "failed build modified tampered output"
            )
            victim.write_bytes(original)
            if os.name == "nt":
                # Windows chmod cannot set POSIX execute bits. Exercise the
                # verifier's mode rejection without claiming native bit evidence.
                with patch.object(Path, "stat", _executable_stat(victim)):
                    _reject(
                        partial(verify_content_host_package, output, host=host),
                        "injected executable member mode accepted",
                    )
            else:
                victim.chmod(0o755)
                _reject(
                    partial(verify_content_host_package, output, host=host),
                    "executable member accepted",
                )
                victim.chmod(0o644)
            extra = output / "hooks.json"
            extra.write_text("{}\n")
            _reject(
                partial(verify_content_host_package, output, host=host),
                "extra hook surface accepted",
            )
            extra.unlink()
            manifest_file = output / LAYOUTS[host][1]
            manifest_bytes = manifest_file.read_bytes()
            invalid = json.loads(manifest_bytes)
            invalid["canonical_methods"][0]["sha256"] = "sha256:" + "0" * 64
            manifest_file.write_text(json.dumps(invalid))
            _reject(
                partial(verify_content_host_package, output, host=host),
                "tampered canonical identity accepted",
            )
            manifest_file.write_bytes(manifest_bytes)
            disguised = output / "unexpected.sh"
            disguised.write_bytes(b"echo unexpected\n")
            invalid = json.loads(manifest_bytes)
            invalid["files"].append(
                {
                    "path": "unexpected.sh",
                    "sha256": "sha256:" + hashlib.sha256(disguised.read_bytes()).hexdigest(),
                }
            )
            manifest_file.write_text(json.dumps(invalid))
            _reject(
                partial(verify_content_host_package, output, host=host),
                "inventoried foreign script accepted",
            )
            disguised.unlink()
            manifest_file.write_bytes(manifest_bytes)
            if os.name != "nt":
                victim.unlink()
                victim.symlink_to(temporary / "sentinel")
                _reject(
                    partial(verify_content_host_package, output, host=host),
                    "linked member accepted",
                )
                victim.unlink()
                victim.write_bytes(original)
                victim.chmod(0o644)
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "tools/build_content_hosts.py"),
                    "--root",
                    str(root),
                    "--host",
                    host,
                    "--output",
                    str(temporary / f"cli-{host}"),
                ],
                cwd=temporary,
                capture_output=True,
                text=True,
                check=False,
            )
            _require(
                result.returncode == 0 and _tree(temporary / f"cli-{host}") == first,
                "explicit-root CLI depends on working directory",
            )
        _reject(
            lambda: build_content_host(root=root, host="gemini", output=temporary / "unsupported"),
            "unsupported host accepted",
        )
        for forbidden in (root, root.parent, root / "plugin-src/claude-chat"):
            _reject(
                partial(build_content_host, root=root, host="claude-chat", output=forbidden),
                "source-overlapping output accepted",
            )
        unowned = temporary / "unowned"
        unowned.mkdir()
        sentinel = unowned / "sentinel"
        sentinel.write_text("preserve")
        _reject(
            lambda: build_content_host(root=root, host="claude-chat", output=unowned),
            "unowned output accepted",
        )
        _require(sentinel.read_text(encoding="utf-8") == "preserve", "unowned output was changed")
    english = (root / "plugin-src/shared/reader/guide.en.md").read_text(encoding="utf-8")
    korean = (root / "plugin-src/shared/reader/guide.ko.md").read_text(encoding="utf-8")
    _require(
        "Skip it for" in english
        and "mechanical work" in english
        and "기계적인 작업에서는 건너뜁니다" in korean,
        "reader guidance imposes mechanical ceremony",
    )
    _require(
        "stop conditions and grounding" in english and "중단 조건, 접지 규칙" in korean,
        "reader guidance weakens canonical contracts",
    )
    return _CHECK_COUNT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    options = parser.parse_args(argv)
    try:
        count = check(Path(options.root).resolve())
    except (AssertionError, OSError, ValueError) as error:
        print(f"content hosts: FAIL ({error})", file=sys.stderr)
        return 1
    print(f"content hosts: PASS ({count} checks; native canonical parity; content-only layouts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
