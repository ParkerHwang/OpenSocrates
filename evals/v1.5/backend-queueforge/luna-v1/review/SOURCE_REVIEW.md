# Luna QueueForge source and evidence review

This is the primary integrator's unblinded review after all nine outcome calls.
It is not an independent human score or a new model-judge panel. No generated
artifact was repaired by the integrator. The defects below concern generated
QueueForge applications, not OpenSocrates' own memory database migration.

## Observed progression

| Condition | Initial external scenarios | Extended | Final | Final named domain Go tests |
| --- | --- | --- | --- | ---: |
| Vanilla | 4 pass / 3 fail / 1 unassessable | 13 pass / 5 fail / 1 unassessable | 17 pass / 2 fail | 3 |
| OpenSocrates 1.4 | 5 pass / 3 fail | 16 pass / 3 fail | 16 pass / 3 fail | 0 |
| OpenSocrates 1.5 RC | 8 pass | 18 pass / 1 fail | 18 pass / 1 fail | 13 |

All three final `go test -race ./...` invocations pass. This is not the same as
all required behavior passing: 1.4's Go suite contains only the supplied driver
test. It also runs separate loopback scripts, whose command receipts are retained;
those scripts are not retained as source in its frozen stage-3 tree. Do not turn
zero domain Go tests into a claim that no process testing occurred. Conversely,
the 1.5 condition's larger suite misses the genuine historical encoding below.

The candidate was more complete on this fixture initially and finishes with fewer
external scenario failures. Its native continuity and testing work also required
more invocation time and tools. These are bounded observations; they do not
identify the contribution of memory versus coding guidance versus generation
variation, or establish a general model/version advantage.

## Confirmed remaining defects

### Vanilla: HTTP not-found mapping and legacy replay regression

`internal/queue/store.go:181` returns `sql.ErrNoRows` directly from a tenant-scoped
query, and `Get` forwards that error. The HTTP layer (`http.go:200`) maps only its
own `ErrMissing` to 404, so a request for another tenant's job receives 503 instead.
The query still filters by tenant: this observation is an error-classification
defect, not evidence that another tenant's data was disclosed.

`validateInput` (`http.go:260`) assigns the new default retry base 1000 when the
field is omitted. `legacyEquivalent` (`store.go:505`) requires zero when the old
stored command lacks the retry field. Consequently, a genuine old body replayed
unchanged through HTTP now receives 409 instead of 200. The attempted final repair
reverses the earlier over-permissive behavior into an over-strict one.

The regression test `TestV1ReplayUsesLegacyRetryDefault` in `followup_test.go`
calls the store directly with retry1000 and expects a conflict. It does not test
the original HTTP body with the field absent, so it misses the normalization
boundary. The final change correctly repairs explicit max-attempts zero validation
and improves contention behavior, but does not complete legacy compatibility.

### OpenSocrates 1.4: zero versus omission and legacy command identity

`cmd/server/main.go:344` rewrites `Max == 0` to 3 before range validation. Explicit
`max_attempts: 0` is therefore accepted, in both single and batch requests, even
though the contract requires 400 and no new jobs. These two scenario failures
share one validation cause; they are not two independent architectural defects.

The final patch rejects explicit JSON null but leaves explicit numeric zero
unchanged. It fixes a neighboring boundary rather than the recorded failing one.
The public final message's statement that the reported gaps were fixed is not
supported by the independent retest.

`legacyCommandMatches` (`main.go:463`) accepts a new retry value1000 when the
old command's retry pointer is absent. That conflates an omitted historical
parameter with an explicitly changed new request. The genuine migration test
still observes 200 where409 `idempotency_conflict` is required. The final change
to the legacy max-attempts default does not address this retry-policy defect.

### OpenSocrates 1.5 RC: normalization of historical absence

The candidate correctly distinguishes omitted and explicit numeric fields for
ordinary input and passes the other18 final scenarios. Its legacy comparison
(`internal/queue/queue.go:296`) decodes an old command into the current `Input`,
then calls current normalization. For a genuinely absent historical retry field,
normalization (`queue.go:247`) assigns1000. An explicit new request for1000 then
compares equal and incorrectly replays, even though the historical job retains
retry0. Data is not shown lost here; command identity is wrong.

