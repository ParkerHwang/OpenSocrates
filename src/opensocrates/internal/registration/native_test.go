package registration

import (
	"context"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"strings"
	"testing"
)

type fakeRunner struct {
	root     string
	disabled bool
	commands []string
}

func (f *fakeRunner) Run(_ context.Context, _ string, args []string) ([]byte, error) {
	command := strings.Join(args, " ")
	f.commands = append(f.commands, command)
	if command == "plugin marketplace list --json" {
		return json.Marshal(map[string]any{"marketplaces": []any{map[string]any{"name": "opensocrates", "root": f.root, "future": true}}})
	}
	if strings.HasPrefix(command, "plugin list") {
		return json.Marshal(map[string]any{"installed": []any{map[string]any{"pluginId": "opensocrates@opensocrates", "version": "1.5.0", "enabled": !f.disabled, "future": "ignored"}}, "available": []any{}})
	}
	return nil, diagnostics.New(diagnostics.Activation, "unexpected-fixture-mutation")
}
func TestCodexDisabledUpdateNeverReregisters(t *testing.T) {
	f := &fakeRunner{root: t.TempDir(), disabled: true}
	n := Native{Host: "codex", Runner: f}
	before, e := n.Inspect(context.Background(), f.root)
	if e != nil || before.Enabled {
		t.Fatal(e)
	}
	if e := n.Replace(context.Background(), before, before); e != nil {
		t.Fatal(e)
	}
	for _, command := range f.commands {
		if strings.Contains(command, " add ") || strings.Contains(command, " remove ") {
			t.Fatal("disabled integration registration changed")
		}
	}
}
func TestCodexForeignRegistrationRefused(t *testing.T) {
	f := &fakeRunner{root: t.TempDir()}
	n := Native{Host: "codex", Runner: f}
	if _, e := n.Inspect(context.Background(), t.TempDir()); e == nil {
		t.Fatal("foreign registration adopted")
	}
}
