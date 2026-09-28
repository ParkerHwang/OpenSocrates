# Project notes

Implement the synthetic AuditLedger contract with tenant isolation, atomic durable changes, retry identity, and preserved legacy evidence. Do not deploy, call other models, or change global settings. Recheck source facts rather than treating prior notes as current evidence.

Current state (2026-09-27): the Go service uses SQLite transactions for writes, stores idempotent responses with effects, and imports v1 rows in a transaction. Entry sequence allocation is tenant local. Historical summaries derive from entries using exact integer accumulation. Request field names are checked exactly, including nested batch items. README documents schema, transaction boundaries, migration, and run commands.

Verified here: Go 1.26.3 build, `go test ./...`, `go vet ./...`, localhost endpoint flows, exact JSON field validation, two-process retries and distinct writes, restart replay, legacy import/reversal/restart, simultaneous empty/v1 migration startup, rollback after an invalid migration, and clean SIGTERM shutdown. The external performance meter was not run in this call. Keep task, tools, and legacy fixtures unchanged; do not retain raw prompts, transcripts, source copies, or private reasoning in memory.
