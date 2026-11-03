# OpenSocrates 2.0 core

Status: active scope, 3 November 2026. This is the slice to build. The other pages in this directory remain the preserved preparation packet: decisions, research, and later work. They are not a gate in front of this slice. This page does not implement or release 2.0.

## The slice

A person asks for a result someone else will read. OpenSocrates turns that request into a usable artifact, keeps the requester's working note separate, and resumes the same work after the session is compacted. The first proof is one Cursor path that places this guidance where the model can read it.

### 1. The artifact is for the recipient

The deliverable stands on its own. It carries the background that reader needs, the requested action, and any uncertainty that would change their decision. Dates, consent, approvals, and commitments appear only when the source or the user supplied them.

The note back to the requester is a separate text. It holds process questions, assumptions, and checks that do not belong in the deliverable. A Korean requester can receive that note in Korean while the email itself is English. An explicit language request wins over the conversation language and over any saved preference.

A short mechanical task, such as keeping three lines in order, produces the requested format and skips method exposition. When one missing fact would change the recommendation, ask that question and continue the work that does not depend on it.

### 2. Continuation restores the facts the draft uses

After compaction or a fresh session, resuming the task brings back:

- the accepted constraint
- the numbers, titles, and quotations the draft depends on
- what is still unsettled
- the distinction between a proposal and an accepted decision

A newer fact updates the part it affects. It leaves an unrelated accepted decision standing, and it leaves a proposal unapproved.

The stored record is those facts. It is a bounded working record, not a raw transcript, a copy of the workspace, a credential, or hidden reasoning. When the host cannot restore the record, say so and continue from what the user just supplied.

### 3. One Cursor path, proved after the slice exists

Build the artifact and the continuation record first, against the synthetic cases, with no host required. Then bind one Cursor surface whose documented event can place guidance in front of the model, and run the same cases on that surface.

Local Cursor and cloud Cursor are different surfaces. The first proof covers one of them. Record installation, whether the guidance was visible to the model, the artifact, and whether resume kept the facts as separate observations. A passing offline case is not host delivery. A delivered prompt is not a useful artifact.

### 4. Methods stay in the background

The 48 methods and ten locales remain in the distribution. This slice uses a method only when a judgment changes the outcome, and it keeps that method's existing evidence and stop conditions. Locale requalification and a reviewer agent come later.

## Proof cases

Use the synthetic wording already in [the evaluation cases](EVALUATION_CASES.md).

| Case | What passing shows |
| --- | --- |
| E01 | Two messages, two readers. Capacity 24 and a tentative booking stay visible. No date, photography consent, or confirmed reservation is invented. |
| E02 | The customer email is English and does not state a launch date. The requester's note is Korean and separate. |
| E04 | The offline choice is asked because it changes the recommendation. The three-row table is produced with no method lecture. |
| E05 | July replaces June. The privacy decision stays accepted. A proposal stays unapproved. |
| E06 | After compaction and after a fresh session, resume restores the accepted constraint and the facts the draft uses, and continues the remaining check. |

E03 and E07 through E10 stay in the preparation packet.

## Work order

1. Implement the artifact boundary for E01, E02, and E04 offline.
2. Implement the continuation record for E05 and E06 offline, including the numbers and quotations the draft uses.
3. Choose one Cursor surface that can deliver guidance to the model, and run those five cases there.
4. Write down what was delivered and whether resume kept the facts. Leave delivery, reading, and usefulness as separate lines.

`src/opensocrates/v2` on the foundation branch is local coordination scaffolding. Extending it does not select a method, write the recipient's artifact, or restore a draft. The four steps above are the work that follows.

## Later work, still recorded

The [master plan](MASTER_PLAN.md) still records the owner's decisions: Cursor as a required host, easier installation, automatic updates where a platform allows them, and withdrawal of the standalone 1.6 track. Host requalification for Codex, Claude, and Antigravity, bot profiles, signed updates, 1.5.3 migration, independent review, and a full locale-delivery measurement remain in that packet. They follow an artifact and one observed Cursor path. An unmeasured v1.5.3 token inventory does not block steps 1 and 2.

Privacy, fail-open behavior, and ordinary-work continuation stay in force.
