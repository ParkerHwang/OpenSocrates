# Integrator-authored derivative repair

Original demonstration commit: `288cee2ff6b96390d2da32541d4c3e1ab2a45116`.
Repair branch: `repairs/v1`. The original application, protocol, evaluation and
historical scores remain unchanged. This derivative contains human-directed
integrator code repairs; it is not an unassisted outcome of the original model run.

Run `npm test` from this directory. Local HTTP tests require loopback binding.
Tests cover direct transitions, service/CLI/HTTP date boundaries, persisted-byte
rollback, batch failure positions, replay, cumulative refunds and output ownership.

Partial return requires an explicit valid date; full return retains the omitted
scheduled-end default. Both commands and batches operate on a private owned draft,
with detached per-operation snapshots and replay data. A normalized v2 batch
clones the full working store once; migration still has its own copy boundary.
Clone counts alone do not demonstrate a wall-time or throughput speedup.
