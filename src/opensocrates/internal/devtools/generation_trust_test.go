package devtools

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestPublicTrustGenerationExactBytes(t *testing.T) {
	source := generatorRepository(t)
	root := t.TempDir()
	if e := copyCheckTree(filepath.Join(source, "config/update"), filepath.Join(root, "config/update")); e != nil {
		t.Fatal(e)
	}
	if e := GenerateTrustConfig(root); e != nil {
		t.Fatal(e)
	}
	for _, name := range []string{"root.json", "identities.json"} {
		canonical, e := os.ReadFile(filepath.Join(root, "config/update", name))
		if e != nil {
			t.Fatal(e)
		}
		embedded, e := os.ReadFile(filepath.Join(root, "src/opensocrates/internal/update/trustconfig", name))
		if e != nil || !bytes.Equal(canonical, embedded) {
			t.Fatal("compiled public trust anchor differs from canonical source")
		}
	}
}