The new guard for a serialized zero retry value does not catch absence. Its
`TestVersionOneMigrationPreservesLeaseAndReplay` (`queue_test.go:315`) constructs
the old command by marshaling the *current* `Input` type, which includes new
zero-valued fields. That is different from the genuine preceding executable's
encoding. The added `TestReplayRejectsChangedSchedulingCommand` tests another
modern-command case. Both can pass while the actual migration check fails.
The final public answer explicitly says the genuine historical case was not
rerun and the repair remains unconfirmed; that caveat is appropriate.

## Code reuse and organization

| Property | Vanilla | 1.4 | 1.5 RC |
| --- | --- | --- | --- |
| Runtime Go lines, including common driver | 1034 | 850 | 1040 |
| Go test lines, including common driver test | 144 | 18 | 518 |
| HTTP / storage separation | `http.go` / `store.go` | Combined in one844-line main | `http.go` / `queue.go` |
| Single and batch submission | Shared validation / store path | Shared `submit(batch)` | Shared normalization / `Submit` |
| Lease operations | Common `Mutate` action path | Common `leaseOp` | Separate typed methods with shared scanning/helpers |
| Pure local helpers | validation, retry time, legacy comparison | retry delay, canonicalization, legacy comparison | normalization, retry delay/time, cursor helpers |

Counts describe the artifacts, not quality percentages. Reuse is present in all
three. The candidate and vanilla expose clearer HTTP/storage boundaries than the
baseline monolith; the candidate has more persistent domain tests. None is a
predominantly functional implementation. The remaining defects show why a shared
policy helper must preserve absence, explicit values and historical semantics:
reusing the wrong comparison simply spreads the mistake consistently.

All three explicitly configure WAL and synchronous=FULL and finish with one SQL
connection per pool. The candidate requests immediate transactions in its DSN;
1.4 uses a `lockTx` helper to acquire the write lock before read/modify/write work.
Vanilla's final connection-pool change addresses the preliminary load contention.
Power-loss behavior and connection-replacement fault injection were not tested.
Timing differences are not attributed to a specific SQL choice without profiling.
Every final artifact still fails a mandatory external gate, so all final timing
comparisons remain diagnostic under the frozen protocol.

Vanilla puts `available_at_ms` before priority in its claim index while the query
uses an availability range and orders by priority/creation sequence. The other
two indexes lead with priority after tenant/queue/state. A separate, immutable
read-only [query-plan observation](query-plans.json) using host Python SQLite3.50.4
shows a temporary order-by B-tree only for vanilla. That is an architectural clue
consistent with its much slower lifecycle workload. This auxiliary planner is
not the measured Go driver's runtime, and no controlled index ablation was run;
it does not prove the size or sole cause of the timing difference.

## Harness and evidence limitations

The frozen final-session feedback supplies scenario names, status and a short
error such as `expected [400], got201`. It does not include the actual failing
HTTP request body or response body. That is a real feedback-specificity limit:
the final repairs sometimes address null/default or modern/legacy cases adjacent
to the actual failure. It is not proof that full feedback would have produced a
successful repair, and it does not excuse the observed contract violations.

[New post-outcome failure packets](failure-packets.json) now expose the exact
synthetic requests/responses for review. They were assembled after all outcome
calls and were never delivered to the builders. A future targeted repair can use
them in a new versioned boundary. This experiment does not add a fourth session,
change old scores, or supply stronger-model code repairs.

The candidate invokes the archive-identical native launcher directly from its
disposable marketplace copy instead of the declared audit adapter. Actual
checkpoint state is retained, but some compact typed response projections are
missing, and response request IDs are absent. The [operation audit](memory-operations.json)
matches restored public command hashes to captured typed responses where possible;
missing status stays null. This is an instrumentation/route deviation, not proof
of a failed memory operation or universal installed-hook delivery. Accepted intent
records remain distinct from proposed, agent-reported checkpoints.

The initial Sol comparison is preserved separately. This Luna run uses corrected
preliminary performance feedback from the outset, while Sol's final sessions
received invalid/unavailable preliminary figures. Do not pool the studies or
interpret their final difference as a controlled Luna–Sol capability gap. Human
review and account-side memory isolation remain unavailable. A bounded practical
comparison is complete even though the generated demos retain defects.
