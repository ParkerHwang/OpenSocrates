package devtools

import (
	"archive/zip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"io"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
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

// A shared bounded sink captures both streams without retaining unbounded tool
// diagnostics. Signing and notarization commands never print their arguments.
type publicationBoundedOutput struct {
	mu       sync.Mutex
	data     []byte
	limit    int
	exceeded bool
}

func (w *publicationBoundedOutput) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if len(p) > w.limit-len(w.data) {
		w.exceeded = true
		return 0, errors.New("release_platform_signing_response_oversize")
	}
	w.data = append(w.data, p...)
	return len(p), nil
}
func publicationExternal(root, name string, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Minute)
	defer cancel()
	command := exec.CommandContext(ctx, name, args...)
	command.Dir = root
	if runtime.GOOS == "darwin" {
		command.Env = macSigningChildEnvironment()
	}
	output := &publicationBoundedOutput{limit: 2 * 1024 * 1024}
	privateDiagnostics := &publicationBoundedOutput{limit: 2 * 1024 * 1024}
	command.Stdout = output
	command.Stderr = privateDiagnostics
	err := command.Run()
	if output.exceeded || privateDiagnostics.exceeded {
		return nil, errors.New("release_platform_signing_response_oversize")
	}
	if err != nil {
		return nil, errors.New("release_platform_signing_failed")
	}
	// notarytool emits machine-readable JSON on stdout; stderr diagnostics
	// remain private and cannot corrupt or be adopted into the JSON receipt.
	// codesign display writes its signature metadata to stderr instead.
	if name == "/usr/bin/codesign" || runtime.GOOS == "windows" {
		return append(output.data, privateDiagnostics.data...), nil
	}
	return output.data, nil
}

type macSignedFile struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
	CDHash string `json:"cdhash"`
}
type publicationSigningCommand func(string, string, ...string) ([]byte, error)

