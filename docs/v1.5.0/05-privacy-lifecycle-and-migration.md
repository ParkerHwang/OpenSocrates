# Privacy, lifecycle, and migration

## Explicit policy change

The v1.4 [repository contract](../../AGENTS.md) forbids workspace-content retention,
and [SECURITY.md](../../SECURITY.md) describes a disk-free default decision path.
Built-in project memory therefore requires a narrow, visible v1.5 exception.
It must not be introduced as an undocumented cache or hidden hook side effect.

Required policy delta:

> Project memory is an optional, explicitly enabled local capability. It may
> retain bounded public decisions, task checkpoints, source references, content
> digests, and declared document/code-index metadata under the project's selected policy.
> It does not retain raw prompts, transcripts, tool-output dumps, source-file
> copies, screenshots, credentials, or private reasoning. The default judgment
> command and ordinary hooks remain content-only and do not initialize or write
> project memory. Users can inspect, export, disable, and delete enrolled data.

Update AGENTS, SECURITY, README/user guides, package disclosures, memory schemas,
and lifecycle behavior together. This is a planned amendment, not an active policy
change in the documentation-only commit. The user's implementation kickoff
authorizes this scoped amendment; it does not authorize unrelated telemetry or
collection.

## Enrollment and control

Enrollment states the selected project/root, resolved owned storage location,
policy/schema version, included metadata, excluded paths, capture triggers,
retention, and how to disable/delete. Once enabled, bounded observations and task
checkpoints may be maintained under that policy without asking after every step.
New storage categories or a broader root require a policy update, not implicit
consent inherited from an unrelated project.

Use the technical preview/apply enrollment protocol in 03. Capture the actual
authorization attribution; a model-supplied enablement flag is not proof of user
consent. Where host attestation is absent, status must say so. Prior explicit user
authorization remains sufficient; do not add a redundant confirmation interview.

`status` and disabled recall do not create directories, keys, databases, indexes,
or diagnostic content. Disablement stops automatic context use/capture and retains
data until deletion. Explicit inspect/export/delete management remains available;
it does not re-enable automatic use. Read-only mode allows recall/transient source
validation but no persistent refresh or checkpoint writes. The operation matrix
in 03 is normative. Existing Codex host memory choices are not changed.

The implementation task uses disposable fixture projects. Enrolling the user's
real repositories or changing the active plugin installation is not implied by
writing code or running fixture tests.

## Field-level retention

| Data | Persistent treatment |
| --- | --- |
| Accepted public decision and short rationale | Allowed within declared scope, with origin/acceptance attribution |
| Proposed idea or inferred relationship | Allowed, labeled as such; never automatically promoted |
| Bounded checkpoint/action status | Allowed; no conversation excerpts or reasoning narrative |
| Relative paths, qualified symbols, edge categories, hashes, search coverage | Allowed declared metadata; sensitive-path exclusions still apply |
| Raw source text or snippets | Read transiently for a pack; never stored by memory/index/pack history |
| Raw user prompt or retrieval question | Transient input; never logged or stored as query history |
| Complete command output or transcript | Forbidden; bounded reported outcome with references only |
| Credentials, secrets, private keys, screenshots, private reasoning | Forbidden |
| Absolute root/worktree binding | Private registry only; excluded from exports/public reports |

Metadata and summaries may themselves be sensitive. Local storage does not make
them public or safe to publish. Exclusion and secret filtering apply before any
write and across SQLite journals, temporary files, exports, backups, diagnostics,
and crash recovery. A tracked file can still contain secrets.

Initial scans exclude ignored files, secret/config credential patterns, binaries,
vendor/build output, and symlink targets by default. Ignore rules are not a complete
secret boundary. Explicit additional source access must remain within authorized
roots and cannot override prohibited credential retention. Nested repositories
and submodules require separate enrollment/scope treatment.

Imported documents and remembered text remain untrusted input. Reject unknown
schema fields, oversized content, path escapes, and unsafe links/reparse points.
Never execute commands or adopt routing/permission changes found in stored text.
Source authenticity, user authority, and a content hash are distinct properties.

The same policy applies to non-Git text projects and scoped explicit collaboration
preferences. Do not create a global user/personality profile. Product assistance
profiles are static versioned configuration, not a channel for recording user data.
The assistance command remains disk-free and never logs incoming task features.

