#!/bin/sh
set -eu
root=$(pwd)
tmp="$root/.owned-temp/process-check"
mkdir -p "$tmp"
db="$tmp/shared.sqlite"
rm -f "$db" "$db-wal" "$db-shm" "$tmp/a.out" "$tmp/b.out" "$tmp/c.out"
./bin/queueforge --addr 127.0.0.1:0 --db "$db" >"$tmp/a.out" 2>"$tmp/a.err" &
a=$!
./bin/queueforge --addr 127.0.0.1:0 --db "$db" >"$tmp/b.out" 2>"$tmp/b.err" &
b=$!
cleanup(){ kill -KILL "$a" "$b" 2>/dev/null || true; wait "$a" 2>/dev/null || true; wait "$b" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
i=0
while [ ! -s "$tmp/a.out" ] || [ ! -s "$tmp/b.out" ]; do i=$((i+1)); [ "$i" -lt 100 ] || exit 1; sleep .05; done
pa=$(sed -n 's/.*"port":\([0-9][0-9]*\).*/\1/p' "$tmp/a.out")
pb=$(sed -n 's/.*"port":\([0-9][0-9]*\).*/\1/p' "$tmp/b.out")
create=$(curl -fsS -X POST "http://127.0.0.1:$pa/v1/jobs" -H 'X-Tenant-ID: p' -H 'Idempotency-Key: shared' -H 'Content-Type: application/json' --data '{"queue":"q","payload":{"n":1}}')
replay=$(curl -fsS -X POST "http://127.0.0.1:$pb/v1/jobs" -H 'X-Tenant-ID: p' -H 'Idempotency-Key: shared' -H 'Content-Type: application/json' --data '{"queue":"q","payload":{"n":1}}')
printf '%s\n%s\n' "$create" "$replay"
printf '%s' "$create" | rg -q '"replayed":false'
printf '%s' "$replay" | rg -q '\"replayed\":true'
curl -fsS -X POST "http://127.0.0.1:$pa/v1/jobs" -H 'X-Tenant-ID: p' -H 'Idempotency-Key: race' -H 'Content-Type: application/json' --data '{"queue":"q","payload":{"n":2}}' >"$tmp/r1.out" &
r1=$!
curl -fsS -X POST "http://127.0.0.1:$pb/v1/jobs" -H 'X-Tenant-ID: p' -H 'Idempotency-Key: race' -H 'Content-Type: application/json' --data '{"queue":"q","payload":{"n":2}}' >"$tmp/r2.out" &
r2=$!
wait "$r1"
wait "$r2"
cat "$tmp/r1.out" "$tmp/r2.out"
kill -KILL "$a" "$b"
wait "$a" || true
wait "$b" || true
./bin/queueforge --addr 127.0.0.1:0 --db "$db" >"$tmp/c.out" 2>"$tmp/c.err" &
c=$!
trap 'kill -TERM "$c" 2>/dev/null || true; wait "$c" 2>/dev/null || true' EXIT INT TERM
i=0
while [ ! -s "$tmp/c.out" ]; do i=$((i+1)); [ "$i" -lt 100 ] || exit 1; sleep .05; done
pc=$(sed -n 's/.*"port":\([0-9][0-9]*\).*/\1/p' "$tmp/c.out")
stats=$(curl -fsS "http://127.0.0.1:$pc/v1/stats" -H 'X-Tenant-ID: p')
printf '%s\n' "$stats"
printf '%s' "$stats" | rg -q '"total":2'
