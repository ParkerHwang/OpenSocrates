# Output Brief: an OpenSocrates 2.0 candidate

This is an experimental, self-contained skill candidate for drafting messages,
reports, and decision documents for a reader. It asks an assistant to preserve
material facts, uncertainty and the user's choices while producing a usable
artifact. It does not send messages or persist user material.

The candidate is not an integrated 2.0 product or evidence of improved answers.
The shared skill source is under
[`plugin-src/experimental-output-brief/skills/output-brief`](../../../plugin-src/experimental-output-brief/skills/output-brief/SKILL.md).
Simply making a skill available does not establish discovery, activation,
reading, or use.

## Experimental packages

From the repository root, run `python3 docs/experiments/v2-output-brief/package.py`.
It produces two local archives from the same skill under
`build/experiments/v2-output-brief/`: an OpenAI-format plugin archive and a
Claude skill archive. These are experimental, unpublished packages, not a 2.0
release. Their generation does not install or enable anything.

- The OpenAI package follows the documented [plugin layout](https://developers.openai.com/plugins/build/plugins).
  Local installation or directory distribution depends on the target surface.
- Claude documents uploading a ZIP containing the skill folder through
  **Customize → Skills**; see [Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)
  for account and code-execution requirements.

Neither archive has yet been qualified for installation, discovery, or use on a
real host. Availability can vary by plan, account, organization, and surface.

## Try it with a fictional request

Give the same request and source facts to the same model and host in two separate
sessions, once without this skill and once with it enabled. Keep the conditions
as comparable as the host permits, and record the exact skill bytes, model,
host, and whether the skill was actually made available. A single comparison is
an example, not a general result. Avoid uploading real private work to a public
evaluation or repository.

> Draft a short English email to visitors about a workshop. There is room for
> 24 people. The venue is still being considered, and no one has agreed to
> photography. Ask visitors to express interest. Explain any remaining question
> to me in Korean.

An adequate email can invite expressions of interest without claiming the venue
is booked or photography approved. A note to the requester may be in Korean;
the email should be in English. Compare accuracy, clarity, usefulness, questions
and time, rather than only checking for particular words. The prompt by itself
does not measure actual skill discovery or use.

This candidate is intended for joint review with the separate personal-rule and
public-benchmark proposals. No host integration, benchmark results, adoption,
or superiority over an unassisted model is claimed.
