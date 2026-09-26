# AuditLedger

A Go HTTP service backed by SQLite (`modernc.org/sqlite v1.59.0`). Build with `go build -o server ./cmd/server`, then run `./server --db ledger.db --listen 127.0.0.1:8080`. Tenant identity is supplied in `X-Tenant`; writes require `Idempotency-Key`.

The schema in `internal/platform/api.go` stores current accounts, append-only tenant entries, transfer and hold state, and successful idempotency responses. Writes use SQLite transactions; entry history is queried by tenant-local snapshot sequence. Startup checks `PRAGMA user_version` and migrates v1 rows in one transaction: infer openings from final account balances and movements, preserve legacy tables, import movements in ID order, and advance to v2. New databases are initialized at v2. SQLite WAL and database transactions allow multiple service processes to share a file.
