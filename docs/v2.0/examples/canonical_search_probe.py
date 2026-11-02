"""Explore literal Korean FTS matching, not the OpenSocrates selector.

Uses public repository content and an in-memory SQLite database only. Candidate
targets are hand-selected examples, not a gold-standard relevance benchmark.
"""

import json
import sqlite3
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    methods = root / "content" / "methods"
    examples = [
        ("premortem-analysis", "실패"),
        ("premortem-analysis", "실패할"),
        ("premortem-analysis", "뭐가 망할지"),
        ("root-cause-analysis", "원인"),
        ("root-cause-analysis", "근본원인"),
        ("stakeholder-analysis", "이해관계자"),
        ("stakeholder-analysis", "이해관계자의"),
    ]
    records = []
    for metadata_path in sorted(methods.glob("*/method.yaml")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        procedure = metadata_path.with_name("procedure.ko.md").read_text(encoding="utf-8")
        records.append((metadata["id"], metadata["display_name"]["ko"] + "\n" + procedure))
    if len(records) != 48:
        raise RuntimeError(f"Expected 48 canonical methods, found {len(records)}")

    with sqlite3.connect(":memory:") as conn:
        for tokenizer in ("unicode61", "trigram"):
            conn.execute(
                f"CREATE VIRTUAL TABLE {tokenizer} "
                f"USING fts5(method_id UNINDEXED, body, tokenize='{tokenizer}')"
            )
            conn.executemany(f"INSERT INTO {tokenizer} VALUES (?, ?)", records)
        print(f"SQLite {sqlite3.sqlite_version}; methods={len(records)}; literal phrase MATCH")
        for method_id, query in examples:
            # Quote the entire example: this measures literal phrase matching,
            # not token expansion, semantic relevance, or a real user request.
            phrase = '"' + query.replace('"', '""') + '"'
            outcomes = []
            for tokenizer in ("unicode61", "trigram"):
                rows = conn.execute(
                    f"SELECT method_id FROM {tokenizer} WHERE {tokenizer} MATCH ?",
                    (phrase,),
                ).fetchall()
                ids = {row[0] for row in rows}
                outcomes.append(
                    f"{tokenizer}={len(ids)} target={'yes' if method_id in ids else 'no'}"
                )
            print(f"{query!r} target={method_id}: {'; '.join(outcomes)}")


if __name__ == "__main__":
    main()
