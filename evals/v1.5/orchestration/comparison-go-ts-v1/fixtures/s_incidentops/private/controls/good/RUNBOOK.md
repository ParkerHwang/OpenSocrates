# IncidentOps local runbook

Use a disposable directory and a local SQLite path. The Go service runs on loopback from `INCIDENTOPS_ADDR`; set `INCIDENTOPS_DB` to a writable local file. The server establishes WAL and FULL synchronous mode at startup and migrates the basic starter schema, then reconciles existing accepted ledgers. It refuses a database whose existing ledger has invalid transitions, leaving the files for inspection.

Compile the Go package and TypeScript frontend from the pinned module and npm lock in the qualified local dependency environment. Run Go tests. Start the server, create tenant-scoped policies and on-call intervals, submit events, and inspect `/api/incidents`, `/api/summary`, and `/api/outbox`. `/api/outbox` is a fake local delivery queue; no worker sends messages. Use the browser to verify that filter changes issue actual GET requests and that an operator action returns from the API before the row changes.

For a restart check, stop the service cleanly and restart it with the same database path. Do not copy a live WAL file without its database and SHM companion. The external qualification script uses fresh disposable copies, keeps failed copies available for debugging, and measures seeded reads and writes separately from functional tests.
