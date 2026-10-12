# Frozen restricted-current-user original-installer probe

This inactive `.txt` source records the one-off Windows ARM64 probe at
001c75a67130946d94022218883e0f8c884cfec2. It is not an active product installer,
credential tool or current acceptance gate.

The parent's existing primary token was restricted with
`CreateRestrictedToken(DISABLE_MAX_PRIVILEGE)`, Administrators marked deny-only,
and the current User SID set as default owner **on the new token only**.
`CreateProcessAsUserW` launched the isolated legacy Node recipe. A synthetic
new file's owner matched the user. Snapshot comparison verified the original
owner/groups/privileges/default DACL unchanged; no account/group/OS policy or
original installer source was changed. A restricted token is not a separate
standard-user account or clean-machine environment.

The authentic npm TGZ private-prefix install succeeded. The unmodified original
v1.5 installer exited 1 at its Windows private-helper invocation, with no useful
helper diagnostic. No source-equivalent layout fallback was used and adoption
was not reached. The receipt therefore remains **UNAVAILABLE**, not successful
original-installer qualification. Use a compatible ordinary user environment;
do not grant new privileges, change desktop/system DACLs or weaken owner guards
to make this probe pass.

Recorded commands: cross-built this Go source with `GOOS=windows GOARCH=arm64
CGO_ENABLED=0 go build`; ran the native launcher from an explicitly owned
private fixture after copying checksum-verified legacy assets and the native
001c75a bundle. The exact source SHA256 is in the content-free receipt. Private
fixture paths, SID values, raw output and credentials are not retained here.
The launcher kills its job on close and closes token/process handles.

Official API references:

- [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken)
- [CreateProcessAsUserW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw)
- [Owner of a new object](https://learn.microsoft.com/en-us/windows/win32/secauthz/owner-of-a-new-object)
