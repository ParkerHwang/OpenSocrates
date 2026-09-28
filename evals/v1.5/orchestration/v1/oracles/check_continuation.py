"""Check documentation-only continuation against exact qualified prior source."""

import ast
import json
import sys
from pathlib import Path


def without_docstring(text):
    tree = ast.parse(text)
    doc = ast.get_docstring(tree, clean=False)
    if doc is None:
        return text.lstrip("\n"), None
    node = tree.body[0]
    data = text.encode("utf-8")
    lines = data.splitlines(keepends=True)
    start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
    end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
    return (data[:start] + data[end:]).decode("utf-8").lstrip("\n"), doc


current = Path(sys.argv[1]).read_text()
prior = Path(sys.argv[2]).read_text()
current_body, current_doc = without_docstring(current)
prior_body, prior_doc = without_docstring(prior)
required_terms = ("effective date", "null", "zero", "missing")
passed = (
    current_body == prior_body
    and current_doc is not None
    and current_doc != prior_doc
    and all(term in current_doc.casefold() for term in required_terms)
)
print(json.dumps({"check": "documentation_only_continuation", "passed": passed}))
raise SystemExit(0 if passed else 1)
