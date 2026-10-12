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
