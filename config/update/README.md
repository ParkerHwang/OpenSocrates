# Native update trust input

`root.json` and `identities.json` are canonical public trust data. The Go
generator copies them byte-for-byte into the runtime embed package under
`src/opensocrates/internal/update/trustconfig/`; generated-check verifies the
copies against these canonical inputs. Runtime source remains entirely under
`src/opensocrates/`. The root currently contains
`{}` deliberately: production update trust is unavailable. This is not a test
root, a network bootstrap URL, or authorization to publish releases.

Before a production build, release maintainers must obtain an independently
reviewed public TUF root signed at the offline root role threshold. Keep all
private keys outside the checkout and release bundle. Root, targets, snapshot,
and timestamp roles must be separated; document offline threshold custody,
expiry renewal, online key compromise revocation, and recovery operators.

The updater uses pinned go-tuf v2.4.2 for root chaining, role signatures,
expiry, rollback and consistent metadata. A private disposable cache feeds an
atomic owner-checked durable trust envelope. Accepted metadata is persisted
before executable activation, even when a later metadata phase fails. Local
runtime rollback never restores an older trust envelope.

Metadata: `https://parkerhwang.github.io/OpenSocrates/updates/stable/metadata/`.
Signed target aliases: `stable/darwin-arm64/opensocrates.archive` and
`stable/windows-amd64/opensocrates.archive`. Their signed custom
`package_path` identifies an immutable GitHub Release tag and asset; every
archive has a signed length and SHA256. HTTPS redirect hosts are explicitly
allowlisted, downloads and timeouts bounded, and custom release compatibility
must pass before activation. Publishing metadata is a separate approved release
step. Do not enable the scheduler in an unsigned preparation build.

Official sources used in choosing the APIs:

- https://github.com/theupdateframework/go-tuf/releases/tag/v2.4.2
- https://github.com/theupdateframework/go-tuf/blob/v2.4.2/metadata/updater/updater.go
- https://github.com/theupdateframework/specification/blob/master/tuf-spec.md
- https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
- https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema
- https://learn.microsoft.com/en-us/windows/win32/taskschd/logontrigger
