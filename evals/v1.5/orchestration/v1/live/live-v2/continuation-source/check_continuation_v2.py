"""Require changed module documentation and exact bytes outside its lines."""

import ast
import json
import sys
from pathlib import Path


def without_docstring(data):
    tree = ast.parse(data.decode("utf-8"))
    doc = ast.get_docstring(tree, clean=False)
    if doc is None:
        return data, None
    node = tree.body[0]
    lines = data.splitlines(keepends=True)
    prefix = lines[node.lineno - 1][:node.col_offset]
    suffix = lines[node.end_lineno - 1][node.end_col_offset:]
    if prefix.strip(b" \t") or suffix.strip(b" \t\r\n"):
        raise ValueError("Docstring must occupy its own complete lines.")
    start = sum(map(len, lines[:node.lineno - 1]))
    end = sum(map(len, lines[:node.end_lineno]))
    return data[:start] + data[end:], doc


try:
    current_body, current_doc = without_docstring(Path(sys.argv[1]).read_bytes())
    prior_body, prior_doc = without_docstring(Path(sys.argv[2]).read_bytes())
    required_terms = ("effective date", "null", "zero", "missing")
    passed = (
        current_body == prior_body
        and current_doc is not None
        and current_doc != prior_doc
        and all(term in current_doc.casefold() for term in required_terms)
    )
except (ValueError, SyntaxError, UnicodeError):
    passed = False
print(json.dumps({"check": "documentation_only_continuation", "passed": passed}))
raise SystemExit(0 if passed else 1)
