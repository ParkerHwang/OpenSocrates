# OpenSocrates v1.5.3 package and source inventory

[English index](README.md) · [한국어 색인](README.ko.md) · [Backlog item B01 (partial)](IMPLEMENTATION_BACKLOG.md) · [v1.5.3 maintenance note](../v1.5.3.md)

This inventory freezes what the published v1.5.3 release contains and which guidance each package is built to supply. It is an input to later 2.0 work. It does not mark a host qualified, a method applied, or a feature complete.

## Scope and B01 status

Backlog item B01 has two parts. This document completes only the first.

| B01 part | Status |
| --- | --- |
| Inventory v1.5.3 host packages and ten-language content; retain unknowns and exact versions | Recorded here, from published release assets, the npm package, the SBOM and tag-identical source |
| Inspect initial guidance and actual delivered tokens per accessible host | **Not done.** No Codex, Claude, or Antigravity process ran during this inspection, so nothing here was observed in a model context |

B01 stays open until the second part is measured on each accessible host, with inaccessible hosts recorded as such. That measurement is required before any comparison against v1.5.3 (including B02 evaluation runs), and before any claim about what a host delivers, reads, or applies, or about effect or cost.

Live measurement is not required to accept this document because the document makes no such claim. Every value comes from a published artifact or from source identical to tag `v1.5.3`. Every statement about host behavior is marked not observed. The sizes and estimated tokens below describe text present in a package or returned by tag-identical code; they are not delivered context. If a later edit adds a delivery, application, effect or cost claim, that edit needs the live evidence.

Inspection date: 2026-11-02. The measurements below come from the public GitHub release, the npm package, the published SBOM, and source files that are byte-identical to tag `v1.5.3`. No Claude, Codex, or Antigravity process was available in this Linux inspection, so no live model context was captured.

## Identity

| Item | Exact value |
| --- | --- |
| Product version | `1.5.3` (`VERSION`, `package.json`, `pyproject.toml`) |
| Release tag | `v1.5.3`, lightweight tag pointing at commit `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c` |
| Tag commit | `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c`, committer date `2026-10-15T09:52:22Z`, “Merge pull request #133” |
| GitHub release | `OpenSocrates 1.5.3`, published `2026-10-15T10:15:57Z`, `draft: false`, `prerelease: false`, `immutable: true`, 17 assets |
| Content revision | `5` |
| Canonical content hash | `sha256:a4d9f4b70f653dee12a3ea758ef10dc391443a19536c7e7f22082962fd252e0f` |
| Normalized semantic hash | `sha256:2c85b27d1586f97ec743e7d3f0a56f02a71a41913589e25a08c4a5ab309df0ab` |
| Current `main` at inspection | `51bdffe49737c52a0aeb425f953bb31d036f6bda` |

`git diff v1.5.3` for `content/methods`, `plugin-src`, `installer/opensocrates.mjs`, `installer/managed-hosts.mjs`, `VERSION`, `package.json`, `pyproject.toml`, and the entry/hook modules cited below was empty. The compiled bundle on current `main` still carries the published content hash. Commits after the tag add evaluation and 2.0 planning material; they do not change this baseline’s packages.

## Versions recorded with the release

From the published SPDX SBOM `opensocrates-1.5.3-sbom.spdx.json` (`sha256:49577418c468027c6ad18ccd2188aa8c5722a42616fbb9428fe423a7d98e1d0c`, created `2026-10-15T09:59:27Z`, SPDX 2.3, 23 packages):

| Component | Version |
| --- | --- |
| Python used for the recorded build | 3.12.15 |
| PyInstaller | 6.21.0 |
| pyinstaller-hooks-contrib | 2026.6 |
| openai-codex | 0.144.4 |
| openai-codex-cli-bin | 0.144.4 |
| pydantic | 2.13.4 |
| pydantic-core | 2.46.4 |

The release manifest repeats the Codex SDK, CLI binary, pydantic, and pydantic-core versions inside the Codex runtime dependency block. npm `engines.node` is `>=20`. The Node version that published `opensocrates@1.5.3` is not in the release metadata.

Host application versions are unknown. This inspection did not launch Codex, Claude Code, Claude Desktop, Claude Chat, Cowork, or Antigravity, and those applications are not installed here.

Tools that performed this inspection, separate from the release build:

