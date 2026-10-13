package management

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"path/filepath"
	"strings"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

func contentLocalePackage(t *testing.T, version string) string {
	t.Helper()
	root := t.TempDir()
	digest := strings.Repeat("a", 64)
	skill := ".agents/skills/opensocrates"
	m := transport.Manifest{Schema: "opensocrates.content-host-manifest/1.0.0", Host: "antigravity", ProductVersion: version, ContentRevision: "4", SourceTreeHash: digest, NormalizedSemanticHash: digest, MethodCount: 48, RuntimeTargets: []string{}, Launchers: []string{}, PublicSkills: []string{"opensocrates"}, SkillRoot: skill, SourceIdentity: map[string]string{"canonical": digest, "templates": digest}}
	locales := []string{"en", "ko", "zh", "ja"}
	if version == "1.5.0" {
		locales, m.ContentRevision = []string{"en", "ko"}, "3"
	}
	contents := map[string][]byte{skill + "/SKILL.md": []byte("Read the canonical references completely.\n"), ".agents/rules/opensocrates.md": []byte("---\ntrigger: always_on\n---\nRead the skill.\n")}
	for i := 0; i < 48; i++ {
		id := fmt.Sprintf("method-%d", i)
		m.MethodIDs = append(m.MethodIDs, id)
		for _, locale := range locales {
			path := skill + "/references/decision/methods/" + locale + "/" + id + ".md"
			body := []byte(locale + ": " + id + "\n")
			contents[path] = body
			h := sha256.Sum256(body)
			m.CanonicalMethods = append(m.CanonicalMethods, transport.CanonicalMethod{Locale: locale, MethodID: id, Path: path, SHA256: hex.EncodeToString(h[:])})
		}
	}
	for _, path := range sortedKeys(contents) {
		full := filepath.Join(root, filepath.FromSlash(path))
		if e := platform.Mkdir(filepath.Dir(full)); e != nil {
			t.Fatal(e)
		}
		if e := platform.AtomicWrite(full, contents[path], 0600); e != nil {
			t.Fatal(e)
		}
		h := sha256.Sum256(contents[path])
		m.Files = append(m.Files, transport.File{Path: path, SHA256: hex.EncodeToString(h[:])})
	}
	b, e := json.Marshal(m)
	if e != nil {
		t.Fatal(e)
	}
	if e := platform.AtomicWrite(filepath.Join(root, "release-manifest.json"), b, 0600); e != nil {
		t.Fatal(e)
	}
	return root
}

func TestReleasedAntigravityLocalesSurviveDisableEnableAndForeignCollision(t *testing.T) {
	for _, version := range []string{"1.5.0", "1.5.1"} {
		preferences := []string{"zh", "ja"}
		if version == "1.5.0" {
			preferences = []string{"en", "ko"}
		}
		for _, preference := range preferences {
			t.Run(version+"/"+preference, func(t *testing.T) {
				base := t.TempDir()
				stateDir := filepath.Join(base, "state")
				if e := platform.Mkdir(stateDir); e != nil {
					t.Fatal(e)
				}
				// These bytes belong to user settings/another installer, not the
				// content host; toggling this integration must never rewrite them.
				settingsValue := domain.DefaultSettings()
				settingsValue.Value["locale_preference"] = preference
				settingsValue.Value["revision"] = contracts.Number(17)
				settings, e := contracts.CanonicalJSON(settingsValue.Value)
				if e != nil {
					t.Fatal(e)
				}
				npm := []byte("unrelated npm installation\n")
				settingsPath := filepath.Join(stateDir, "settings.json")
				npmPath := filepath.Join(base, "unrelated-npm.txt")
				for path, data := range map[string][]byte{settingsPath: settings, npmPath: npm} {
					if e := platform.AtomicWrite(path, data, 0600); e != nil {
						t.Fatal(e)
					}
				}
				m := Manager{StateDir: stateDir, Home: base, GOOS: "darwin", GOARCH: "arm64", LookupEnv: func(string) string { return "" }}
				ctx := context.Background()
				if _, e := m.Handle(ctx, Request{Action: "install", Host: "antigravity", Package: contentLocalePackage(t, version), Version: version}); e != nil {
					t.Fatal(e)
				}
				paths, e := m.Paths("antigravity", "")
				if e != nil {
					t.Fatal(e)
				}
				for _, action := range []string{"disable", "enable", "disable"} {
					result, e := m.Handle(ctx, Request{Action: action, Host: "antigravity"})
					if e != nil || result.Version != version || result.Enabled != (action == "enable") {
						t.Fatalf("%s changed released locale state: %v", action, e)
					}
					marker, _, e := owned(paths, "antigravity")
					if e != nil || marker == nil || marker.Enabled != (action == "enable") {
						t.Fatalf("ownership after %s: %v", action, e)
					}
					locales := []string{"en", "ko", "zh", "ja"}
					if version == "1.5.0" {
						locales = []string{"en", "ko"}
					}
					for _, locale := range locales {
						name := ".agents/skills/opensocrates/references/decision/methods/" + locale + "/method-0.md"
						physical, e := antiPhysical(paths, name, marker.Enabled)
						if e != nil {
							t.Fatal(e)
						}
						actual, e := platform.ReadOwnedFile(physical, 1024)
						if e != nil || string(actual) != locale+": method-0\n" {
							t.Fatalf("%s canonical file changed: %v", locale, e)
						}
					}
				}
				foreign := []byte("foreign rule must survive\n")
				if e := platform.Mkdir(filepath.Dir(paths.Rule)); e != nil {
					t.Fatal(e)
				}
				if e := platform.AtomicWrite(paths.Rule, foreign, 0600); e != nil {
					t.Fatal(e)
				}
				if _, e := m.Handle(ctx, Request{Action: "enable", Host: "antigravity"}); e == nil {
					t.Fatal("foreign rule collision accepted")
				}
				for path, expected := range map[string][]byte{settingsPath: settings, npmPath: npm, paths.Rule: foreign} {
					actual, e := platform.ReadOwnedFile(path, 4096)
					if e != nil || !bytes.Equal(actual, expected) {
						t.Fatalf("unrelated bytes changed: %v", e)
					}
				}
			})
		}
	}
}
