import hashlib
import os
import secrets
import sqlite3
from contextlib import closing
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tenants (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY, tenant TEXT NOT NULL REFERENCES tenants(id),
    role TEXT NOT NULL CHECK(role IN ('admin','operator','viewer')),
    salt TEXT NOT NULL, password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, email TEXT NOT NULL REFERENCES users(email),
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory (
    tenant TEXT NOT NULL REFERENCES tenants(id), sku TEXT NOT NULL,
    name TEXT NOT NULL, on_hand INTEGER NOT NULL CHECK(on_hand BETWEEN 0 AND 1000000000),
    reserved INTEGER NOT NULL CHECK(reserved BETWEEN 0 AND on_hand),
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    version INTEGER NOT NULL CHECK(version >= 1), PRIMARY KEY(tenant,sku)
);
CREATE TABLE IF NOT EXISTS orders (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    tenant TEXT NOT NULL REFERENCES tenants(id), client_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','reserved','shipped','cancelled','returned')),
    version INTEGER NOT NULL CHECK(version >= 1),
    total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
    UNIQUE(tenant,client_ref), UNIQUE(tenant,id)
);
CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant,seq);
CREATE TABLE IF NOT EXISTS order_lines (
    tenant TEXT NOT NULL, order_id TEXT NOT NULL, position INTEGER NOT NULL,
    sku TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
    returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(returned_quantity BETWEEN 0 AND quantity),
    PRIMARY KEY(tenant,order_id,sku),
    FOREIGN KEY(tenant,order_id) REFERENCES orders(tenant,id),
    FOREIGN KEY(tenant,sku) REFERENCES inventory(tenant,sku)
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL REFERENCES tenants(id),
    action TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL,
    created_at TEXT NOT NULL, status TEXT, details TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant,id);
CREATE INDEX IF NOT EXISTS audit_entity_id ON audit(tenant,entity_id,id DESC);
CREATE TABLE IF NOT EXISTS idempotency (
    tenant TEXT NOT NULL REFERENCES tenants(id), key TEXT NOT NULL,
    fingerprint TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(tenant,key)
);
"""


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 210_000).hex()


class Database:
    def __init__(self, directory, seed=False):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'depotflow.sqlite3'
        with closing(self.connect()) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(SCHEMA)
            conn.execute('BEGIN IMMEDIATE')
            conn.execute("INSERT OR IGNORE INTO metadata VALUES ('cursor_secret', ?)",
                         (secrets.token_hex(32),))
            conn.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1')")
            if seed and not conn.execute('SELECT 1 FROM tenants LIMIT 1').fetchone():
                self.seed(conn)
            conn.commit()
        os.chmod(self.path, 0o600)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('PRAGMA busy_timeout=15000')
        conn.create_function('casefold', 1, str.casefold, deterministic=True)
        return conn

    @staticmethod
    def seed(conn):
        for tenant in ('north', 'south'):
            conn.execute('INSERT INTO tenants VALUES (?)', (tenant,))
            for role in ('admin', 'operator', 'viewer'):
                salt = secrets.token_hex(16)
                conn.execute('INSERT INTO users VALUES (?,?,?,?,?)',
                             (f'{role}@{tenant}.example', tenant, role, salt,
                              password_hash('DepotDemo!2026', salt)))
            for sku, name, count, price in (
                ('BOLT', 'Steel bolt kit', 100, 1250),
                ('CABLE', 'Cable assembly', 60, 2499),
                ('SAMPLE', 'Sample pack', 20, 0),
            ):
                conn.execute('INSERT INTO inventory VALUES (?,?,?,?,?,?,1)',
                             (tenant, sku, name, count, 0, price))
