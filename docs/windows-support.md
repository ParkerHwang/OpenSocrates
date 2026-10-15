# Windows x64 native support — v1.6.0 candidate

[한국어](windows-support.ko.md) · [Native guide](native-v1.6.md)

The candidate migrates the supported Codex CLI/Desktop and Antigravity
workspace/global paths to Go and retains Claude account verification/export.
Native Windows Claude Code is excluded. Windows ARM64, WSL, network shares and
additional platforms are not qualified. End users need the native `.exe` and
Windows x64 bundle, without Python, Node.js, npm or Go.

```text
.\opensocrates.exe verify --host codex --package "C:\Downloads\opensocrates-v1.6.0-windows-x64.zip"
.\opensocrates.exe install --host codex --package "C:\Downloads\opensocrates-v1.6.0-windows-x64.zip"
.\opensocrates.exe status --host codex
```

Use `adopt` instead of `install` to explicitly migrate a verified owned v1.5 npm
installation. Preserve settings, registrations, trust, disabled state and one
update owner. `--host all` means Codex only. Quote absolute local-drive workspace
and output paths. Do not use shell or PowerShell wrappers as the first-party
runtime/install implementation; the commands above invoke the native Go binary.

Codex opt-in stable scheduling uses the per-user Task Scheduler task outside
hooks, with 24-hour checks and delayed login. Signed metadata verification and
compatibility/expiry/rollback guards apply. Major/breaking schema updates are
not automatic. Production root/signing and actual native scheduler evidence are
release gates. Manual lifecycle for Antigravity remains separate; exporting an
account ZIP does not upload or activate it.

Actual Windows validation must exercise protected DACL/current owner checks,
held parent handles, reparse/junction refusal, exclusive locks, long Unicode
paths, binary I/O, archive aliases/streams/case collisions, modified foreign
files, concurrent operations and Go helper replacement of in-use executables.
Cross-compilation cannot establish those behaviors. Legacy credential-copy and
POSIX context access remain unavailable. Hooks fail open; host trust requires
interactive review and a fresh session.

Contributors use pinned Go 1.27.2 and the Go-native source/package/lifecycle
checks in [CONTRIBUTING.md](../CONTRIBUTING.md) on Windows x64. Native Mac gates
remain required separately. A native fixture pass, authenticated CLI delivery,
Desktop GUI loading, clean-machine install and platform signing/SmartScreen
are distinct evidence cells. Record exact commit/commands/results and missing
cells in the implementation handoff.

The [v1.5 guide](windows-v1.5.md) and [v1.4 worklog](windows-v1.4.0-worklog.md)
are historical release evidence, not validation of this Go candidate.

Codex CLI/Desktop hook command execution is qualified only with the normal
inherited default PowerShell context. The configured native command is
`& "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe"`; it is OS/host
configuration, not a first-party PowerShell wrapper. Custom/cmd fallback shells
are unsupported and fail open explicitly. Installation diagnostics use
`opensocrates.exe manage diagnose --host HOST`, separate from runtime diagnostics.
