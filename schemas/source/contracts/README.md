# Language-neutral v1 wire contracts

The JSON Schema documents in this directory are canonical source inputs for the
Go generator. They were promoted byte-for-byte from the released v1.5.0 schema
graph. This makes the frozen wire contract independent of Python dataclass
reflection. Change these source documents, then run `make generate`; do not edit
`schemas/v1` outputs. Schema identifiers and additive compatibility remain fixed.
