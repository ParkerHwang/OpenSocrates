package update

import (
	"bytes"
	"context"
	"crypto"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/sigstore/sigstore/pkg/signature"
	"github.com/theupdateframework/go-tuf/v2/metadata"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func fixtureRoot(t *testing.T) ([]byte, map[string][]signature.Signer) {
	t.Helper()
	root := metadata.Root(time.Now().Add(365 * 24 * time.Hour))
	root.Signed.Roles[metadata.ROOT].Threshold = 2
	signers := map[string][]signature.Signer{}
	for _, role := range []string{metadata.ROOT, metadata.ROOT, metadata.TARGETS, metadata.SNAPSHOT, metadata.TIMESTAMP} {
		_, private, e := ed25519.GenerateKey(rand.Reader)
		if e != nil {
			t.Fatal(e)
		}
		s, e := signature.LoadSigner(private, crypto.Hash(0))
		if e != nil {
			t.Fatal(e)
		}
		p, e := s.PublicKey()
		if e != nil {
			t.Fatal(e)
		}
		key, e := metadata.KeyFromPublicKey(p)
		if e != nil {
			t.Fatal(e)
		}
		if e = root.Signed.AddKey(key, role); e != nil {
			t.Fatal(e)
		}
		signers[role] = append(signers[role], s)
	}
	for _, s := range signers[metadata.ROOT] {
		if _, e := root.Sign(s); e != nil {
			t.Fatal(e)
		}
	}
	b, e := root.ToBytes(false)
	if e != nil {
		t.Fatal(e)
	}
	return b, signers
}
func fixtureRelease(t *testing.T, version string, n int64) ([]byte, map[string][]byte, []byte) {
	t.Helper()
	root, signers := fixtureRoot(t)
	archive := []byte("fixture archive payload")
	rel := Release{Schema: "opensocrates.release/1.0.0", Version: version, ContentRevision: "1.5.0-frozen", Channel: "stable", OS: "darwin", Arch: "arm64", MinimumManager: "1.6.0", DataSchema: 1, Profiles: []string{"codex"}, PackagePath: "v" + version + "/native.zip"}
	now := time.Now()
	out, e := SignRelease(SigningInputs{Root: root, Signers: signers, TargetsVersion: n, SnapshotVersion: n, TimestampVersion: n, ExpiresTargets: now.Add(24 * time.Hour), ExpiresSnapshot: now.Add(24 * time.Hour), ExpiresTimestamp: now.Add(time.Hour), Targets: map[string]SignedArchive{"stable/darwin-arm64/opensocrates.archive": {Release: rel, Data: archive}}}, now)
	if e != nil {
		t.Fatal(e)
	}
	return root, out, archive
}

type memoryFetcher struct{ files map[string][]byte }

func (f *memoryFetcher) DownloadFile(url string, max int64, _ time.Duration) ([]byte, error) {
	b, ok := f.files[url]
	if !ok {
		return nil, &metadata.ErrDownloadHTTP{StatusCode: 404}
	}
	if int64(len(b)) > max {
		return nil, &metadata.ErrLengthOrHashMismatch{}
	}
	return append([]byte(nil), b...), nil
}
func repositoryFixture(t *testing.T) (Repository, *memoryFetcher, []byte) {
	root, out, archive := fixtureRelease(t, "1.6.1", 1)
	files := map[string][]byte{}
	for name, b := range out {
		files["https://metadata.example/"+name] = b
	}
	files["https://metadata.example/1.targets.json"] = out["targets.json"]
	files["https://metadata.example/1.snapshot.json"] = out["snapshot.json"]
	files["https://assets.example/v1.6.1/native.zip"] = archive
	f := &memoryFetcher{files}
	return Repository{BootstrapRoot: root, MetadataURL: "https://metadata.example/", TargetsURL: "https://assets.example/", Fetcher: f}, f, archive
}
func TestSignedFetchAndDurableTrust(t *testing.T) {
	r, _, archive := repositoryFixture(t)
	state := filepath.Join(t.TempDir(), "trust")
	c, e := r.Fetch(context.Background(), state, "stable/darwin-arm64/opensocrates.archive")
	if e != nil {
		t.Fatal(e)
	}
	b, e := platform.ReadFile(c.Archive, MaxArchiveSize)
	if e != nil || !bytes.Equal(b, archive) {
		t.Fatal("wrong target bytes")
	}
	b, e = platform.ReadFile(filepath.Join(state, "trust.json"), 12<<20)
	if e != nil {
		t.Fatal(e)
	}
	var trust trustState
	if json.Unmarshal(b, &trust) != nil || len(trust.Roles) != 4 {
		t.Fatal("accepted trust not persisted")
	}
}
func TestTamperedTargetDoesNotActivate(t *testing.T) {
	r, f, _ := repositoryFixture(t)
	f.files["https://assets.example/v1.6.1/native.zip"] = []byte("tampered")
	if _, e := r.Fetch(context.Background(), filepath.Join(t.TempDir(), "trust"), "stable/darwin-arm64/opensocrates.archive"); e == nil {
		t.Fatal("tampered target accepted")
	}
}
func TestExpiredMetadataPreservesInstallation(t *testing.T) {
	r, f, _ := repositoryFixture(t)
	b := f.files["https://metadata.example/timestamp.json"]
	var data map[string]any
	_ = json.Unmarshal(b, &data)
	data["signed"].(map[string]any)["expires"] = "2000-01-01T00:00:00Z"
	f.files["https://metadata.example/timestamp.json"], _ = json.Marshal(data)
	if _, e := r.Fetch(context.Background(), filepath.Join(t.TempDir(), "trust"), "stable/darwin-arm64/opensocrates.archive"); e == nil {
		t.Fatal("expired unsigned modification accepted")
	}
}
func TestNoNetworkTrustBootstrap(t *testing.T) {
	r, _, _ := repositoryFixture(t)
	r.BootstrapRoot = []byte("{}")
	if _, e := r.Fetch(context.Background(), filepath.Join(t.TempDir(), "trust"), "stable/darwin-arm64/opensocrates.archive"); e == nil {
		t.Fatal("missing installer root accepted")
	}
	if ValidateProductionRoot([]byte("{}"), time.Now()) == nil {
		t.Fatal("unsigned release enabled")
	}
}
func TestStableCompatibilityPolicy(t *testing.T) {
	base := Release{Schema: "opensocrates.release/1.0.0", Version: "1.7.0", ContentRevision: "frozen", Channel: "stable", OS: "windows", Arch: "amd64", MinimumManager: "1.6.0", DataSchema: 1, Profiles: []string{"codex"}, PackagePath: "v1.7.0/native.zip"}
	for _, tc := range []struct {
		name   string
		alter  func(*Release)
		result string
	}{{"minor", func(*Release) {}, "apply"}, {"major", func(r *Release) { r.Version = "2.0.0" }, "prepare_only"}, {"schema", func(r *Release) { r.DataSchema = 2 }, "prepare_only"}, {"manager", func(r *Release) { r.MinimumManager = "1.7.0" }, "prepare_only"}, {"old", func(r *Release) { r.Version = "1.5.0" }, "current"}} {
		t.Run(tc.name, func(t *testing.T) {
			r := base
			tc.alter(&r)
			got, e := Compatible(r, "1.6.0", "windows", "amd64", true)
			if e != nil || got != tc.result {
				t.Fatalf("%s %v", got, e)
			}
		})
	}
}
func TestSchedulerDocumentsAndOwnership(t *testing.T) {
	manager := filepath.Join(t.TempDir(), "Application Support", "OpenSocrates", "bin", "opensocrates")
	p, e := LaunchAgent(manager)
	if e != nil || !ownedPlist(p, manager) {
		t.Fatal("invalid owned plist")
	}
	if ownedPlist(p, "/other/manager") {
		t.Fatal("foreign executable accepted")
	}
	if strings.Contains(string(p), "npx") {
		t.Fatal("npm dependency retained")
	}
	if _, e = WindowsTask(`C:\Users\예시\OpenSocrates\opensocrates.exe`, "S-1-5-21-1"); e != nil {
		t.Fatal(e)
	}
}
func TestTransportRejectsHTTPAndUnexpectedHosts(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte("unused")) }))
	defer server.Close()
	f := Transport{AllowedHosts: []string{"github.com"}}
	for _, raw := range []string{server.URL, "https://evil.example/file", "https://github.com:444/file", "https://user:secret@github.com/file"} {
		if _, e := f.DownloadFile(raw, 1024, 0); e == nil {
			t.Fatal("unapproved transport accepted")
		}
	}
}
func TestRunDisabledIsOffline(t *testing.T) {
	called := false
	e := Engine{StateDir: filepath.Join(t.TempDir(), "state"), Version: "1.6.0", OS: "darwin", Arch: "arm64", Apply: func(context.Context, Candidate) (ApplyResult, error) { called = true; return ApplyResult{}, nil }}
	r, err := e.Run(context.Background(), true, false)
	if err != nil || r.Result != "disabled" || called {
		t.Fatal("disabled updater attempted network or apply")
	}
}

