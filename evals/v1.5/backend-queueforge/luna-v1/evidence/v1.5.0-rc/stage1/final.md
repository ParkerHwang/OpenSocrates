Implemented the QueueForge API and documented build, run, and verification commands in [README.md](<WORKSPACE>/README.md). The supplied driver helper/test and exact `go.mod`/`go.sum` remain unchanged.

**Verified:** `go build -o bin/queueforge ./cmd/server`, `go test ./...`, and `./scripts/process-check.sh` passed. The process check confirmed concurrent same-key submissions across two servers return one job, then confirmed both jobs survive SIGKILL and are readable after restart. Focused tests cover tenant isolation, strict validation, atomic batch rejection, lease fencing, heartbeat, deadline equality, max attempts, and completion replay.

The process check’s shell reports the expected SIGKILL notices. The service uses synthetic tenant headers; production authentication, TLS, and job execution are outside scope. No commit was created.
