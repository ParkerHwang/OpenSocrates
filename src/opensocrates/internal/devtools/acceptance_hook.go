package devtools

import (
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

// The supported shells come from the pinned host's normal environment-shell
// path. A cmd/custom-shell fallback is not silently treated as qualification.
func qualifiedHookShell(target string) string {
	if target == "darwin-arm64" {
		return "zsh_posix"
	}
	if target == "windows-x64" {
		return "windows_powershell_5_1"
	}
	return "unsupported"
}
func configuredHookMatches(command, host, target, event string) bool {
	normalized := map[string]string{"SessionStart": "session_started", "UserPromptSubmit": "user_prompt_submitted", "PreToolUse": "tool_succeeded", "PostToolUse": "tool_succeeded", "PreCompact": "pre_compaction", "Stop": "completion_candidate", "SessionEnd": "session_ended"}
	value, ok := normalized[event]
	if !ok || (host != "codex" && host != "claude") {
		return false
	}
	if host == "claude" && (target != "darwin-arm64" || (event != "SessionStart" && event != "UserPromptSubmit" && event != "Stop" && event != "SessionEnd")) {
		return false
	}
	suffix := " hook " + host + " " + value
	switch target {
	case "darwin-arm64":
		root := "$PLUGIN_ROOT"
		if host == "claude" {
			root = "$CLAUDE_PLUGIN_ROOT"
		}
		return command == "\""+root+"/runtime/darwin-arm64/opensocrates\""+suffix
	case "windows-x64":
		return host == "codex" && command == `& "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe"`+suffix
	}
	return false
}

// configuredHookInvocation passes the actual closed generated string unchanged
// to the host shell. It never substitutes a filesystem path into command code.
func configuredHookInvocation(command, host, target string) (string, []string, error) {
	if !configuredHookMatches(command, host, target, "SessionStart") {
		return "", nil, errors.New("configured_session_hook_invalid")
	}
	switch target {
	case "darwin-arm64":
		shell, e := platform.SystemExecutable("zsh")
		if e != nil {
			return "", nil, e
		}
		return shell, []string{"-c", command}, nil
	case "windows-x64":
		shell, e := platform.SystemExecutable("powershell.exe")
		if e != nil {
			return "", nil, e
		}
		return shell, []string{"-NoProfile", "-Command", command}, nil
	}
	return "", nil, errors.New("configured_hook_shell_unsupported")
}
