package devtools

import (
	"bytes"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func generatedCheckFixture(t *testing.T) string {
	t.Helper()
	source := generatorRepository(t)
	root := t.TempDir()
	for _, relative := range []string{"VERSION", "content", "schemas/source", "schemas/v1", "config/update", "src/opensocrates/internal/content/assets", "src/opensocrates/internal/contracts/assets", "src/opensocrates/internal/update/trustconfig"} {
		if e := copyCheckTree(filepath.Join(source, relative), filepath.Join(root, relative)); e != nil {
			t.Fatal(e)
		}
	}
	return root
}
func TestGeneratedCheckRejectsStaleRuntimeEmbedsWithoutRewriting(t *testing.T) {
	for _, mutation := range []struct {
		relative string
		change   func(map[string]any)
	}{
		{"src/opensocrates/internal/content/assets/compiled-content.bundle.json", func(v map[string]any) { v["product_version"] = "9.9.9" }},
		{"src/opensocrates/internal/content/assets/compiled-response-policy.json", func(v map[string]any) {
			entry := obj(obj(v["locales"])["en"])
			entry["protected_rule"] = str(entry["protected_rule"]) + " stale embedded guidance"
		}},
		{"src/opensocrates/internal/content/assets/compiled-reasoning-content.bundle.json", func(v map[string]any) {
			entry := obj(arr(v["injectable_content"])[0])
			entry["display_name"] = str(entry["display_name"]) + " stale embedded name"
		}},
		{"src/opensocrates/internal/contracts/assets/user-settings.schema.json", func(v map[string]any) { v["title"] = "Stale but valid JSON Schema annotation" }},
	} {
		t.Run(filepath.Base(mutation.relative), func(t *testing.T) {
			root := generatedCheckFixture(t)
			path := filepath.Join(root, mutation.relative)
			v, e := checkObject(path)
			if e != nil {
				t.Fatal(e)
			}
			mutation.change(v)
			mutated, e := Canonical(v)
			if e != nil {
				t.Fatal(e)
			}
			if e = os.WriteFile(path, mutated, 0644); e != nil {
				t.Fatal(e)
			}
			var diagnostics bytes.Buffer
			status := RunChecks([]string{"generated", "--root", root}, io.Discard, &diagnostics)
			if status != 1 || !strings.Contains(diagnostics.String(), "generated_mismatch:"+mutation.relative) {
				t.Fatalf("stale runtime embed accepted or not identified: status=%d %s", status, diagnostics.String())
			}
			after, e := os.ReadFile(path)
			if e != nil || !bytes.Equal(after, mutated) {
				t.Fatal("check overwrote the reference embed")
			}
		})
	}
}
func TestGeneratedCheckRejectsMissingAndExtraRuntimeEmbedInventory(t *testing.T) {
	root := generatedCheckFixture(t)
	relative := "src/opensocrates/internal/contracts/assets/user-settings.schema.json"
	path := filepath.Join(root, relative)
	original, e := os.ReadFile(path)
	if e != nil {
		t.Fatal(e)
	}
	if e = os.Remove(path); e != nil {
		t.Fatal(e)
	}
	codes, e := checkGenerated(checkOptions{root: root})
	if e != nil || !strings.Contains(strings.Join(codes, " "), "generated_mismatch:"+relative) {
		t.Fatalf("missing embed accepted: %v %v", codes, e)
	}
	if e = os.WriteFile(path, original, 0644); e != nil {
		t.Fatal(e)
	}
	extraRelative := "src/opensocrates/internal/content/assets/unexpected.json"
	if e = os.WriteFile(filepath.Join(root, extraRelative), []byte("{}\n"), 0644); e != nil {
		t.Fatal(e)
	}
	codes, e = checkGenerated(checkOptions{root: root})
	if e != nil || !strings.Contains(strings.Join(codes, " "), "generated_mismatch:"+extraRelative) {
		t.Fatalf("extra embedded runtime JSON accepted: %v %v", codes, e)
	}
}
