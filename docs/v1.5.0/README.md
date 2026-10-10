# OpenSocrates v1.5.0 implementation preparation

The Mac implementation now lives on `feat/v1.5-macos`. See the
[Mac guide](../macos-v1.5.md), [practical observations](../../evals/v1.5-macos/REPORT.md)
and [Windows continuation](WINDOWS_HANDOFF.md). The preparation materials below
remain the original scope and source contracts; they are not final implementation
or release evidence.

Prepared 2026-10-07 from released v1.4.0 source
`5a2ff3c312e92aa8a44d0905465674d9a4e4f645`. This package fixes the revised
product scope, host approach, source seams, work order, and practical acceptance
before implementation. It does not restore host support or publish v1.5.0.

OpenSocrates helps people who are not expert AI users obtain results they can
understand, judge, and use. Preserve the 48-method reasoning foundation and
Codex experience; add Claude Code, Claude web/Desktop and Cowork, and the
Antigravity conversation application. Include native Windows qualification.
Dedicated coding-specialist features are outside this release scope.

## Start here

| Document | What it settles |
| --- | --- |
| [Accepted scope](16-product-refocus-and-host-support.md) | User goal, requested hosts, coding exclusion, and honest evidence boundaries |
| [Implementation plan](IMPLEMENTATION_PLAN.md) | Fixed initial choices, source seams, ownership, dependencies and exit criteria |
| [Claude host plan](CLAUDE_HOST_PLAN.md) | Local Code versus account delivery, cloud Cowork, Windows and migration of the old skill |
| [Antigravity host plan](ANTIGRAVITY_HOST_PLAN.md) | Conversation-app rules/skills, current packaging, permissions and lifecycle |
| [Practical acceptance](PRACTICAL_ACCEPTANCE.md) | Reader outcome cases and host-specific checks, without a coding leaderboard |
| [Local observations](local-observations.json) | Sanitized read-only inspection; availability is separate from automatic activation |
| [Preparation handoff](PREPARATION_HANDOFF.md) | GitHub pointers, actual checks, remaining evidence and next action |
| [Implementation kickoff](IMPLEMENTATION_KICKOFF.md) | Self-contained instructions for starting the first work package |

Read scope and implementation plan first. Use the matching host plan when
implementing that surface. Preserve [AGENTS.md](../../AGENTS.md),
[CONTRIBUTING.md](../../CONTRIBUTING.md), and [SECURITY.md](../../SECURITY.md).
Their current Codex-only statements describe released support. Change those
statements and their governance assertions together when new implementation
warrants it, without weakening privacy or user authority.

## Baseline and historical work

Use `prep/v1.5-product-refocus` as the preparation branch. Runtime, canonical
methods, schemas, installer, package versions, and dependency pins still match
v1.4.0. Existing local product settings remain unchanged.

The earlier [Closed PR #95](https://github.com/ParkerHwang/OpenSocrates/pull/95),
source `f04d57fa84a82fbb0e3feb6894ec1210f135b3a8`, preserves the old coding,
memory, orchestration, and comparison record. Do not merge that candidate into
this implementation. Do not import its code or guides; new improvements start
from v1.4 and the current user need. The earlier 01-15 specifications belong
to that historical branch, not this preparation package.

All original 48 methods, teacher questions, common system content, and EN/KO
response-policy content are unchanged between the released baseline and old
candidate. A broad rewrite of those foundations is not justified by the current
evidence. The first improvement work examines concrete reader difficulties and
changes only the relevant controller or guidance behavior.

## Preparation completion

Preparation is complete when host mechanisms have primary-source research,
local observations have honest scope, source seams and work dependencies are
identified, default choices avoid unresolved setup questions, the baseline and
documentation checks pass, and GitHub contains a recoverable handoff.

Automatic host participation and improved final results are implementation
acceptance, not proof supplied by this preparation. Missing live Windows or
cloud-hook evidence is listed once and assigned to a later work package; it
does not prevent starting the first package. Publishing, merging, and replacing
an active installation are separate actions.
