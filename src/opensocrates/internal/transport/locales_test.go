package transport

import (
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

func writeLocaleFixture(t *testing.T, root string, m Manifest, files map[string][]byte) {
	t.Helper()
	m.Files = nil
	paths := make([]string, 0, len(files))
	for path := range files {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	for _, path := range paths {
		contents := files[path]
		full := filepath.Join(root, filepath.FromSlash(path))
		if e := platform.Mkdir(filepath.Dir(full)); e != nil {
			t.Fatal(e)
		}
		if e := platform.AtomicWrite(full, contents, 0600); e != nil {
			t.Fatal(e)
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
	if e := platform.AtomicWrite(filepath.Join(root, filepath.FromSlash(path)), b, 0600); e != nil {
		t.Fatal(e)
	}
}

func TestReleasedMethodLocaleVersionBoundary(t *testing.T) {
	for _, host := range []string{"codex", "claude", "antigravity", "claude-chat"} {
		for _, version := range []string{"1.5.0", "1.5.1", "1.5.2", "1.6.0"} {
			t.Run(host+"/"+version, func(t *testing.T) {
				root, m, files := localeFixture(t, host, version)
				writeLocaleFixture(t, root, m, files)
				pack, e := Verify(root, host, version, "darwin-arm64")
				if e != nil || pack.Manifest.ProductVersion != version {
					t.Fatalf("released layout refused: %v", e)
				}
			})
		}
	}
}

func TestNewPackagesRefuseConsistentIncompleteOrSubstitutedMethodInventories(t *testing.T) {
	for _, host := range []string{"codex", "claude", "antigravity", "claude-chat"} {
		for _, mutation := range []string{"missing-th", "old-two-locales", "old-four-locales", "unknown-locale", "unknown-method", "wrong-filename", "extra-locale", "extra-method"} {
			t.Run(host+"/"+mutation, func(t *testing.T) {
				root, m, files := localeFixture(t, host, "1.6.0")
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
				writeLocaleFixture(t, root, m, files)
				_, e := Verify(root, host, "1.6.0", "darwin-arm64")
				var category *diagnostics.Error
				if !errors.As(e, &category) || category.Code != diagnostics.Verification || category.Stage != "methods" {
					t.Fatalf("expected canonical rejection, got %v", e)
				}
			})
		}
	}
}

func TestCanonicalMethodRowsRequireExactIdentityPathAndDigest(t *testing.T) {
	for _, host := range []string{"antigravity", "claude-chat"} {
		for _, mutation := range []string{"duplicate", "unknown-locale", "path", "digest"} {
			t.Run(host+"/"+mutation, func(t *testing.T) {
				root, m, files := localeFixture(t, host, "1.5.2")
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
				writeLocaleFixture(t, root, m, files)
				if _, e := Verify(root, host, "1.5.2", ""); e == nil {
					t.Fatal("misbound canonical reference accepted")
				}
			})
		}
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
