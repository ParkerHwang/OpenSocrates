package devtools

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPublicationAdministrationReadCredentialIsMandatoryAndNarrow(t *testing.T) {
	t.Setenv("GH_TOKEN", "fixture-content-token")
	t.Setenv("GITHUB_TOKEN", "fixture-fallback-token")
	t.Setenv("OPENSOCRATES_RELEASE_ADMIN_READ_TOKEN", "")
	endpoint, _ := url.Parse("https://api.github.com/repos/" + publicationRepository + "/immutable-releases")
	if _, err := publicationCredential(http.MethodGet, endpoint); err == nil || !strings.Contains(err.Error(), "admin_read_credential_unavailable") {
		t.Fatal("ordinary contents token must not satisfy administration-read gate")
	}
	t.Setenv("OPENSOCRATES_RELEASE_ADMIN_READ_TOKEN", "fixture-admin-read-token")
	token, err := publicationCredential(http.MethodGet, endpoint)
	if err != nil || token != "fixture-admin-read-token" {
		t.Fatal("approved administration-read credential was not selected")
	}
	if _, err := publicationCredential(http.MethodPut, endpoint); err == nil {
		t.Fatal("administration credential allowed a write method")
	}
	for _, address := range []string{"https://api.github.com/repos/" + publicationRepository + "/releases", "https://uploads.github.com/repos/" + publicationRepository + "/releases/1/assets?name=test.zip"} {
		ordinary, _ := url.Parse(address)
		token, err := publicationCredential(http.MethodPost, ordinary)
		if err != nil || token != "fixture-content-token" {
			t.Fatal("administration credential escaped its read-only endpoint")
		}
	}
	first := &http.Request{URL: endpoint}
	redirect, _ := url.Parse("https://api.github.com/repos/" + publicationRepository + "/releases")
	if err := publicationHTTP().CheckRedirect(&http.Request{URL: redirect}, []*http.Request{first}); err == nil {
		t.Fatal("administration credential followed a different endpoint redirect")
	}
}

func TestPublicationRemoteTag(t *testing.T) {
	commit := strings.Repeat("a", 40)
	other := strings.Repeat("b", 40)
	for _, test := range []struct {
		name, output, want string
		bad                bool
	}{
		{"lightweight", commit + "\trefs/tags/v1.6.0", commit, false},
		{"annotated", other + "\trefs/tags/v1.6.0\n" + commit + "\trefs/tags/v1.6.0^{}", commit, false},
		{"missing", "", "", true},
		{"foreign", commit + "\trefs/tags/v1.6.1", "", true},
		{"duplicate", commit + "\trefs/tags/v1.6.0\n" + commit + "\trefs/tags/v1.6.0", "", true},
		{"malformed", "bad\trefs/tags/v1.6.0", "", true},
	} {
		t.Run(test.name, func(t *testing.T) {
			got, err := publicationRemoteTag(test.output, "v1.6.0")
			if (err != nil) != test.bad || got != test.want {
				t.Fatalf("tag gate returned %q %v", got, err)
			}
		})
	}
}

func TestPublicationReleaseMetadataCannotHideMissingOrDuplicateAssets(t *testing.T) {
	inventory := publicationInventory{ProductVersion: "1.6.0", Assets: []publicationAsset{{Name: "native.zip", Size: 3, SHA256: strings.Repeat("a", 64)}}}
	release := publicationRemoteRelease{Tag: "v1.6.0", Immutable: true, PublishedAt: "2026-10-12T00:00:00Z", Assets: []publicationRemoteAsset{{Name: "native.zip", Size: 3, Digest: "sha256:" + strings.Repeat("a", 64)}}}
	if err := publicationVerifyMetadata(release, inventory); err != nil {
		t.Fatal(err)
	}
	release.Draft = true
	if err := publicationVerifyMetadata(release, inventory); err == nil {
		t.Fatal("draft accepted")
	}
	release.Draft = false
	release.Immutable = false
	if err := publicationVerifyMetadata(release, inventory); err == nil {
		t.Fatal("mutable release accepted")
	}
	release.Immutable = true
	release.Assets = append(release.Assets, release.Assets[0])
	if err := publicationVerifyMetadata(release, inventory); err == nil {
		t.Fatal("duplicate assets accepted")
	}
	release.Assets = []publicationRemoteAsset{{Name: "other.zip", Size: 3, Digest: "sha256:" + strings.Repeat("a", 64)}}
	if err := publicationVerifyMetadata(release, inventory); err == nil {
		t.Fatal("foreign replacement accepted")
	}
}

func TestPublicationArchiveAuthenticatesInventoryAndRejectsTraversal(t *testing.T) {
	data := []byte("native executable")
	manifest := map[string]any{"files": []any{map[string]any{"path": "bin/runtime", "sha256": digest(data), "size": len(data), "mode": 493}}}
	for _, test := range []struct {
		name, path string
		body       []byte
		extra      bool
		bad        bool
	}{
		{"valid", "bin/runtime", data, false, false},
		{"tamper", "bin/runtime", []byte("different bytes"), false, true},
		{"traversal", "../runtime", data, false, true},
		{"unlisted", "bin/runtime", data, true, true},
	} {
		t.Run(test.name, func(t *testing.T) {
			var b bytes.Buffer
			writer := zip.NewWriter(&b)
			header := &zip.FileHeader{Name: test.path, Method: zip.Store}
			header.SetMode(0755)
			file, err := writer.CreateHeader(header)
			if err != nil {
				t.Fatal(err)
			}
			file.Write(test.body)
			encoded, _ := json.Marshal(manifest)
			entry, err := writer.Create("bundle-manifest.json")
			if err != nil {
				t.Fatal(err)
			}
			entry.Write(encoded)
			if test.extra {
				extra, _ := writer.Create("foreign.txt")
				extra.Write([]byte("x"))
			}
			writer.Close()
			path := filepath.Join(t.TempDir(), "native.zip")
			if err = os.WriteFile(path, b.Bytes(), 0600); err != nil {
				t.Fatal(err)
			}
			_, err = publicationBundleManifest(path)
			if (err != nil) != test.bad {
				t.Fatalf("archive gate: %v", err)
			}
		})
	}
}
