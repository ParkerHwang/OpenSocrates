package devtools

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math/big"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"github.com/sigstore/sigstore/pkg/signature"
	"github.com/theupdateframework/go-tuf/v2/metadata"
)

const networkFixtureHost = "network-update.opensocrates.invalid"
const networkFixtureTarget = "stable/darwin-arm64/opensocrates.archive"
const networkFixturePayload = "isolated network qualification candidate\n"

// This explicit development gate never obtains production signing handles or
// contacts a public service. It exercises production Transport and Repository
// code with local-only dialing and an ephemeral, explicitly trusted TLS root.
func networkUpdateAcceptance() (report map[string]any, err error) {
	report = map[string]any{
		"target": nativeAcceptanceTarget(), "runtime_os": runtime.GOOS, "runtime_arch": runtime.GOARCH,
		"evidence_scope": "isolated_development_trust_https", "production_signing": false,
		"public_transport": false, "self_update": false, "live_host_claimed": false,
		"live_host_delivery_claimed": false, "native_package_verified": false,
		"running_executable_replacement_verified": false, "signed_target_fixture": "darwin-arm64",
		"production_transport_code_exercised": true, "synthetic_owned_payload": true,
		"tls_trust": "ephemeral_certificate_explicit_root_pool", "dialing": "fixture_host_443_to_loopback_only",
		"private_keys_persisted": false, "host_registration_changed": false, "scheduler_changed": false,
	}
	commit, sourceErr := gitOutput(".", "rev-parse", "HEAD")
	commit = strings.TrimSpace(commit)
	if sourceErr != nil || !legacyAcceptanceCommitValid(commit) {
		return report, errors.New("qualification source unavailable")
	}
	report["source_git_commit"] = commit
	root, err := platform.MkdirTemp("", "opensocrates-network-acceptance-")
	if err != nil {
		return report, errors.New("disposable network fixture unavailable")
	}
	defer func() {
		cleanup := os.RemoveAll(root)
		_, stat := os.Lstat(root)
		clean := cleanup == nil && os.IsNotExist(stat)
		report["disposable_cleanup_verified"] = clean
		if !clean {
			report["pass"] = false
			if err == nil {
				err = errors.New("disposable network fixture cleanup incomplete")
			}
		}
	}()
	fixture, err := newNetworkUpdateFixture()
	if err != nil {
		return report, errors.New("development HTTPS fixture unavailable")
	}
	defer fixture.close()
	report["pass"] = false
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	target := filepath.Join(root, "owned-payload")
	if err = platform.AtomicWrite(target, []byte("isolated previous payload\n"), 0600); err != nil {
		return report, err
	}
	before, err := lifecycle.Inspect(target)
	if err != nil {
		return report, err
	}
	transactions := lifecycle.Engine{StateDir: filepath.Join(root, "lifecycle")}
	var committed lifecycle.Journal
	applyCalls := 0
	apply := func(ctx context.Context, candidate update.Candidate) (update.ApplyResult, error) {
		source, parseErr := prepareNetworkFixtureCandidate(candidate, filepath.Join(root, "extracted-"+lifecycle.NewID()))
		if parseErr != nil {
			return update.ApplyResult{}, parseErr
		}
		applyCalls++
		committed, parseErr = transactions.Execute(ctx, lifecycle.Plan{Action: "update", Host: "codex", Scope: "global", Version: candidate.Release.Version, Mutations: []lifecycle.Mutation{{Target: target, Source: source, Expected: &before}}})
		return update.ApplyResult{Version: candidate.Release.Version}, parseErr
	}
	engine := func(state string) update.Engine {
		return update.Engine{StateDir: filepath.Join(root, state), Version: "1.6.0", OS: "darwin", Arch: "arm64", Repository: fixture.repository(ctx), Apply: apply}
	}
	if err = fixture.publish(2, false, false); err != nil {
		return report, err
	}
	receipt, err := engine("accepted-update").Run(ctx, false, true)
	if err != nil || receipt.Result != "updated" || committed.Stage != "committed" || applyCalls != 1 {
		return report, errors.New("HTTPS update lifecycle activation failed")
	}
	activated, err := platform.ReadFile(target, 4096)
	if err != nil || string(activated) != networkFixturePayload {
		return report, errors.New("activated fixture payload differs")
	}
	report["signed_metadata_and_archive_https_verified"] = true
	report["bounded_archive_parsed_and_payload_hash_verified"] = true
	report["shared_lifecycle_activation_verified"] = true
	recovered, err := transactions.Recover(ctx, committed.ID)
	restored, inspectErr := lifecycle.Inspect(target)
	if err != nil || inspectErr != nil || recovered.Stage != "rolled-back" || !lifecycle.Equal(before, restored) {
		return report, errors.New("HTTPS update verified rollback failed")
	}
	report["shared_lifecycle_rollback_verified"] = true
	checkRejected := func(state, name string) error {
		result, rejected := engine(state).Run(ctx, false, true)
		actual, inspectErr := lifecycle.Inspect(target)
		if rejected == nil || result.Result != "unavailable" || inspectErr != nil || !lifecycle.Equal(before, actual) || applyCalls != 1 {
			return fmt.Errorf("%s rejection or payload preservation failed", name)
		}
		report[name+"_rejected_payload_preserved"] = true
		return nil
	}
	if err = fixture.publish(2, false, true); err != nil {
		return report, err
	}
	if err = checkRejected("tampered-update", "tampered_archive"); err != nil {
		return report, err
	}
	if err = fixture.publish(3, true, false); err != nil {
		return report, err
	}
	if err = checkRejected("expired-update", "signed_expired_metadata"); err != nil {
		return report, err
	}
	if err = fixture.publish(1, false, false); err != nil {
		return report, err
	}
	if err = checkRejected("accepted-update", "metadata_rollback"); err != nil {
		return report, err
	}
	metadataRequests, archiveRequests := fixture.requestCounts()
	if metadataRequests < 3 || archiveRequests < 2 {
		return report, errors.New("HTTPS fixture exchange evidence incomplete")
	}
	report["https_metadata_requests"] = metadataRequests
	report["https_archive_requests"] = archiveRequests
	fixture.close()
	if err = checkRejected("offline-update", "offline"); err != nil {
		return report, err
	}
	report["pass"] = true
	return report, nil
}