| Tool | Version |
| --- | --- |
| Python | 3.12.3 |
| Node.js | v22.23.4 |
| git | 2.43.0 |
| GitHub CLI | 2.103.0 (2026-10-21) |

## Size and token measurement

Three counts are reported for text that can be read from a package or from tag-identical source:

- UTF-8 bytes
- Unicode scalars (Python `len` of the decoded string)
- `estimated_injection_tokens`, `math.ceil(utf-8 bytes / 4)`, from `estimate_injection_tokens` in `src/opensocrates/content/injection.py`

Codex selector context is rejected when that estimate is greater than or equal to `MAX_INJECTION_ESTIMATED_TOKENS` (`2500`). Claude entry context is rejected above `MAX_CONTEXT_BYTES` (`16384`). The Antigravity builder rejects an entry rule above `4096` bytes. These are repository limits. They are not a vendor’s billed tokenizer, and they were not observed as usage on a running model. Whitespace-delimited counts are a weak size signal for Korean, Chinese, Japanese, and Thai, so locale comparisons below use bytes and scalars.

## npm installer

`opensocrates@1.5.3` is the public installer. It does not contain the 48 methods or the host archives.

| Field | Value |
| --- | --- |
| dist-tag `latest` | `1.5.3` |
| npm publish time | `2026-10-15T10:18:56.217Z` |
| `gitHead` | `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c` |
| unpacked size / file count | 353462 bytes / 18 files |
| integrity | `sha512-+KdKwmuPe/1v6O8iU7qRLi2QhKz+qZmhSfz4UuBjeZeJxwu4mcjciC7hIzoSRiQSX0KHRx+wii4V5NoYVsCl4A==` |
| tarball sha1 | `aaa1d98a534402f733c38378594c7c9d0b66d7e8` |
| tarball sha256 (downloaded) | `0fc8db7074a5481e8b2d54c1d26dbd71b52478ab89dc591b7fc2d967ffd9757d` (95655 bytes) |

Packed paths: `LICENSE`, `VERSION`, `package.json`, `CHANGELOG.md`, ten `README*.md` files, `SECURITY.md`, `installer/managed-hosts.mjs`, `installer/opensocrates.mjs`, `installer/windows.ps1`.

Downloaded release copies of the installer helpers match the tree and the release manifest:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `opensocrates.mjs` | 158511 | `58dd5768d00be4321410681d0467f1d89d550a9d540e92be2e7222787ddd4df0` |
| `managed-hosts.mjs` | 46138 | `ca9622cdde0c07a6a76fa2ca3454f128d81118ccdab2e5bc65e8a9e2ff7a80d2` |
| `windows.ps1` | 9639 | `6396e4ecf00890898fcd682724414bc5770bce7f5e1521650b25f149f4798bab` |

The manifest records the first two hashes under `installer_dependencies`. `windows.ps1` is a release asset; its hash above is from the downloaded asset.

## Published release assets

All five zip sidecar files matched the downloaded zip bytes. The release manifest’s archive hashes match those sidecars. Asset byte sizes are the GitHub release metadata sizes.

| Asset | Bytes | SHA-256 |
| --- | --- | --- |
| `opensocrates-1.5.3-codex-plugin.zip` | 134351980 | `b28d4acde94c4f7e6572299723a8900f12b17f73a695dcaf599193fe4d855ea8` |
| `opensocrates-1.5.3-codex-plugin-windows-x64.zip` | 160197900 | `aa387c054d8e869c19c5721ca9532e377d128216c6e632730069a2bd8f1fb79d` |
| `opensocrates-1.5.3-claude-plugin.zip` | 134305930 | `ed4114a9af699502b446962cba7787cd2085641c1235ca69c923f73dca94e592` |
| `opensocrates-1.5.3-claude-chat-skills.zip` | 2140659 | `ee0163505a39251acb15b6db4eaddbc98845ad28b7354de220466110e84a7fd5` |
| `opensocrates-1.5.3-antigravity-plugin.zip` | 2157475 | `4f8252b186044741134d722f5e15f3dd338ad0b22945dd13b2e91d12a3fc96ce` |
| `opensocrates-1.5.3-release-manifest.json` | 6349 | `48696acdb5321659efee22a8cd98d656c9d04c65e9bc91d43457dbc9b65f9331` |
| `opensocrates-1.5.3-limitations.json` | 2018 | `ed39a148130289296a08b27175b9b55c065136fcf892d4a490bde360859502c9` |
| `opensocrates-1.5.3-sbom.spdx.json` | 17323 | `49577418c468027c6ad18ccd2188aa8c5722a42616fbb9428fe423a7d98e1d0c` |
| `opensocrates-1.5.3-checksums.sha256` | 390559 | not re-hashed in this inspection |
| five `*.zip.sha256` sidecars | 102–114 | text companions of the zips above |
| `opensocrates.mjs`, `managed-hosts.mjs`, `windows.ps1` | see installer table | see installer table |

