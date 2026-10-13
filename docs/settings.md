# Reasoning locale preference

[한국어](settings.ko.md) · [v1.5.2 language and platform scope](v1.5.2.md)

The native runtime exposes a closed locale preference. It controls the retained
selector's instruction language; it is not an npm installer option, answer
language setting, host UI setting or guarantee of automatic skill use.

| Code | Authored instruction language |
| --- | --- |
| `en` | English |
| `ko` | Korean |
| `zh` | Simplified Chinese |
| `ja` | Japanese |
| `fr` | French |
| `de` | German |
| `it` | Italian |
| `es` | Spanish |
| `pt` | Portuguese, Brazilian orthography under the generic code |
| `th` | Thai |
| `follow` | Clear the stored preference and follow current-input detection |

From the installed Codex package root on Mac:

```sh
bin/launch.sh locale codex get
bin/launch.sh locale codex set fr
bin/launch.sh locale codex set th
bin/launch.sh locale codex set follow
bin/launch.sh locale codex reset
```

From the Windows x64 Codex package root:

```powershell
node bin/launch.mjs locale codex get
node bin/launch.mjs locale codex set pt
node bin/launch.mjs locale codex reset
```

The corresponding source-development entry in the locked repository environment:

```sh
uv run --locked python -m opensocrates locale get
uv run --locked python -m opensocrates locale set de
uv run --locked python -m opensocrates locale reset
```

`set` takes exactly one of `en|ko|zh|ja|fr|de|it|es|pt|th|follow`. `get` and `reset`
take no language argument. Unsupported choices and extra arguments are rejected;
there is no arbitrary locale or installer `--locale` argument. `follow` and
`reset` clear only `locale_preference` through the existing settings mutation
path; other settings and preferences remain governed by their existing
normalization and persistence contracts.

A trusted request preference overrides a stored one. Without either, any
recognized kana selects Japanese. Otherwise dominant Thai, Hangul or Han selects
Thai, Korean or Chinese. Empty input, ties and unknown scripts use English.
French, German, Italian, Spanish and Portuguese share Latin script and need an
explicit or saved choice. Han-only Japanese needs `ja` to resolve ambiguity.
Script detection counts characters, not words, and is not language recognition
for every multilingual input.

Stateless `decision` requests require explicit JSON `locale` from the ten authored
language codes, never `follow`, and read no stored settings. Use
`bin/launch.sh decision codex` on Mac, `node bin/launch.mjs decision codex` on
Windows, or `bin/launch.sh decision claude` in the Mac Claude package. Follow the
installed `skills/opensocrates/references/decision/request.json` envelope and
routing contract; do not pass an invented `--locale` flag.

The retained SDK selector is unavailable on Windows. Account skills and
Antigravity content use the corresponding language guide and references without
this preference store. Setting a native preference does not upload, activate or
configure a Claude account skill. Existing two-/four-language content remains
historical; choose only available languages when using an older package.
