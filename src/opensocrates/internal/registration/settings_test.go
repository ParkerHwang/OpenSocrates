package registration

import (
	"bytes"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"path/filepath"
	"testing"
)

func TestCodexScopedSettingsRestorePreservesForeignBytes(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "managed-marketplaces", "opensocrates")
	path := filepath.Join(base, "config.toml")
	before := []byte("# foreign comment\nmodel = 'synthetic'\nprecise = 9_007_199_254_740_993\n\n[plugins.\"opensocrates@opensocrates\"] # owned comment\nenabled = false\ncustom = '한글😀'\n\n[plugins.\"other@other\"]\nenabled = true\n")
	if e := platform.AtomicWrite(path, before, 0600); e != nil {
		t.Fatal(e)
	}
	n := Native{Host: "codex"}
	data, e := n.readSettings(root)
	if e != nil {
		t.Fatal(e)
	}
	after := []byte("# foreign comment\nmodel = 'synthetic'\nprecise = 9_007_199_254_740_993\n\n[plugins.\"other@other\"]\nenabled = true\n")
	if e := platform.AtomicWrite(path, after, 0600); e != nil {
		t.Fatal(e)
	}
	if e := n.restoreSettings(root, data); e != nil {
		t.Fatal(e)
	}
	got, e := platform.ReadOwnedFile(path, 4<<20)
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.HasPrefix(got, after) || !bytes.Contains(got, []byte("# owned comment")) {
		t.Fatal("foreign source spelling or owned comment changed")
	}
	restored, e := n.readSettings(root)
	if e != nil || restored[settingsKey] != data[settingsKey] {
		t.Fatal("owned settings not restored")
	}
}
func TestCodexChangedOwnedSettingsPreserved(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "managed-marketplaces", "opensocrates")
	path := filepath.Join(base, "config.toml")
	before := []byte("[plugins.\"opensocrates@opensocrates\"]\nenabled = false\ncustom = 'old'\n")
	if e := platform.AtomicWrite(path, before, 0600); e != nil {
		t.Fatal(e)
	}
	n := Native{Host: "codex"}
	data, e := n.readSettings(root)
	if e != nil {
		t.Fatal(e)
	}
	modified := []byte("[plugins.\"opensocrates@opensocrates\"]\nenabled = true\ncustom = 'foreign edit'\n")
	if e := platform.AtomicWrite(path, modified, 0600); e != nil {
		t.Fatal(e)
	}
	if e := n.restoreSettings(root, data); e == nil {
		t.Fatal("changed owned settings overwritten")
	}
	actual, e := platform.ReadOwnedFile(path, 4<<20)
	if e != nil || !bytes.Equal(actual, modified) {
		t.Fatal("changed config destroyed")
	}
}
func TestTOMLMultilineAndForeignPrefixNeverCaptured(t *testing.T) {
	raw := []byte("message = '''\n[plugins.\"opensocrates@opensocrates\"]\nenabled = true\n'''\n[plugins.\"opensocrates@opensocrates-other\"]\nenabled = true\n")
	ranges, source, e := managedRanges(raw, "opensocrates@opensocrates")
	if e != nil || len(ranges) != 0 || source != "" {
		t.Fatal("foreign or string-literal table captured")
	}
}
