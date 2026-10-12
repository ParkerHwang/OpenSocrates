package devtools

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

type publicationAsset struct {
	Name   string `json:"name"`
	Size   int64  `json:"size"`
	SHA256 string `json:"sha256"`
}
type publicationInventory struct {
	Schema         string             `json:"schema"`
	ProductVersion string             `json:"product_version"`
	Commit         string             `json:"source_git_commit"`
	Assets         []publicationAsset `json:"assets"`
}
type publicationRemoteAsset struct {
	Name   string `json:"name"`
	Size   int64  `json:"size"`
	URL    string `json:"browser_download_url"`
	APIURL string `json:"url"`
	Digest string `json:"digest"`
}
type publicationRemoteRelease struct {
	ID          int64                    `json:"id"`
	Tag         string                   `json:"tag_name"`
	Draft       bool                     `json:"draft"`
	Immutable   bool                     `json:"immutable"`
	PublishedAt string                   `json:"published_at"`
	UploadURL   string                   `json:"upload_url"`
	Assets      []publicationRemoteAsset `json:"assets"`
}

func publicationHTTP() *http.Client {
	return &http.Client{Timeout: 15 * time.Minute, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) > 5 || req.URL.Scheme != "https" {
			return errors.New("release_redirect_invalid")
		}
		allowed := map[string]bool{"api.github.com": true, "uploads.github.com": true, "github.com": true, "release-assets.githubusercontent.com": true, "objects.githubusercontent.com": true}
		if !allowed[req.URL.Hostname()] {
			return errors.New("release_redirect_host_invalid")
		}
		if len(via) > 0 && publicationAdministrationEndpoint(via[0].URL) && req.URL.String() != via[0].URL.String() {
			return errors.New("release_immutability_redirect_forbidden")
		}
		// Tokens never follow cross-host redirects, including asset/CDN redirects.
		if len(via) > 0 && via[0].URL.Hostname() != req.URL.Hostname() {
			req.Header.Del("Authorization")
		}
		return nil
	}}
}

func publicationRequest(method, address, contentType string, body io.Reader) (*http.Response, error) {
	parsed, err := url.Parse(address)
	if err != nil || parsed.Scheme != "https" || (parsed.Host != "api.github.com" && parsed.Host != "uploads.github.com") {
		return nil, errors.New("release_endpoint_invalid")
	}
	token, err := publicationCredential(method, parsed)
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
	req, err := http.NewRequestWithContext(ctx, method, address, body)
	if err != nil {
		cancel()
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2026-03-10")
	req.Header.Set("User-Agent", "OpenSocrates-release")
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	response, err := publicationHTTP().Do(req)
	if err != nil {
		cancel()
		return nil, errors.New("release_transport_failed")
	}
	response.Body = &publicationClosingBody{ReadCloser: response.Body, cancel: cancel}
	return response, nil
}

// GitHub's immutable-release settings endpoint needs Administration:read;
// Actions' contents:write token cannot grant it. Keep this separate approved
// credential restricted to one read-only endpoint and never fall back to the
// ordinary release token for that check.
func publicationCredential(method string, endpoint *url.URL) (string, error) {
	if publicationAdministrationEndpoint(endpoint) {
		if method != http.MethodGet {
			return "", errors.New("release_immutability_credential_read_only")
		}
		token := os.Getenv("OPENSOCRATES_RELEASE_ADMIN_READ_TOKEN")
		if token == "" {
			return "", errors.New("release_immutability_admin_read_credential_unavailable")
		}
		return token, nil
	}
	token := os.Getenv("GH_TOKEN")
	if token == "" {
		token = os.Getenv("GITHUB_TOKEN")
	}
	if token == "" {
		return "", errors.New("release_token_unavailable")
	}
	return token, nil
}

func publicationAdministrationEndpoint(endpoint *url.URL) bool {
	return endpoint.Scheme == "https" && endpoint.Host == "api.github.com" && endpoint.Path == "/repos/"+publicationRepository+"/immutable-releases"
}

type publicationClosingBody struct {
	io.ReadCloser
	cancel context.CancelFunc
}

func (b *publicationClosingBody) Close() error { err := b.ReadCloser.Close(); b.cancel(); return err }

func publicationAPI(method, path string, value any, out any) error {
	var body io.Reader
	if value != nil {
		b, err := json.Marshal(value)
		if err != nil {
			return err
		}
		body = bytes.NewReader(b)
	}
	response, err := publicationRequest(method, "https://api.github.com/repos/"+publicationRepository+path, "application/json", body)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return fmt.Errorf("release_api_status_%d", response.StatusCode)
	}
	if out == nil {
		return nil
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, 8*1024*1024+1))
	if err != nil || len(data) > 8*1024*1024 {
		return errors.New("release_api_response_invalid")
	}
	if err = json.Unmarshal(data, out); err != nil {
		return errors.New("release_api_json_invalid")
	}
	return nil
}

