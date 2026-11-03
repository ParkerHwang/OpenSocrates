# Development start and handoff

This packet prepares development. No runtime behavior is changed by the packet. The owner requested the 2.0 target, mandated Cursor support, requested easy installation and automatic updates, and withdrew the standalone 1.6 track. The work may start without restarting discovery from this conversation.

The first build is [the core slice](CORE.md). Read that page before treating the wider packet as the current job. Installation, bots, review arms, and migration stay recorded here and start after the slice has an artifact and one observed Cursor path. The former parent issue #136 and workstream issues #138–#145 were deleted; the core page is the current scope.

## First session

1. Read repository `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, [the core slice](CORE.md), and this packet. Reconcile the current `main` and any newer release with the pinned v1.5.3 baseline, and search the current issue/PR state before changing files.
2. Inventory relevant current source and the preserved 1.6 heads in the master plan. Prior 1.6 evidence is revision-specific, and the older withdrawn v1.5 candidate must not be merged, cherry-picked or copied. Separate independently reusable 1.6 work from unverified behavior. `src/opensocrates/v2` on the foundation branch is coordination scaffolding, not the artifact or the continuation record.
3. Create a focused branch or isolated worktree from the current 2.0 line. Preserve other work and installations. Implement the core offline against [the synthetic cases](EVALUATION_CASES.md): artifact cases E01, E02, and E04, then continuation cases E05 and E06. The v1.5.3 package inventory remains in [the package and source inventory](RELEASE_BASELINE_1.5.3.md). An unmeasured host-token inventory does not block these offline cases. Use disposable fixtures and synthetic content.
4. After those cases pass offline, bind one Cursor surface that can place guidance in front of the model and run the same cases there. Record delivery, reading, and the artifact as separate observations. Wider host adapters, lifecycle, review, and bot experiments stay in the master plan until that path has a result. Use the referenced acceptance documents as tests, not as authorization to act beyond user requests.
5. Open small linked draft PRs with concrete changes, exact validation and unresolved evidence. Do not merge, release, change active installations or broaden permissions simply because development was requested. Use the normal repository workflow and existing user authorization.

## Minimum cases to retain

The current slice proves these:

- Two reader-facing messages keep each reader's facts, invent no date or consent, and leave requester-only uncertainty in a separate note.
- A short mechanical formatting task bypasses methods and independent-review overhead.
- Ambiguous intent that changes the outcome prompts a focused question; a nonmaterial missing detail does not block progress.
- A Korean user requests an English external email: the draft is English; internal uncertainty is delivered separately to the user in Korean. Recipient-relevant uncertainty is not hidden, and no commitments are invented.
- After compaction and a fresh session, the accepted constraint and the facts the draft uses persist. A changed fact refreshes only the part it affects.

These stay in the packet for later work:

- Japanese and English source material produce a Korean report with intact provenance and no assumed source language change.
- Deletion and project isolation hold through retrieval and derived indexes; a stale record does not confer authority.
- A clean install, already-disabled install, interrupted update and 1.5.3-to-2.0 transition preserve unrelated settings and expose human-only trust steps.
- The required Cursor integration distinguishes local and cloud behavior. Bot profile claims require direct host-specific evidence.
- Timed evaluation includes ordinary host, current release, v2 without extra reviewers, serial review and parallel review; compare equivalent tasks and retain failures.

## Evidence and completion

Record release/source version, operating system, host surface, model and configuration, operation, expected behavior, actual result, output evidence and limitations. Keep successful installation, guidance delivery, method read, claimed application and useful outcome separate. Report failures and timeouts instead of discarding or relabeling them.

The core slice is ready for review when E01, E02, E04, E05, and E06 pass offline and one Cursor surface has separate observations for delivery, the artifact, and resume. The wider 2.0 milestone is ready for review only when all chosen mandatory host/OS cells, product cases, locale/content boundaries, memory controls, 1.x migration, signed update/recovery and the full required repository checks are complete or their limitations explicitly prevent the corresponding claim. Test native and cloud/account surfaces separately. The owner can decide bot release support after the research; it is not a license to remove mandatory Cursor.

## Preserved historical starting points

- Released v1.5.3: `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c`.
- Superseded 1.6 implementation PR: [Go runtime and lifecycle](https://github.com/ParkerHwang/OpenSocrates/pull/112), `8c49b2debbc622d58a928204a9a4ddb3118f5a08`.
- Superseded 1.6 planning PR: [Go preparation](https://github.com/ParkerHwang/OpenSocrates/pull/110), `2893da99980538408ac004d03f23a43de4eab92d`.
- Previously reported substantive-task delivery omission: former issue #124 was deleted; its cause and frequency remain unresolved.
- The [office-work evaluation lab PR](https://github.com/ParkerHwang/OpenSocrates/pull/135) is independent and may provide related evidence when its own conditions are met; its former issue #134 was deleted.