type networkFixtureManifest struct {
	Schema  string `json:"schema"`
	Version string `json:"version"`
	SHA256  string `json:"sha256"`
}

func networkFixtureArchive() ([]byte, error) {
	hash := sha256.Sum256([]byte(networkFixturePayload))
	manifest, err := json.Marshal(networkFixtureManifest{Schema: "opensocrates.network-fixture/1", Version: "1.6.1", SHA256: hex.EncodeToString(hash[:])})
	if err != nil {
		return nil, err
	}
	var buffer bytes.Buffer
	w := zip.NewWriter(&buffer)
	for _, file := range []struct {
		name string
		data []byte
	}{{"fixture-manifest.json", manifest}, {"fixture-payload.txt", []byte(networkFixturePayload)}} {
		header := &zip.FileHeader{Name: file.name, Method: zip.Deflate}
		header.SetMode(0600)
		entry, err := w.CreateHeader(header)
		if err != nil {
			return nil, err
		}
		if _, err = entry.Write(file.data); err != nil {
			return nil, err
		}
	}
	if err := w.Close(); err != nil {
		return nil, err
	}
	return buffer.Bytes(), nil
}

// Synthetic payload validation is deliberately separate from native package
// qualification. The production archive scanner enforces names, types, modes,
// counts and byte limits before any lifecycle target can be changed.
func prepareNetworkFixtureCandidate(candidate update.Candidate, destination string) (string, error) {
	limits := platform.ArchiveLimits{MaxEntries: 2, MaxFileBytes: 4096, MaxTotalBytes: 8192}
	entries, err := platform.VerifyArchive(candidate.Archive, limits)
	if err != nil || len(entries) != 2 {
		return "", errors.New("invalid network fixture archive")
	}
	names := map[string]bool{"fixture-manifest.json": true, "fixture-payload.txt": true}
	for _, entry := range entries {
		if entry.Directory || !names[entry.Name] {
			return "", errors.New("invalid network fixture inventory")
		}
		delete(names, entry.Name)
	}
	if err = platform.ExtractArchive(candidate.Archive, destination, limits); err != nil {
		return "", err
	}
	b, err := platform.ReadFile(filepath.Join(destination, "fixture-manifest.json"), 4096)
	if err != nil {
		return "", err
	}
	var manifest networkFixtureManifest
	decoder := json.NewDecoder(bytes.NewReader(b))
	decoder.DisallowUnknownFields()
	var extra any
	if decoder.Decode(&manifest) != nil || decoder.Decode(&extra) != io.EOF || manifest.Schema != "opensocrates.network-fixture/1" || manifest.Version != candidate.Release.Version {
		return "", errors.New("invalid network fixture manifest")
	}
	payload := filepath.Join(destination, "fixture-payload.txt")
	hash, err := platform.SHA256File(payload, 4096)
	if err != nil || hash != manifest.SHA256 {
		return "", errors.New("network fixture payload hash differs")
	}
	return payload, nil
}