`opensocrates-1.5.3-checksums.sha256` was not expanded line by line. Zip identity uses the sidecars and the manifest.

## Host packages that ship

Public README and [v1.5.3 note](../v1.5.3.md) claim four profiles: Codex on Apple-silicon Mac and Windows x64, native Claude Code on Apple-silicon Mac, a content-only Claude account skill, and Antigravity workspace/global content on Apple-silicon Mac and Windows x64. The release contains one archive per profile, plus a separate Windows Codex archive. There is no second Antigravity archive and no Windows Claude Code archive.

| Profile | Archive | Members | Runtime inside the zip | Hooks | Public skill entry |
| --- | --- | --- | --- | --- | --- |
| Codex, `darwin-arm64` | `opensocrates-1.5.3-codex-plugin.zip` | 715 | `runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime`, 3871456 bytes, `sha256:3c9b8d121b3618c070309bb107172eff6209e5177960fc0a4a18c68e82c649e4` | `hooks/hooks.json`; launcher `bin/launch.sh` (6725 bytes) | `skills/opensocrates/SKILL.md`, plus `skills/rigor/SKILL.md` and `skills/trace/SKILL.md` |
| Codex, `windows-x64` | `opensocrates-1.5.3-codex-plugin-windows-x64.zip` | 781 | `runtime/windows-x64/opensocrates-runtime/opensocrates-runtime.exe`, 4062674 bytes, `sha256:a246bfc25e16679813d59fa0bd656b63137de84969641b60b1d550ed7591ed3c` | same seven events; launcher `bin/launch.mjs` (2700 bytes) via `node` | same three skill paths; controller and rigor differ by the launcher line |
| Claude Code, `darwin-arm64` | `opensocrates-1.5.3-claude-plugin.zip` | 708 | same `darwin-arm64` runtime bytes and hash as Mac Codex | `hooks/hooks.json`; launcher `bin/launch.sh` (2803 bytes) | `skills/opensocrates/SKILL.md` only |
| Claude account skill | `opensocrates-1.5.3-claude-chat-skills.zip` | 516 | none | none | `opensocrates/SKILL.md` |
| Antigravity content | `opensocrates-1.5.3-antigravity-plugin.zip` | 517 | none | none | `.agents/skills/opensocrates/SKILL.md` and always-on rule `.agents/rules/opensocrates.md` |

The Mac Codex runtime hash matches `runtimes.codex.artifact_sha256` in the release manifest. The Claude archive contains that same runtime file. Package manifests inside the archives record `capability_evidence.status: "unknown"`.

Plugin manifests:

- Codex `.codex-plugin/plugin.json` (234 bytes): name `opensocrates`, version `1.5.3`, hooks `./hooks/hooks.json`, skills `./skills/`, description “Evidence-based judgment support for Codex CLI and Desktop.”
- Claude `.claude-plugin/plugin.json` (348 bytes): name `opensocrates`, version `1.5.3`, description “Reasoning assistance for synthesis, stakeholder context, decisions, and messages.” The manifest does not itself list a hooks path; `hooks/hooks.json` is still a zip member.

Codex command files, present only in the Codex archives, are explicit commands rather than session-start text: `commands/auto.md` (422 bytes), `commands/evidence-audit.md` (420), `commands/opensocrates-status.md` (402), `commands/reasoning-trace.md` (445), `commands/status.md` (374). Sizes are from the Mac archive. They were not compared byte for byte with Windows.

### Profiles with no v1.5.3 archive

The 17-asset set has no Grok, Cursor, or OpenCode package. [Grok](../grok-support.md), [Cursor](../cursor-support.md), and [OpenCode](../opencode-support.md) are historical records and state that those integrations are removed and unsupported in 1.4.0. Cursor is a required 2.0 host in [the master plan](MASTER_PLAN.md); that requirement is not a 1.5.3 package. Linux, Intel Mac, and Windows ARM64 native archives are absent. Native Windows Claude Code is absent.

