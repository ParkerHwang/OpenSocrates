# Measurement repair 2

The original closed-loop dispatcher started its three-second drain timer when it
launched worker goroutines. It cancelled them at the warmup boundary, before the
measurement window. All six executed version-1 cells are invalid performance
observations; they remain unchanged. The other version-1 scheduled rows were
skipped after that failure, even where the old coordinator says `seed unavailable`.

The repair anchors the drain deadline to the end of warmup plus measurement. A
new 3-second warmup / 8-second closed-loop mock regression requires actual timed
successes, at least 11 seconds elapsed, and no drain cancellation. Existing
arrival, timeout/drain, malformed-response, lifecycle and timing controls remain.

No candidate code, instructions, model call or historical observation is changed.
All nine development calls are complete. Stage 3 received invalid/unavailable
preliminary performance feedback, so its edits cannot be characterized as
optimization informed by a valid external benchmark. Corrected measurements of
the already frozen stage-2 and stage-3 binaries are made after development.

`manifest.json` is frozen before these corrected measurements. It binds the
original protocol, repaired tools, six binaries/source receipts, and six existing
publicly seeded databases and reference lists. The original 18 preliminary and
81 final schedules, resource limits and stop rules are retained. There is no
automatic retry after a new broken cell. Reused seeds are copied per cell and are
never mutated. Read-only verification hashes all bound files before and after.

The new coordinator labels a stopped arm explicitly instead of calling its seed
unavailable. Numeric timing JSON is losslessly compressed with gzip level 1 and
digests. Only owned stopped cell databases are removed after retaining metrics,
conservation and file digests. Original version-1 evidence is untouched.

Qualification stays unchanged: the candidate's failing self-test remains a failed
artifact gate even if a separate review diagnoses an obsolete assertion. Load
figures for that artifact are diagnostic and cannot silently become qualified.
