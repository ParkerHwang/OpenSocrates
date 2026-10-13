package devtools

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha1"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/asn1"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	"math/big"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func macSigningFixture(t *testing.T) (string, string, []byte, []byte) {
	t.Helper()
	temp, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	for name, value := range map[string]string{"RUNNER_TEMP": temp, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "mac-sign", "OPENSOCRATES_MAC_SIGNING_STATE": "", "OPENSOCRATES_MAC_SIGNING_KEYCHAIN": "", "OPENSOCRATES_MAC_TEAM_ID": "6HM2UD6746", "OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE": macSigningProfile, "OPENSOCRATES_NOTARY_APPLE_ID": "fixture@example.invalid", "OPENSOCRATES_NOTARY_APP_PASSWORD": "fixture-secret-app-password", "OPENSOCRATES_MAC_CERTIFICATE_PASSWORD": "fixture-secret-p12-password", "OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64": base64.StdEncoding.EncodeToString([]byte("fixture-private-p12")), "GITHUB_SHA": strings.Repeat("a", 40)} {
		t.Setenv(name, value)
	}
	env := filepath.Join(temp, "github-env")
	if err = os.WriteFile(env, nil, 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("GITHUB_ENV", env)
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	cert := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "Developer ID Application: Fixture", OrganizationalUnit: []string{"6HM2UD6746"}}, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(time.Hour), KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageCodeSigning}, ExtraExtensions: []pkix.Extension{{Id: asn1.ObjectIdentifier{1, 2, 840, 113635, 100, 6, 1, 13}, Value: []byte{5, 0}}}}
	der, err := x509.CreateCertificate(rand.Reader, cert, cert, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	hash := sha1.Sum(der)
	identity := hex.EncodeToString(hash[:])
	t.Setenv("OPENSOCRATES_MAC_SIGN_IDENTITY", identity)
	identities := []byte("  1) " + strings.ToUpper(identity) + " \"Developer ID Application: Fixture (6HM2UD6746)\"\n     1 valid identities found\n")
	return temp, identity, identities, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
}

type macSigningFake struct {
	t                 *testing.T
	list              []string
	identities, certs []byte
	fail              string
	calls             []string
}

func (f *macSigningFake) run(root, name string, args ...string) ([]byte, error) {
	f.t.Helper()
	f.calls = append(f.calls, name+":"+args[0])
	if args[0] == f.fail {
		return nil, errors.New("mac_signing_private_command_failed")
	}
	switch args[0] {
	case "list-keychains":
		if len(args) > 3 {
			f.list = append([]string{}, args[4:]...)
			return nil, nil
		}
		rows := []string{}
		for _, path := range f.list {
			rows = append(rows, "\""+path+"\"")
		}
		return []byte(strings.Join(rows, "\n")), nil
	case "create-keychain":
		path := args[len(args)-1]
		if err := os.WriteFile(path, []byte("encrypted fixture keychain"), 0600); err != nil {
			f.t.Fatal(err)
		}
		f.list = append([]string{path}, f.list...)
	case "delete-keychain":
		return nil, os.Remove(args[1])
	case "find-identity":
		return f.identities, nil
	case "find-certificate":
		return f.certs, nil
	}
	return nil, nil
}

