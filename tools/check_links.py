#!/usr/bin/env python3
"""Check repository-local Markdown and HTML links without network access."""

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import unquote, urlsplit

DEFAULT_PATHS = (
    "README.md",
    "README.ko.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".github/release-notes",
)
MARKDOWN_LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))")
REFERENCE_LINK = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))", re.MULTILINE)
HTML_LINK = re.compile(r"\bhref\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
HTML_ID = re.compile(r"<(?:a|[a-z][a-z0-9]*)\b[^>]*\bid=['\"]([^'\"]+)['\"]", re.IGNORECASE)
EXTERNAL_SCHEMES = {"http", "https", "ftp", "mailto", "tel"}


class LinkCheckError(RuntimeError):
    """Raised for invalid checker configuration."""


@dataclass(frozen=True)
class Link:
    source: str
    line: int
    target: str


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(value), encoding="utf-8")


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _slugify(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[`*_~]", "", value)
    value = html.unescape(value).strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^\w\- ]+", "", value, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", value).strip("-")


def _headings(path: Path) -> set[str]:
    anchors: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return anchors
    counts: dict[str, int] = {}
    for line in text.splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        base = _slugify(match.group(2))
        if not base:
            continue
        index = counts.get(base, 0)
        counts[base] = index + 1
        anchors.add(base if index == 0 else f"{base}-{index}")
    for match in HTML_ID.finditer(text):
        anchors.add(unquote(match.group(1)).lower())
    return anchors


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _extract_links(path: Path, root: Path) -> list[Link]:
    relative = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8")
    links: list[Link] = []
    for match in MARKDOWN_LINK.finditer(text):
        target = match.group(1) or match.group(2)
        if target:
            links.append(Link(relative, _line_number(text, match.start()), target))
    for match in REFERENCE_LINK.finditer(text):
        target = match.group(2) or match.group(3)
        if target:
            links.append(Link(relative, _line_number(text, match.start()), target))
    for match in HTML_LINK.finditer(text):
        links.append(
            Link(
                relative,
                _line_number(text, match.start()),
                html.unescape(match.group(1)),
            )
        )
    return links


def _iter_markdown(root: Path, selected: list[str] | None) -> list[Path]:
    values = selected or list(DEFAULT_PATHS)
    files: list[Path] = []
    for value in values:
        path = _resolve(root, value)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise LinkCheckError(f"link-check path escapes repository root: {value}") from exc
        if not path.exists():
            raise LinkCheckError(f"link-check path does not exist: {value}")
        if path.is_file():
            if path.suffix.lower() in {".md", ".markdown", ".html", ".htm"}:
                files.append(path)
        else:
            files.extend(
                item
                for item in path.rglob("*")
                if item.is_file() and item.suffix.lower() in {".md", ".markdown", ".html", ".htm"}
            )
    return sorted(set(files))


def _is_external(target: str) -> bool:
    parsed = urlsplit(target)
    return parsed.scheme.lower() in EXTERNAL_SCHEMES or target.startswith("//")


def _check_link(root: Path, link: Link) -> tuple[dict[str, Any] | None, bool]:
    target = link.target.strip()
    if not target or target.startswith("javascript:") or target.startswith("data:"):
        return {
            "source": link.source,
            "line": link.line,
            "reason": "unsafe_link_scheme",
        }, False
    if _is_external(target):
        return None, True
    parsed = urlsplit(target)
    if parsed.scheme:
        return {
            "source": link.source,
            "line": link.line,
            "reason": "unsupported_link_scheme",
        }, False
    path_part = unquote(parsed.path)
    source_path = root / link.source
    if path_part:
        candidate = (
            root / path_part.lstrip("/")
            if path_part.startswith("/")
            else source_path.parent / path_part
        )
        resolved = candidate.resolve()
    else:
        resolved = source_path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return {
            "source": link.source,
            "line": link.line,
            "reason": "link_escapes_repository",
        }, False
    if not resolved.exists():
        return {
            "source": link.source,
            "line": link.line,
            "reason": "target_missing",
        }, False
    fragment = unquote(parsed.fragment).strip().lower()
    if (
        fragment
        and resolved.is_file()
        and resolved.suffix.lower() in {".md", ".markdown", ".html", ".htm"}
    ):
        if fragment not in _headings(resolved):
            return {
                "source": link.source,
                "line": link.line,
                "reason": "anchor_missing",
            }, False
    return None, False


def check(root: Path, selected: list[str] | None) -> dict[str, Any]:
    files = _iter_markdown(root, selected)
    failures: list[dict[str, Any]] = []
    checked = 0
    external = 0
    for path in files:
        try:
            links = _extract_links(path, root)
        except (OSError, UnicodeError):
            failures.append(
                {
                    "source": path.relative_to(root).as_posix(),
                    "line": 1,
                    "reason": "document_unreadable",
                }
            )
            continue
        for link in links:
            checked += 1
            failure, is_external = _check_link(root, link)
            external += int(is_external)
            if failure:
                failures.append(failure)
    return {
        "schema": "opensocrates.link-check-evidence/1.0.0",
        "generated_at": _iso_now(),
        "documents": len(files),
        "checked_links": checked,
        "external_links_not_fetched": external,
        "failures": failures,
        "status": "pass" if not failures else "fail",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument(
        "--path",
        action="append",
        help="Markdown/HTML file or directory, relative to root; repeatable",
    )
    parser.add_argument("--report", help="machine-readable evidence JSON path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _resolve(Path.cwd(), args.root)
    report_path = _resolve(root, args.report or "build/evidence/links.json")
    try:
        report = check(root, args.path)
        status = 0 if report["status"] == "pass" else 1
    except LinkCheckError as exc:
        report = {
            "schema": "opensocrates.link-check-evidence/1.0.0",
            "generated_at": _iso_now(),
            "status": "blocked",
            "reason": str(exc)[:240],
        }
        status = 2
    _write_json(report_path, report)
    print(_canonical_json(report), end="")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
