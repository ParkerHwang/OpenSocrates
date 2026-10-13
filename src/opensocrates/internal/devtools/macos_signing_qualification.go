package devtools

import (
	"context"
	"debug/buildinfo"
	"errors"
	"flag"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
)

// RunMacOSSigningQualification qualifies the actual candidate bytes on an
// approved isolated hosted runner. It does not manufacture tag/production
// flags, production receipts, TUF metadata or public release assets.
func RunMacOSSigningQualification(root string, args []string) error {
	f := flag.NewFlagSet("macos-signing-qualify", flag.ContinueOnError)
	f.SetOutput(io.Discard)
	expected := f.String("commit", os.Getenv("OPENSOCRATES_EXPECTED_SOURCE_SHA"), "exact candidate source")
	f.StringVar(&root, "root", root, "source checkout")
	if f.Parse(args) != nil || len(f.Args()) != 0 {
		return errors.New("mac_signing_qualification_arguments_invalid")
	}
	root, err := filepath.Abs(root)
	if err != nil {
		return errors.New("mac_signing_qualification_source_invalid")
	}
	if *expected != os.Getenv("OPENSOCRATES_EXPECTED_SOURCE_SHA") {
		return errors.New("mac_signing_qualification_commit_required")
	}
	if err = requireMacSigningPurpose(root, "qualification"); err != nil {
		return err
	}
	identity, team, keychain, profile, err := macSigningConfiguration(root, "qualification")
	if err != nil {
		return err
	}
	if keychain == "" || profile != "opensocrates-notary-ci" {
		return errors.New("mac_signing_qualification_credentials_unavailable")
	}
	// Runtime builds occur before credential injection. Check exact VCS build
	// identity again before signing; never execute a mismatched candidate.
	for _, name := range []string{"opensocrates", "opensocrates-update-helper"} {
		if err = macQualificationBuildIdentity(filepath.Join(root, "dist", "runtime", "darwin-arm64", name), *expected); err != nil {
			return err
		}
	}
	files, err := macSignRuntime(root, identity, team, keychain, publicationExternal)
	if err != nil {
		return err
	}
	manifest, err := PackageNative(root, "darwin-arm64", "", "dist/native/darwin-arm64")
	if err != nil {
		return errors.New("mac_signing_qualification_package_failed")
	}
	if manifest["source_git_commit"] != *expected || manifest["dirty_tree"] != false {
		return errors.New("mac_signing_qualification_package_identity_mismatch")
	}
	notary, err := macNotarizeDistribution(root, identity, team, keychain, profile, publicationExternal)
	if err != nil {
		return err
	}
	notary["schema"] = "opensocrates.macos-notarization-candidate/2.0.0"
	notary["source_commit"] = *expected
	notary["target"] = "darwin-arm64"
	// Retry only online ticket propagation after Apple's Accepted log has bound
	// these exact bytes. Neither submission nor signing is repeated.
	version, err := publicationVersion(root)
	if err != nil {
		return err
	}
	relativeFiles := []string{"bin/opensocrates", "bin/opensocrates-update-helper", "packages/codex/runtime/darwin-arm64/opensocrates", "packages/claude/runtime/darwin-arm64/opensocrates"}
	packagePath := filepath.Join(root, "dist", "native", "darwin-arm64")
	paths := []string{}
	for _, name := range relativeFiles {
		paths = append(paths, filepath.Join(packagePath, filepath.FromSlash(name)))
	}
	paths = append(paths, filepath.Join(root, "dist", publicationInstallerName(version, "darwin-arm64")))
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	if err = macVerifyAcceptedPaths(ctx, paths, update.DefaultNativeTrust(), platform.VerifyNativeSignature, 6, 10*time.Second); err != nil {
		return err
	}
	// Use the documented relative release path, retaining the lexical alias and
	// manager/helper-before-execution gates in CheckNativeRelease.
	if err = CheckNativeRelease(root, filepath.Join("dist", "native", "darwin-arm64"), "darwin-arm64", io.Discard); err != nil {
		return errors.New("mac_signing_qualification_release_check_failed")
	}
	archiveHash, archiveSize, err := publicationHash(filepath.Join(root, "dist", str(notary["archive"])))
	installerHash, installerSize, installerErr := publicationHash(paths[len(paths)-1])
	acceptedInstaller := obj(notary["standalone_installer"])
	if err != nil || installerErr != nil || archiveHash != notary["sha256"] || !publicationReceiptInteger(notary["size"], archiveSize) || installerHash != acceptedInstaller["installer_sha256"] || !publicationReceiptInteger(acceptedInstaller["installer_size"], installerSize) {
		return errors.New("mac_signing_qualification_accepted_bytes_changed")
	}
	if err = requireMacSigningPurpose(root, "qualification"); err != nil {
		return err
	}
	tree, err := publicationGit(root, "rev-parse", "HEAD^{tree}")
	if err != nil || !publicationCommitPattern.MatchString(tree) {
		return errors.New("mac_signing_qualification_tree_invalid")
	}
	evidence := filepath.Join(root, "build", "evidence")
	provenance := map[string]any{"schema": "opensocrates.macos-signing-candidate-provenance/1.0.0", "repository": publicationRepository, "commit": *expected, "tree": tree, "platform": "darwin-arm64", "go_version": runtime.Version()}
	provenancePath := filepath.Join(evidence, "macos-signing-candidate-provenance.json")
	if err = writeJSON(provenancePath, provenance); err != nil {
		return err
	}
	sbomPath := filepath.Join(evidence, "macos-signing-candidate-sbom.cdx.json")
	if err = WriteSBOM(packagePath, sbomPath); err != nil {
		return errors.New("mac_signing_qualification_sbom_failed")
	}
	provenanceHash, _, err := publicationHash(provenancePath)
	if err != nil {
		return err
	}
	sbomHash, _, err := publicationHash(sbomPath)
	if err != nil {
		return err
	}
	environment, err := macQualificationVersions(root, publicationExternal)
	if err != nil {
		return err
	}
	if err = publicationReceipt(root, "macos-signing-candidate-notarization.json", notary); err != nil {
		return err
	}
	records := []map[string]any{}
	for index, path := range paths {
		hash, size, err := publicationHash(path)
		if err != nil {
			return err
		}
		name := publicationInstallerName(version, "darwin-arm64")
		if index < len(relativeFiles) {
			name = relativeFiles[index]
		}
		records = append(records, map[string]any{"path": name, "sha256": hash, "size": size, "pinned_notarized_verified": true})
	}
	return publicationReceipt(root, "macos-signing-candidate-qualification.json", map[string]any{
		"schema": "opensocrates.macos-signing-candidate-qualification/1.0.0", "repository": publicationRepository, "source_commit": *expected, "target": "darwin-arm64", "status": "verified",
		"evidence_level": "candidate-hosted-native-platform-integrity", "environment": environment, "team_id": team, "certificate_sha1": strings.ToLower(identity), "signed_runtime": files, "native_verification": records,
		"release_check": "passed", "source_provenance": provenance, "source_provenance_sha256": provenanceHash, "sbom_sha256": sbomHash,
		"limitations": map[string]bool{"clean_machine": false, "quarantined_download": false, "final_merged_tag": false, "production_tuf_trust": false, "production_publication": false},
	})
}