func TestMacSigningPrepareAndCleanupPreserveExistingKeychains(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	root := filepath.Join(temp, "source")
	os.Mkdir(root, 0700)
	original := []string{"/Users/runner/Library/Keychains/login.keychain-db", "/Library/Keychains/System.keychain"}
	fake := &macSigningFake{t: t, list: append([]string{}, original...), identities: ids, certs: certs}
	if err := macSigningPrepare(root, fake.run); err != nil {
		t.Fatal(err)
	}
	path, err := macSigningOwnedKeychain()
	if err != nil {
		t.Fatal(err)
	}
	if len(fake.list) != 3 || fake.list[0] != path {
		t.Fatal("private keychain not explicitly searched")
	}
	state, err := os.ReadFile(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))
	if err != nil {
		t.Fatal(err)
	}
	for _, secret := range []string{"fixture-secret-app-password", "fixture-secret-p12-password", "fixture-private-p12"} {
		if strings.Contains(string(state), secret) {
			t.Fatal("private state retained credentials")
		}
	}
	if _, err = os.Stat(filepath.Join(filepath.Dir(path), "certificate.p12")); !os.IsNotExist(err) {
		t.Fatal("P12 remained after import")
	}
	if err = macSigningCleanup(root, fake.run); err != nil {
		t.Fatal(err)
	}
	if !macSigningSameList(fake.list, original) {
		t.Fatal("original search list not restored")
	}
	if _, err = os.Stat(filepath.Dir(path)); !os.IsNotExist(err) {
		t.Fatal("private directory remained")
	}
	if err = macSigningCleanup(root, fake.run); err != nil {
		t.Fatal("repeat cleanup failed")
	}
	receipt, err := os.ReadFile(filepath.Join(root, "build/evidence/macos-keychain-cleanup.json"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(receipt), temp) || strings.Contains(string(receipt), "fixture-secret") {
		t.Fatal("cleanup receipt leaked private metadata")
	}
}

func TestMacSigningPartialFailuresRollbackAndDoNotLogSecrets(t *testing.T) {
	for _, stage := range []string{"create-keychain", "import", "set-key-partition-list", "find-identity", "notarytool"} {
		t.Run(stage, func(t *testing.T) {
			temp, _, ids, certs := macSigningFixture(t)
			fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs, fail: stage}
			err := macSigningPrepare(temp, fake.run)
			if err == nil || strings.Contains(err.Error(), "fixture") || strings.Contains(err.Error(), temp) {
				t.Fatalf("unsafe failure: %v", err)
			}
			if !macSigningSameList(fake.list, []string{"/original.keychain-db"}) {
				t.Fatal("failed setup altered existing search list")
			}
			if _, err = os.Stat(filepath.Dir(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))); !os.IsNotExist(err) {
				t.Fatal("failed setup retained private material")
			}
		})
	}
}

func TestMacSigningCleanupPreservesForeignSearchListChanges(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs}
	if err := macSigningPrepare(temp, fake.run); err != nil {
		t.Fatal(err)
	}
	directory := filepath.Dir(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))
	fake.list = append(fake.list, "/foreign.keychain-db")
	err := macSigningCleanup(temp, fake.run)
	if err == nil || err.Error() != "mac_signing_cleanup_foreign_search_list_preserved" {
		t.Fatal("foreign changes not reported")
	}
	if !macSigningSameList(fake.list, []string{"/original.keychain-db", "/foreign.keychain-db"}) {
		t.Fatal("foreign keychain changed")
	}
	if _, err = os.Stat(directory); !os.IsNotExist(err) {
		t.Fatal("foreign search change retained credentials")
	}
}

func TestMacSigningCleanupRejectsForeignStateAndPartialKeychainCannotSign(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs}
	if err := macSigningPrepare(temp, fake.run); err != nil {
		t.Fatal(err)
	}
	statePath := os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE")
	data, _ := os.ReadFile(statePath)
	var state macSigningState
	json.Unmarshal(data, &state)
	state.Prepared = false
	changed, _ := json.Marshal(state)
	os.WriteFile(statePath, changed, 0600)
	if _, err := macSigningOwnedKeychain(); err == nil {
		t.Fatal("partial preparation accepted")
	}
	state.RunID = "999"
	changed, _ = json.Marshal(state)
	os.WriteFile(statePath, changed, 0600)
	before := len(fake.calls)
	if err := macSigningCleanup(temp, fake.run); err == nil || len(fake.calls) != before {
		t.Fatal("foreign marker authorized cleanup")
	}
	os.WriteFile(statePath, data, 0600)
	if err := macSigningCleanup(temp, fake.run); err != nil {
		t.Fatal(err)
	}
}

