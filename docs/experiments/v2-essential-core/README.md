# OpenSocrates: essential core experiment

This small, standalone skill is a new 2.0 candidate: help a person make
progress, while distinguishing what is established from what is assumed or
unknown. When a choice matters, it should make the trade-off and a condition
that could change the decision clear. For simple work it should stay out of the
way.

The candidate's guidance is [`SKILL.md`](../../../plugin-src/experimental-core/skills/opensocrates-core/SKILL.md),
accompanied by the project MIT license.
It is plain text, with no scripts, tools, hooks, installer, or telemetry. It can
be read and used as instructions, or provided to a compatible host using that
host's skill setup. There is no published 2.0 release; the local ZIP below is
an experimental way to share this file.
The skill adapts two ideas described below, but does not invoke the 1.x method
library or run those full methods. Existing 1.x files are unchanged.

The earlier [output-brief experiment](https://github.com/ParkerHwang/OpenSocrates/pull/164)
is preserved separately, including its scanner and benchmark. They are not part
of this candidate. This is an experiment, not a release; there is not yet
evidence of improved outcomes over an unassisted model or a short instruction.

The distinction between binding requirements and preferences is adapted from
the 1.x [trade-off analysis](../../../content/methods/trade-off-analysis/procedure.en.md).
The idea of checking whether information could change an action comes from
[value of information](../../../content/methods/value-of-information/procedure.en.md).
The short guidance is not either full procedure and does not call them.

## Try the local skill in Codex

Copy the `opensocrates-core` skill folder into your project's
`.agents/skills/` folder, then start a new Codex session for that project and
explicitly request `$opensocrates-core` with your task. If a folder with that
name already exists, back it up or choose another project before copying. To
remove this experiment, remove the copied folder. If 1.x is also active in
the host, both sets of guidance may be available; a separate project alone
does not necessarily isolate a user-wide installation.

In one temporary project using Codex CLI 0.166.0-alpha.5.1, an explicit
`$opensocrates-core` request led to a successful read of the copied skill file
and a response to a synthetic decision task. This was observed with the earlier
skill at `b813474` (unchanged at `176c146`), before the decision guidance was
updated. It does not prove automatic discovery, application, or general
usefulness, or establish behavior in other hosts.

## Make a portable skill ZIP

From the root of a Git checkout in a macOS or Linux shell, create a ZIP
containing only the committed `opensocrates-core/SKILL.md` and `LICENSE`.
Uncommitted edits are not included. The command replaces an existing ZIP at
the same output path:

```sh
mkdir -p build/experiments/v2-essential-core
git archive --format=zip --prefix=opensocrates-core/ --output=build/experiments/v2-essential-core/opensocrates-core-experimental.zip HEAD:plugin-src/experimental-core/skills/opensocrates-core SKILL.md LICENSE
```

For a Codex project, extract that folder into `.agents/skills/`, preserving any
existing folder as described above. Claude's [custom skill instructions](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)
describe uploading a ZIP with the skill folder at its root via **Customize →
Skills**. Claude's instructions say skills require code execution to be
enabled; organization settings may also restrict them. The archive structure
has been inspected locally, but uploading, activation, and use of this candidate
in Claude have not been tested. Creating the ZIP does not install or publish
it. Its name differs from the 1.x skill; do not use the 1.x skill's Replace
action to install this experiment.

## Try a decision

> We planned to buy a cloud tool, but the work now has to run offline. Compare
> buying, building, and a temporary manual process. We do not yet know whether
> the tool supports offline use or whether the team can maintain a custom tool.

A useful response can keep the mandatory offline requirement separate from
preferences such as convenience, and compare the options without assuming
offline support, staff capacity, or the feasibility of manual work. A tool
that cannot work offline fails the requirement; one whose offline support is
unknown remains conditional, not rejected or approved. The response can
identify an accessible way to check offline support, explain how the answer
could affect the choice, and continue any work that does not depend on it.
This is an illustrative prompt, not a recorded test result.

If comparing answers, use the same task and relevant context in separate
conversations, including a short ordinary instruction as well as no added
instruction. Inspect whether the skill actually reached the model, whether the
answers help, and whether the extra guidance gets in the way. Results from one
example do not establish general effectiveness.
