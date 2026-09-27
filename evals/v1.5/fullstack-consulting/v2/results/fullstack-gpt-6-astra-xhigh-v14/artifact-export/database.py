"""SQLite lifecycle. Each request owns its connection and transaction."""
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3

ROOT = Path(__file__).resolve().parent


def connect(path):
    db = sqlite3.connect(path, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA synchronous=FULL')
    db.create_function('casefold', 1, lambda s: s.casefold(), deterministic=True)
    return db


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 240_000).hex()


def initialize(data_dir, seed=False):
    directory = Path(data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'depotflow.sqlite3'
    db = connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript((ROOT / 'schema.sql').read_text())
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('cursor_secret', secrets.token_hex(32)))
        db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('schema_version', '1'))
        # Existing organizations are the durable seed guard; stock is never topped up.
        if seed and not db.execute('SELECT 1 FROM tenants LIMIT 1').fetchone():
            for tenant in ('north', 'south'):
                db.execute('INSERT INTO tenants VALUES (?)', (tenant,))
                for role in ('admin', 'operator', 'viewer'):
                    salt = secrets.token_hex(16)
                    db.execute('INSERT INTO users VALUES (?,?,?,?,?)',
                               (f'{role}@{tenant}.example', tenant, role, salt,
                                password_hash('DepotDemo!2026', salt)))
                for sku, name, stock, price in [('BOLT', 'Steel bolt kit', 100, 1250),
                                               ('CABLE', 'Cable assembly', 60, 2499),
                                               ('SAMPLE', 'Sample pack', 20, 0)]:
                    db.execute('INSERT INTO inventory VALUES (?,?,?,?,?,?,?)',
                               (tenant, sku, name, stock, 0, price, 1))
        db.commit()
    finally:
        db.close()
    os.chmod(path, 0o600)
    return path
