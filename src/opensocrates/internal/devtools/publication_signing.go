package devtools

import (
	"context"
	"encoding/json"
	"errors"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

func publicationNativeTarget(target string) error {
	return publicationNativeTargetFor(target, runtime.GOOS, runtime.GOARCH)
}

func publicationNativeTargetFor(target, goos, goarch string) error {
	if target == "darwin-arm64" && goos == "darwin" && goarch == "arm64" {
		return nil
	}
	if target == "windows-x64" && goos == "windows" && goarch == "amd64" {
		return nil
	}
	if target == "windows-arm64" && goos == "windows" && goarch == "arm64" {
		return nil
	}
	return errors.New("release_native_platform_required")
}

func publicationExternal(root, name string, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	command := exec.CommandContext(ctx, name, args...)
	command.Dir = root
	// External signing diagnostics can contain identity/keychain paths. Capture,
	// verify privately and report a fixed code; never log command args or output.
	data, err := command.CombinedOutput()
	if err != nil {
		return nil, errors.New("release_platform_signing_failed")
	}
	if len(data) > 4*1024*1024 {
		return nil, errors.New("release_platform_signing_response_oversize")
	}
	return data, nil
}

func publicationSign(o publicationOptions) error {
	if err := publicationRequireEnvironment(); err != nil {
		return err
	}
	if _, err := publicationIdentity(o.root); err != nil {
		return err
	}
	if err := publicationNativeTarget(o.target); err != nil {
		return err
	}
	folder := filepath.Join(o.root, "dist", "runtime", o.target)
	names := []string{"opensocrates", "opensocrates-update-helper"}
	receiptFiles := []map[string]any{}
	for _, name := range names {
		if runtime.GOOS == "windows" {
			name += ".exe"
		}
		path := filepath.Join(folder, name)
		if _, _, err := publicationHash(path); err != nil {
			return err
		}
		switch runtime.GOOS {
		case "darwin":
			identity := os.Getenv("OPENSOCRATES_MAC_SIGN_IDENTITY")
			team := os.Getenv("OPENSOCRATES_MAC_TEAM_ID")
			if identity == "" || !regexp.MustCompile(`^[A-Z0-9]{10}$`).MatchString(team) {
				return errors.New("release_mac_signing_configuration_unavailable")
			}
			if _, err := publicationExternal(o.root, "/usr/bin/codesign", "--force", "--options", "runtime", "--timestamp", "--sign", identity, path); err != nil {
				return err
			}
			if _, err := publicationExternal(o.root, "/usr/bin/codesign", "--verify", "--strict", "--verbose=2", path); err != nil {
				return err
			}
			details, err := publicationExternal(o.root, "/usr/bin/codesign", "--display", "--verbose=4", path)
			if err != nil || !strings.Contains(string(details), "TeamIdentifier="+team+"\n") {
				return errors.New("release_mac_signer_identity_mismatch")
			}
		case "windows":
			thumbprint := os.Getenv("OPENSOCRATES_WINDOWS_CERT_SHA1")
			timestamp := os.Getenv("OPENSOCRATES_WINDOWS_TIMESTAMP_URL")
			tool := os.Getenv("OPENSOCRATES_SIGNTOOL")
			if tool == "" {
				tool = "signtool.exe"
			}
			if !regexp.MustCompile(`^[A-Fa-f0-9]{40}$`).MatchString(thumbprint) {
				return errors.New("release_windows_certificate_unavailable")
			}
			parsed, err := url.Parse(timestamp)
			if err != nil || parsed.Scheme != "https" || parsed.Host == "" || parsed.User != nil {
				return errors.New("release_windows_timestamp_invalid")
			}
			if _, err = publicationExternal(o.root, tool, "sign", "/sha1", thumbprint, "/fd", "SHA256", "/tr", timestamp, "/td", "SHA256", path); err != nil {
				return err
			}
			if _, err = publicationExternal(o.root, tool, "verify", "/pa", "/all", "/tw", path); err != nil {
				return err
			}
		}
		hash, size, err := publicationHash(path)
		if err != nil {
			return err
		}
		receiptFiles = append(receiptFiles, map[string]any{"name": name, "sha256": hash, "size": size})
	}
	return publicationReceipt(o.root, "platform-signing-"+o.target+".json", map[string]any{"schema": "opensocrates.platform-signing/1.0.0", "target": o.target, "commit": os.Getenv("GITHUB_SHA"), "status": "verified", "files": receiptFiles, "native": true})
}

func publicationNotarize(o publicationOptions) error {
	if err := publicationRequireEnvironment(); err != nil {
		return err
	}
	if err := publicationNativeTarget("darwin-arm64"); err != nil {
		return err
	}
	if _, err := publicationIdentity(o.root); err != nil {
		return err
	}
	profile := os.Getenv("OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE")
	if profile == "" {
		return errors.New("release_notary_configuration_unavailable")
	}
	version, err := publicationVersion(o.root)
	if err != nil {
		return err
	}
	archive := filepath.Join(o.root, "dist", "opensocrates-v"+version+"-darwin-arm64.zip")
	hash, size, err := publicationHash(archive)
	if err != nil {
		return err
	}
	result, err := publicationExternal(o.root, "/usr/bin/xcrun", "notarytool", "submit", archive, "--keychain-profile", profile, "--wait", "--output-format", "json")
	if err != nil {
		return err
	}
	var status struct {
		ID     string `json:"id"`
		Status string `json:"status"`
	}
	if json.Unmarshal(result, &status) != nil || status.Status != "Accepted" || status.ID == "" {
		return errors.New("release_notarization_not_accepted")
	}
	// Apple does not support stapling ZIPs. Preserve Apple's accepted submission
	// receipt bound to the final ZIP digest; Gatekeeper runtime evidence is separate.
	return publicationReceipt(o.root, "notarization-darwin-arm64.json", map[string]any{"schema": "opensocrates.notarization/1.0.0", "commit": os.Getenv("GITHUB_SHA"), "status": "Accepted", "submission_id": status.ID, "archive": filepath.Base(archive), "sha256": hash, "size": size})
}
