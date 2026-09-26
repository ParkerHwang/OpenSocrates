# Starter

`go build -o server ./cmd/server` currently builds a deliberate TODO executable.
Implement the API described in the task. This driver wrapper is generic and
contains no schema or business logic. Dependency downloads are ordinary build
setup, not a reference solution. `python3 legacy/produce.py /tmp/legacy.db`
creates the original v1 schema and rows. Do not overwrite an existing database.
