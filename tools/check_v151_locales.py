"""Release locale contract checks; semantic translation review remains separate."""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

from opensocrates.content.loader import load_reasoning_content_projections
from validate_content import parse_yaml_file

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th")
IDENTIFIER = re.compile(r"`([A-Za-z][A-Za-z0-9_-]*)`")
NUMBER_WORDS = dict(
    zip(
        ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"),
        (str(value) for value in range(1, 11)),
        strict=True,
    )
)


class LocalizationContracts(unittest.TestCase):
    def test_authoring_catalog_is_fully_localized(self) -> None:
        catalog = parse_yaml_file(ROOT / "content/catalog.yaml")
        for family in catalog["families"]:
            for field in ("display_name", "intent", "family_output"):
                self.assertEqual(set(family[field]), set(LOCALES))
        for method in catalog["methods"]:
            metadata = parse_yaml_file(ROOT / "content/methods" / method["id"] / "method.yaml")
            self.assertEqual(method["display_name"], metadata["display_name"])
            for field in ("display_name", "route_when", "avoid_when", "required_public_output"):
                self.assertEqual(set(method[field]), set(LOCALES))
                self.assertTrue(all(text.strip() for text in method[field].values()))

    def test_complete_native_projections_and_public_keys(self) -> None:
        projections = load_reasoning_content_projections(
            ROOT / "content/compiled-reasoning-content.bundle.json"
        )
        self.assertEqual(len(projections.injectable_content), 48 * len(LOCALES))
        seen: set[tuple[str, str]] = set()
        for content in projections.injectable_content:
            key = (content.method_id, content.locale)
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertEqual(content.content_revision, projections.content_revision)
        for entry in projections.selection_catalog.entries:
            for locale in LOCALES:
                self.assertIn((entry.method_id, locale), seen)
            directory = ROOT / "content/methods" / entry.method_id
            english = (directory / "procedure.en.md").read_text(encoding="utf-8")
            expected = set(IDENTIFIER.findall(english))
            for locale in LOCALES[2:]:
                translated = (directory / f"procedure.{locale}.md").read_text(encoding="utf-8")
                with self.subTest(method=entry.method_id, locale=locale):
                    self.assertTrue(expected <= set(IDENTIFIER.findall(translated)))
                    self.assertNotEqual(translated, english)

    def test_translated_examples_preserve_routing_and_numbers(self) -> None:
        for directory in sorted((ROOT / "content/methods").iterdir()):
            original = parse_yaml_file(directory / "cases.en.yaml")
            for locale in LOCALES[2:]:
                translated = parse_yaml_file(directory / f"cases.{locale}.yaml")
                self.assertEqual(translated["schema"], original["schema"])
                self.assertEqual(len(translated["cases"]), len(original["cases"]))
                for source, target in zip(original["cases"], translated["cases"], strict=True):
                    with self.subTest(method=directory.name, locale=locale, case=source["id"]):
                        self.assertEqual(set(source), set(target))
                        for field, value in source.items():
                            if field not in {"prompt", "rationale"}:
                                self.assertEqual(target[field], value)
                        for field in ("prompt", "rationale"):
                            self.assertNotEqual(target[field], source[field])
                            source_numbers = Counter(re.findall(r"\d+(?:\.\d+)?", source[field]))
                            translated_numbers = Counter(
                                re.findall(r"\d+(?:\.\d+)?", target[field])
                            )
                            # Native prose may render English "two" as 2 while
                            # explicit numerical data must retain its value.
                            word_numbers = Counter(
                                NUMBER_WORDS[word]
                                for word in re.findall(r"\b\w+\b", source[field].lower())
                                if word in NUMBER_WORDS
                            )
                            self.assertTrue(source_numbers <= translated_numbers)
                            self.assertTrue(translated_numbers <= source_numbers + word_numbers)

    def test_teacher_question_counts_and_contract(self) -> None:
        catalog = json.loads((ROOT / "content/teacher-questions.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(catalog["methods"]), 48)
        for locale in LOCALES:
            seen: set[str] = set()
            for method, localized in catalog["methods"].items():
                self.assertEqual(set(localized), set(LOCALES))
                questions = localized[locale]
                self.assertEqual(len(questions), 3)
                for question in questions:
                    with self.subTest(method=method, locale=locale):
                        self.assertTrue(question.endswith("?"))
                        self.assertGreaterEqual(len(question), 20)
                        self.assertLessEqual(len(question), 220)
                        self.assertNotIn(question, seen)
                        seen.add(question)
            self.assertEqual(len(seen), 144)


if __name__ == "__main__":
    unittest.main()
