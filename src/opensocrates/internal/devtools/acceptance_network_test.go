package devtools

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"github.com/theupdateframework/go-tuf/v2/metadata"
)

func TestNetworkUpdateAcceptanceReceipt(t *testing.T) {
	report, err := networkUpdateAcceptance()
	if err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"pass", "production_transport_code_exercised", "signed_metadata_and_archive_https_verified", "bounded_archive_parsed_and_payload_hash_verified", "shared_lifecycle_activation_verified", "shared_lifecycle_rollback_verified", "tampered_archive_rejected_payload_preserved", "signed_expired_metadata_rejected_payload_preserved", "metadata_rollback_rejected_payload_preserved", "offline_rejected_payload_preserved", "disposable_cleanup_verified"} {
		if report[name] != true {
			t.Fatalf("missing qualification: %s", name)
		}
	}
	if report["evidence_scope"] != "isolated_development_trust_https" {
		t.Fatal("evidence scope differs")
	}
	for _, name := range []string{"production_signing", "public_transport", "self_update", "live_host_claimed", "private_keys_persisted", "host_registration_changed", "scheduler_changed"} {
		if report[name] != false {
			t.Fatalf("scope overclaimed: %s", name)
		}
	}
	b, err := json.Marshal(report)
	if err != nil || bytes.Contains(b, []byte("https://")) || bytes.Contains(b, []byte("BEGIN PRIVATE")) || bytes.Contains(b, []byte(networkFixturePayload)) {
		t.Fatal("receipt contains fixture content or endpoint")
	}
}

func TestNetworkFixtureExpiredTimestampIsAuthentic(t *testing.T) {
	f, err := newNetworkUpdateFixture()
	if err != nil {
		t.Fatal(err)
	}
	defer f.close()
	if err = f.publish(1, true, false); err != nil {
		t.Fatal(err)
	}
	root, err := metadata.Root().FromBytes(f.root)
	if err != nil {
		t.Fatal(err)
	}
	timestamp, err := metadata.Timestamp().FromBytes(f.files["/metadata/timestamp.json"])
	if err != nil || root.VerifyDelegate(metadata.TIMESTAMP, timestamp) != nil || !timestamp.Signed.Expires.Before(time.Now()) {
		t.Fatal("expiry scenario must reject an authentic expired timestamp")
	}
}

func TestNetworkFixtureUsesVerifiedTLSAndTransportURLPolicy(t *testing.T) {
	f, err := newNetworkUpdateFixture()
	if err != nil {
		t.Fatal(err)
	}
	defer f.close()
	if err = f.publish(1, false, false); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	transport := f.repository(ctx).Fetcher
	for _, address := range []string{"http://" + networkFixtureHost + "/metadata/root.json", "https://foreign.invalid/metadata/root.json", "https://" + networkFixtureHost + ":444/metadata/root.json", "https://user@" + networkFixtureHost + "/metadata/root.json"} {
		if _, err := transport.DownloadFile(address, 4096, 0); err == nil {
			t.Fatal("fixture bypassed production URL policy")
		}
	}
	clone := f.client.Transport.(*http.Transport).Clone()
	clone.TLSClientConfig.RootCAs = x509.NewCertPool()
	defer clone.CloseIdleConnections()
	untrusted := &update.Transport{Context: ctx, AllowedHosts: []string{networkFixtureHost}, Client: &http.Client{Transport: clone, Timeout: 3 * time.Second}}
	if _, err = untrusted.DownloadFile("https://"+networkFixtureHost+"/metadata/root.json", 4096, 0); err == nil {
		t.Fatal("untrusted TLS certificate accepted")
	}
	metadataRequests, archiveRequests := f.requestCounts()
	if metadataRequests != 0 || archiveRequests != 0 {
		t.Fatal("rejected transport attempt reached fixture HTTP handler")
	}
	if _, err = transport.DownloadFile("https://"+networkFixtureHost+"/metadata/root.json", 1, 0); err == nil {
		t.Fatal("HTTPS response exceeded explicit download bound")
	}
}

func TestSignedMalformedNetworkArchivesNeverActivate(t *testing.T) {
	for _, name := range []string{"payload_hash", "payload_limit", "entry_limit", "path_traversal", "release_version"} {
		t.Run(name, func(t *testing.T) {
			root, err := platform.MkdirTemp(t.TempDir(), "network-invalid-")
			if err != nil {
				t.Fatal(err)
			}
			f, err := newNetworkUpdateFixture()
			if err != nil {
				t.Fatal(err)
			}
			defer f.close()
			payload := []byte(networkFixturePayload)
			hash := sha256.Sum256(payload)
			manifest := networkFixtureManifest{Schema: "opensocrates.network-fixture/1", Version: "1.6.1", SHA256: hex.EncodeToString(hash[:])}
			files := map[string][]byte{}
			switch name {
			case "payload_hash":
				payload[0] ^= 1
			case "payload_limit":
				payload = []byte(strings.Repeat("a", 4097))
			case "entry_limit":
				files["extra.txt"] = []byte("foreign")
			case "path_traversal":
				files["../foreign.txt"] = []byte("foreign")
			case "release_version":
				manifest.Version = "1.6.2"
			}
			files["fixture-manifest.json"], err = json.Marshal(manifest)
			if err != nil {
				t.Fatal(err)
			}
			files["fixture-payload.txt"] = payload
			var buffer bytes.Buffer
			writer := zip.NewWriter(&buffer)
			for filename, data := range files {
				header := &zip.FileHeader{Name: filename, Method: zip.Deflate}
				header.SetMode(0600)
				file, err := writer.CreateHeader(header)
				if err != nil {
					t.Fatal(err)
				}
				if _, err = file.Write(data); err != nil {
					t.Fatal(err)
				}
			}
			if err = writer.Close(); err != nil {
				t.Fatal(err)
			}
			f.archive = buffer.Bytes()
			if err = f.publish(1, false, false); err != nil {
				t.Fatal(err)
			}
			target := filepath.Join(root, "owned-payload")
			if err = platform.AtomicWrite(target, []byte("preserved previous payload"), 0600); err != nil {
				t.Fatal(err)
			}
			before, err := lifecycle.Inspect(target)
			if err != nil {
				t.Fatal(err)
			}
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			activated := false
			engine := update.Engine{StateDir: filepath.Join(root, "update"), Version: "1.6.0", OS: "darwin", Arch: "arm64", Repository: f.repository(ctx), Apply: func(ctx context.Context, c update.Candidate) (update.ApplyResult, error) {
				source, err := prepareNetworkFixtureCandidate(c, filepath.Join(root, "extracted"))
				if err != nil {
					return update.ApplyResult{}, err
				}
				transactions := lifecycle.Engine{StateDir: filepath.Join(root, "lifecycle")}
				_, err = transactions.Execute(ctx, lifecycle.Plan{Action: "update", Host: "codex", Scope: "global", Mutations: []lifecycle.Mutation{{Target: target, Source: source, Expected: &before}}})
				activated = err == nil
				return update.ApplyResult{}, err
			}}
			receipt, err := engine.Run(ctx, false, true)
			after, inspectErr := lifecycle.Inspect(target)
			if err == nil || receipt.Result != "failed" || activated || inspectErr != nil || !lifecycle.Equal(before, after) {
				t.Fatal("signed malformed archive activated or previous payload changed")
			}
		})
	}
}