type networkUpdateFixture struct {
	server           *httptest.Server
	client           *http.Client
	root, archive    []byte
	signers          map[string][]signature.Signer
	mu               sync.Mutex
	files            map[string][]byte
	metadataRequests int
	archiveRequests  int
}

func newNetworkUpdateFixture() (*networkUpdateFixture, error) {
	f := &networkUpdateFixture{signers: map[string][]signature.Signer{}}
	root := metadata.Root(time.Now().Add(180 * 24 * time.Hour))
	root.Signed.Roles[metadata.ROOT].Threshold = 2
	for _, role := range []string{metadata.ROOT, metadata.ROOT, metadata.TARGETS, metadata.SNAPSHOT, metadata.TIMESTAMP} {
		_, private, err := ed25519.GenerateKey(rand.Reader)
		if err != nil {
			return nil, err
		}
		signer, err := signature.LoadSigner(private, crypto.Hash(0))
		if err != nil {
			return nil, err
		}
		public, err := signer.PublicKey()
		if err != nil {
			return nil, err
		}
		key, err := metadata.KeyFromPublicKey(public)
		if err != nil {
			return nil, err
		}
		if err = root.Signed.AddKey(key, role); err != nil {
			return nil, err
		}
		f.signers[role] = append(f.signers[role], signer)
	}
	for _, signer := range f.signers[metadata.ROOT] {
		if _, err := root.Sign(signer); err != nil {
			return nil, err
		}
	}
	var err error
	f.root, err = root.ToBytes(false)
	if err != nil {
		return nil, err
	}
	f.archive, err = networkFixtureArchive()
	if err != nil {
		return nil, err
	}
	public, private, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, err
	}
	now := time.Now()
	serial, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
	if err != nil {
		return nil, err
	}
	certificate := &x509.Certificate{SerialNumber: serial, DNSNames: []string{networkFixtureHost}, NotBefore: now.Add(-time.Minute), NotAfter: now.Add(time.Hour), KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}, BasicConstraintsValid: true}
	der, err := x509.CreateCertificate(rand.Reader, certificate, certificate, public, private)
	if err != nil {
		return nil, err
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		return nil, err
	}
	pool := x509.NewCertPool()
	pool.AddCert(cert)
	f.server = httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		defer f.mu.Unlock()
		if r.Method != http.MethodGet || r.Host != networkFixtureHost {
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		data, exists := f.files[r.URL.Path]
		if !exists {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if r.URL.Path == "/targets/v1.6.1/fixture.zip" {
			f.archiveRequests++
		} else {
			f.metadataRequests++
		}
		w.Header().Set("Content-Length", strconv.Itoa(len(data)))
		_, _ = w.Write(data)
	}))
	f.server.Config.ErrorLog = log.New(io.Discard, "", 0)
	f.server.TLS = &tls.Config{Certificates: []tls.Certificate{{Certificate: [][]byte{der}, PrivateKey: private}}, MinVersion: tls.VersionTLS12}
	f.server.StartTLS()
	address := f.server.Listener.Addr().String()
	transport := &http.Transport{TLSClientConfig: &tls.Config{RootCAs: pool, MinVersion: tls.VersionTLS12}, DialContext: func(ctx context.Context, network, destination string) (net.Conn, error) {
		if destination != networkFixtureHost+":443" {
			return nil, errors.New("fixture only allows its isolated HTTPS endpoint")
		}
		return (&net.Dialer{Timeout: 2 * time.Second}).DialContext(ctx, network, address)
	}}
	f.client = &http.Client{Transport: transport, Timeout: 3 * time.Second}
	return f, nil
}

