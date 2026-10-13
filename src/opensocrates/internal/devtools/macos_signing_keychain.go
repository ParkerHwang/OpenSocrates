package devtools

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha1"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	"flag"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
)

const macSigningStateSchema = "opensocrates.hosted-mac-keychain-state/1.0.0"
const macSigningProfile = "opensocrates-notary-ci"
const macSigningMaxP12 = 1024 * 1024

var macSigningSHA1 = regexp.MustCompile(`^[a-fA-F0-9]{40}$`)
var macSigningTeam = regexp.MustCompile(`^[A-Z0-9]{10}$`)
var macSigningJob = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,100}$`)
var macSigningNumber = regexp.MustCompile(`^[0-9]{1,30}$`)

type macSigningState struct {
	Schema             string   `json:"schema"`
	Directory          string   `json:"directory"`
	RunnerTemp         string   `json:"runner_temp"`
	RunID              string   `json:"run_id"`
	Attempt            string   `json:"attempt"`
	Job                string   `json:"job"`
	Prepared           bool     `json:"prepared"`
	Identity           string   `json:"identity"`
	Team               string   `json:"team"`
	OriginalSearchList []string `json:"original_search_list"`
}

type macSigningCommand func(string, string, ...string) ([]byte, error)

// Only the newly created keychain belongs to this tool. The runner's default
// keychain and every pre-existing keychain's access controls remain untouched.
func RunMacOSSigningSetup(root, command string, args []string) error {
	f := flag.NewFlagSet(command, flag.ContinueOnError)
	f.SetOutput(io.Discard)
	purpose := f.String("purpose", "production", "production or qualification")
	f.StringVar(&root, "root", root, "source checkout")
	if f.Parse(args) != nil || len(f.Args()) != 0 {
		return errors.New("mac_signing_arguments_invalid")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return errors.New("mac_signing_source_invalid")
	}
	if command == "macos-signing-cleanup" {
		return macSigningCleanup(absolute, macSigningPrivateExternal)
	}
	if command != "macos-signing-prepare" {
		return errors.New("mac_signing_command_invalid")
	}
	if err = requireMacSigningPurpose(absolute, *purpose); err != nil {
		return err
	}
	return macSigningPrepare(absolute, macSigningPrivateExternal)
}

func requireMacSigningPurpose(root, purpose string) error {
	if err := macSigningHostedEnvironment(runtime.GOOS, runtime.GOARCH); err != nil {
		return err
	}
	switch purpose {
	case "production":
		if err := publicationRequireEnvironment(); err != nil {
			return err
		}
		_, err := publicationIdentity(root)
		return err
	case "qualification":
		if os.Getenv("GITHUB_EVENT_NAME") != "push" || os.Getenv("GITHUB_REF") != "refs/heads/codex/v1.6-go-native" {
			return errors.New("mac_signing_qualification_branch_required")
		}
		expected := os.Getenv("OPENSOCRATES_EXPECTED_SOURCE_SHA")
		if !publicationCommitPattern.MatchString(expected) || expected != os.Getenv("GITHUB_SHA") {
			return errors.New("mac_signing_qualification_commit_required")
		}
		head, err := publicationGit(root, "rev-parse", "HEAD")
		if err != nil || head != expected {
			return errors.New("mac_signing_qualification_checkout_mismatch")
		}
		status, err := publicationGit(root, "status", "--porcelain", "--untracked-files=all")
		if err != nil || status != "" {
			return errors.New("mac_signing_qualification_source_dirty")
		}
		return nil
	default:
		return errors.New("mac_signing_purpose_invalid")
	}
}

func macSigningHostedEnvironment(goos, goarch string) error {
	if goos != "darwin" || goarch != "arm64" || os.Getenv("GITHUB_ACTIONS") != "true" || os.Getenv("GITHUB_REPOSITORY") != publicationRepository || os.Getenv("OPENSOCRATES_RUNNER_ENVIRONMENT") != "github-hosted" || os.Getenv("RUNNER_OS") != "macOS" || os.Getenv("RUNNER_ARCH") != "ARM64" || os.Getenv("OPENSOCRATES_RUNNER_ARCH") != "ARM64" {
		return errors.New("mac_signing_hosted_arm64_required")
	}
	return nil
}

func macSigningChildEnvironment() []string {
	result := []string{"PATH=/usr/bin:/bin:/usr/sbin:/sbin"}
	for _, name := range []string{"HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "DEVELOPER_DIR"} {
		if value, ok := os.LookupEnv(name); ok {
			result = append(result, name+"="+value)
		}
	}
	return result
}

type macSigningBoundedOutput struct {
	data     bytes.Buffer
	overflow bool
}

func (w *macSigningBoundedOutput) Write(p []byte) (int, error) {
	if w.data.Len()+len(p) > 2*1024*1024 {
		w.overflow = true
		return 0, errors.New("mac_signing_response_oversize")
	}
	return w.data.Write(p)
}

// Secret arguments required by Apple's CLI are confined to the isolated job;
// neither argument lists, private command output nor OS errors are returned.
func macSigningPrivateExternal(root, name string, args ...string) ([]byte, error) {
	switch name {
	case "/usr/bin/security", "/usr/bin/xcrun", "/usr/bin/codesign":
	default:
		return nil, errors.New("mac_signing_tool_invalid")
	}
	timeout := 3 * time.Minute
	if name == "/usr/bin/xcrun" {
		timeout = 30 * time.Minute
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Dir = root
	cmd.Env = macSigningChildEnvironment()
	var output macSigningBoundedOutput
	cmd.Stdout, cmd.Stderr = &output, &output
	err := cmd.Run()
	if output.overflow {
		return nil, errors.New("mac_signing_response_oversize")
	}
	if err != nil {
		return nil, errors.New("mac_signing_private_command_failed")
	}
	return output.data.Bytes(), nil
}

func macSigningParseSearchList(data []byte) ([]string, error) {
	if len(data) > 65536 {
		return nil, errors.New("mac_signing_search_list_invalid")
	}
	result := []string{}
	seen := map[string]bool{}
	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		path, err := strconv.Unquote(line)
		if err != nil || !filepath.IsAbs(path) || strings.ContainsAny(path, "\r\n\x00") || seen[path] || len(result) >= 64 {
			return nil, errors.New("mac_signing_search_list_invalid")
		}
		seen[path] = true
		result = append(result, path)
	}
	return result, nil
}

func macSigningEmit(values map[string]string) error {
	envPath := os.Getenv("GITHUB_ENV")
	if !filepath.IsAbs(envPath) {
		return errors.New("mac_signing_job_environment_invalid")
	}
	info, err := os.Lstat(envPath)
	if err != nil || !info.Mode().IsRegular() {
		return errors.New("mac_signing_job_environment_invalid")
	}
	file, err := os.OpenFile(envPath, os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		return errors.New("mac_signing_job_environment_unavailable")
	}
	defer file.Close()
	for _, name := range []string{"OPENSOCRATES_MAC_SIGNING_STATE", "OPENSOCRATES_MAC_SIGNING_KEYCHAIN", "OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE"} {
		value, ok := values[name]
		if !ok {
			continue
		}
		if strings.ContainsAny(value, "\r\n\x00") {
			return errors.New("mac_signing_job_environment_invalid")
		}
		if _, err = io.WriteString(file, name+"="+value+"\n"); err != nil {
			return errors.New("mac_signing_job_environment_unavailable")
		}
		if err = os.Setenv(name, value); err != nil {
			return errors.New("mac_signing_job_environment_unavailable")
		}
	}
	if file.Sync() != nil {
		return errors.New("mac_signing_job_environment_unavailable")
	}
	return nil
}

func macSigningPrepare(root string, run macSigningCommand) (result error) {
	if os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE") != "" {
		return errors.New("mac_signing_state_already_present")
	}
	identity, team := os.Getenv("OPENSOCRATES_MAC_SIGN_IDENTITY"), os.Getenv("OPENSOCRATES_MAC_TEAM_ID")
	appleID, appPassword := os.Getenv("OPENSOCRATES_NOTARY_APPLE_ID"), os.Getenv("OPENSOCRATES_NOTARY_APP_PASSWORD")
	certificatePassword := os.Getenv("OPENSOCRATES_MAC_CERTIFICATE_PASSWORD")
	encoded := os.Getenv("OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64")
	if !macSigningSHA1.MatchString(identity) || !macSigningTeam.MatchString(team) || team != update.DefaultNativeTrust().DarwinTeamID || os.Getenv("OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE") != macSigningProfile || len(appleID) < 3 || len(appleID) > 320 || !strings.Contains(appleID, "@") || strings.ContainsAny(appleID, "\r\n\x00") || len(appPassword) == 0 || len(appPassword) > 1024 || strings.ContainsAny(appPassword, "\r\n\x00") || len(certificatePassword) == 0 || len(certificatePassword) > 1024 || strings.ContainsAny(certificatePassword, "\r\n\x00") || len(encoded) > base64.StdEncoding.EncodedLen(macSigningMaxP12) {
		return errors.New("mac_signing_configuration_invalid")
	}
	p12, err := base64.StdEncoding.Strict().DecodeString(encoded)
	if err != nil || len(p12) == 0 || len(p12) > macSigningMaxP12 {
		return errors.New("mac_signing_certificate_invalid")
	}
	temp := os.Getenv("RUNNER_TEMP")
	canonical, err := filepath.EvalSymlinks(temp)
	if err != nil || !filepath.IsAbs(temp) || filepath.Clean(temp) != temp || canonical != temp || strings.ContainsAny(temp, "\r\n\x00") {
		return errors.New("mac_signing_runner_temp_invalid")
	}
	runID, attempt, job := os.Getenv("GITHUB_RUN_ID"), os.Getenv("GITHUB_RUN_ATTEMPT"), os.Getenv("GITHUB_JOB")
	if !macSigningNumber.MatchString(runID) || !macSigningNumber.MatchString(attempt) || !macSigningJob.MatchString(job) {
		return errors.New("mac_signing_run_identity_invalid")
	}
	original, err := run(root, "/usr/bin/security", "list-keychains", "-d", "user")
	if err != nil {
		return err
	}
	list, err := macSigningParseSearchList(original)
	if err != nil {
		return err
	}
	directory, err := os.MkdirTemp(temp, "opensocrates-mac-signing-")
	if err != nil {
		return errors.New("mac_signing_private_directory_unavailable")
	}
	if os.Chmod(directory, 0700) != nil {
		_ = os.Remove(directory)
		return errors.New("mac_signing_private_directory_unavailable")
	}
	state := macSigningState{Schema: macSigningStateSchema, Directory: directory, RunnerTemp: temp, RunID: runID, Attempt: attempt, Job: job, Identity: identity, Team: team, OriginalSearchList: list}
	statePath := filepath.Join(directory, "state.json")
	data, _ := json.Marshal(state)
	if os.WriteFile(statePath, data, 0600) != nil {
		_ = os.Remove(directory)
		return errors.New("mac_signing_state_write_failed")
	}
	// Register cleanup before creating any keychain, changing search state or
	// invoking a command that consumes a credential.
	if err = macSigningEmit(map[string]string{"OPENSOCRATES_MAC_SIGNING_STATE": statePath}); err != nil {
		_ = os.Remove(statePath)
		_ = os.Remove(directory)
		return err
	}
	defer func() {
		if result != nil {
			if macSigningCleanup(root, run) != nil {
				result = errors.New("mac_signing_prepare_and_cleanup_failed")
			}
		}
	}()
	p12Path := filepath.Join(directory, "certificate.p12")
	if os.WriteFile(p12Path, p12, 0600) != nil {
		return errors.New("mac_signing_certificate_write_failed")
	}
	clear(p12)
	random := make([]byte, 32)
	if _, err = rand.Read(random); err != nil {
		return errors.New("mac_signing_random_unavailable")
	}
	password := base64.RawURLEncoding.EncodeToString(random)
	clear(random)
	keychain := filepath.Join(directory, "signing.keychain-db")
	calls := [][]string{
		{"create-keychain", "-p", password, keychain},
		{"set-keychain-settings", "-lut", "7200", keychain},
		{"unlock-keychain", "-p", password, keychain},
		{"import", p12Path, "-k", keychain, "-P", certificatePassword, "-T", "/usr/bin/codesign", "-T", "/usr/bin/security"},
		{"set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", password, keychain},
	}
	for _, args := range calls {
		if _, err = run(root, "/usr/bin/security", args...); err != nil {
			return err
		}
	}
	if os.Remove(p12Path) != nil {
		return errors.New("mac_signing_certificate_unlink_failed")
	}
	identities, err := run(root, "/usr/bin/security", "find-identity", "-v", "-p", "codesigning", keychain)
	if err != nil {
		return err
	}
	certs, err := run(root, "/usr/bin/security", "find-certificate", "-a", "-p", keychain)
	if err != nil {
		return err
	}
	if err = macSigningValidateCertificate(identities, certs, identity, team); err != nil {
		return err
	}
	if _, err = run(root, "/usr/bin/xcrun", "notarytool", "store-credentials", macSigningProfile, "--apple-id", appleID, "--password", appPassword, "--team-id", team, "--keychain", keychain, "--validate"); err != nil {
		return errors.New("mac_signing_notary_authentication_failed")
	}
	wanted := append([]string{keychain}, list...)
	if _, err = run(root, "/usr/bin/security", append([]string{"list-keychains", "-d", "user", "-s"}, wanted...)...); err != nil {
		return err
	}
	state.Prepared = true
	data, _ = json.Marshal(state)
	pending := filepath.Join(directory, "state.pending")
	if os.WriteFile(pending, data, 0600) != nil || os.Rename(pending, statePath) != nil {
		return errors.New("mac_signing_state_write_failed")
	}
	return macSigningEmit(map[string]string{"OPENSOCRATES_MAC_SIGNING_KEYCHAIN": keychain, "OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE": macSigningProfile})
}

func macSigningValidateCertificate(identities, certs []byte, identity, team string) error {
	row := regexp.MustCompile(`(?m)^\s*[0-9]+\) ([0-9A-Fa-f]{40}) "Developer ID Application:[^"\r\n]*"\s*$`).FindAllSubmatch(identities, -1)
	if len(row) != 1 || !strings.EqualFold(string(row[0][1]), identity) || !regexp.MustCompile(`(?m)^\s*1 valid identities found\s*$`).Match(identities) {
		return errors.New("mac_signing_private_identity_mismatch")
	}
	remaining := certs
	matched := 0
	for len(remaining) > 0 {
		block, rest := pem.Decode(remaining)
		if block == nil {
			if len(bytes.TrimSpace(remaining)) != 0 {
				return errors.New("mac_signing_certificate_metadata_invalid")
			}
			break
		}
		remaining = rest
		if block.Type != "CERTIFICATE" {
			return errors.New("mac_signing_certificate_metadata_invalid")
		}
		cert, err := x509.ParseCertificate(block.Bytes)
		if err != nil {
			return errors.New("mac_signing_certificate_metadata_invalid")
		}
		hash := sha1.Sum(cert.Raw)
		if !strings.EqualFold(hex.EncodeToString(hash[:]), identity) {
			continue
		}
		matched++
		hasDeveloperID := false
		for _, extension := range cert.Extensions {
			if extension.Id.String() == "1.2.840.113635.100.6.1.13" {
				hasDeveloperID = true
			}
		}
		hasCodeSigning := false
		for _, usage := range cert.ExtKeyUsage {
			if usage == x509.ExtKeyUsageCodeSigning {
				hasCodeSigning = true
			}
		}
		if !hasDeveloperID || !hasCodeSigning || len(cert.Subject.OrganizationalUnit) != 1 || cert.Subject.OrganizationalUnit[0] != team || time.Now().Before(cert.NotBefore) || !time.Now().Before(cert.NotAfter) {
			return errors.New("mac_signing_certificate_team_mismatch")
		}
	}
	if matched != 1 {
		return errors.New("mac_signing_certificate_metadata_invalid")
	}
	return nil
}