func TestMetadataRollbackAndFreezeRejected(t *testing.T) {
	root, signers := fixtureRoot(t)
	now := time.Now()
	makeSet := func(n int64, expiry time.Time) map[string][]byte {
		rel := Release{Schema: "opensocrates.release/1.0.0", Version: "1.6.1", ContentRevision: "frozen", Channel: "stable", OS: "darwin", Arch: "arm64", MinimumManager: "1.6.0", DataSchema: 1, Profiles: []string{"codex"}, PackagePath: "v1.6.1/native.zip"}
		out, e := SignRelease(SigningInputs{Root: root, Signers: signers, TargetsVersion: n, SnapshotVersion: n, TimestampVersion: n, ExpiresTargets: now.Add(time.Hour), ExpiresSnapshot: now.Add(time.Hour), ExpiresTimestamp: expiry, Targets: map[string]SignedArchive{"stable/darwin-arm64/opensocrates.archive": {Release: rel, Data: []byte("archive")}}}, now.Add(-2*time.Hour))
		if e != nil {
			t.Fatal(e)
		}
		return out
	}
	install := func(f *memoryFetcher, set map[string][]byte, n string) {
		for name, b := range set {
			f.files["https://metadata.example/"+name] = b
		}
		f.files["https://metadata.example/"+n+".targets.json"] = set["targets.json"]
		f.files["https://metadata.example/"+n+".snapshot.json"] = set["snapshot.json"]
	}
	f := &memoryFetcher{map[string][]byte{"https://assets.example/v1.6.1/native.zip": []byte("archive")}}
	install(f, makeSet(2, now.Add(time.Hour)), "2")
	r := Repository{BootstrapRoot: root, MetadataURL: "https://metadata.example/", TargetsURL: "https://assets.example/", Fetcher: f}
	state := filepath.Join(t.TempDir(), "trust")
	if _, e := r.Fetch(context.Background(), state, "stable/darwin-arm64/opensocrates.archive"); e != nil {
		t.Fatal(e)
	}
	install(f, makeSet(1, now.Add(time.Hour)), "1")
	if _, e := r.Fetch(context.Background(), state, "stable/darwin-arm64/opensocrates.archive"); e == nil {
		t.Fatal("signed timestamp rollback accepted")
	}
	install(f, makeSet(3, now.Add(-time.Hour)), "3")
	if _, e := r.Fetch(context.Background(), state, "stable/darwin-arm64/opensocrates.archive"); e == nil {
		t.Fatal("signed expired metadata accepted")
	}
}
func TestPartialRootAcceptanceSurvivesFailedRefresh(t *testing.T) {
	root, signers := fixtureRoot(t)
	next, e := metadata.Root().FromBytes(root)
	if e != nil {
		t.Fatal(e)
	}
	next.Signed.Version = 2
	next.ClearSignatures()
	for _, s := range signers[metadata.ROOT] {
		if _, e = next.Sign(s); e != nil {
			t.Fatal(e)
		}
	}
	b, e := next.ToBytes(false)
	if e != nil {
		t.Fatal(e)
	}
	if VerifyRootRotation(root, b) != nil {
		t.Fatal("valid chained root rejected")
	}
	f := &memoryFetcher{map[string][]byte{"https://metadata.example/2.root.json": b}}
	r := Repository{BootstrapRoot: root, MetadataURL: "https://metadata.example/", TargetsURL: "https://assets.example/", Fetcher: f}
	state := filepath.Join(t.TempDir(), "trust")
	if _, e = r.Fetch(context.Background(), state, "stable/darwin-arm64/opensocrates.archive"); e == nil {
		t.Fatal("missing timestamp accepted")
	}
	raw, e := platform.ReadFile(filepath.Join(state, "trust.json"), 12<<20)
	if e != nil {
		t.Fatal(e)
	}
	var trust trustState
	if json.Unmarshal(raw, &trust) != nil {
		t.Fatal("missing trust envelope")
	}
	accepted, e := metadata.Root().FromBytes(trust.Roles["root"])
	if e != nil || accepted.Signed.Version != 2 {
		t.Fatal("accepted root rotation not durable")
	}
	next.Signed.Version = 4
	next.ClearSignatures()
	for _, s := range signers[metadata.ROOT] {
		_, _ = next.Sign(s)
	}
	b, _ = next.ToBytes(false)
	if VerifyRootRotation(root, b) == nil {
		t.Fatal("skipped root versions accepted")
	}
}