func macQualificationBuildIdentity(path, commit string) error {
	if err := verifyGoBinary(path, "darwin-arm64"); err != nil {
		return errors.New("mac_signing_qualification_runtime_invalid")
	}
	info, err := buildinfo.ReadFile(path)
	if err != nil {
		return errors.New("mac_signing_qualification_runtime_invalid")
	}
	settings := map[string]string{}
	for _, setting := range info.Settings {
		settings[setting.Key] = setting.Value
	}
	if settings["vcs.revision"] != commit || settings["vcs.modified"] != "false" {
		return errors.New("mac_signing_qualification_runtime_source_mismatch")
	}
	return nil
}
func macVerifyAcceptedPaths(ctx context.Context, paths []string, policy platform.NativeTrustPolicy, verify func(context.Context, string, platform.NativeTrustPolicy) error, attempts int, delay time.Duration) error {
	if attempts < 1 || attempts > 6 || delay < 0 || delay > 10*time.Second || len(paths) != 5 {
		return errors.New("mac_signing_qualification_verification_bounds_invalid")
	}
	for attempt := 0; attempt < attempts; attempt++ {
		if ctx.Err() != nil {
			return errors.New("mac_signing_qualification_online_verification_incomplete")
		}
		all := true
		for _, path := range paths {
			if err := verify(ctx, path, policy); err != nil {
				all = false
				break
			}
		}
		if all {
			return nil
		}
		if attempt+1 < attempts {
			timer := time.NewTimer(delay)
			select {
			case <-ctx.Done():
				timer.Stop()
				return errors.New("mac_signing_qualification_online_verification_incomplete")
			case <-timer.C:
			}
		}
	}
	return errors.New("mac_signing_qualification_online_verification_incomplete")
}
func macQualificationVersions(root string, run publicationSigningCommand) (map[string]any, error) {
	result := map[string]any{"runner_environment": "github-hosted", "os": "macOS", "architecture": "arm64", "go_version": runtime.Version()}
	for _, item := range []struct {
		field, tool string
		args        []string
		pattern     *regexp.Regexp
	}{
		{"os_version", "/usr/bin/sw_vers", []string{"-productVersion"}, regexp.MustCompile(`^[0-9]+\.[0-9]+(?:\.[0-9]+)?$`)},
		{"os_build", "/usr/bin/sw_vers", []string{"-buildVersion"}, regexp.MustCompile(`^[A-Za-z0-9]{4,20}$`)},
	} {
		data, err := run(root, item.tool, item.args...)
		value := strings.TrimSpace(string(data))
		if err != nil || !item.pattern.MatchString(value) {
			return nil, errors.New("mac_signing_qualification_tool_version_invalid")
		}
		result[item.field] = value
	}
	data, err := run(root, "/usr/bin/xcrun", "notarytool", "--version")
	match := regexp.MustCompile(`([0-9]+\.[0-9]+\.[0-9]+) \(([0-9]+)\)`).FindStringSubmatch(string(data))
	if err != nil || len(match) != 3 {
		return nil, errors.New("mac_signing_qualification_tool_version_invalid")
	}
	result["notarytool_version"] = match[1]
	result["notarytool_build"] = match[2]
	return result, nil
}
