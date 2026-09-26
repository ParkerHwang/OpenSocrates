#!/usr/bin/env python3
"""Produce an actual old-format database, not a new-format database with a flag."""
import argparse, json, pathlib, sqlite3

def produce(path, fixture=None):
    data = json.loads(pathlib.Path(fixture or pathlib.Path(__file__).with_name("fixture.json")).read_text())
    if pathlib.Path(path).exists():
        raise FileExistsError(path)
    with sqlite3.connect(path) as db:
        db.executescript("""CREATE TABLE legacy_accounts(tenant TEXT, name TEXT, balance INTEGER, PRIMARY KEY(tenant,name));
CREATE TABLE legacy_movements(id INTEGER PRIMARY KEY, tenant TEXT, source TEXT, target TEXT, units INTEGER);
CREATE TABLE legacy_notes(key TEXT PRIMARY KEY, value TEXT);
PRAGMA user_version=1;""")
        db.executemany("INSERT INTO legacy_accounts VALUES(?,?,?)", data["accounts"])
        db.executemany("INSERT INTO legacy_movements VALUES(?,?,?,?,?)", data["movements"])
        db.executemany("INSERT INTO legacy_notes VALUES(?,?)", data["notes"])
    return data

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("database"); p.add_argument("--fixture")
    a = p.parse_args(); produce(a.database, a.fixture)
