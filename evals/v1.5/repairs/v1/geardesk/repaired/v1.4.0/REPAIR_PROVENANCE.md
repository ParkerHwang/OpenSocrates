# Integrator-authored derivative repair

Original demonstration commit: `8769ec1cf8b1f35aa229f57c4c597c41b5dc4d55`.
Repair branch: `repairs/v1`. The original application, protocol, evaluation and
historical scores remain unchanged. This derivative contains human-directed
integrator code repairs; it is not an unassisted outcome of the original model run.

Run `npm test` from this directory. Local HTTP tests require loopback binding.
Tests cover direct transitions, service/CLI/HTTP date boundaries, persisted-byte
rollback, batch failure positions, replay, cumulative refunds and output ownership.

Historical mixed aggregate-only deposits have no defensible line allocation.
Migration marks `depositPlan: null`; partial returns reject with an explicit
validation error. Full return preserves the known aggregate refund. Historical
quote lines with complete nonnegative integer deposits summing to the aggregate
and exact unit divisibility support partial returns. A single homogeneous line
with an exactly divisible aggregate also supports derivation. No current catalog
prices recover historical amounts. New bookings retain quote-line deposits and
the unit deposit plan. Importing additional historical allocation is out of scope.

Awaiting the existing rejection assertion clarifies test lifecycle; no historical
false-green claim is made. Replay data is now detached from saved replay evidence.
