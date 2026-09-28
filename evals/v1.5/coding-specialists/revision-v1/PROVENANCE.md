# Specialist provenance and review boundary

The externally authored v0.1.0 package remains unchanged. Its 24 original file
digests and the corrected v0.1.1 digests are recorded in baseline.json. The public
runtime source in `plugin-src/shared/coding-specialists/v0.1.1/` matches the twelve
corrected prompt files exactly. The original author's full source map binds 37
repository files at `53e36e0`; the correction does not recast that authoring snapshot
as current runtime behavior. The five integrated cells use an actual separately
qualified candidate ZIP.

The main integrator read all twelve prompts, their integration contract, validator,
source notes and worked-case design. Primary review repaired the Korean terminology,
runtime discriminator, approved-contract-change ambiguity and installation-status
wording. Independent human language review remains unavailable. Published authoring
examples and their worked answers were not included in outcome prompts. Integrated
cases are bounded usability/regression patterns, not held-out quality samples.

## Intellectual basis recorded by the author

| Procedure | Author's cited primary basis | Scope of attribution |
| --- | --- | --- |
| Contracts | [Eiffel: Design by Contract and Assertions](https://www.eiffel.org/doc/eiffelstudio/I2E-_Design_by_Contract_and_Assertions) | Established contract reasoning adapted into an agent-facing procedure |
| Transitions | [Lamport: Specifying Systems](https://lamport.azurewebsites.net/tla/book-02-08-08.pdf), [AWS: idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | Authored combination of state/event and retry reasoning; not a formal model check |
| Ownership | [Rust: references and borrowing](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html), [React: state structure](https://react.dev/learn/choosing-the-state-structure) | Original cross-language composition informed by language/framework guidance; not a universal borrowing or normalization mandate |

These are the authoring map's citations; this integration pass reviewed that map
and the resulting content rather than repeating the entire literature review.
The main thread separately read the official OpenAI guidance on
[skills/prompts](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)
and the [Codex platform](https://developers.openai.com/blog/codex-as-a-platform).
None of these sources proves that this library improves the tested model. Vendor
benchmarks, profiles and workflow defaults are not imported as OpenSocrates evidence.

The procedure names, selection policy and task-facing sequence are versioned
authored content. They are not registered additions to the 48-method native catalog.
No native Chinese API, hidden prompt compiler, extra model or new memory policy is
introduced. General procedure bodies, evidence/stop contracts and schema bytes are
preserved. Static availability, observed emitted bodies, reported use and actual
cognitive application remain different evidence states.