func publicationImmutableEnabled() error {
	var value struct {
		Enabled bool `json:"enabled"`
	}
	if err := publicationAPI("GET", "/immutable-releases", nil, &value); err != nil {
		return publicationError("release_immutability_administration_read_check", err)
	}
	if !value.Enabled {
		return errors.New("release_immutability_required")
	}
	return nil
}

func publicationReadInventory(root string) (publicationInventory, error) {
	var inventory publicationInventory
	version, err := publicationVersion(root)
	if err != nil {
		return inventory, err
	}
	data, err := os.ReadFile(filepath.Join(root, "dist", "opensocrates-v"+version+"-publication-inventory.json"))
	if err != nil {
		return inventory, err
	}
	if err = json.Unmarshal(data, &inventory); err != nil {
		return inventory, err
	}
	if inventory.Schema != "opensocrates.publication-inventory/1.0.0" || inventory.ProductVersion != version || !publicationCommitPattern.MatchString(inventory.Commit) {
		return inventory, errors.New("release_inventory_identity_invalid")
	}
	names := map[string]bool{}
	for _, asset := range inventory.Assets {
		if asset.Name != filepath.Base(asset.Name) || strings.ContainsAny(asset.Name, "\\/\x00") || names[asset.Name] || !publicationHashPattern.MatchString(asset.SHA256) || asset.Size < 1 {
			return inventory, errors.New("release_inventory_invalid")
		}
		names[asset.Name] = true
		digest, size, err := publicationHash(filepath.Join(root, "dist", asset.Name))
		if err != nil || digest != asset.SHA256 || size != asset.Size {
			return inventory, errors.New("release_inventory_bytes_mismatch")
		}
	}
	// Installer, both bundles, production trust and all online metadata are required.
	required := []string{"opensocrates-v" + version + "-darwin-arm64", "opensocrates-v" + version + "-windows-x64.exe", "opensocrates-v" + version + "-darwin-arm64.zip", "opensocrates-v" + version + "-windows-x64.zip", "root.json", "targets.json", "snapshot.json", "timestamp.json"}
	for _, name := range required {
		if !names[name] {
			return inventory, errors.New("release_required_asset_missing")
		}
	}
	return inventory, nil
}

func publicationPublish(o publicationOptions) error {
	if err := publicationRequireEnvironment(); err != nil {
		return err
	}
	commit, err := publicationIdentity(o.root)
	if err != nil {
		return err
	}
	if err = publicationImmutableEnabled(); err != nil {
		return err
	}
	inventory, err := publicationReadInventory(o.root)
	if err != nil {
		return err
	}
	if inventory.Commit != commit {
		return errors.New("release_inventory_commit_mismatch")
	}
	response, err := publicationRequest("GET", "https://api.github.com/repos/"+publicationRepository+"/releases/tags/v"+inventory.ProductVersion, "", nil)
	if err != nil {
		return err
	}
	status := response.StatusCode
	response.Body.Close()
	if status != http.StatusNotFound {
		return errors.New("release_collision_or_lookup_failed")
	}
	notes, err := os.ReadFile(filepath.Join(o.root, ".github", "release-notes", "v"+inventory.ProductVersion+".md"))
	if err != nil {
		return err
	}
	var release publicationRemoteRelease
	payload := map[string]any{"tag_name": "v" + inventory.ProductVersion, "target_commitish": commit, "name": "OpenSocrates " + inventory.ProductVersion, "body": string(notes), "draft": true, "prerelease": false}
	if err = publicationAPI("POST", "/releases", payload, &release); err != nil {
		return err
	}
	if release.ID < 1 || !release.Draft || release.Tag != "v"+inventory.ProductVersion {
		return errors.New("release_draft_identity_invalid")
	}
	// The draft remains recoverable if any upload fails. Never delete or replace it.
	for _, asset := range inventory.Assets {
		address := "https://uploads.github.com/repos/" + publicationRepository + "/releases/" + strconv.FormatInt(release.ID, 10) + "/assets?name=" + url.QueryEscape(asset.Name)
		file, err := os.Open(filepath.Join(o.root, "dist", asset.Name))
		if err != nil {
			return err
		}
		uploaded, err := publicationRequest("POST", address, "application/octet-stream", file)
		file.Close()
		if err != nil {
			return err
		}
		var remote publicationRemoteAsset
		data, readErr := io.ReadAll(io.LimitReader(uploaded.Body, 2*1024*1024))
		uploaded.Body.Close()
		if uploaded.StatusCode != 201 || readErr != nil || json.Unmarshal(data, &remote) != nil || remote.Name != asset.Name || remote.Size != asset.Size || remote.Digest != "sha256:"+asset.SHA256 {
			return errors.New("release_upload_digest_mismatch")
		}
	}
	// Inventory itself is represented by release-manifest metadata to avoid a
	// recursive self-hash; publication inventory is retained as Actions evidence.
	if err = publicationAPI("PATCH", "/releases/"+strconv.FormatInt(release.ID, 10), map[string]any{"draft": false}, &release); err != nil {
		return err
	}
	return publicationVerifyPublic(o)
}