The published limitations file records several fields together. They are quoted here as published strings, including where they sit beside a shipped Windows Codex zip:

- `platforms.windows-x64`: `not_shipped`
- `platforms.darwin-arm64`: `observed_local`
- `platforms.darwin-x64` and `platforms.linux-x64`: `not_shipped`
- `windows_packages.codex`: the Windows zip and its SHA-256, target `windows-x64`
- `additional_profiles.claude`, `claude-chat`, and `antigravity`: `new_windows_delivery` is `not implemented`; `application` is `unverified`; `live_delivery` is `separate bounded qualification`
- `windows.claude_code`: `excluded by Windows scope; Mac native profile retained`
- `windows.claude_account`: `portable content-only ZIP; verified export is not live account selection`
- `windows.antigravity`: `owned modular workspace/global lifecycle; app loading/results need separate observations`
- `windows.automatic_updates`: `unavailable; manual update required`
- `windows.arm64` and `windows.clean_machine`: `unvalidated`
- `live_host_probe_status.codex`: `unvalidated_current_candidate`
- `signing_status`: `unvalidated`

## Ten-language content

Locales, in builder order: `en`, `ko`, `zh`, `ja`, `fr`, `de`, `it`, `es`, `pt`, `th`.

### Authoring tree

Counted from `content/methods/` on the tag-identical tree:

- 48 method directories
- each `method.yaml` has `content_revision` 5 and a distinct `id`
- each directory has `procedure.<locale>.md` and `cases.<locale>.yaml` for all ten locales
- 1008 files = 48 method records + 480 procedures + 480 case files
- missing procedure or case pairs: 0

Method ids, bundle order:

`abduction`, `argument-mapping`, `assumption-mapping`, `bayesian-updating`, `boundary-critique`, `causal-loop-diagramming`, `causal-reasoning`, `conceptual-analysis`, `cost-benefit-analysis`, `critical-thinking`, `cynefin-framework`, `decision-tree-analysis`, `deduction`, `defeasible-reasoning`, `deontic-reasoning`, `design-thinking`, `double-loop-learning`, `evidence-hierarchy`, `failure-mode-effects-analysis`, `falsificationism`, `first-principles`, `game-theory`, `induction`, `jobs-to-be-done`, `lateral-thinking`, `lean-startup`, `logic-tree`, `mece`, `morphological-analysis`, `pdca-cycle`, `pestel-analysis`, `pragmatism`, `premortem-analysis`, `pyramid-principle`, `reference-class-forecasting`, `reflective-equilibrium`, `robust-decision-making`, `root-cause-analysis`, `scenario-planning`, `sensitivity-analysis`, `socratic-questioning`, `stakeholder-analysis`, `steelman-reasoning`, `systems-thinking`, `trade-off-analysis`, `triangulation`, `triz`, `value-of-information`.

Authoring procedure UTF-8 bytes, summed across 48 files in each locale:

| Locale | UTF-8 bytes | Unicode scalars |
| --- | ---: | ---: |
| en | 258046 | 257493 |
| ko | 273843 | 124097 |
| zh | 216689 | 87208 |
| ja | 275261 | 106688 |
| fr | 287488 | 276473 |
| de | 244398 | 240193 |
| it | 272777 | 271081 |
| es | 244856 | 240969 |
| pt | 252444 | 243100 |
| th | 496568 | 184739 |
| all ten | 2822370 | |

Case files are authoring material. None of the five release zips contain `cases.*` members.

### Packaged canonical procedures

Each release zip contains 480 assembled method files, 48 per locale, under `references/decision/methods/<locale>/<method-id>.md`. SHA-256 of those 480 files is identical across Mac Codex, Windows Codex, Claude, the account skill, and Antigravity. Account-skill and Antigravity manifests list `canonical_methods` length 480 and `method_count` 48. The account-skill manifest’s `method_ids` equal the compiled bundle’s `method_ids`.

These assembled files are larger than the authoring procedures. The English `critical-thinking` packaged file is 10608 bytes and contains the authoring `procedure.en.md` (5485 bytes) after a teacher-question preamble. One inclusion check does not grade translation quality.

Packaged assembled-procedure UTF-8 bytes, from the account-skill zip (the other four zips match by hash):

