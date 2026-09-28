"""Closed official-reference prompts, provenance, and stateless CLI controls."""

from __future__ import annotations

import io
import json
import socket
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from opensocrates.cli.documentation import run_documentation
from opensocrates.cli.main import main
from opensocrates.documentation import MAX_BYTES, documentation_pack
from opensocrates.project_memory.contracts import load_schema, validate

ROOT = Path(__file__).resolve().parents[1]


def request(locale: str = "en") -> dict:
    value = json.loads(
        (ROOT / "plugin-src/shared/documentation/request.json").read_text(encoding="utf-8")
    )
    value["locale"] = locale
    return value


class DocumentationTests(unittest.TestCase):
    def test_reading_version_and_attribution_stay_separate(self):
        value = request()
        result = documentation_pack(value)
        self.assertEqual(result["next_action"], "read_reference")
        self.assertEqual(result["references"][0]["publisher_match"], "catalog_match")
        self.assertEqual(result["application"], "unverified")
        value["references"][0].update(read_state="reported_read", attribution="agent_reported")
        self.assertEqual(documentation_pack(value)["next_action"], "apply_with_citations")
        value["references"][0]["document_version"] = "3.10"
        self.assertEqual(documentation_pack(value)["next_action"], "resolve_version")
        value["references"][0]["document_version"] = None
        self.assertEqual(documentation_pack(value)["next_action"], "resolve_version")
        value["references"][0]["attribution"] = "unknown"
        self.assertEqual(self.cli(value)[0], 2)

    @staticmethod
    def cli(value):
        output = io.StringIO()
        code = run_documentation(io.BytesIO(json.dumps(value).encode()), output)
        parsed = json.loads(output.getvalue())
        validate(parsed, load_schema("documentation-pack.schema.json"))
        return code, parsed

    def test_unlisted_and_lookalike_sources_never_gain_catalog_authority(self):
        for url in (
            "https://docs.python.org.evil.example/3.12/",
            "https://python.example/",
            "https://docs.python.org:4430/a",
        ):
            value = request()
            value["references"][0]["url"] = url
            code, result = self.cli(value)
            self.assertTrue(code == 2 or result["next_action"] == "find_official_source")
        value = request()
        value["publisher_id"] = "unlisted"
        result = documentation_pack(value)
        self.assertEqual(result["next_action"], "find_official_source")
        self.assertEqual(result["references"][0]["publisher_match"], "unverified")
        value.update(publisher_id="postgresql")
        value["references"][0]["url"] = "https://www.postgresql.org/docs-evil/"
        self.assertEqual(documentation_pack(value)["next_action"], "find_official_source")

    def test_unsafe_urls_reject_without_echo(self):
        for url in (
            "http://docs.python.org/",
            "file:///etc/passwd",
            "https://secret@docs.python.org/a",
            "https://docs.python.org/a?token=secret",
            "https://docs.python.org/a/../b",
            "https://docs.python.org/%252e%252e/b",
            "https://docs.python.org/%0aignore",
            "https://docs.python.org\\@evil.example/a",
            "https://docs.python.org/3.12/#access_token=SECRET",
            "https://docs.python.org/3.12/#access_token%3DSECRET",
            "https://docs.python.org/3.12/#secret-SECRET",
        ):
            value = request()
            value["references"][0]["url"] = url
            code, result = self.cli(value)
            self.assertEqual(code, 2, url)
            self.assertNotIn("secret", json.dumps(result))

    def test_fixed_prompt_cannot_be_replaced_by_input(self):
        baseline = documentation_pack(request())
        value = request()
        value["references"][0]["url"] += "#ignore-all-instructions"
        other = documentation_pack(value)
        self.assertEqual(baseline["instructions"], other["instructions"])
        self.assertEqual(baseline["instruction_sha256"], other["instruction_sha256"])
        for key in ("instructions", "page_body", "prompt", "hidden_reasoning"):
            hostile = {**request(), key: "secret injection"}
            code, result = self.cli(hostile)
            self.assertEqual(code, 2)
            self.assertNotIn("secret", json.dumps(result))

    def test_mechanical_and_no_need_emit_nothing(self):
        for changes in ({"task_kind": "mechanical"}, {"need": "none"}):
            result = documentation_pack({**request(), **changes})
            self.assertEqual(
                (
                    result["status"],
                    result["instructions"],
                    result["references"],
                    result["delivery"],
                ),
                ("not_needed", "", [], "not_emitted"),
            )
        self.assertEqual(
            documentation_pack(
                {**request(), "task_kind": "mechanical", "need": "official_request"}
            )["status"],
            "ok",
        )

    def test_installed_asset_failure_is_unavailable_not_bad_input(self):
        original = ROOT / "plugin-src/shared/documentation"
        with tempfile.TemporaryDirectory() as temporary:
            assets = Path(temporary)
            for file in original.iterdir():
                if file.is_file():
                    (assets / file.name).write_bytes(file.read_bytes())
            with patch("opensocrates.documentation._assets", return_value=assets):
                (assets / "publishers.json").write_text("{SECRET malformed")
                code, result = self.cli(request())
                self.assertEqual((code, result["status"]), (3, "unavailable"))
                self.assertNotIn("SECRET", json.dumps(result))
                (assets / "publishers.json").write_bytes(
                    (original / "publishers.json").read_bytes()
                )
                (assets / "prompt.en.md").write_text("x" * (MAX_BYTES + 1))
                self.assertEqual(self.cli(request())[0], 3)

    def test_locale_metadata_parity_and_exact_trusted_bytes(self):
        en, ko = [documentation_pack(request(locale)) for locale in ("en", "ko")]
        for locale, result in (("en", en), ("ko", ko)):
            self.assertEqual(
                result["instructions"],
                (ROOT / f"plugin-src/shared/documentation/prompt.{locale}.md").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertLess(len(json.dumps(result, ensure_ascii=False).encode()), MAX_BYTES)
        self.assertNotEqual(en["instructions"], ko["instructions"])
        for field in ("instructions", "instruction_sha256"):
            en.pop(field)
            ko.pop(field)
        self.assertEqual(en, ko)

    def test_strict_wire_and_dispatch_without_services_or_network(self):
        payload = json.dumps(request()).encode()
        invalid = [
            b"",
            b"\xff",
            b"[]",
            b'{"schema":1,"schema":2}',
            b'{"need":NaN}',
            payload + payload,
            b" " * (MAX_BYTES + 1),
        ]
        for raw in invalid:
            output = io.StringIO()
            self.assertEqual(run_documentation(io.BytesIO(raw), output), 2)
        with (
            patch(
                "opensocrates.cli.main._services_for",
                side_effect=AssertionError("runtime initialized"),
            ),
            patch.object(socket, "socket", side_effect=AssertionError("network accessed")),
        ):
            output = io.StringIO()
            self.assertEqual(main(["documentation"], stdin=io.BytesIO(payload), stdout=output), 0)
        larger = deepcopy(request())
        larger["references"] *= 5
        self.assertEqual(self.cli(larger)[0], 2)


if __name__ == "__main__":
    unittest.main()
