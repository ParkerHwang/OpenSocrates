# Clean Apple-silicon Mac acceptance

Use this procedure to test the current pull request on a real, newly configured
Mac before merging. It installs into the authenticated user's default Claude
Code and Codex homes; it is not a sandbox test.

This is a pre-release acceptance path. Version 1.1.2 is not yet available from
the public npm and GitHub Release endpoints, so the harness downloads the
successful macOS package artifact built from the exact pull-request commit and
passes those archives to the real packed npm installer. It proves the package,
installer, two-host transaction, registration, managed layout, and status
contract. It does not prove the final public registry and release download path;
run the published one-line install separately after release.

## Before you start

Use an Apple-silicon Mac that has never had a managed OpenSocrates installation.
The harness refuses to overwrite an existing OpenSocrates state directory,
LaunchAgent, managed marketplace, or host registration.

Install and sign in to all prerequisites:

- [Node.js](https://nodejs.org/en/download) 20 or later;
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started)
  2.1.205 or later, with `claude auth status` succeeding;
- [Codex CLI](https://help.openai.com/en/articles/11381614-api-codex-cli-and-sign-in-with-chatgpt),
  with `codex login status` succeeding;
- [GitHub CLI](https://cli.github.com/manual/index), with `gh auth login`
  completed; and
- Git.

Wait until the current pull request has a successful `CI` run for its latest
commit. The harness rejects an older commit or an artifact from a different run.

## Run the automated acceptance

Open Terminal and run:

```bash
gh repo clone ParkerHwang/OpenSocrates
cd OpenSocrates
gh pr checkout YOUR_PR_NUMBER
git pull --ff-only
node tools/clean_machine_acceptance.mjs
```

The checkout must be clean. The harness then:

1. verifies default paths, Apple-silicon macOS, tool versions, and host logins;
2. proves that no previous managed OpenSocrates installation exists;
3. pins the checkout, pull request, CI run, and native artifact to one commit;
4. verifies the Claude and Codex archive hashes from the combined release
   manifest;
5. packs this checkout as an npm package and installs both hosts in one real
   transaction;
6. checks private desired state, exact host registrations, package versions,
   Claude's single public `/opensocrates` skill, and all-host drift status; and
7. writes a privacy-safe result directory under your home directory.

It does not enable automatic updates, upload results, store raw command output,
or include prompts, transcripts, authentication identity, credentials, or
absolute local paths in the report. Temporary CI and npm files are deleted when
the run ends.

## Complete the manual checks and share the result

When automation passes, the harness prints the path to
`manual-observations.md`. Open that file and complete its four checks in fresh
Claude Code and Codex tasks. Change every:

```text
PENDING
```

to either `PASS` or `FAIL`. Do not add notes or paste prompts, transcripts,
account names, credentials, or local paths; the pack command rejects changes
outside the four result fields.

Run the exact `--pack` command printed by the harness. It creates a ZIP next to
the result directory. Attach that ZIP to the Codex task handling the current
pull request; the report contains enough commit, CI, integrity, installation,
and status evidence for the maintainer to evaluate the test.

If automation fails, the harness creates the privacy-safe ZIP immediately.
Attach it without copying authentication output. A checksum or clean-baseline
failure blocks installation; the all-host installer rolls back hosts already
changed when activation fails. A post-install assertion failure leaves the
managed state available for diagnosis.

## Remove the test installation

After the result has been collected, remove both managed host installations:

```bash
node installer/opensocrates.mjs remove --host all
```

This removes only the OpenSocrates roots owned by the installer. It does not
sign out of Claude Code, Codex, or GitHub CLI.