func macSigningConfiguration(root, purpose string) (identity, team, keychain, profile string, err error) {
	identity = os.Getenv("OPENSOCRATES_MAC_SIGN_IDENTITY")
	team = os.Getenv("OPENSOCRATES_MAC_TEAM_ID")
	profile = os.Getenv("OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE")
	if !regexp.MustCompile(`^[A-Fa-f0-9]{40}$`).MatchString(identity) || team != update.DefaultNativeTrust().DarwinTeamID || !regexp.MustCompile(`^[A-Z0-9]{10}$`).MatchString(team) {
		err = errors.New("release_mac_signing_configuration_unavailable")
		return
	}
	if os.Getenv("OPENSOCRATES_MAC_SIGNING_KEYCHAIN") != "" || purpose == "qualification" {
		if err = requireMacSigningPurpose(root, purpose); err != nil {
			return
		}
		keychain, err = macSigningOwnedKeychain()
		if err != nil {
			return
		}
	}
	if profile != "" && !regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`).MatchString(profile) {
		err = errors.New("release_notary_configuration_invalid")
	}
	return
}
func macSigningRequirement(identity, team string) string {
	return fmt.Sprintf(`=anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists and certificate leaf[field.1.2.840.113635.100.6.1.13] exists and certificate leaf[subject.OU] = "%s" and certificate leaf = H"%s"`, team, strings.ToLower(identity))
}
func macVerifySigned(root, path, relative, identity, team string, run publicationSigningCommand) (macSignedFile, error) {
	var result macSignedFile
	if _, err := run(root, "/usr/bin/codesign", "--verify", "--strict", "-R", macSigningRequirement(identity, team), path); err != nil {
		return result, err
	}
	details, err := run(root, "/usr/bin/codesign", "--display", "--verbose=4", path)
	text := string(details)
	cd := regexp.MustCompile(`(?m)^CDHash=([a-f0-9]{40})$`).FindStringSubmatch(text)
	if err != nil || len(cd) != 2 || !strings.Contains(text, "TeamIdentifier="+team+"\n") || !regexp.MustCompile(`(?m)^CodeDirectory .*flags=.*\(.*runtime.*\)`).MatchString(text) || !regexp.MustCompile(`(?m)^Timestamp=.+$`).MatchString(text) {
		return result, errors.New("release_mac_signer_identity_mismatch")
	}
	hash, size, err := publicationHash(path)
	if err != nil {
		return result, err
	}
	return macSignedFile{Path: relative, SHA256: hash, Size: size, CDHash: cd[1]}, nil
}
func macSignRuntime(root, identity, team, keychain string, run publicationSigningCommand) ([]macSignedFile, error) {
	records := []macSignedFile{}
	for _, name := range []string{"opensocrates", "opensocrates-update-helper"} {
		path := filepath.Join(root, "dist", "runtime", "darwin-arm64", name)
		if _, _, err := publicationHash(path); err != nil {
			return nil, err
		}
		args := []string{"--force", "--options", "runtime", "--timestamp", "--sign", identity}
		if keychain != "" {
			args = append(args, "--keychain", keychain)
		}
		args = append(args, path)
		if _, err := run(root, "/usr/bin/codesign", args...); err != nil {
			return nil, err
		}
		record, err := macVerifySigned(root, path, name, identity, team, run)
		if err != nil {
			return nil, err
		}
		records = append(records, record)
	}
	return records, nil
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
			identity, team, keychain, _, err := macSigningConfiguration(o.root, "production")
			if err != nil {
				return err
			}
			args := []string{"--force", "--options", "runtime", "--timestamp", "--sign", identity}
			if keychain != "" {
				args = append(args, "--keychain", keychain)
			}
			args = append(args, path)
			if _, err = publicationExternal(o.root, "/usr/bin/codesign", args...); err != nil {
				return err
			}
			if _, err = macVerifySigned(o.root, path, name, identity, team, publicationExternal); err != nil {
				return err
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
	commit, err := publicationIdentity(o.root)
	if err != nil {
		return err
	}
	identity, team, keychain, profile, err := macSigningConfiguration(o.root, "production")
	if err != nil {
		return err
	}
	receipt, err := macNotarizeDistribution(o.root, identity, team, keychain, profile, publicationExternal)
	if err != nil {
		return err
	}
	receipt["schema"] = "opensocrates.notarization/1.0.0"
	receipt["commit"] = commit
	return publicationReceipt(o.root, "notarization-darwin-arm64.json", receipt)
}

var macSubmissionPattern = regexp.MustCompile(`^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$`)

type macNotaryStatus struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}
type macNotaryLog struct {
	JobID      string          `json:"jobId"`
	Status     string          `json:"status"`
	SHA256     string          `json:"sha256"`
	StatusCode int             `json:"statusCode"`
	Issues     json.RawMessage `json:"issues"`
	Tickets    []struct {
		Path            string `json:"path"`
		CDHash          string `json:"cdhash"`
		Arch            string `json:"arch"`
		DigestAlgorithm string `json:"digestAlgorithm"`
	} `json:"ticketContents"`
}

// The raw Apple log may contain private paths or diagnostics. Only closed counts
// and verified digests leave this function; even accepted warnings fail closed.
func macValidateNotaryLog(data []byte, id, hash, archive string, files []macSignedFile) (map[string]any, error) {
	var log macNotaryLog
	if json.Unmarshal(data, &log) != nil || log.JobID != id || log.Status != "Accepted" || log.StatusCode != 0 || log.SHA256 != hash {
		return nil, errors.New("release_notarization_log_mismatch")
	}
	var issues []json.RawMessage
	if len(log.Issues) == 0 || (string(log.Issues) != "null" && json.Unmarshal(log.Issues, &issues) != nil) || len(issues) != 0 {
		return nil, errors.New("release_notarization_issues_present")
	}
	expected := map[string]string{}
	for _, file := range files {
		expected[file.Path] = file.CDHash
	}
	if len(expected) != len(files) || len(log.Tickets) != len(expected) {
		return nil, errors.New("release_notarization_ticket_inventory_mismatch")
	}
	seen := map[string]bool{}
	for _, ticket := range log.Tickets {
		path := strings.TrimPrefix(ticket.Path, archive+"/")
		if expected[path] == "" || seen[path] || ticket.CDHash != expected[path] || ticket.Arch != "arm64" || ticket.DigestAlgorithm != "SHA-256" {
			return nil, errors.New("release_notarization_ticket_mismatch")
		}
		seen[path] = true
	}
	return map[string]any{"status": "Accepted", "sha256_matches": true, "issue_count": 0, "ticket_count": len(log.Tickets), "all_runtime_cdhashes_ticketed": true}, nil
}
func macNotaryAccept(root, archive, profile, keychain string, files []macSignedFile, run publicationSigningCommand) (map[string]any, error) {
	if profile == "" {
		return nil, errors.New("release_notary_configuration_unavailable")
	}
	hash, size, err := publicationHash(archive)
	if err != nil {
		return nil, err
	}
	auth := []string{"--keychain-profile", profile}
	if keychain != "" {
		auth = append(auth, "--keychain", keychain)
	}
	args := append([]string{"notarytool", "submit", archive}, auth...)
	args = append(args, "--no-wait", "--no-progress", "--output-format", "json")
	data, err := run(root, "/usr/bin/xcrun", args...)
	if err != nil {
		return nil, err
	}
	var status macNotaryStatus
	if json.Unmarshal(data, &status) != nil || !macSubmissionPattern.MatchString(status.ID) {
		return nil, errors.New("release_notarization_submission_invalid")
	}
	// Submit once, then wait on that ID. A wait timeout never resubmits the bytes.
	args = append([]string{"notarytool", "wait", status.ID}, auth...)
	args = append(args, "--timeout", "25m", "--no-progress", "--output-format", "json")
	data, err = run(root, "/usr/bin/xcrun", args...)
	if err != nil {
		return nil, errors.New("release_notarization_wait_incomplete")
	}
	var accepted macNotaryStatus
	if json.Unmarshal(data, &accepted) != nil || accepted.ID != status.ID || accepted.Status != "Accepted" {
		return nil, errors.New("release_notarization_not_accepted")
	}
	args = append([]string{"notarytool", "log", status.ID}, auth...)
	args = append(args, "--no-progress")
	data, err = run(root, "/usr/bin/xcrun", args...)
	if err != nil {
		return nil, err
	}
	log, err := macValidateNotaryLog(data, status.ID, hash, filepath.Base(archive), files)
	if err != nil {
		return nil, err
	}
	after, afterSize, err := publicationHash(archive)
	if err != nil || after != hash || afterSize != size {
		return nil, errors.New("release_notarization_bytes_changed")
	}
	return map[string]any{"status": "Accepted", "submission_id": status.ID, "archive": filepath.Base(archive), "sha256": hash, "size": size, "apple_log": log, "runtime_files": files}, nil
}
func macInstallerWrapper(installer, directory string) (string, error) {
	archive := filepath.Join(directory, "installer-notary.zip")
	source, err := os.Open(installer)
	if err != nil {
		return "", err
	}
	defer source.Close()
	output, err := os.OpenFile(archive, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return "", err
	}
	writer := zip.NewWriter(output)
	header := &zip.FileHeader{Name: filepath.Base(installer), Method: zip.Deflate}
	header.SetMode(0755)
	entry, err := writer.CreateHeader(header)
	if err == nil {
		_, err = io.Copy(entry, source)
	}
	if closeErr := writer.Close(); err == nil {
		err = closeErr
	}
	if closeErr := output.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return "", errors.New("release_notarization_wrapper_failed")
	}
	return archive, nil
}
func macDistributionFiles(root, version, identity, team string, run publicationSigningCommand) ([]macSignedFile, macSignedFile, error) {
	files := []macSignedFile{}
	var installerRecord macSignedFile
	folder := filepath.Join(root, "dist", "native", "darwin-arm64")
	manifest, err := publicationBundleManifest(filepath.Join(root, "dist", "opensocrates-v"+version+"-darwin-arm64.zip"))
	if err != nil {
		return nil, installerRecord, err
	}
	inventory := map[string]map[string]any{}
	for _, item := range arr(manifest["files"]) {
		r := obj(item)
		inventory[str(r["path"])] = r
	}
	for _, relative := range []string{"bin/opensocrates", "bin/opensocrates-update-helper", "packages/codex/runtime/darwin-arm64/opensocrates", "packages/claude/runtime/darwin-arm64/opensocrates"} {
		record, err := macVerifySigned(root, filepath.Join(folder, filepath.FromSlash(relative)), relative, identity, team, run)
		if err != nil {
			return nil, installerRecord, err
		}
		if strings.TrimPrefix(str(inventory[relative]["sha256"]), "sha256:") != record.SHA256 {
			return nil, installerRecord, errors.New("release_notarization_package_mismatch")
		}
		files = append(files, record)
	}
	installer := filepath.Join(root, "dist", publicationInstallerName(version, "darwin-arm64"))
	installerRecord, err = macVerifySigned(root, installer, filepath.Base(installer), identity, team, run)
	if err != nil || installerRecord.SHA256 != files[0].SHA256 || installerRecord.Size != files[0].Size || installerRecord.CDHash != files[0].CDHash {
		return nil, installerRecord, errors.New("release_installer_bundle_mismatch")
	}
	for _, duplicate := range files[2:] {
		if duplicate.SHA256 != files[0].SHA256 || duplicate.CDHash != files[0].CDHash {
			return nil, installerRecord, errors.New("release_notarization_package_mismatch")
		}
	}
	return files, installerRecord, nil
}
func macNotarizeDistribution(root, identity, team, keychain, profile string, run publicationSigningCommand) (map[string]any, error) {
	version, err := publicationVersion(root)
	if err != nil {
		return nil, err
	}
	temp := os.Getenv("RUNNER_TEMP")
	if temp == "" || !filepath.IsAbs(temp) {
		return nil, errors.New("release_notarization_runner_temp_required")
	}
	actual, err := filepath.EvalSymlinks(temp)
	if err != nil || filepath.Clean(temp) != actual {
		return nil, errors.New("release_notarization_runner_temp_invalid")
	}
	rel, err := filepath.Rel(root, temp)
	if err != nil || rel == "." || (rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator))) {
		return nil, errors.New("release_notarization_runner_temp_inside_source")
	}
	private, err := os.MkdirTemp(temp, "opensocrates-notary-")
	if err != nil {
		return nil, errors.New("release_notarization_temp_failed")
	}
	defer os.RemoveAll(private)
	files, installerFile, err := macDistributionFiles(root, version, identity, team, run)
	if err != nil {
		return nil, err
	}
	payload := filepath.Join(root, "dist", "opensocrates-v"+version+"-darwin-arm64.zip")
	receipt, err := macNotaryAccept(root, payload, profile, keychain, files, run)
	if err != nil {
		return nil, err
	}
	wrapper, err := macInstallerWrapper(filepath.Join(root, "dist", installerFile.Path), private)
	if err != nil {
		return nil, err
	}
	installer, err := macNotaryAccept(root, wrapper, profile, keychain, []macSignedFile{installerFile}, run)
	if err != nil {
		return nil, err
	}
	installer["installer"] = installerFile.Path
	installer["installer_sha256"] = installerFile.SHA256
	installer["installer_size"] = installerFile.Size
	installer["payload_submission_id"] = receipt["submission_id"]
	installer["payload_notarized_first"] = true
	after, size, err := publicationHash(filepath.Join(root, "dist", installerFile.Path))
	if err != nil || after != installerFile.SHA256 || size != installerFile.Size {
		return nil, errors.New("release_notarization_installer_changed")
	}
	receipt["standalone_installer"] = installer
	return receipt, nil
}
