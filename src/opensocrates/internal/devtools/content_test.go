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
	if generated["source_tree_hash"] != "sha256:993c30191b0d2b67af88a25c2631d9e8fddeeaf9dadfd0ff4fb07dd62539dcab" || generated["normalized_semantic_hash"] != "sha256:835a1e32695e863b3696c3bf5dcf1acb7faa580d889129e617524fbc0d9908e6" {
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

// These identities are taken from v1.5.1 release commit 5a6a7fa2, independently
// of the Go implementation and outputs generated during this migration.
func TestReleasedProjectionAndPolicyBytes(t *testing.T) {
	root := generatorRepository(t)
	for name, want := range map[string]string{"compiled-reasoning-content.bundle.json": "sha256:470a959d91432f1f2fdb0bcda20e6d3e8293e75e892bd72a64f40fa996646e57", "compiled-response-policy.json": "sha256:89b5bdf18ff449cf8c40e7431703170a2cd392eea47ecf9d4c09da24f10c1a8b"} {
		b, e := os.ReadFile(filepath.Join(root, "content", name))
		if e != nil {
			t.Fatal(e)
		}
		if digest(b) != want {
			t.Errorf("%s is not byte-equivalent to v1.5.1", name)
		}
	}
}
