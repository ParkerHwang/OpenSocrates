# Codex entry loss on large submissions

[한국어](codex-large-submission-entry.ko.md)

The leading explanation for the omission reported in [#124](https://github.com/ParkerHwang/OpenSocrates/issues/124)
is a size-triggered loss of discovery guidance. This is a strong inference from
the recorded size pattern and a reproducible parser defect, not a proven account
of the historical hook invocation. [PR #126](https://github.com/ParkerHwang/OpenSocrates/pull/126)
addresses scope and wording separately; its merge does not establish this cause.
The reproducible input-bound defect is tracked separately in
[#127](https://github.com/ParkerHwang/OpenSocrates/issues/127), so its correction
does not automatically close the historical incident.

## Verified mechanism and historical limits

In the [v1.5.2 native parser](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/src/opensocrates/hosts/codex/native.py),
non-`PostToolUse` envelopes larger than 32,768 bytes are rejected before JSON
parsing. The default decision-point adapter also passes through that parser,
although submission discovery needs no prompt content. The hook ingress accepts
up to 4 MiB. A valid submission between those bounds can therefore exit zero
with empty output instead of the entry guidance. Fail-open continuation hides
this loss from the ordinary task; exit zero alone is not delivery evidence.

The investigation used synthetic, in-memory `run_hook` calls with an injected
adapter and memory-only services, without launching an installed hook or writing
product state. On the baseline path:

| Synthetic raw JSON envelope | Observed result |
| --- | --- |
| 32,768 bytes | Exact v1.5.2 entry emitted: 1,398 UTF-8 bytes |
| 32,769 bytes | Exit zero; empty output |
| 96,822 bytes, including a 96,732-byte synthetic prompt | Exit zero; empty output |

Separately, bounded inspection of the original host record established:

| Recorded turn | Persisted prompt size | Entry in persisted developer context |
| --- | --- | --- |
| Original strategy synthesis | 96,732 UTF-8 bytes | No entry marker found |
| First follow-up | 74 UTF-8 bytes | Exact 1,398-byte v1.5.2 entry |
| Second follow-up | 173 UTF-8 bytes | Same exact entry |

The later entry hash was
`e21fd108ba3e0c5960abf88da3972c2ed17982ab3ad4571c90f45e001141501e`.
The original session recorded Codex CLI `0.162.0-alpha.17.2` and model
`gpt-6.1-sol`. These are session metadata, not a claim about another host/build.
Only sanitized sizes, entry identity and version metadata are reported here.

The original hook stdin and an execution receipt are unavailable to this
investigation. The persisted prompt need not equal the hook payload, and absence
from the persisted record does not prove absence from every actual model input.
Trust settings inspected after the incident do not prove the original hashes
matched. Trust/host invocation, timeout and record coverage remain alternatives
or possible contributors. The agent's later project-versus-tool explanation is
a reported self-assessment, not independent causal evidence.

## Bounded correction

The candidate change gives **default `UserPromptSubmit` discovery** a separate
metadata projection before the retained legacy 32 KiB envelope guard. It uses
the existing 4 MiB ingress cap, validates the JSON envelope, event/lane,
session metadata and prompt type, and discards prompt content, paths, model data
and unknown fields rather than forwarding them to application code.

The correction preserves strict legacy parsing and other event paths, residue
cleanup, empty fail-open responses to invalid input, and the fixed discovery
entry. It does not start method selection, retain callback content, change hook
trust, modify an active installation, or add logging/telemetry. It is not a
blanket increase to every native-event limit.

Baseline reproduction and candidate verification are recorded separately. The
linked change's final handoff records exact commits, commands and results;
source checks alone establish neither live delivery nor answer quality.

## Recorded source verification

At `01d363def89cf456faeee6bec49daf67c645fa7f`, on Apple-silicon macOS with
Python 3.12, the following integrated command passed with exit zero:

```sh
make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check
```

This includes the 12 normal-hook composition/entry checks (including the new
large-submission cases), 35 decision-point checks and 26 selector-contract cases.
Code and security review found no actionable defects. The active installation
was not changed; these source checks do not establish live delivery or
spontaneous application. Final PR metadata and CI results remain in the linked
change's handoff.

## Minimal next checks

1. Reproduce the three baseline sizes using generated JSON and injected
   memory-only services. For the candidate, additionally exercise the 4 MiB
   boundary, malformed JSON, wrong prompt/session types and event/lane mismatch.
   Check exact entry emission and the absence of state/content retention.
2. Verify unchanged strict legacy limits, other callbacks and cleanup. Run the
   repository checks after integration and record the tested source identity.
3. If useful, use a separately qualified candidate package in an isolated
   profile with short/large synthetic submissions. Keep host build, trust and
   task content controlled. Use supported host evidence to distinguish hook
   invocation, returned entry and entry delivered to the relevant turn. If any
   stage is unobservable, mark it unknown rather than failed or successful.
4. Assess spontaneous consideration separately using an ordinary synthetic task.
   A delivered entry does not prove method selection, complete reading,
   application or usefulness. A successful explicit reminder proves neither
   hook delivery nor spontaneous use; valid reuse need not create a fresh read.

The [documented hook contract](https://learn.chatgpt.com/docs/hooks) describes
`UserPromptSubmit` input and developer-context delivery. It does not make a
persisted transcript a complete delivery receipt. Existing permitted host
observations and transient sanitized measurements are sufficient for bounded
checks; no private conversation, hidden reasoning or new persistent product log
is required.

Observing a small actual hook payload for the historical turn would weaken the
size explanation. Observing an oversized actual payload rejected by this parser
would strengthen it. In their absence, a controlled size-dependent candidate
comparison can establish the corrected defect, while historical attribution and
general omission frequency remain bounded claims.