func macSigningReadOwnedState() (macSigningState, error) {
	var state macSigningState
	path, temp := os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"), os.Getenv("RUNNER_TEMP")
	if !filepath.IsAbs(temp) || filepath.Clean(temp) != temp || !filepath.IsAbs(path) || filepath.Base(path) != "state.json" {
		return state, errors.New("mac_signing_cleanup_state_invalid")
	}
	directory := filepath.Dir(path)
	if filepath.Dir(directory) != temp || !strings.HasPrefix(filepath.Base(directory), "opensocrates-mac-signing-") {
		return state, errors.New("mac_signing_cleanup_state_invalid")
	}
	canonical, err := filepath.EvalSymlinks(directory)
	if err != nil || canonical != directory {
		return state, errors.New("mac_signing_cleanup_state_invalid")
	}
	dirInfo, err := os.Lstat(directory)
	if err != nil || !dirInfo.IsDir() || dirInfo.Mode().Perm() != 0700 {
		return state, errors.New("mac_signing_cleanup_state_invalid")
	}
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm() != 0600 || info.Size() > 65536 {
		return state, errors.New("mac_signing_cleanup_state_invalid")
	}
	data, err := os.ReadFile(path)
	if err != nil || json.Unmarshal(data, &state) != nil || state.Schema != macSigningStateSchema || state.Directory != directory || state.RunnerTemp != temp || state.RunID != os.Getenv("GITHUB_RUN_ID") || state.Attempt != os.Getenv("GITHUB_RUN_ATTEMPT") || state.Job != os.Getenv("GITHUB_JOB") || !macSigningNumber.MatchString(state.RunID) || !macSigningNumber.MatchString(state.Attempt) || !macSigningJob.MatchString(state.Job) || len(state.OriginalSearchList) > 64 {
		return macSigningState{}, errors.New("mac_signing_cleanup_state_invalid")
	}
	for _, entry := range state.OriginalSearchList {
		if !filepath.IsAbs(entry) || strings.ContainsAny(entry, "\r\n\x00") {
			return macSigningState{}, errors.New("mac_signing_cleanup_state_invalid")
		}
	}
	return state, nil
}