func TestSchedulerPartialActivationRollbackRestoresLegacy(t *testing.T) {
	home := t.TempDir()
	manager := filepath.Join(home, "bin", "opensocrates")
	a := NewSchedulerAdapter("darwin", home, manager, filepath.Join(home, "state"))
	legacy := []byte(`<plist version="1.0"><dict><key>Label</key><string>com.opensocrates.auto-update</string><key>ProgramArguments</key><array><string>/owned/bin/npx</string><string>--yes</string><string>opensocrates@latest</string><string>auto-update</string><string>run</string></array></dict></plist>`)
	if e := platform.Mkdir(filepath.Dir(a.Root())); e != nil {
		t.Fatal(e)
	}
	if e := platform.AtomicWrite(a.Root(), legacy, 0600); e != nil {
		t.Fatal(e)
	}
	loaded := true
	failBootstrap := true
	a.Command = func(ctx context.Context, exe string, args ...string) ([]byte, error) {
		switch args[0] {
		case "print":
			if len(args) > 1 && strings.HasSuffix(args[1], "/"+SchedulerLabel) && !loaded {
				return nil, closed("activation", "scheduler")
			}
			return []byte("services = {}"), nil
		case "bootout":
			loaded = false
		case "bootstrap":
			if failBootstrap {
				failBootstrap = false
				return nil, closed("activation", "scheduler")
			}
			loaded = true
		}
		return nil, nil
	}
	change, e := PrepareMigration(context.Background(), a, true)
	if e != nil {
		t.Fatal(e)
	}
	if e = a.Replace(context.Background(), change.Before, change.After); e == nil {
		t.Fatal("bootstrap failure not returned")
	}
	if e = a.Replace(context.Background(), change.After, change.Before); e != nil {
		t.Fatal(e)
	}
	b, e := platform.ReadFile(a.Root(), 1<<20)
	if e != nil || !bytes.Equal(b, legacy) || !loaded {
		t.Fatal("legacy updater registration or document not restored")
	}
	if e = a.Verify(context.Background(), change.Before); e != nil {
		t.Fatal(e)
	}
}
func TestSchedulerRefusesModifiedForeignDocument(t *testing.T) {
	home := t.TempDir()
	manager := filepath.Join(home, "bin", "opensocrates")
	a := NewSchedulerAdapter("darwin", home, manager, filepath.Join(home, "state"))
	if e := platform.Mkdir(filepath.Dir(a.Root())); e != nil {
		t.Fatal(e)
	}
	owned, e := LaunchAgent(manager)
	if e != nil {
		t.Fatal(e)
	}
	if e = platform.AtomicWrite(a.Root(), owned, 0600); e != nil {
		t.Fatal(e)
	}
	a.Command = func(context.Context, string, ...string) ([]byte, error) { return nil, nil }
	change, e := PrepareMigration(context.Background(), a, false)
	if e != nil {
		t.Fatal(e)
	}
	foreign := bytes.ReplaceAll(owned, []byte(manager), []byte("/foreign/manager"))
	if e = platform.AtomicWrite(a.Root(), foreign, 0600); e != nil {
		t.Fatal(e)
	}
	if a.Replace(context.Background(), change.Before, change.After) == nil {
		t.Fatal("foreign scheduler removed")
	}
	b, e := platform.ReadFile(a.Root(), 1<<20)
	if e != nil || !bytes.Equal(b, foreign) {
		t.Fatal("foreign scheduler changed")
	}
}
