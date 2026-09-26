# QueueForge

QueueForge is a local, synthetic multi-tenant queue API. SQLite is authoritative; the pinned `modernc.org/sqlite` driver supplies SQLite, `internal/queue` owns persistence and lifecycle transitions, `internal/queue/http.go` implements validation and HTTP responses, and `cmd/server` owns process startup and shutdown. Payloads are stored as JSON and never executed. Tenant IDs are synthetic request context, not production authentication.

Build and run with Go 1.26.3:

```sh
go test ./...
go build -o bin/queueforge ./cmd/server
./bin/queueforge --addr 127.0.0.1:0 --db /absolute/path/queue.sqlite
```

The first stdout line reports the selected port as JSON. Set `--clock-file /absolute/path/millis` to use the file's millisecond timestamp for lease operations. API operations require `X-Tenant-ID`; see `BRIEF.md` for endpoints and limits. SQLite uses WAL, FULL synchronous mode, and schema version 1. The implementation does not include production authentication, payload execution, queue cancellation, or a frontend.
