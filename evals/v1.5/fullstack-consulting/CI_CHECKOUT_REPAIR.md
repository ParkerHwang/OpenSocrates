# Windows CI checkout repair

CI run 36313029304 failed on exact commit
`2c4247e359ee94cf8e594c9945191e81885ae28b` before the Windows tests started.
Git for Windows could not create six preserved npm content-cache files below a
completed synthetic artifact because their complete paths exceeded its default
path handling. The failure was a checkout/configuration problem, not a failed
OpenSocrates runtime assertion or an outcome-model failure.

The Windows job now supplies `core.longpaths=true` through command-scoped
`GIT_CONFIG_COUNT/KEY_0/VALUE_0` environment variables. This covers checkout and
the later clean-tree provenance inspection. It does not write global settings,
alter the user's host, rename evidence paths, shorten candidate filenames, remove
cache evidence, modify frozen bytes, or rerun a model outcome.

[Git for Windows documents long-path support](https://github.com/git-for-windows/git/blob/main/Documentation/config/core.adoc)
for built-in commands. [Git documents the process-scoped configuration variables](https://git-scm.com/docs/git-config#_environment).
The actual hosted Windows run remains the decisive verification; macOS inspection
of the environment setting alone is not a Windows pass. Preserve the original
failed run and report the repaired commit's CI independently.
