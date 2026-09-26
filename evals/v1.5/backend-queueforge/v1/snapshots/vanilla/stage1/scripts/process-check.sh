#!/bin/sh
set -eu
base=.owned-temp/process-check
mkdir -p "$base"
rm -f "$base"/live.sqlite "$base"/live.sqlite-shm "$base"/live.sqlite-wal "$base"/a.port "$base"/b.port "$base"/c.port
full_db="$(pwd)/$base/live.sqlite"
./bin/queueforge --addr 127.0.0.1:0 --db "$full_db" > "$base/a.port" 2> "$base/a.err" &
a=$!
./bin/queueforge --addr 127.0.0.1:0 --db "$full_db" > "$base/b.port" 2> "$base/b.err" &
b=$!
cleanup(){ kill "$a" "$b" 2>/dev/null || true; if [ "${c:-}" != "" ]; then kill "$c" 2>/dev/null || true; fi; wait "$a" "$b" 2>/dev/null || true; if [ "${c:-}" != "" ]; then wait "$c" 2>/dev/null || true; fi; }
trap cleanup EXIT
n=0
while [ ! -s "$base/a.port" ] || [ ! -s "$base/b.port" ]; do n=$((n+1)); [ "$n" -lt 100 ] || exit 1; sleep 0.05; done
pa=$(jq -r .port "$base/a.port")
pb=$(jq -r .port "$base/b.port")
aurl="http://127.0.0.1:$pa"
burl="http://127.0.0.1:$pb"
first=$(curl -fsS "$aurl/v1/jobs" -H 'X-Tenant-ID: tenant' -H 'Idempotency-Key: k1' -H 'Content-Type: application/json' --data '{"queue":"q","payload":{"n":1}}')
second=$(curl -fsS "$burl/v1/jobs" -H 'X-Tenant-ID: tenant' -H 'Idempotency-Key: k2' -H 'Content-Type: application/json' --data '{"queue":"q","payload":{"n":2}}')
id1=$(printf '%s' "$first" | jq -r .job.id)
id2=$(printf '%s' "$second" | jq -r .job.id)
claim1=$(curl -fsS "$aurl/v1/queues/q/claim" -H 'X-Tenant-ID: tenant' -H 'Content-Type: application/json' --data '{"worker_id":"a","lease_ms":10000}')
claim2=$(curl -fsS "$burl/v1/queues/q/claim" -H 'X-Tenant-ID: tenant' -H 'Content-Type: application/json' --data '{"worker_id":"b","lease_ms":10000}')
c1=$(printf '%s' "$claim1" | jq -r .job.id)
c2=$(printf '%s' "$claim2" | jq -r .job.id)
[ "$c1" != "$c2" ]
[ "$c1" = "$id1" ]
[ "$c2" = "$id2" ]
kill -KILL "$a" "$b"
wait "$a" "$b" 2>/dev/null || true
./bin/queueforge --addr 127.0.0.1:0 --db "$full_db" > "$base/c.port" 2> "$base/c.err" &
c=$!
n=0
while [ ! -s "$base/c.port" ]; do n=$((n+1)); [ "$n" -lt 100 ] || exit 1; sleep 0.05; done
pc=$(jq -r .port "$base/c.port")
stats=$(curl -fsS "http://127.0.0.1:$pc/v1/stats" -H 'X-Tenant-ID: tenant')
[ "$(printf '%s' "$stats" | jq -r .total)" = 2 ]
[ "$(printf '%s' "$stats" | jq -r .leased)" = 2 ]
printf 'two-process claim IDs: %s %s; restart stats: %s\n' "$c1" "$c2" "$stats"
