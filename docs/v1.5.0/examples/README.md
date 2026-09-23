# Synthetic contract examples

These examples are specification fixtures only. UUIDs, paths, timestamps, and
digests are illustrative; they do not describe real observations or completed
work. A valid JSON file is not evidence of a working runtime or a finalized schema.

- [Observation record](observation-record.json): source observation separated from lifecycle and freshness.
- [Checkpoint request](checkpoint-request.json): bounded resumable task state with reported execution status.
- [Context pack](context-pack.json): scoped evidence, uncertainty, and an unverified application state.

The implementation must generate strict schemas and add positive/negative tests
for these contracts. In particular, agent submissions cannot set runtime-owned
evidence fields merely because a response example contains them.