func macSigningOwnedKeychain() (string, error) {
	state, err := macSigningReadOwnedState()
	if err != nil {
		return "", err
	}
	path := filepath.Join(state.Directory, "signing.keychain-db")
	if !state.Prepared || !strings.EqualFold(state.Identity, os.Getenv("OPENSOCRATES_MAC_SIGN_IDENTITY")) || state.Team != os.Getenv("OPENSOCRATES_MAC_TEAM_ID") || os.Getenv("OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE") != macSigningProfile || os.Getenv("OPENSOCRATES_MAC_SIGNING_KEYCHAIN") != path {
		return "", errors.New("mac_signing_owned_keychain_required")
	}
	info, err := os.Lstat(path)
	if err != nil || !info.Mode().IsRegular() {
		return "", errors.New("mac_signing_owned_keychain_required")
	}
	return path, nil
}

func macSigningCleanup(root string, run macSigningCommand) error {
	if os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE") == "" {
		return nil
	}
	state, err := macSigningReadOwnedState()
	if err != nil {
		// A successfully cleaned directory is absent when always() repeats cleanup.
		path := os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE")
		if _, statErr := os.Lstat(filepath.Dir(path)); os.IsNotExist(statErr) && filepath.Dir(filepath.Dir(path)) == os.Getenv("RUNNER_TEMP") && strings.HasPrefix(filepath.Base(filepath.Dir(path)), "opensocrates-mac-signing-") {
			return nil
		}
		return err
	}
	keychain := filepath.Join(state.Directory, "signing.keychain-db")
	var cleanupError error
	foreign := false
	data, listErr := run(root, "/usr/bin/security", "list-keychains", "-d", "user")
	if listErr == nil {
		current, parseErr := macSigningParseSearchList(data)
		if parseErr == nil {
			filtered := []string{}
			for _, path := range current {
				if path != keychain {
					filtered = append(filtered, path)
				}
			}
			foreign = !macSigningSameList(filtered, state.OriginalSearchList)
			restore := state.OriginalSearchList
			if foreign {
				restore = filtered
			}
			if _, err = run(root, "/usr/bin/security", append([]string{"list-keychains", "-d", "user", "-s"}, restore...)...); err != nil {
				cleanupError = errors.New("mac_signing_cleanup_search_list_failed")
			}
		} else {
			cleanupError = errors.New("mac_signing_cleanup_search_list_failed")
		}
	} else {
		cleanupError = errors.New("mac_signing_cleanup_search_list_failed")
	}
	// Even if inspecting/restoring the search list fails, remove only this job's
	// owned private keychain and private files. Never overwrite unknown changes.
	if info, statErr := os.Lstat(keychain); statErr == nil {
		if !info.Mode().IsRegular() {
			return errors.New("mac_signing_cleanup_keychain_invalid")
		}
		if _, err = run(root, "/usr/bin/security", "delete-keychain", keychain); err != nil {
			cleanupError = errors.New("mac_signing_cleanup_keychain_failed")
		}
	} else if !os.IsNotExist(statErr) {
		return errors.New("mac_signing_cleanup_keychain_invalid")
	}
	// Delete only owned names; an unexpected file prevents removing the folder.
	for _, name := range []string{"certificate.p12", "state.pending", "signing.keychain-db", "signing.keychain-db-shm", "signing.keychain-db-wal"} {
		path := filepath.Join(state.Directory, name)
		if info, err := os.Lstat(path); err == nil && !info.Mode().IsRegular() {
			return errors.New("mac_signing_cleanup_private_file_invalid")
		}
		if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
			return errors.New("mac_signing_cleanup_private_file_failed")
		}
	}
	entries, err := os.ReadDir(state.Directory)
	if err != nil || len(entries) != 1 || entries[0].Name() != "state.json" {
		return errors.New("mac_signing_cleanup_unexpected_private_file")
	}
	if os.Remove(filepath.Join(state.Directory, "state.json")) != nil || os.Remove(state.Directory) != nil {
		return errors.New("mac_signing_cleanup_private_directory_failed")
	}
	if cleanupError != nil {
		return cleanupError
	}
	if foreign {
		return errors.New("mac_signing_cleanup_foreign_search_list_preserved")
	}
	if publicationReceipt(root, "macos-keychain-cleanup.json", map[string]any{"schema": "opensocrates.hosted-mac-keychain-cleanup/1.0.0", "commit": os.Getenv("GITHUB_SHA"), "status": "verified", "owned_keychain_deleted": true, "private_files_deleted": true, "original_search_list_restored": true}) != nil {
		return errors.New("mac_signing_cleanup_receipt_failed")
	}
	return nil
}

func macSigningSameList(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}