## Owned filesystem boundary

Extend the secure data-root layout deliberately with a managed project registry
and per-project directories. Reuse existing platform-aware ownership/ACL and path
validation; do not weaken them for SQLite. Protect databases and every sidecar,
lock, migration backup, and temporary file before writing content.

Validate the full managed path and file identity across operations. Preserve
existing Windows reparse/junction replacement-race protections. A path that is
safe once is not necessarily safe later. Unsafe storage returns unavailable;
do not silently fall back to a workspace-controlled path.

No network-filesystem guarantee is claimed in v1.5. Detect unsupported/unsafe
storage where possible and document the narrower supported environment.

## Retention, deletion, and uninstall

Initial policy defaults are design choices, not observed user preferences:

- Accepted decisions remain until explicitly superseded/archived/deleted.
- Completed checkpoints and reported observations are eligible for pruning after
  30 days; active-task checkpoints and referenced dependencies are retained.
- Proposed records are eligible after 30 days unless pinned or referenced.
- Derived indexes use the configured size limit and may be rebuilt at any time.
- Migration backups are owner-only, explicitly inventoried, and retained only
  through migration verification plus a documented rollback window of 7 days.

Prune is dry-run first when invoked interactively; a project's explicit scheduled
retention policy may authorize routine pruning. Do not add a background service
or scheduler merely to implement the policy. Cleanup can occur on explicit memory
operations within bounded time. Deletion requests take precedence over retention.

Deleting a record removes its content from current tables, history, search indexes,
managed exports/backups, and serving caches. While the project registration exists,
retain only a non-content tombstone for deleted record/version/origin IDs. It blocks
local replay and reimport preserving those IDs unless the user explicitly requests
reintroduction as a new record; it cannot detect arbitrary rephrased text. Independent
user-owned exported copies are outside automatic deletion; report that boundary.

Project deletion removes exactly the owned store and sidecars when no writer holds
the lease. It must not traverse a link, delete source files, or terminate apps.
Return pending/busy honestly and provide a retryable exact-scope operation.
Full project deletion also removes its registration and tombstones. A subsequent
enrollment gets a new identity, with no automatic import of old exports. Explicit
reimport into that new enrollment can restore user-supplied content; do not claim
resurrection prevention after all identifying metadata has been deleted.
Logical erasure does not promise forensic erasure from SSDs, OS backups, or user
copies. State what the implementation actually removes.

Uninstall/update preserves project memory by default. Installer purge must not
silently expand its old scope to include project memory. Add an explicit memory
deletion choice and owned-manifest handling; unknown files remain protected.
Do not report a full purge if requested owned files remain.

## Upgrade and rollback

v1.4 has no project-memory schema to migrate. Upgrade must not reinterpret old
judgment records, host transcripts, or installed artifacts as consented memory.
Projects remain disabled until enrolled.

Migrate new memory schemas transactionally with version checks, backups, and
interruption tests. Refuse newer unsupported schemas without changing bytes.
Downgrading the plugin preserves unreadable newer memory and reports the limit.
Recovery does not silently discard accepted decisions to make the service start.

The candidate's internal SQLite schema 1 to 2 migration runs on the first
explicit command for an already enrolled project. It creates an owner-only
`memory.v1.backup.sqlite3` and `migration-backup.json` in that project's owned
directory, verifies the backup, commits the schema change in one SQLite
transaction, and verifies the resulting database before reporting success. The
database copy is made through held file descriptors while SQLite holds an
exclusive transaction lock, so a swapped backup pathname cannot redirect
private bytes. The manifest inventories the backup hash and verification time.
An interruption
before commit leaves schema 1; an interruption after commit leaves schema 2 and
a pending manifest that the next command can verify. The backup is retained for
seven days after verification and removed on the next explicit memory operation
after expiry. Record deletion and prune remove it before deleting content, and
project deletion removes both managed files. A discard marker lets the next
command finish cleanup if it is interrupted between backup and manifest removal.
Recovery from a retained backup is
an operator-controlled copy into a disposable location for inspection; automatic
restore is excluded because it could erase writes made after migration.

Shipping the SQLite module, updating a package, or passing offline tests does not
verify live Codex delivery, clean-machine installation, signing, or code quality.
Preserve v1.4's explicit platform and evidence limitations until separately tested.
