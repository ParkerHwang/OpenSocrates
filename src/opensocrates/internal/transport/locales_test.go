package transport

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

// Inventories are rebound after deliberate changes, so these tests distinguish
// content identity/completeness from a simple file-hash mismatch.
func localeFixture(t *testing.T, host, version string) (string, Manifest, map[string][]byte) {
	t.Helper()
	// Windows may give testing's temporary root an Administrators owner.
	// Create a new explicitly current-user-owned package root; never repair
	// existing ownership or weaken the verifier to accommodate a fixture.
	root := filepath.Join(t.TempDir(), "private-package")
	if e := platform.Mkdir(root); e != nil {
		t.Fatal(e)
	}
	digest := strings.Repeat("a", 64)
	m := Manifest{Host: host, ProductVersion: version, ContentRevision: "4", SourceTreeHash: digest, NormalizedSemanticHash: digest, MethodCount: 48}
	files := map[string][]byte{}
	skill := "skills/opensocrates"
	if host == "codex" || host == "claude" {
		m.Schema = "opensocrates.plugin-release-manifest/1.0.0"
		m.RuntimeTargets = []string{"darwin-arm64"}
		m.ReleaseTargets = []string{"darwin-arm64"}
		plugin := ".codex-plugin/plugin.json"
		if host == "claude" {
			plugin = ".claude-plugin/plugin.json"
		}
		files[plugin] = []byte(`{"name":"opensocrates","version":"` + version + `"}`)
	} else {
		m.Schema = "opensocrates.content-host-manifest/1.0.0"
		m.RuntimeTargets, m.Launchers = []string{}, []string{}
		m.PublicSkills = []string{"opensocrates"}
		m.SourceIdentity = map[string]string{"canonical": digest, "templates": digest}
		skill = ".agents/skills/opensocrates"
		if host == "claude-chat" {
			skill = "opensocrates"
		} else {
			files[".agents/rules/opensocrates.md"] = []byte("---\ntrigger: always_on\n---\nRead the skill.\n")
		}
		m.SkillRoot = skill
	}
	files[skill+"/SKILL.md"] = []byte("Read each authored method completely.\n")
	locales := []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"}
	switch version {
	case "1.5.0":
		locales, m.ContentRevision = []string{"en", "ko"}, "3"
	case "1.5.1":
		locales, m.ContentRevision = []string{"en", "ko", "zh", "ja"}, "4"
	default:
		m.ContentRevision = "5"
	}
	for i := 0; i < 48; i++ {
		id := fmt.Sprintf("method-%d", i)
		m.MethodIDs = append(m.MethodIDs, id)
		for _, locale := range locales {
			path := skill + "/references/decision/methods/" + locale + "/" + id + ".md"
			contents := []byte(locale + ": " + id + "\n")
			files[path] = contents
			if m.SkillRoot != "" {
				h := sha256.Sum256(contents)
				m.CanonicalMethods = append(m.CanonicalMethods, CanonicalMethod{Locale: locale, MethodID: id, Path: path, SHA256: hex.EncodeToString(h[:])})
			}
		}
	}
	return root, m, files
}

// A fixture belongs to one serial host suite. Each production Verify call
// still independently reads and checks the entire inventory; only redundant
// fixture writes are avoided.
type localePackageFixture struct {
	root     string
	manifest Manifest
	files    map[string][]byte
}