| Locale | UTF-8 bytes |
| --- | ---: |
| en | 519763 |
| ko | 549954 |
| zh | 456069 |
| ja | 565715 |
| fr | 575110 |
| de | 502788 |
| it | 549515 |
| es | 508521 |
| pt | 515920 |
| th | 915114 |
| all 480 files | 5658469 |

Each native Codex and Claude zip also has 48 short compatibility cards at `skills/opensocrates/references/methods/<method-id>.md`. They point at the ten locale procedures. They are not the procedures. Mac and Windows cards differ only by the launcher line (`${PLUGIN_ROOT}/bin/launch.sh control codex` versus `node "${PLUGIN_ROOT}/bin/launch.mjs" control codex`). Claude’s cards are a shorter index and omit that launcher paragraph (30 lines versus 18 lines on the `abduction` card). The account skill and Antigravity packages have no compatibility-card directory.

Each package also has ten decision catalogs and ten reader guides plus ten decision guides. Catalog sizes matched among Mac Codex, Claude, and the account skill, from `catalog.zh.json` at 20418 bytes through `catalog.th.json` at 26042 bytes. Guide sizes below are from the account skill:

| Locale | Reader guide bytes | Decision guide bytes |
| --- | ---: | ---: |
| en | 3308 | 3384 |
| ko | 4218 | 3969 |
| zh | 2993 | 3085 |
| ja | 4169 | 4493 |
| fr | 4043 | 4499 |
| de | 4028 | 4286 |
| it | 3717 | 4158 |
| es | 3812 | 4346 |
| pt | 3674 | 4114 |
| th | 8321 | 8620 |

## Guidance each package is built to supply

“Supplied by the package” means text present in the archive, or the fixed string the tag-identical runtime returns on a hook. It is not a captured model prompt. The published runtime binaries were not executed; this environment cannot run the Apple-silicon or Windows executables. Hook behavior below is from source that matches the tag.

### Shared entry string

`ENTRY_GUIDANCE` in `src/opensocrates/selector/entry.py` is the fixed Codex and Claude hook text. `ENTRY_GUIDANCE_MAX_BYTES` is 1600.

| Measure | Value |
| --- | --- |
| UTF-8 bytes | 1535 |
| Unicode scalars | 1535 |
| Whitespace-delimited units | 203 |
| Estimated injection tokens | 384 |
| SHA-256 | `5889118d6c44bbf0c25db55c85cee707255809dae8ce98ce0ffc169cc1845d70` |

The string tells the agent to keep goals, permissions, constraints, and completion conditions; to consider support when substantive thinking starts or materially changes; to skip a method for prescribed mechanical steps; to read a full canonical procedure in the task locale before applying it; and to use the reader guide for synthesis, explanations, decisions, and messages. It states that no initial method is selected.

### Codex

`hooks/hooks.json` registers seven command hooks. Mac commands call `${PLUGIN_ROOT}/bin/launch.sh`. Windows commands call `node "${PLUGIN_ROOT}/bin/launch.mjs"`.

| Event | Matcher | Timeout seconds | Normalized launcher argument |
| --- | --- | --- | --- |
| SessionStart | `startup\|resume\|clear\|compact` | 2 | `session_started` |
| UserPromptSubmit | none | omitted in the file | `user_prompt_submitted` |
| PreToolUse | `Bash\|apply_patch\|mcp__.*` | 2 | `tool_succeeded` |
| PostToolUse | `Bash\|apply_patch\|mcp__.*` | 2 | `tool_succeeded` |
| PreCompact | `manual\|auto` | 2 | `pre_compaction` |
| Stop | none | 3 | `completion_candidate` |
| SessionEnd | `other` | 3 | `session_ended` |

Two rows need a note. `UserPromptSubmit` has no `timeout` key on purpose: a comment in `src/opensocrates/hosts/codex/commands.py` says the selector call is bounded internally at thirty seconds and the host timeout is left out so Codex applies its documented 600-second maximum. That maximum comes from the source comment; this inspection did not observe it in Codex. `PreToolUse` maps to no event of its own (`NATIVE_TO_NORMALIZED` gives `None`). The launcher still receives `tool_succeeded` because it only accepts the normalized names, but a `PreToolUse` call is metadata-only and produces no domain event. The table's last column is the launcher argument, not a claim that a tool succeeded.

