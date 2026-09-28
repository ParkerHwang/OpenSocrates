"""Static specialist identity and native-boundary checks, not model-effect proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from check_decision_points import request
from opensocrates.content.injection import ProjectionInstructionAssembler
from opensocrates.content.loader import load_compiled_bundle, load_reasoning_content_projections
from opensocrates.selector.decision import DecisionSession

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = Path("coding-specialists/v0.1.1")
SOURCE = ROOT / "plugin-src/shared" / RELATIVE
LOCALES = {"en", "ko", "zh-CN"}
IDENTIFIERS = {"csp-contracts", "csp-transitions", "csp-ownership"}


def validate_library(directory: Path) -> dict[str, object]:
    """Reject missing/altered members and misrepresented native capabilities."""
    manifest = json.loads((directory / "library.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "opensocrates.coding-specialists.library/1.0.0"
    assert manifest["version"] == "0.1.1"
    assert manifest["status"] == "provisional"
    assert manifest["delivery"] == "static_agent_directed"
    assert manifest["native_registered"] is False
    assert manifest["native_locales"] == ["en", "ko"]
    assert set(manifest["static_locales"]) == LOCALES
    assert manifest["general_method_count"] == 48
    assert set(manifest["specialists"]) == IDENTIFIERS
    assert set(manifest["procedures"]) == IDENTIFIERS
    expected = {
        f"{stem}.{locale}.md"
        for stem in ("router", "contracts", "transitions", "ownership")
        for locale in LOCALES
    }
    entries = manifest["files"]
    assert len(entries) == len(expected)
    assert {entry["path"] for entry in entries} == expected
    actual = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()}
    assert actual == expected | {"library.json"}
    for entry in entries:
        path = directory / entry["path"]
        assert path.parent == directory and not path.is_symlink()
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
        assert len(content) == entry["bytes"] and b"\r" not in content
        assert b"/Users/" not in content and b"worked-examples.md" not in content
        for relative in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content.decode("utf-8")):
            assert relative in expected, relative
            assert (directory / relative).is_file()
    for locale in LOCALES:
        assert manifest["router"][locale] == f"router.{locale}.md"
        for identifier in IDENTIFIERS:
            stem = identifier.removeprefix("csp-")
            assert manifest["procedures"][identifier][locale] == f"{stem}.{locale}.md"
            assert f"{identifier}@0.1.1" in (directory / f"{stem}.{locale}.md").read_text(
                encoding="utf-8"
            )
    return {
        "status": "pass",
        "prompt_files": len(entries),
        "static_locales": sorted(LOCALES),
        "native_registered": False,
        "effect": "not_measured_by_this_check",
    }


def verify_packaged_library(package: Path) -> dict[str, object]:
    destination = package / "skills/opensocrates/references" / RELATIVE
    result = validate_library(destination)
    paths = sorted(SOURCE.iterdir())
    for source in paths:
        assert (destination / source.name).read_bytes() == source.read_bytes(), source.name
    release = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
    recorded = {entry["path"]: entry["sha256"] for entry in release["files"]}
    for source in paths:
        copied = destination / source.name
        assert recorded[copied.relative_to(package).as_posix()] == (
            "sha256:" + hashlib.sha256(copied.read_bytes()).hexdigest()
        )
    return {**result, "package_members": len(paths), "canonical_methods": release["method_count"]}


class SpecialistBoundaries(unittest.TestCase):
    def test_package_inventory_binds_the_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            destination = package / "skills/opensocrates/references" / RELATIVE
            shutil.copytree(SOURCE, destination)
            release = {
                "method_count": 48,
                "files": [
                    {
                        "path": path.relative_to(package).as_posix(),
                        "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                    for path in destination.iterdir()
                ],
            }
            manifest = package / "release-manifest.json"
            manifest.write_text(json.dumps(release), encoding="utf-8")
            self.assertEqual(verify_packaged_library(package)["package_members"], 13)
            release["files"][0]["sha256"] = "sha256:" + "0" * 64
            manifest.write_text(json.dumps(release), encoding="utf-8")
            with self.assertRaises(AssertionError):
                verify_packaged_library(package)

    def test_complete_static_library(self):
        self.assertEqual(validate_library(SOURCE)["prompt_files"], 12)

    def test_changed_or_missing_prompt_is_rejected(self):
        for mode in ("changed", "missing"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "library"
                shutil.copytree(SOURCE, target)
                member = target / "ownership.zh-CN.md"
                if mode == "changed":
                    member.write_text("altered procedure", encoding="utf-8")
                else:
                    member.unlink()
                with self.assertRaises((AssertionError, FileNotFoundError)):
                    validate_library(target)

    def test_false_native_registration_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "library"
            shutil.copytree(SOURCE, target)
            value = json.loads((target / "library.json").read_text(encoding="utf-8"))
            value["native_registered"] = True
            (target / "library.json").write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(AssertionError):
                validate_library(target)

    def test_native_catalog_rejects_specialists_and_chinese(self):
        bundle = load_compiled_bundle(ROOT / "content/compiled-content.bundle.json")
        assembler = ProjectionInstructionAssembler(
            load_reasoning_content_projections(
                ROOT / "content/compiled-reasoning-content.bundle.json"
            )
        )
        session = DecisionSession(bundle, assembler)
        catalog = session.handle({"operation": "catalog", "locale": "en"})
        self.assertEqual(len(catalog["methods"]), 48)
        self.assertTrue(IDENTIFIERS.isdisjoint({method["id"] for method in catalog["methods"]}))
        for identifier in IDENTIFIERS:
            self.assertEqual(session.handle(request(identifier))["reason"], "unknown_method")
        self.assertEqual(
            session.handle({"operation": "catalog", "locale": "zh-CN"})["status"], "unavailable"
        )
        selected = session.handle(request("deduction", locale="ko"))
        self.assertEqual(selected["selected"], ["deduction"])
        specialist_digest = (
            "sha256:" + hashlib.sha256((SOURCE / "contracts.ko.md").read_bytes()).hexdigest()
        )
        rejected = session.handle(
            {
                "operation": "acknowledge",
                "context": "a" * 32,
                "epoch": 0,
                "digests": [specialist_digest],
            }
        )
        self.assertEqual(rejected["status"], "unavailable")
        self.assertIsNotNone(
            session.handle(request("deduction", locale="ko"))["methods"][0]["instructions"]
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.package:
        result = verify_packaged_library(args.package)
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SpecialistBoundaries)
        outcome = unittest.TextTestRunner(verbosity=2).run(suite)
        result = {
            "status": "pass" if outcome.wasSuccessful() else "fail",
            "tests": outcome.testsRun,
            "model_calls": 0,
            "human_language_review": None,
        }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
