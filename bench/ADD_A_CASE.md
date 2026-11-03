# Add one public bench case

This is the first contribution the harness asks for. Keep the repository pull
request template, and add the block below under Summary.

## Checklist

- [ ] Search open cases so the scenario is not a duplicate.
- [ ] Add `bench/cases/<id>.json` with `public_synthetic: true`.
- [ ] Use fictional facts only. No private prompts, transcripts, credentials, or real customer text.
- [ ] State the user task in the user's language. Do not require the headings "Recipient body" or "Requester memo".
- [ ] Write checks against envelope fields `body` and `requester_notes` only. A rule must be decidable without a model. For `forbid_text`, list `clear_exceptions` for spans that are clearly not the forbidden claim, and `ambiguous_cues` for nearby wording that must stay `needs_human_review`. Do not treat a product scanner flag as the bench result. A paraphrase that avoids the literal pattern is a blind spot, not a pass you have proved.
- [ ] If the case allows arithmetic, put the operands in `materials` and set `arithmetic_policy.pretended_verification` to `fail`.
- [ ] Add an authored fixture only when you want to show the scorer a concrete envelope. Set `origin` to `authored_example` and `model_called` to `false`. A fixture cannot verify a model call. Say what the text illustrates.
- [ ] Leave a condition without a fixture when you do not have an output. The runner records `model_unavailable`.
- [ ] Do not invent a model score, a pass rate, or an effect size.
- [ ] Run `make bench`. In the pull request, paste the new rows and say whether a live model was called.

## Pull request snippet

```markdown
### Bench case

- Case id:
- Public synthetic facts only.
- Checks use the bench envelope (`body`, `requester_notes`) and do not require fixed English headings.
- Fixture origin: authored_example / recorded_model_output / none
- Live model called: no / yes, with the command name and the reason code
- `make bench` rows for this case:
```

## Reason codes

| Code | When to use it |
| --- | --- |
| `pass` | Every rule check passed on an envelope. |
| `condition_fail` | The envelope parsed, and at least one decidable rule failed. |
| `needs_human_review` | A literal match is ambiguous. Do not record it as pass or fail. |
| `model_unavailable` | No fixture and no live command, or the command executable is missing. Execution may have been attempted. Model use stays unverified. |
| `model_error` | A command ran and did not return a usable envelope. That failure does not verify a model call. |
| `input_error` | The case, fixture, or condition manifest is invalid. |
| `scorer_error` | A rule could not be applied. |
