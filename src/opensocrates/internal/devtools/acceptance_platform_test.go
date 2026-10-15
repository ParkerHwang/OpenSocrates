package devtools

import (
	"os"
	"testing"
)

func TestNativeAcceptanceSeparatesWindowsArchitectures(t *testing.T) {
	for _, scenario := range []struct{ goos, goarch, target string }{
		{"darwin", "arm64", "darwin-arm64"},
		{"windows", "amd64", "windows-x64"},
		{"windows", "arm64", "windows-arm64"},
		{"windows", "386", "unsupported"},
		{"darwin", "amd64", "unsupported"},
		{"linux", "arm64", "unsupported"},
	} {
		if actual := nativeAcceptanceTargetFor(scenario.goos, scenario.goarch); actual != scenario.target {
			t.Fatal("native evidence target conflated or widened")
		}
	}
	for _, target := range []string{"windows-x64", "windows-arm64"} {
		command := `& "$env:PLUGIN_ROOT\runtime\` + target + `\opensocrates.exe" hook codex session_started`
		if !configuredHookMatches(command, "codex", target, "SessionStart") || qualifiedHookShell(target) != "windows_powershell_5_1" {
			t.Fatal("native Windows command profile rejected")
		}
		other := "windows-arm64"
		if target == other {
			other = "windows-x64"
		}
		if configuredHookMatches(command, "codex", other, "SessionStart") || configuredHookMatches(command, "claude", target, "SessionStart") {
			t.Fatal("emulated/foreign runtime command or unsupported Windows host accepted")
		}
	}
}

func TestAcceptanceArtifactArchitectureCannotBeRelabeled(t *testing.T) {
	target := nativeAcceptanceTarget()
	if target == "unsupported" {
		t.Skip("supported native runtime required")
	}
	self, err := os.Executable()
	if err != nil {
		t.Fatal("native executable unavailable")
	}
	if !acceptanceExecutableMatchesTarget(self, target) {
		t.Fatal("native executable architecture unavailable or mismatched")
	}
	for _, other := range []string{"windows-x64", "windows-arm64", "darwin-arm64", "unsupported"} {
		if other != target && acceptanceExecutableMatchesTarget(self, other) {
			t.Fatal("native executable relabeled as a different architecture")
		}
	}
}
