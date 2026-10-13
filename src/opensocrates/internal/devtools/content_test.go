package devtools

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func generatorRepository(t *testing.T) string {
	t.Helper()
	p, e := filepath.Abs("../../../..")
	if e != nil {
		t.Fatal(e)
	}
	return p
}
func TestReleasedContentGenerationEquivalence(t *testing.T) {
	root := generatorRepository(t)
	stage := t.TempDir()
	for _, path := range []string{"content", "schemas/source"} {
		if e := copyCheckTree(filepath.Join(root, path), filepath.Join(stage, path)); e != nil {
			t.Fatal(e)
		}
	}
	before := map[string][]byte{}
	for _, name := range []string{"compiled-content.bundle.json", "compiled-reasoning-content.bundle.json", "compiled-response-policy.json"} {
		b, e := os.ReadFile(filepath.Join(root, "content", name))
		if e != nil {
			t.Fatal(e)
		}
		before[name] = b
	}
	bundle, e := ReadObject(filepath.Join(root, "content/compiled-content.bundle.json"))
	if e != nil {
		t.Fatal(e)
	}
	if e = GenerateContent(stage, str(bundle["product_version"])); e != nil {
		t.Fatal(e)
	}
	for name, expected := range before {
		actual, e := os.ReadFile(filepath.Join(stage, "content", name))
		if e != nil {
			t.Fatal(e)
		}
		if !bytes.Equal(expected, actual) {
			t.Errorf("%s differs from released content baseline", name)
		}
	}
	generated, e := ReadObject(filepath.Join(stage, "content/compiled-content.bundle.json"))
	if e != nil {
		t.Fatal(e)
	}
	if generated["source_tree_hash"] != "sha256:e1e11f7a772cb2a3f6c8dc0e3b22b0787cdc903de69842de957577a177cee7be" || generated["normalized_semantic_hash"] != "sha256:b5fc82f5ce8725bd23b7d270014f90853e39474e7b00ae4f20553a484524c659" {
		t.Fatal("frozen source or semantic identity changed")
	}
}
func TestGenerationRejectsInvalidAuthoring(t *testing.T) {
	root := generatorRepository(t)
	stage := t.TempDir()
	for _, path := range []string{"content", "schemas/source"} {
		if e := copyCheckTree(filepath.Join(root, path), filepath.Join(stage, path)); e != nil {
			t.Fatal(e)
		}
	}
	path := filepath.Join(stage, "content/methods/abduction/method.yaml")
	source, e := ReadObject(path)
	if e != nil {
		t.Fatal(e)
	}
	source["family"] = "unrecognized"
	if e = writeJSON(path, source); e != nil {
		t.Fatal(e)
	}
	if e = GenerateContent(stage, "1.6.0"); e == nil {
		t.Fatal("unknown family accepted")
	}
}
func TestSourceHashUnicodeAndFormatting(t *testing.T) {
	dir := t.TempDir()
	if e := os.WriteFile(filepath.Join(dir, "text.md"), []byte("한글\r\n\r\n"), 0600); e != nil {
		t.Fatal(e)
	}
	a, e := SourceTreeHash(dir)
	if e != nil {
		t.Fatal(e)
	}
	if e = os.WriteFile(filepath.Join(dir, "text.md"), []byte("한글\n"), 0600); e != nil {
		t.Fatal(e)
	}
	b, e := SourceTreeHash(dir)
	if e != nil || a != b {
		t.Fatal("line ending normalization changed")
	}
}

// These identities are taken from v1.5.2 release commit 9838db16, independently
// of the Go implementation and outputs generated during this migration.
func TestReleasedProjectionAndPolicyBytes(t *testing.T) {
	root := generatorRepository(t)
	for name, want := range map[string]string{"compiled-reasoning-content.bundle.json": "sha256:92705b167dad181fb808880833d95dc4721d8cdcc683833f70b63a6856b6b38a", "compiled-response-policy.json": "sha256:2e6b28af5a1c47ae097bac6021b35c6511afab1bc7ff17ce5a0a66c0482ee85b"} {
		b, e := os.ReadFile(filepath.Join(root, "content", name))
		if e != nil {
			t.Fatal(e)
		}
		if digest(b) != want {
			t.Errorf("%s is not byte-equivalent to v1.5.2", name)
		}
	}
}
