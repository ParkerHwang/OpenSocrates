package hosts

import "testing"

func TestClosedDistributionScope(t *testing.T) {
	all, err := Expand("all")
	if err != nil || len(all) != 1 || all[0] != Codex {
		t.Fatal("legacy all semantics changed")
	}
	claude, _ := Get(Claude)
	if claude.Supports(WindowsX64, Global, "install") {
		t.Fatal("native Windows Claude is excluded")
	}
	account, _ := Get(ClaudeAccount)
	if account.RuntimeAdapter || account.ScheduledUpdates || account.Supports(MacARM64, Export, "install") {
		t.Fatal("account export cannot imply runtime activation")
	}
	for _, id := range []ID{Claude, Antigravity, ClaudeAccount} {
		p, _ := Get(id)
		if p.ScheduledUpdates {
			t.Fatal("additional profile lacks scheduled qualification")
		}
	}
	if _, err := Get("opencode"); err == nil {
		t.Fatal("retired host silently adopted")
	}
}

func TestWindowsARM64DistributionScope(t *testing.T) {
	for _, id := range []ID{Codex, Antigravity, ClaudeAccount} {
		p, e := Get(id)
		if e != nil {
			t.Fatal(e)
		}
		scope, command := Global, "install"
		if id == ClaudeAccount {
			scope, command = Export, "export"
		}
		if !p.Supports(WindowsARM64, scope, command) {
			t.Fatal("agreed Windows ARM64 profile unavailable")
		}
	}
	claude, _ := Get(Claude)
	if claude.Supports(WindowsARM64, Global, "install") {
		t.Fatal("Windows ARM64 silently added native Claude Code")
	}
	if got := DistributionTarget("windows", "amd64"); got != "windows-x64" {
		t.Fatal("released x64 asset spelling changed")
	}
	if got := DistributionTarget("windows", "arm64"); got != "windows-arm64" {
		t.Fatal("ARM64 distribution spelling differs")
	}
	for _, target := range []string{"windows-arm64", "windows-x64", "darwin-arm64"} {
		goos, arch, ok := ParseDistributionTarget(target)
		if !ok || DistributionTarget(goos, arch) != target {
			t.Fatal("native target round trip failed")
		}
	}
	for _, target := range []string{"windows-386", "windows-amd64", "darwin-amd64", "linux-arm64"} {
		if _, _, ok := ParseDistributionTarget(target); ok {
			t.Fatal("unagreed native target accepted")
		}
	}
	all, _ := Expand("all")
	if len(all) != 1 || all[0] != Codex {
		t.Fatal("host all semantics changed")
	}
}