With `decision_point_mode` (the default in `src/opensocrates/cli/runtime.py`), `UserPromptSubmit` and `SessionStart` whose `source` is `compact` return `additionalContext` set to `ENTRY_GUIDANCE` alone. Startup, resume, and clear `SessionStart` take the empty selector result, so they do not attach that string. The other registered events do not attach it either. Whether a trusted host actually ran the hook, and whether Codex also placed a skill body in the same context, was not observed.

The release manifest records a darwin-arm64 release-build timing for the generated SessionStart hook: configured timeout 2000 ms, 20 samples, startup p95 18.708 ms, compact p95 134.015 ms. That block is latency of the hook process during release assembly. This inspection did not re-run it, and it is not a token count.

Controller skills are available in the archive. Their presence is not evidence they were in the initial context.

| File | Bytes | Scalars | Whitespace units | Estimated tokens | SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| Mac `skills/opensocrates/SKILL.md` | 51048 | 38055 | 4509 | 12762 | `659634b8896346c89d796194630b7ae4d02f55069c038b06884060062a7f6da3` |
| Windows `skills/opensocrates/SKILL.md` | 51056 | 38063 | 4510 | 12764 | `400b4232aafb6a73b88fdb998cbd5fe44ad1e0e916b1ef62c34388a7f3849dca` |
| Mac `skills/rigor/SKILL.md` | 10564 | 7662 | 1020 | 2641 | `33c14d9a89293defd65cc2daf4abeeea9ebaa682d27b7f96b78f9550000255df` |
| Windows `skills/rigor/SKILL.md` | 10572 | 7670 | 1021 | 2643 | not recorded separately; the only line difference is the launcher literal |
| `skills/trace/SKILL.md` (Mac and Windows identical) | 3922 | 2962 | 412 | 981 | `8d9e41059eea74c549500fd3c563dd624321de51d6c21f020a012f86b4c8cd7f` |

The Mac/Windows controller difference is one line, the same launcher substitution as the compatibility cards. The `opensocrates` skill description field is 260 bytes and is the same string on every host profile below: “Supports framing, interpretation, exploration, learning, research design, reasoning checks, approach choice, evaluation and explanation when substantive thinking is needed, including when OpenSocrates is the subject. Prescribed mechanical steps need no method.”

`rigor` description: “Use for an explicitly requested OpenSocrates rigor control or a declared active rigor level.” `trace` description: “Use for an explicitly requested public judgment trace or cross-examination; never expose private reasoning or raw inputs.” The Mac Codex controller skill body does not contain the literal `1.5.3`. Version `1.5.3` is in `plugin.json`.

### Claude Code

`hooks/hooks.json` registers four command hooks. The command is `${CLAUDE_PLUGIN_ROOT}/bin/launch.sh` with args `hook`, `claude`, and the normalized name.

| Event | Matcher | Timeout seconds | Args tail |
| --- | --- | --- | --- |
| SessionStart | `startup\|resume\|clear\|compact\|fork` | 3 | `session_started` |
| UserPromptSubmit | none | 3 | `user_prompt_submitted` |
| Stop | none | 1 | `completion_candidate` |
| SessionEnd | none | 1 | `session_ended` |

`build_entry_response` attaches context for `SessionStart` and `UserPromptSubmit` when the installed root resolves and the controller plus ten decision guides are regular files inside that root. Stop and SessionEnd are outside `ENTRY_EVENTS`, so the hook writes no `additionalContext` for them. The context is `ENTRY_GUIDANCE`, then a controller path, then ten `guide.<locale>.md` paths, then a fixed instruction to read the controller and applicable guide and to call `bin/launch.sh decision claude` when available. The closing sentence says the entry selects no method and attests to no read or application.

The absolute paths are installation-specific, so the delivered byte count is not a single published number. The fixed characters, excluding the 11 JSON-encoded absolute paths, are 1930 UTF-8 bytes (estimated tokens 483). The hook refuses the response above 16384 bytes. No installed plugin root was available here, so the path contribution is unknown. A missing or incomplete install root makes the hook write empty stdout.

`skills/opensocrates/SKILL.md` in the Claude archive is 51036 bytes, 37558 scalars, 4453 whitespace units, 12759 estimated tokens, SHA-256 `b231b58222256a8e085472399448a48966df6214f799731c6bcda223dcdaea1f`. It is a separate file from the hook context. Whether Claude Code inlines it before the model call was not observed. The body does not contain the literal `1.5.3`.

