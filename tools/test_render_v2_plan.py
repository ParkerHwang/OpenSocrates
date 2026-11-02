"""Check the standalone plan's generated navigation without opening a browser."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    "VISION_2.0.ko.md",
    "SYSTEM_2.0.ko.md",
    "ROADMAP_2.0.ko.md",
    "VALIDATION_2.0.ko.md",
    "FLOW_2.0.ko.svg",
)


class PlanParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.fragments: list[str] = []
        self.headings: list[tuple[str, str]] = []
        self.nav_links: list[tuple[str, str]] = []
        self.nav_labels: dict[str, str] = {}
        self.links: list[tuple[str, str]] = []
        self.nav_details = 0
        self.summary_controls = 0
        self.external_loads = 0
        self._in_summary = False
        self._in_nav = False
        self._heading_tag: str | None = None
        self._heading_id: str | None = None
        self._heading_text: list[str] = []
        self._link_target: str | None = None
        self._link_in_nav = False
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"] or "")
        if tag == "a":
            self._start_link(attributes)
        if tag == "nav" and attributes.get("aria-label") == "문서 목차":
            self._in_nav = True
        if (
            tag == "script"
            or attributes.get("src")
            or (tag == "link" and attributes.get("rel") == "stylesheet")
        ):
            self.external_loads += 1
        if self._in_nav and tag == "details":
            self.nav_details += 1
        if self._in_nav and tag == "summary":
            self._in_summary = True
        if self._in_summary and tag in {"a", "button", "input"}:
            self.summary_controls += 1
        if tag in {"h2", "h3"}:
            self._heading_tag = tag
            self._heading_id = attributes.get("id")
            self._heading_text = []

    def _start_link(self, attributes: dict[str, str | None]) -> None:
        target = attributes.get("href")
        if target and target.startswith("#"):
            self.fragments.append(target[1:])
        self._link_target = target
        self._link_text = []
        self._link_in_nav = self._in_nav
        if self._in_nav and target and attributes.get("aria-label"):
            self.nav_labels[target] = attributes["aria-label"] or ""

    def handle_data(self, data: str) -> None:
        if self._heading_id is not None:
            self._heading_text.append(data)
        if self._link_target is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_tag and self._heading_id is not None:
            self.headings.append((self._heading_id, "".join(self._heading_text)))
            self._heading_id = None
            self._heading_tag = None
        if tag == "a" and self._link_target is not None:
            item = (self._link_target, "".join(self._link_text))
            self.links.append(item)
            if self._link_in_nav:
                self.nav_links.append(item)
            self._link_target = None
        if tag == "nav":
            self._in_nav = False
        if tag == "summary":
            self._in_summary = False


class RenderPlanNavigationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="opensocrates-plan-nav-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.docs = root / "docs" / "v2.0"
        self.docs.mkdir(parents=True)
        (root / "tools").mkdir()
        shutil.copy2(ROOT / "tools" / "render_v2_plan.py", root / "tools")
        for name in FILES:
            shutil.copy2(ROOT / "docs" / "v2.0" / name, self.docs)
        self.renderer = root / "tools" / "render_v2_plan.py"

    def render(self) -> PlanParser:
        subprocess.run([sys.executable, str(self.renderer)], check=True, capture_output=True)
        parser = PlanParser()
        parser.feed((self.docs / "PLAN_2.0.ko.html").read_text(encoding="utf-8"))
        return parser

    def test_navigation_covers_headings_without_duplicate_targets(self) -> None:
        page = self.render()
        markdown = MarkdownIt("commonmark")
        expected = sum(
            token.type == "heading_open" and token.tag in {"h2", "h3"}
            for name in FILES[:-1]
            for token in markdown.parse((self.docs / name).read_text(encoding="utf-8"))
        )
        self.assertEqual(len(page.ids), len(set(page.ids)))
        self.assertTrue(set(page.fragments).issubset(set(page.ids)))
        self.assertIn("content", page.fragments)
        self.assertEqual(page.nav_details, 4)
        self.assertEqual(page.summary_controls, 0)
        self.assertEqual(page.external_loads, 0)
        self.assertEqual(len(page.headings), expected)
        self.assertEqual(
            set(page.headings),
            {(target[1:], text) for target, text in page.nav_links if "-section-" in target},
        )
        self.assertEqual(len(page.headings) + 4, len(page.nav_links))
        targets = {text: target for target, text in page.links}
        heading_ids = {title: anchor for anchor, title in page.headings}
        self.assertEqual(
            targets["두 업무 합성 가이드 사례"],
            "#" + heading_ids["두 업무에서 만들어진 후보와 현재 요청: 합성 사례"],
        )
        self.assertEqual(
            targets["시스템 설계 §12–14"],
            "#" + heading_ids["12. 공통 가이드 생성 지침의 작업 초안"],
        )

    def test_duplicate_and_inserted_headings_keep_existing_targets(self) -> None:
        before = self.render()
        vision = self.docs / "VISION_2.0.ko.md"
        text = vision.read_text(encoding="utf-8")
        text = text.replace(
            "## 제품이 제공할 경험",
            "## 특별 < 제목 & **강조**\n\n## 특별 < 제목 & **강조**\n\n## 제품이 제공할 경험",
            1,
        )
        vision.write_text(text, encoding="utf-8")
        after = self.render()
        self.assertTrue(set(before.headings).issubset(set(after.headings)))
        duplicates = [anchor for anchor, title in after.headings if title == "특별 < 제목 & 강조"]
        self.assertEqual(len(duplicates), 2)
        self.assertNotEqual(duplicates[0], duplicates[1])
        self.assertIn("2번째", after.nav_labels["#" + duplicates[1]])
        self.assertTrue(
            {(anchor, "특별 < 제목 & 강조") for anchor in duplicates}.issubset(
                {(target[1:], title) for target, title in after.nav_links}
            )
        )

    def test_renumbering_does_not_change_a_section_target(self) -> None:
        before = self.render()
        system = self.docs / "SYSTEM_2.0.ko.md"
        text = system.read_text(encoding="utf-8").replace("## 1. 구현 경계", "## 9. 구현 경계", 1)
        system.write_text(text, encoding="utf-8")
        after = self.render()
        old_id = next(anchor for anchor, title in before.headings if title == "1. 구현 경계")
        new_id = next(anchor for anchor, title in after.headings if title == "9. 구현 경계")
        self.assertEqual(old_id, new_id)

    def test_specific_link_rejects_ambiguous_target(self) -> None:
        system = self.docs / "SYSTEM_2.0.ko.md"
        text = system.read_text(encoding="utf-8")
        text += "\n### 두 업무에서 만들어진 후보와 현재 요청: 합성 사례\n"
        system.write_text(text, encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.render()
        self.assertIn(b"missing or ambiguous", caught.exception.stderr)


if __name__ == "__main__":
    unittest.main()