func (f *networkUpdateFixture) repository(ctx context.Context) update.Repository {
	base := "https://" + networkFixtureHost
	return update.Repository{BootstrapRoot: f.root, MetadataURL: base + "/metadata/", TargetsURL: base + "/targets/", AllowedHosts: []string{networkFixtureHost}, Fetcher: &update.Transport{Context: ctx, AllowedHosts: []string{networkFixtureHost}, Client: f.client}}
}

func (f *networkUpdateFixture) publish(version int64, expired, tampered bool) error {
	now := time.Now()
	release := update.Release{Schema: "opensocrates.release/1.0.0", Version: "1.6.1", ContentRevision: "synthetic-network-fixture", Channel: "stable", OS: "darwin", Arch: "arm64", MinimumManager: "1.6.0", DataSchema: 1, Profiles: []string{"codex"}, PackagePath: "v1.6.1/fixture.zip"}
	files, err := update.SignRelease(update.SigningInputs{Root: f.root, Signers: f.signers, TargetsVersion: version, SnapshotVersion: version, TimestampVersion: version, ExpiresTargets: now.Add(time.Hour), ExpiresSnapshot: now.Add(time.Hour), ExpiresTimestamp: now.Add(time.Hour), Targets: map[string]update.SignedArchive{networkFixtureTarget: {Release: release, Data: f.archive}}}, now)
	if err != nil {
		return err
	}
	if expired {
		timestamp, err := metadata.Timestamp().FromBytes(files["timestamp.json"])
		if err != nil {
			return err
		}
		timestamp.Signed.Expires = now.Add(-time.Hour)
		timestamp.Signatures = nil
		for _, signer := range f.signers[metadata.TIMESTAMP] {
			if _, err := timestamp.Sign(signer); err != nil {
				return err
			}
		}
		if files["timestamp.json"], err = timestamp.ToBytes(false); err != nil {
			return err
		}
	}
	served := map[string][]byte{}
	for name, data := range files {
		served["/metadata/"+name] = data
	}
	served["/metadata/"+strconv.FormatInt(version, 10)+".targets.json"] = files["targets.json"]
	served["/metadata/"+strconv.FormatInt(version, 10)+".snapshot.json"] = files["snapshot.json"]
	archive := append([]byte(nil), f.archive...)
	if tampered {
		archive[len(archive)/2] ^= 1
	}
	served["/targets/v1.6.1/fixture.zip"] = archive
	f.mu.Lock()
	f.files = served
	f.mu.Unlock()
	return nil
}

func (f *networkUpdateFixture) requestCounts() (int, int) {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.metadataRequests, f.archiveRequests
}

func (f *networkUpdateFixture) close() {
	f.client.CloseIdleConnections()
	f.server.Close()
}
