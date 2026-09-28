CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
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
  tenant TEXT NOT NULL REFERENCES tenants(id), sku TEXT NOT NULL, name TEXT NOT NULL,
  on_hand INTEGER NOT NULL CHECK(typeof(on_hand)='integer' AND on_hand BETWEEN 0 AND 9007199254740991),
  reserved INTEGER NOT NULL DEFAULT 0 CHECK(typeof(reserved)='integer' AND reserved BETWEEN 0 AND on_hand),
  price_cents INTEGER NOT NULL CHECK(typeof(price_cents)='integer' AND price_cents BETWEEN 0 AND 9007199254740991),
  version INTEGER NOT NULL DEFAULT 1 CHECK(typeof(version)='integer' AND version > 0),
  PRIMARY KEY(tenant,sku)
);
CREATE TABLE IF NOT EXISTS orders (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
  tenant TEXT NOT NULL REFERENCES tenants(id), client_ref TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('draft','reserved','shipped','cancelled','returned')),
  version INTEGER NOT NULL DEFAULT 1 CHECK(typeof(version)='integer' AND version > 0),
  total_cents INTEGER NOT NULL CHECK(typeof(total_cents)='integer' AND total_cents BETWEEN 0 AND 9007199254740991),
  UNIQUE(tenant,client_ref), UNIQUE(tenant,id)
);
CREATE INDEX IF NOT EXISTS orders_tenant_seq ON orders(tenant,seq);
CREATE INDEX IF NOT EXISTS orders_tenant_status_seq ON orders(tenant,status,seq);
CREATE TABLE IF NOT EXISTS order_lines (
  tenant TEXT NOT NULL, order_id TEXT NOT NULL, position INTEGER NOT NULL,
  sku TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity > 0),
  unit_price_cents INTEGER NOT NULL CHECK(typeof(unit_price_cents)='integer' AND unit_price_cents >= 0),
  returned_quantity INTEGER NOT NULL DEFAULT 0 CHECK(typeof(returned_quantity)='integer' AND returned_quantity BETWEEN 0 AND quantity),
  PRIMARY KEY(tenant,order_id,sku),
  FOREIGN KEY(tenant,order_id) REFERENCES orders(tenant,id),
  FOREIGN KEY(tenant,sku) REFERENCES inventory(tenant,sku)
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL REFERENCES tenants(id),
  action TEXT NOT NULL, entity_id TEXT NOT NULL,
  actor TEXT NOT NULL REFERENCES users(email), created_at TEXT NOT NULL,
  details TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_tenant_id ON audit(tenant,id);
CREATE TABLE IF NOT EXISTS order_status_history (
  tenant TEXT NOT NULL, order_id TEXT NOT NULL,
  audit_id INTEGER NOT NULL REFERENCES audit(id),
  status TEXT NOT NULL CHECK(status IN ('draft','reserved','shipped','cancelled','returned')),
  PRIMARY KEY(tenant,order_id,audit_id),
  FOREIGN KEY(tenant,order_id) REFERENCES orders(tenant,id)
);
CREATE TABLE IF NOT EXISTS idempotency (
  tenant TEXT NOT NULL REFERENCES tenants(id), key TEXT NOT NULL,
  fingerprint TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY(tenant,key)
);