func publicationVerifyMetadata(release publicationRemoteRelease, inventory publicationInventory) error {
	if release.Tag != "v"+inventory.ProductVersion || release.Draft || !release.Immutable || release.PublishedAt == "" || len(release.Assets) != len(inventory.Assets) {
		return errors.New("public_release_identity_invalid")
	}
	expected := map[string]publicationAsset{}
	for _, asset := range inventory.Assets {
		expected[asset.Name] = asset
	}
	for _, asset := range release.Assets {
		local, ok := expected[asset.Name]
		if !ok || asset.Size != local.Size || asset.Digest != "sha256:"+local.SHA256 {
			return errors.New("public_release_inventory_mismatch")
		}
		delete(expected, asset.Name)
	}
	if len(expected) != 0 {
		return errors.New("public_release_asset_missing")
	}
	return nil
}

func publicationVerifyPublic(o publicationOptions) error {
	commit, err := publicationIdentity(o.root)
	if err != nil {
		return err
	}
	inventory, err := publicationReadInventory(o.root)
	if err != nil {
		return err
	}
	if inventory.Commit != commit {
		return errors.New("public_release_commit_mismatch")
	}
	var release publicationRemoteRelease
	if err = publicationAPI("GET", "/releases/tags/v"+inventory.ProductVersion, nil, &release); err != nil {
		return err
	}
	if err = publicationVerifyMetadata(release, inventory); err != nil {
		return err
	}
	files := []map[string]any{}
	for _, asset := range release.Assets {
		parsed, err := url.Parse(asset.APIURL)
		if err != nil || parsed.Host != "api.github.com" || !strings.HasPrefix(parsed.Path, "/repos/"+publicationRepository+"/releases/assets/") {
			return errors.New("public_release_asset_endpoint_invalid")
		}
		// API metadata is not byte transport. Request a public CDN URL separately,
		// without a token, and compare the actual body to the inventory digest.
		publicURL, err := url.Parse(asset.URL)
		if err != nil || publicURL.Scheme != "https" || publicURL.Host != "github.com" || publicURL.Path != "/"+publicationRepository+"/releases/download/v"+inventory.ProductVersion+"/"+asset.Name {
			return errors.New("public_release_download_endpoint_invalid")
		}
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
		request, _ := http.NewRequestWithContext(ctx, "GET", asset.URL, nil)
		download, err := publicationHTTP().Do(request)
		if err != nil {
			cancel()
			return errors.New("public_release_download_failed")
		}
		if download.StatusCode != 200 {
			download.Body.Close()
			cancel()
			return errors.New("public_release_download_failed")
		}
		h := sha256.New()
		size, err := io.Copy(h, io.LimitReader(download.Body, asset.Size+1))
		download.Body.Close()
		cancel()
		hash := hex.EncodeToString(h.Sum(nil))
		if err != nil || size != asset.Size || hash != strings.TrimPrefix(asset.Digest, "sha256:") {
			return errors.New("public_release_bytes_mismatch")
		}
		files = append(files, map[string]any{"name": asset.Name, "size": size, "sha256": hash})
	}
	sort.Slice(files, func(i, j int) bool { return files[i]["name"].(string) < files[j]["name"].(string) })
	return publicationReceipt(o.root, "public-release-verified.json", map[string]any{"schema": "opensocrates.public-release-verification/1.0.0", "repository": publicationRepository, "commit": commit, "tag": release.Tag, "immutable": true, "files": files, "verified_at": time.Now().UTC().Format(time.RFC3339)})
}
