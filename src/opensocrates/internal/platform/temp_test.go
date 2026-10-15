package platform

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestExplicitOwnedTemporaryObjects(t *testing.T) {
	base := t.TempDir()
	dir, e := MkdirTemp(base, "stage-*-suffix")
	if e != nil {
		t.Fatal(e)
	}
	if e = Guard(dir); e != nil {
		t.Fatal("new temporary directory not current-user private")
	}
	if !strings.HasPrefix(filepath.Base(dir), "stage-") || !strings.HasSuffix(filepath.Base(dir), "-suffix") {
		t.Fatal("temporary pattern substitution differs")
	}
	f, e := CreateTemp(dir, "export-*")
	if e != nil {
		t.Fatal(e)
	}
	name := f.Name()
	if !filepath.IsAbs(name) || filepath.Dir(name) != dir {
		f.Close()
		t.Fatal("temporary file does not report actual name")
	}
	if _, e = f.Write([]byte("owned temporary")); e != nil {
		f.Close()
		t.Fatal(e)
	}
	if e = f.Sync(); e != nil {
		f.Close()
		t.Fatal(e)
	}
	if e = f.Close(); e != nil {
		t.Fatal(e)
	}
	if e = Guard(name); e != nil {
		t.Fatal("new temporary file not current-user private")
	}
	b, e := ReadFile(name, 100)
	if e != nil || string(b) != "owned temporary" {
		t.Fatal("temporary content differs")
	}
	if e = RemoveTree(dir); e != nil {
		t.Fatal(e)
	}
}
func TestTemporaryFactoryRejectsAliasesAndExistingEntries(t *testing.T) {
	base := t.TempDir()
	for _, pattern := range []string{"../outside", "dir/child", "dir\\child", "nul\x00"} {
		if _, e := MkdirTemp(base, pattern); e == nil {
			t.Fatal("unsafe directory pattern accepted")
		}
		if f, e := CreateTemp(base, pattern); e == nil {
			f.Close()
			t.Fatal("unsafe file pattern accepted")
		}
	}
	existing := filepath.Join(base, "existing")
	if e := os.Mkdir(existing, 0700); e != nil {
		t.Fatal(e)
	}
	if e := mkdirExclusive(existing); !os.IsExist(e) {
		t.Fatal("existing temporary directory adopted")
	}
	file := filepath.Join(base, "existing-file")
	if e := os.WriteFile(file, []byte("sentinel"), 0600); e != nil {
		t.Fatal(e)
	}
	if f, e := createExclusiveTemp(file); !os.IsExist(e) {
		if f != nil {
			f.Close()
		}
		t.Fatal("existing temporary file adopted")
	}
	b, e := os.ReadFile(file)
	if e != nil || string(b) != "sentinel" {
		t.Fatal("existing file changed")
	}
}
