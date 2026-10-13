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

With the installed native executable on Mac:

```sh
./opensocrates locale get
./opensocrates locale set fr
./opensocrates locale set th
./opensocrates locale set follow
./opensocrates locale reset
```

With the native Windows x64 or ARM64 executable:

```powershell
.\opensocrates.exe locale get
.\opensocrates.exe locale set pt
.\opensocrates.exe locale reset
```

For source development, use the Go runtime command below `src/opensocrates/`.
End users require no Go, Python, Node.js or npm. The native `locale` command
has no host argument; [maintenance v1.5.2 commands](v1.5.2.md) remain historical.

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
`./opensocrates decision` on Mac, `.\opensocrates.exe decision` on
Windows. Native `decision` has no host argument. Follow the
installed `skills/opensocrates/references/decision/request.json` envelope and
routing contract; do not pass an invented `--locale` flag.

The retained SDK selector is unavailable on Windows. Account skills and
Antigravity content use the corresponding language guide and references without
this preference store. Setting a native preference does not upload, activate or
configure a Claude account skill. Existing two-/four-language content remains
historical; choose only available languages when using an older package.
