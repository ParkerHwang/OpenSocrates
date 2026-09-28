import hashlib
import secrets
import sqlite3
from pathlib import Path

PASSWORD_ROUNDS = 240_000


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), PASSWORD_ROUNDS).hex()


def connect(path):
    db = sqlite3.connect(path, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA synchronous=FULL')
    db.create_function('casefold', 1, str.casefold, deterministic=True)
    return db


def initialize(path, seed=False):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript(Path(__file__).with_name('schema.sql').read_text())
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('cursor_secret', secrets.token_hex(32)))
        if seed and db.execute('SELECT COUNT(*) FROM tenants').fetchone()[0] == 0:
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
                    db.execute('INSERT INTO inventory(tenant,sku,name,on_hand,price_cents) VALUES (?,?,?,?,?)',
                               (tenant, sku, name, stock, price))
        db.commit()
    finally:
        db.close()
