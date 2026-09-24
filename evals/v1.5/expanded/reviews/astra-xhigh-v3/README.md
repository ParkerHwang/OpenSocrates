# Provisional Astra evidence continuation

This is a new immutable execution manifest for the evidence phase of the
[60-packet review](../astra-xhigh-v2/README.md). It preserves all original first-pass
judgments and the completed A01 evidence assessment. It does not rerun outcome
cells, repair candidate artifacts, rewrite the rubric or replace old scores.

The exact user-provided `opensocrates_bilingual_reviewer` configuration remains
`gpt-6-astra` / `xhigh` / `read-only`. Its definition, derived runtime profile,
client and schema bytes are unchanged from v2. Every call still uses a fresh,
disposable, isolated context containing only its assigned packet views, the fixed
rubric, its own locked first-pass objects and corresponding opaque evidence.
The original user agent file remains untouched.

Two v2 four-packet evidence calls hit the frozen 900-second limit without a
completed assessment. The integrator stopped the coordinator and the next two
active calls to prevent repeated unchanged dispatch. All four attempts remain
in v2, with missing usage explicitly null. Input hashes were unchanged; disposable
credential copies and profiles were removed. The two previously completed A01
packet assessments remain valid and are not rerun. This does not establish the
precise cause of the longer calls.

V3 partitions the remaining 58 packets into 30 assignments of one or two packets,
retaining their original order and language separation. Projected first-pass files
change only the envelope assignment ID and selected packet list; every retained
packet object is identical to its original locked judgment. The manifest pins the
original and projected files. Three calls may run concurrently, each still bounded
to 900 seconds and 256 KiB of returned text. One fresh same-tuple format/citation
retry is allowed; no semantic feedback or artifact repair is permitted. The
dispatcher submits only the active window and stops new dispatch after a terminal
failure. Already-running calls finish within their original limits.

The prompt asks for complete evidence reads without repeated schema/role dumps.
It does not change scoring anchors, omit required fields, or treat shorter text as
less internal reasoning. The first-pass scores, gates, findings and blinding state
must remain exact. Separate post-evidence fields preserve all revisions and
disagreements. All original 60 first passes were locked before any disclosure;
all 60 evidence assessments must lock before analytical unblinding.

Human scores remain unavailable. These are provisional judgments from one Astra
configuration across fresh contexts. Local memory restrictions do not prove
account-side isolation, and requested client identity is not an independent backend
echo. No profile promotion, held-out margin, sample-size claim or release follows.

After committing this manifest, `python3 evals/v1.5/expanded/reviews/astra-xhigh-v3/review.py evidence`
runs the authorized continuation. The integrator owns validation and persistence;
the reviewer cannot modify files, invoke other agents, rerun candidate checks or
access treatment maps. All attempts and nulls belong in the final joined ledger.
