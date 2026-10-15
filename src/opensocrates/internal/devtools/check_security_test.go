package devtools

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDomainURIParsingDoesNotAuthorizeNetworkIO(t *testing.T) {
	root := t.TempDir()
	dir := filepath.Join(root, "src", "opensocrates", "internal", "domain")
	if err := os.MkdirAll(dir, 0700); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "source.go")
	for _, entry := range []struct {
		dependency string
		allowed    bool
	}{{"net/url", true}, {"net/http", false}, {"net", false}, {"os/exec", false}} {
		if err := os.WriteFile(path, []byte("package domain\nimport _ \""+entry.dependency+"\"\n"), 0600); err != nil {
			t.Fatal(err)
		}
		codes, err := checkBoundaries(root)
		if err != nil {
			t.Fatal(err)
		}
		if (len(codes) == 0) != entry.allowed {
			t.Fatalf("boundary for %s: %v", entry.dependency, codes)
		}
	}
}
