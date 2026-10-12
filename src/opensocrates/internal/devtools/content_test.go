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
	if generated["source_tree_hash"] != "sha256:b8824656fc53d588cc6a570de102531266ef2a7b39f04694d058c8da5c2418a6" || generated["normalized_semantic_hash"] != "sha256:e50af8296165a7c8e8a9a6e27d4881bbc816b7efe9e1c84ea798c80fb54efa48" {
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

// These identities are taken from v1.5.0 release commit cf663431, independently
// of the Go implementation and outputs generated during this migration.
func TestReleasedProjectionAndPolicyBytes(t *testing.T) {
	root := generatorRepository(t)
	for name, want := range map[string]string{"compiled-reasoning-content.bundle.json": "sha256:5d8ea1f90df1bfab09d63f42ef162f59edfab2784c4b415a62128cc93a5d337d", "compiled-response-policy.json": "sha256:43e592bea342c9bc91d816fbe39d4d1e67063adb9bad4a2919926aec4dfae86f"} {
		b, e := os.ReadFile(filepath.Join(root, "content", name))
		if e != nil {
			t.Fatal(e)
		}
		if digest(b) != want {
			t.Errorf("%s is not byte-equivalent to v1.5.0", name)
		}
	}
}
