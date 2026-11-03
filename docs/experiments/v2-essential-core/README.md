# OpenSocrates: essential core experiment

This small, standalone skill is a new 2.0 candidate: help a person make
progress, while distinguishing what is established from what is assumed or
unknown. When a choice matters, it should make the trade-off and a condition
that could change the decision clear. For simple work it should stay out of the
way.

The entire candidate is [`SKILL.md`](../../../plugin-src/experimental-core/skills/opensocrates-core/SKILL.md).
It is plain text, with no scripts, tools, hooks, installer, or telemetry. It can
be read and used as instructions, or provided to a compatible host using that
host's skill setup. This repository does not yet provide an installable package.
It does not invoke the
1.x method library; connecting a particular method is future work, not a
capability claimed here. Existing 1.x files are unchanged.

The earlier [output-brief experiment](https://github.com/ParkerHwang/OpenSocrates/pull/164)
is preserved separately, including its scanner and benchmark. They are not part
of this candidate. This is an experiment, not a release or a claim that the
skill improves outcomes over an unassisted model or a short instruction.

## Try the local skill in Codex

Copy the `opensocrates-core` skill folder into your project's
`.agents/skills/` folder, then start a new Codex session for that project and
explicitly request `$opensocrates-core` with your task. If a folder with that
name already exists, back it up or choose another project before copying. To
remove this experiment, remove the copied folder.

In one temporary project using Codex CLI 0.166.0-alpha.5.1, an explicit
`$opensocrates-core` request led to a successful read of the copied skill file
and a response to a synthetic decision task. This observation does not prove
automatic discovery, application, or general usefulness, or establish behavior
in other hosts.

## Try a decision

> We planned to buy a cloud tool, but the work now has to run offline. Compare
> buying, building, and a temporary manual process. We do not yet know whether
> the tool supports offline use or whether the team can maintain a custom tool.

A useful response can compare the options without assuming offline support,
staff capacity, or the feasibility of manual work. It can identify a small
next step that does not depend on those unknowns and explain what would change
its recommendation. This is an illustrative prompt, not a recorded test result.

If comparing answers, use the same task and relevant context in separate
conversations, including a short ordinary instruction as well as no added
instruction. Inspect whether the skill actually reached the model, whether the
answers help, and whether the extra guidance gets in the way. Results from one
example do not establish general effectiveness.
