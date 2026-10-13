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
	"encoding/pem"
	"math/big"
	"os"
	"path/filepath"
	"runtime"
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
	for _, host := range []struct{ goos, goarch string }{
		{"darwin", "amd64"}, {"windows", "amd64"}, {"windows", "arm64"},
		{"linux", "amd64"}, {"linux", "arm64"},
	} {
		if err := macSigningHostedEnvironment(host.goos, host.goarch); err == nil {
			t.Fatalf("foreign native host accepted: %s/%s", host.goos, host.goarch)
		}
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

// The production entrypoint checks the native platform before reading signing
// credentials or invoking Apple tools, even when Actions runner fields claim Mac.
func TestMacSigningPrepareRejectsForeignNativeHost(t *testing.T) {
	if runtime.GOOS == "darwin" && runtime.GOARCH == "arm64" {
		t.Skip("native Mac ARM64; foreign platforms are covered by the portable gate table")
	}
	for name, value := range map[string]string{
		"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": publicationRepository,
		"OPENSOCRATES_RUNNER_ENVIRONMENT": "github-hosted", "OPENSOCRATES_RUNNER_ARCH": "ARM64",
		"RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
	} {
		t.Setenv(name, value)
	}
	err := RunMacOSSigningSetup(t.TempDir(), "macos-signing-prepare", []string{"--purpose", "qualification"})
	if err == nil || err.Error() != "mac_signing_hosted_arm64_required" {
		t.Fatalf("foreign native prepare reached signing setup: %v", err)
	}
}
