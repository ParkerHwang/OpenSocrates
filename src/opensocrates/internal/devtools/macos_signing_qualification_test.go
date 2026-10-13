package devtools

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
)

func TestMacSigningConfigurationCannotReplacePinnedTeam(t *testing.T) {
	t.Setenv("OPENSOCRATES_MAC_SIGN_IDENTITY", strings.Repeat("a", 40))
	t.Setenv("OPENSOCRATES_MAC_SIGNING_KEYCHAIN", "")
	t.Setenv("OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE", "opensocrates-notary-ci")
	t.Setenv("OPENSOCRATES_MAC_TEAM_ID", "WRONG12345")
	if _, _, _, _, err := macSigningConfiguration(t.TempDir(), "production"); err == nil {
		t.Fatal("environment replaced compiled publisher pin")
	}
	t.Setenv("OPENSOCRATES_MAC_TEAM_ID", update.DefaultNativeTrust().DarwinTeamID)
	if _, _, _, _, err := macSigningConfiguration(t.TempDir(), "production"); err != nil {
		t.Fatal(err)
	}
	t.Setenv("OPENSOCRATES_MAC_SIGN_IDENTITY", "arbitrary keychain label")
	if _, _, _, _, err := macSigningConfiguration(t.TempDir(), "production"); err == nil {
		t.Fatal("arbitrary identity label accepted")
	}
}
func TestMacSignedMetadataRequiresPinnedCertificateRuntimeAndTimestamp(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "runtime")
	os.WriteFile(path, []byte("signed fixture"), 0600)
	identity := strings.Repeat("a", 40)
	team := "6HM2UD6746"
	details := "CodeDirectory v=20500 size=123 flags=0x10000(runtime) hashes=10+2 location=embedded\nCDHash=" + strings.Repeat("b", 40) + "\nTeamIdentifier=" + team + "\nTimestamp=Oct 12, 2026 at 10:00:00\n"
	for _, test := range []struct {
		name, details string
		bad           bool
	}{
		{"valid", details, false}, {"wrongteam", strings.Replace(details, team, "WRONG12345", 1), true}, {"adhoc", strings.Replace(details, "0x10000(runtime)", "0x2(adhoc)", 1), true}, {"no_timestamp", strings.Replace(details, "Timestamp=Oct 12, 2026 at 10:00:00\n", "", 1), true}, {"no_cdhash", strings.Replace(details, "CDHash=", "Unknown=", 1), true},
	} {
		t.Run(test.name, func(t *testing.T) {
			calls := 0
			run := func(root, tool string, args ...string) ([]byte, error) {
				calls++
				if calls == 1 {
					if strings.Join(args, " ") != "--verify --strict -R "+macSigningRequirement(identity, team)+" "+path {
						t.Fatal("certificate pin missing")
					}
					return nil, nil
				}
				return []byte(test.details), nil
			}
			result, err := macVerifySigned(root, path, "bin/runtime", identity, team, run)
			if (err != nil) != test.bad {
				t.Fatalf("unexpected verification result: %v", err)
			}
			if !test.bad && (result.SHA256 == "" || result.Size != 14 || result.CDHash != strings.Repeat("b", 40)) {
				t.Fatal("closed metadata missing")
			}
		})
	}
}
func TestMacNotaryLogBindsActualTicketsAndRejectsAcceptedWarnings(t *testing.T) {
	id := "00000000-0000-0000-0000-000000000001"
	hash := strings.Repeat("a", 64)
	cd := strings.Repeat("b", 40)
	valid := map[string]any{"jobId": id, "status": "Accepted", "statusCode": 0, "sha256": hash, "issues": nil, "ticketContents": []any{map[string]any{"path": "payload.zip/bin/runtime", "cdhash": cd, "arch": "arm64", "digestAlgorithm": "SHA-256"}}}
	files := []macSignedFile{{Path: "bin/runtime", CDHash: cd}}
	encode := func(value any) []byte { b, _ := json.Marshal(value); return b }
	if _, err := macValidateNotaryLog(encode(valid), id, hash, "payload.zip", files); err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		name, key string
		value     any
	}{
		{"wrong_job", "jobId", "00000000-0000-0000-0000-000000000002"}, {"rejected", "status", "Rejected"}, {"wrong_hash", "sha256", strings.Repeat("c", 64)}, {"warning", "issues", []any{map[string]any{"severity": "warning", "message": "PRIVATE_DIAGNOSTIC"}}}, {"missing_issues", "issues", ""}, {"wrong_cdhash", "ticketContents", []any{map[string]any{"path": "payload.zip/bin/runtime", "cdhash": strings.Repeat("c", 40), "arch": "arm64", "digestAlgorithm": "SHA-256"}}}, {"foreign_path", "ticketContents", []any{map[string]any{"path": "payload.zip/bin/foreign", "cdhash": cd, "arch": "arm64", "digestAlgorithm": "SHA-256"}}}, {"duplicate", "ticketContents", append(arr(valid["ticketContents"]), arr(valid["ticketContents"])...)},
	} {
		t.Run(test.name, func(t *testing.T) {
			value := map[string]any{}
			for k, v := range valid {
				value[k] = v
			}
			value[test.key] = test.value
			if _, err := macValidateNotaryLog(encode(value), id, hash, "payload.zip", files); err == nil || strings.Contains(err.Error(), "PRIVATE_DIAGNOSTIC") {
				t.Fatal("invalid log accepted or diagnostics exposed")
			}
		})
	}
}
func TestMacNotaryWaitTimeoutNeverResubmits(t *testing.T) {
	root := t.TempDir()
	archive := filepath.Join(root, "payload.zip")
	os.WriteFile(archive, []byte("archive"), 0600)
	submits, waits, logs := 0, 0, 0
	run := func(root, tool string, args ...string) ([]byte, error) {
		joined := strings.Join(args, " ")
		if !strings.Contains(joined, "--keychain-profile opensocrates-notary-ci --keychain /owned/keychain") {
			t.Fatal("owned credentials omitted")
		}
		switch args[1] {
		case "submit":
			submits++
			if !strings.Contains(joined, "--no-wait") {
				t.Fatal("submission not separated from wait")
			}
			return []byte(`{"id":"00000000-0000-0000-0000-000000000001"}`), nil
		case "wait":
			waits++
			return nil, errors.New("private tool path")
		case "log":
			logs++
			return nil, nil
		}
		t.Fatal("unexpected command")
		return nil, nil
	}
	_, err := macNotaryAccept(root, archive, "opensocrates-notary-ci", "/owned/keychain", nil, run)
	if err == nil || err.Error() != "release_notarization_wait_incomplete" || submits != 1 || waits != 1 || logs != 0 {
		t.Fatal("wait retried submission or leaked error")
	}
}
func TestMacNotaryRejectedNeverRetrievesOrAcceptsLog(t *testing.T) {
	root := t.TempDir()
	archive := filepath.Join(root, "payload.zip")
	os.WriteFile(archive, []byte("archive"), 0600)
	calls := 0
	run := func(root, tool string, args ...string) ([]byte, error) {
		calls++
		if args[1] == "submit" {
			return []byte(`{"id":"00000000-0000-0000-0000-000000000001"}`), nil
		}
		if args[1] == "wait" {
			return []byte(`{"id":"00000000-0000-0000-0000-000000000001","status":"Invalid"}`), nil
		}
		t.Fatal("rejected submission continued")
		return nil, nil
	}
	if _, err := macNotaryAccept(root, archive, "profile", "", nil, run); err == nil || calls != 2 {
		t.Fatal("Apple rejection accepted")
	}
}
func TestMacInstallerNotaryContainerPreservesActualInstallerBytes(t *testing.T) {
	root := t.TempDir()
	installer := filepath.Join(root, "opensocrates-v1.6.0-darwin-arm64")
	data := []byte("actual signed installer")
	os.WriteFile(installer, data, 0755)
	private := t.TempDir()
	archive, err := macInstallerWrapper(installer, private)
	if err != nil {
		t.Fatal(err)
	}
	reader, err := zip.OpenReader(archive)
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	if len(reader.File) != 1 || reader.File[0].Name != filepath.Base(installer) || reader.File[0].Mode().Perm() != 0755 {
		t.Fatal("installer container inventory mismatch")
	}
	stream, _ := reader.File[0].Open()
	got, _ := io.ReadAll(stream)
	stream.Close()
	if !bytes.Equal(got, data) {
		t.Fatal("notarization changed standalone installer")
	}
	entries, _ := os.ReadDir(root)
	if len(entries) != 1 {
		t.Fatal("transient container entered source")
	}
}
func TestMacAcceptedOnlineVerificationRetriesOnlyChecksWithPinnedPolicy(t *testing.T) {
	paths := []string{"a", "b", "c", "d", "e"}
	calls := 0
	policy := update.DefaultNativeTrust()
	verify := func(ctx context.Context, path string, p platform.NativeTrustPolicy) error {
		calls++
		if p != policy {
			t.Fatal("online retry relaxed trust")
		}
		if calls == 1 {
			return errors.New("ticket unavailable")
		}
		return nil
	}
	if err := macVerifyAcceptedPaths(context.Background(), paths, policy, verify, 2, 0); err != nil || calls != 6 {
		t.Fatal("accepted online checks did not retry boundedly")
	}
	calls = 0
	verify = func(context.Context, string, platform.NativeTrustPolicy) error {
		calls++
		return errors.New("unavailable")
	}
	if err := macVerifyAcceptedPaths(context.Background(), paths, policy, verify, 2, 0); err == nil || calls != 2 {
		t.Fatal("online verification failed open")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := macVerifyAcceptedPaths(ctx, paths, policy, verify, 2, time.Second); err == nil {
		t.Fatal("cancelled verification passed")
	}
}
func TestMacCandidateQualificationCannotCreateProductionReceiptsFromLocalFlags(t *testing.T) {
	root := t.TempDir()
	t.Setenv("GITHUB_ACTIONS", "")
	t.Setenv("OPENSOCRATES_EXPECTED_SOURCE_SHA", strings.Repeat("a", 40))
	t.Setenv("OPENSOCRATES_RELEASE_APPROVED", "true")
	if err := RunMacOSSigningQualification(root, []string{"--commit", strings.Repeat("a", 40)}); err == nil {
		t.Fatal("candidate qualification allowed local masquerade")
	}
	if _, err := os.Stat(filepath.Join(root, "build")); !os.IsNotExist(err) {
		t.Fatal("unauthorized invocation produced evidence")
	}
	if err := RunMacOSSigningQualification(root, []string{"--commit", strings.Repeat("b", 40)}); err == nil {
		t.Fatal("expected commit overridden")
	}
}
func TestPublicationBoundedOutputDoesNotRetainUnboundedDiagnostic(t *testing.T) {
	writer := &publicationBoundedOutput{limit: 8}
	writer.Write([]byte("abcd"))
	if _, err := writer.Write([]byte("oversized")); err == nil || !writer.exceeded || string(writer.data) != "abcd" {
		t.Fatal("unbounded diagnostic retained")
	}
}