### Claude account skill

The zip has no hooks, launcher, or runtime. Delivery in the content manifest is `account-skill`. `public_skills` is `["opensocrates"]`. `opensocrates/SKILL.md` is 51567 bytes, 38033 scalars, 4535 whitespace units, 12892 estimated tokens, SHA-256 `2be8f250d41f8dc72bcd1a101ff280843b6a9def149fb9ccb4fd9e948f5320c9`. The body includes the literal `OpenSocrates 1.5.3, content revision 5.` The skill says no native runtime or extra model request is part of the skill.

The 260-byte description is the discovery text stored in the skill frontmatter. Whether Claude’s skill index shows only that description, and whether a turn loads the full file, depends on account selection. Export and a verified zip do not establish upload, enablement, or selection. The package manifest says content generation is not live host delivery.

The setup guides also publish a standing instruction for a person to paste into the account so ordinary requests can load the skill without naming it. That text is not a member of the zip. English, from [the setup guide](../setup-guide.md#claude-standing-instructions): 397 bytes, 397 scalars, 57 whitespace units, 100 estimated tokens, SHA-256 `ee47d9c47a3bfef1257436d29824e1373799188f99bea0948c7d4b5491160214`. Korean, from [the Korean setup guide](../setup-guide.ko.md#claude-standing-instructions): 412 bytes, 176 scalars, 41 whitespace units, 103 estimated tokens, SHA-256 `560e74eead111ce88eaa6481b101ddae9bef71acc6316fcda9ca1f5d420dd6f7`. Whether any account has saved either text was not observed. Web and Desktop can be different accounts, as the setup guide already says.

### Antigravity

The content manifest delivery is `modular-workspace`. There is no hook or runtime. The skill file is byte-identical to the account skill (`2be8f250…`). The standing rule is `.agents/rules/opensocrates.md`:

| Measure | Value |
| --- | --- |
| UTF-8 bytes | 1508 |
| Unicode scalars | 1508 |
| Whitespace-delimited units | 202 |
| Estimated injection tokens | 377 |
| SHA-256 | `2367c723201e68782281f4cf8d207ff7fe65711bc8e319e822c47a333f88d24d` |

The file starts with `trigger: always_on` and the description “Support substantive thinking with suitable grounded methods and reader guidance.” The body points at `@../skills/opensocrates/SKILL.md` and does not inline that skill. The builder requires this prefix and rejects the rule above 4096 bytes; 1508 is inside that limit. Whether Antigravity injects the rule on each model call, and whether it expands the `@` reference into the same context, was not observed.

The same zip is the Mac and Windows content archive named by the release. The limitations strings about Windows Antigravity are quoted in the asset section. No Antigravity application version was available.

## Unknowns retained

- Live model-context tokens, billed tokens, and latency on Claude, Codex, and Antigravity. No host process ran. This is the open part of B01 described under [Scope and B01 status](#scope-and-b01-status).
- Whether Codex or Claude Code place `SKILL.md`, `rigor`, or `trace` in the initial context in addition to, or instead of, hook `additionalContext`.
- The exact Claude hook byte count on a real install path.
- Stdout of the published PyInstaller binaries. Hook text was read from tag-identical Python, not from the frozen executable.
- Whether an account has uploaded the skill, enabled it, or saved the standing instruction, on web, Desktop Chat, or Cowork separately.
- Whether Antigravity honors `always_on` and whether it expands the skill reference.
- Codex, Claude, and Antigravity application versions and account plans.
- The Node.js version that published the npm package.
- A line-by-line audit of `opensocrates-1.5.3-checksums.sha256`.
- Translation quality. File counts and hashes do not establish it.
- Why an application was omitted despite installed and approved hooks, as reported in former issue #124 (now deleted). This inventory records what each package is built to supply; it does not explain that report or estimate how often it happens.
- B02 and later backlog items. Synthetic evaluation cases, task contracts, and new host adapters are not part of this record.

## Reproduce

Download the v1.5.3 release assets and compare each zip to its `.sha256` sidecar. Count `content/methods/*/procedure.<locale>.md` and `cases.<locale>.yaml`. Hash `references/decision/methods/<locale>/*.md` inside each zip. Measure `ENTRY_GUIDANCE` with `estimate_injection_tokens`. Do not treat a matching hash as a live host receipt.