func TestMacSigningRejectsWrongIdentityCertificateTeamAndInvalidP12(t *testing.T) {
	temp, identity, ids, certs := macSigningFixture(t)
	if err := macSigningValidateCertificate(ids, certs, identity, "6HM2UD6746"); err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		ids, certs     []byte
		identity, team string
	}{
		{ids, certs, strings.Repeat("0", 40), "6HM2UD6746"},
		{ids, certs, identity, "OTHERTEAM1"},
		{append(ids, ids...), certs, identity, "6HM2UD6746"},
		{ids, []byte("not a certificate"), identity, "6HM2UD6746"},
		{[]byte(strings.Replace(string(ids), "1 valid identities", "11 valid identities", 1)), certs, identity, "6HM2UD6746"},
	} {
		if err := macSigningValidateCertificate(test.ids, test.certs, test.identity, test.team); err == nil {
			t.Fatal("foreign certificate identity accepted")
		}
	}
	for _, encoded := range []string{"invalid!", "", strings.Repeat("A", base64.StdEncoding.EncodedLen(macSigningMaxP12)+1)} {
		t.Setenv("OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64", encoded)
		calls := 0
		err := macSigningPrepare(temp, func(string, string, ...string) ([]byte, error) { calls++; return nil, nil })
		if err == nil || calls != 0 {
			t.Fatal("invalid P12 reached private OS tools")
		}
	}
}

func TestMacSigningHostedGateAndChildEnvironment(t *testing.T) {
	for name, value := range map[string]string{"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": publicationRepository, "OPENSOCRATES_RUNNER_ENVIRONMENT": "github-hosted", "OPENSOCRATES_RUNNER_ARCH": "ARM64", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64"} {
		t.Setenv(name, value)
	}
	if err := macSigningHostedEnvironment("darwin", "arm64"); err != nil {
		t.Fatal(err)
	}
	if err := macSigningHostedEnvironment("darwin", "amd64"); err == nil {
		t.Fatal("Intel accepted")
	}
	for _, name := range []string{"OPENSOCRATES_RUNNER_ENVIRONMENT", "OPENSOCRATES_RUNNER_ARCH", "GITHUB_REPOSITORY", "GITHUB_ACTIONS"} {
		previous := os.Getenv(name)
		t.Setenv(name, "foreign")
		if err := macSigningHostedEnvironment("darwin", "arm64"); err == nil {
			t.Fatal("foreign runner accepted")
		}
		t.Setenv(name, previous)
	}
	t.Setenv("OPENSOCRATES_NOTARY_APP_PASSWORD", "fixture-notary-secret")
	t.Setenv("GH_TOKEN", "fixture-github-secret")
	t.Setenv("OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64", "fixture-key-secret")
	environment := strings.Join(macSigningChildEnvironment(), "\n")
	if strings.Contains(environment, "fixture-") || strings.Contains(environment, "GH_TOKEN") || strings.Contains(environment, "OPENSOCRATES_") {
		t.Fatal("private commands inherited credentials")
	}
	var output macSigningBoundedOutput
	if _, err := output.Write(make([]byte, 2*1024*1024)); err != nil {
		t.Fatal(err)
	}
	if _, err := output.Write([]byte("extra")); err == nil || !output.overflow {
		t.Fatal("private output not bounded")
	}
	if _, err := macSigningPrivateExternal(".", "/foreign/tool", "secret"); err == nil || strings.Contains(err.Error(), "secret") {
		t.Fatal("unapproved command accepted")
	}
}

func TestMacSigningCleanupStillDeletesPrivateFilesWhenSearchInspectionFails(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs}
	if err := macSigningPrepare(temp, fake.run); err != nil {
		t.Fatal(err)
	}
	directory := filepath.Dir(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))
	fake.fail = "list-keychains"
	for _, name := range []string{"GITHUB_REF", "GITHUB_SHA", "OPENSOCRATES_NOTARY_APP_PASSWORD", "OPENSOCRATES_MAC_CERTIFICATE_PASSWORD", "OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64", "OPENSOCRATES_MAC_SIGNING_KEYCHAIN"} {
		t.Setenv(name, "")
	}
	err := macSigningCleanup(temp, fake.run)
	if err == nil || err.Error() != "mac_signing_cleanup_search_list_failed" {
		t.Fatal("search-list failure hidden")
	}
	if _, err = os.Stat(directory); !os.IsNotExist(err) {
		t.Fatal("cancelled job retained credentials")
	}
}