func fixturePaths(files map[string][]byte) []string {
	paths := make([]string, 0, len(files))
	for path := range files {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	return paths
}

func cloneFixtureFiles(files map[string][]byte) map[string][]byte {
	cloned := make(map[string][]byte, len(files))
	for name, contents := range files {
		cloned[name] = contents
	}
	return cloned
}

func (fixture *localePackageFixture) replace(t *testing.T, m Manifest, files map[string][]byte) {
	t.Helper()
	if fixture.files == nil {
		fixture.files = map[string][]byte{}
	}
	for _, path := range fixturePaths(fixture.files) {
		if _, keep := files[path]; !keep {
			if e := platform.Remove(filepath.Join(fixture.root, filepath.FromSlash(path))); e != nil {
				t.Fatal(e)
			}
			delete(fixture.files, path)
		}
	}
	m.Files = nil
	for _, path := range fixturePaths(files) {
		contents := files[path]
		current, exists := fixture.files[path]
		if !exists || !bytes.Equal(current, contents) {
			full := filepath.Join(fixture.root, filepath.FromSlash(path))
			if e := platform.Mkdir(filepath.Dir(full)); e != nil {
				t.Fatal(e)
			}
			if e := platform.AtomicWrite(full, contents, 0600); e != nil {
				t.Fatal(e)
			}
			fixture.files[path] = contents
		}
		h := sha256.Sum256(contents)
		m.Files = append(m.Files, File{Path: path, SHA256: hex.EncodeToString(h[:])})
	}
	b, e := json.Marshal(m)
	if e != nil {
		t.Fatal(e)
	}
	path := "release-manifest.json"
	if m.Host == "claude-chat" {
		path = "opensocrates/release-manifest.json"
	}
	if e := platform.AtomicWrite(filepath.Join(fixture.root, filepath.FromSlash(path)), b, 0600); e != nil {
		t.Fatal(e)
	}
	fixture.manifest = m
}

func (fixture *localePackageFixture) mutate(t *testing.T, m Manifest, files map[string][]byte) {
	t.Helper()
	beforeManifest, beforeFiles := fixture.manifest, cloneFixtureFiles(fixture.files)
	// Cleanup executes before the next serial subtest, including on Fatal.
	// Restoring uses the same ownership-checked private file APIs as setup.
	t.Cleanup(func() { fixture.replace(t, beforeManifest, beforeFiles) })
	fixture.replace(t, m, files)
}

func versionedFixture(m Manifest, allFiles map[string][]byte, version, revision string, locales []string) (Manifest, map[string][]byte) {
	m.ProductVersion, m.ContentRevision = version, revision
	m.CanonicalMethods = append([]CanonicalMethod(nil), m.CanonicalMethods...)
	rows := m.CanonicalMethods[:0]
	for _, row := range m.CanonicalMethods {
		if contains(locales, row.Locale) {
			rows = append(rows, row)
		}
	}
	m.CanonicalMethods = rows
	skill := "skills/opensocrates"
	if m.SkillRoot != "" {
		skill = m.SkillRoot
	}
	prefix := skill + "/references/decision/methods/"
	files := map[string][]byte{}
	for path, contents := range allFiles {
		if strings.HasPrefix(path, prefix) {
			locale := strings.Split(strings.TrimPrefix(path, prefix), "/")[0]
			if !contains(locales, locale) {
				continue
			}
		}
		files[path] = contents
	}
	if m.Host == "codex" || m.Host == "claude" {
		plugin := ".codex-plugin/plugin.json"
		if m.Host == "claude" {
			plugin = ".claude-plugin/plugin.json"
		}
		files[plugin] = []byte(`{"name":"opensocrates","version":"` + version + `"}`)
	}
	return m, files
}

func TestReleasedMethodLocaleVersionBoundary(t *testing.T) {
	for _, host := range []string{"codex", "claude", "antigravity", "claude-chat"} {
		t.Run(host, func(t *testing.T) {
			root, latest, allFiles := localeFixture(t, host, "1.6.0")
			fixture := localePackageFixture{root: root}
			// Build the complete private tree once, growing it across releases;
			// v1.6.0 changes only metadata after the v1.5.2 ten-language case.
			for _, tc := range []struct {
				version, revision string
				locales           []string
			}{
				{"1.5.0", "3", []string{"en", "ko"}},
				{"1.5.1", "4", []string{"en", "ko", "zh", "ja"}},
				{"1.5.2", "5", []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"}},
				{"1.6.0", "5", []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"}},
			} {
				t.Run(tc.version, func(t *testing.T) {
					m, files := versionedFixture(latest, allFiles, tc.version, tc.revision, tc.locales)
					fixture.replace(t, m, files)
					pack, e := Verify(root, host, tc.version, "darwin-arm64")
					if e != nil || pack.Manifest.ProductVersion != tc.version || pack.Manifest.ContentRevision != tc.revision {
						t.Fatalf("released layout refused: %v", e)
					}
				})
			}
			t.Run("consistent-inventory-guards", func(t *testing.T) {
				testMethodInventoryMutations(t, host, &fixture)
			})
			if host == "antigravity" || host == "claude-chat" {
				t.Run("canonical-reference-guards", func(t *testing.T) {
					testCanonicalReferenceMutations(t, host, &fixture)
				})
			}
		})
	}
}

func testMethodInventoryMutations(t *testing.T, host string, fixture *localePackageFixture) {
	t.Helper()
	for _, mutation := range []string{"missing-th", "old-two-locales", "old-four-locales", "unknown-locale", "unknown-method", "wrong-filename", "extra-locale", "extra-method"} {
		t.Run(mutation, func(t *testing.T) {
			m, files := fixture.manifest, cloneFixtureFiles(fixture.files)
			skill := "skills/opensocrates"
			if m.SkillRoot != "" {
				skill = m.SkillRoot
			}
			prefix := skill + "/references/decision/methods/"
			path := prefix + "ja/method-0.md"
			switch mutation {
			case "missing-th":
				delete(files, prefix+"th/method-0.md")
			case "old-two-locales":
				for name := range files {
					if strings.HasPrefix(name, prefix) && !strings.HasPrefix(name, prefix+"en/") && !strings.HasPrefix(name, prefix+"ko/") {
						delete(files, name)
					}
				}
			case "old-four-locales":
				for name := range files {
					if strings.HasPrefix(name, prefix) && !strings.HasPrefix(name, prefix+"en/") && !strings.HasPrefix(name, prefix+"ko/") && !strings.HasPrefix(name, prefix+"zh/") && !strings.HasPrefix(name, prefix+"ja/") {
						delete(files, name)
					}
				}
			case "extra-locale":
				files[prefix+"ru/method-0.md"] = files[path]
			case "extra-method":
				files[prefix+"th/unknown.md"] = files[path]
			case "unknown-locale":
				files[prefix+"ru/method-0.md"] = files[path]
				delete(files, path)
			case "unknown-method":
				files[prefix+"ja/unknown.md"] = files[path]
				delete(files, path)
			case "wrong-filename":
				files[prefix+"ja/method-0.txt"] = files[path]
				delete(files, path)
			}
			fixture.mutate(t, m, files)
			_, e := Verify(fixture.root, host, "1.6.0", "darwin-arm64")
			var category *diagnostics.Error
			if !errors.As(e, &category) || category.Code != diagnostics.Verification || category.Stage != "methods" {
				t.Fatalf("expected canonical rejection, got %v", e)
			}
		})
	}
}

func testCanonicalReferenceMutations(t *testing.T, host string, fixture *localePackageFixture) {
	t.Helper()
	// v1.5.2 and v1.6.0 use the same complete ten-language tree; only the
	// released version/plugin metadata changes for this exact legacy case.
	m, files := versionedFixture(fixture.manifest, fixture.files, "1.5.2", "5", []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"})
	fixture.mutate(t, m, files)
	for _, mutation := range []string{"duplicate", "unknown-locale", "path", "digest"} {
		t.Run(mutation, func(t *testing.T) {
			m := fixture.manifest
			m.CanonicalMethods = append([]CanonicalMethod(nil), m.CanonicalMethods...)
			switch mutation {
			case "duplicate":
				m.CanonicalMethods[1] = m.CanonicalMethods[0]
			case "unknown-locale":
				m.CanonicalMethods[0].Locale = "ru"
			case "path":
				m.CanonicalMethods[0].Path = m.CanonicalMethods[1].Path
			case "digest":
				m.CanonicalMethods[0].SHA256 = strings.Repeat("b", 64)
			}
			fixture.mutate(t, m, fixture.files)
			if _, e := Verify(fixture.root, host, "1.5.2", ""); e == nil {
				t.Fatal("misbound canonical reference accepted")
			}
		})
	}
}

func TestMethodLocaleGenerationsFollowReleasedNumericVersionGuards(t *testing.T) {
	for _, tc := range []struct {
		version string
		count   int
	}{
		{"0.9.99", 2}, {"1.4.999", 2}, {"1.5.0", 2},
		{"1.5.1", 4}, {"1.05.001", 4}, {"1.5.2", 10},
		{"1.5.999999999999999999999999", 10}, {"1.6.0", 10}, {"2.0.0", 10},
	} {
		if got := len(methodLocales(tc.version)); got != tc.count {
			t.Fatalf("version %s requires %d locales, got %d", tc.version, tc.count, got)
		}
	}
}

func TestCanonicalMethodWireRejectsAdditionalOrMissingKeys(t *testing.T) {
	for _, raw := range []string{
		`{"locale":"th","method_id":"deduction","path":"p","sha256":"h","future":true}`,
		`{"locale":"th","method_id":"deduction","path":"p"}`,
		`{"locale":"th","locale":"fr","method_id":"deduction","path":"p","sha256":"h"}`,
	} {
		var row CanonicalMethod
		if json.Unmarshal([]byte(raw), &row) == nil {
			t.Fatal("noncanonical reference object accepted")
		}
	}
}
