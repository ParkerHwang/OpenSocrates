package update

import (
	"bytes"
	"context"
	"crypto"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"encoding/xml"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/sigstore/sigstore/pkg/signature"
	"github.com/theupdateframework/go-tuf/v2/metadata"
	"io"
	"net/http"
	"net/http/httptest"
	"os/user"
	"path/filepath"
	"reflect"
	"runtime"
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

func TestWindowsTaskSchemaOrderAndPolicy(t *testing.T) {
	const manager = `C:\Users\예시 사용자\OpenSocrates\opensocrates.exe`
	const sid = "S-1-5-21-12345-67890-13579-1001"
	document, err := WindowsTask(manager, sid)
	if err != nil {
		t.Fatal(err)
	}
	// Microsoft's schema extends triggerBaseType with logonTriggerType.
	// The base sequence must finish before derived UserId and Delay appear:
	// https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema
	decoder := xml.NewDecoder(bytes.NewReader(document))
	depth, triggerDepth := 0, -1
	var children []string
	for {
		token, err := decoder.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		switch element := token.(type) {
		case xml.StartElement:
			depth++
			if element.Name.Local == "LogonTrigger" {
				triggerDepth = depth
			}
			if triggerDepth >= 0 && depth == triggerDepth+1 {
				children = append(children, element.Name.Local)
			}
		case xml.EndElement:
			if element.Name.Local == "LogonTrigger" {
				triggerDepth = -1
			}
			depth--
		}
	}
	if !reflect.DeepEqual(children, []string{"Enabled", "Repetition", "UserId", "Delay"}) {
		t.Fatalf("LogonTrigger violates base-before-derived schema order: %v", children)
	}
	var task struct {
		Trigger struct {
			Enabled    bool `xml:"Enabled"`
			Repetition struct {
				Interval string `xml:"Interval"`
				Stop     bool   `xml:"StopAtDurationEnd"`
			} `xml:"Repetition"`
			UserID string `xml:"UserId"`
			Delay  string `xml:"Delay"`
		} `xml:"Triggers>LogonTrigger"`
		Principal struct {
			UserID    string `xml:"UserId"`
			LogonType string `xml:"LogonType"`
			RunLevel  string `xml:"RunLevel"`
		} `xml:"Principals>Principal"`
		Instances string `xml:"Settings>MultipleInstancesPolicy"`
		Action    struct {
			Command   string `xml:"Command"`
			Arguments string `xml:"Arguments"`
		} `xml:"Actions>Exec"`
	}
	if err := xml.Unmarshal(document, &task); err != nil {
		t.Fatal(err)
	}
	if !task.Trigger.Enabled || task.Trigger.Repetition.Interval != "PT24H" || task.Trigger.Repetition.Stop || task.Trigger.Delay != "PT5M" || task.Trigger.UserID != sid {
		t.Fatalf("unexpected stable login policy: %+v", task.Trigger)
	}
	if task.Principal.UserID != sid || task.Principal.LogonType != "InteractiveToken" || task.Principal.RunLevel != "LeastPrivilege" || task.Instances != "IgnoreNew" {
		t.Fatalf("unexpected user privilege or concurrency policy: %+v", task.Principal)
	}
	if task.Action.Command != manager || task.Action.Arguments != "auto-update run --scheduled" || !ownedTask(document, manager) {
		t.Fatal("scheduler command or ownership policy changed")
	}
	engine := Engine{StateDir: filepath.Join(t.TempDir(), "state"), Version: "1.6.0", OS: "windows", Arch: "amd64"}
	policy, err := engine.Policy()
	if err != nil || policy.Enabled || policy.Channel != "stable" {
		t.Fatal("automatic updates must remain stable-channel opt-in")
	}
}

func TestEncodeTaskImportXMLUnicodeRoundTrip(t *testing.T) {
	const manager = `C:\Users\예시 사용자 🧠\OpenSocrates\opensocrates.exe`
	canonical, err := WindowsTask(manager, "S-1-5-21-12345-67890-13579-1001")
	if err != nil {
		t.Fatal(err)
	}
	importXML, err := EncodeTaskImportXML(canonical)
	if err != nil {
		t.Fatal(err)
	}
	if len(importXML)%2 != 0 || len(importXML) < 2 || importXML[0] != 0xff || importXML[1] != 0xfe {
		t.Fatal("task import requires a UTF-16LE BOM and complete code units")
	}
	decoded := decodeWindows(importXML)
	if !bytes.HasPrefix(decoded, []byte(taskUTF16Declaration)) || !bytes.Contains(decoded, []byte(manager)) {
		t.Fatal("declaration or Unicode path corrupted at native import boundary")
	}
	normalized, err := normalizeTaskXML(importXML)
	if err != nil || !bytes.Equal(normalized, canonical) || !ownedTask(normalized, manager) {
		t.Fatal("import/query round trip changed canonical ownership document")
	}
	if !bytes.HasPrefix(canonical, []byte(taskUTF8Declaration)) {
		t.Fatal("import transformation mutated canonical recovery state")
	}
}

func TestEncodeTaskImportXMLRejectsMalformedInput(t *testing.T) {
	canonical, err := WindowsTask(`C:\Users\example\OpenSocrates\opensocrates.exe`, "S-1-5-21-12345-67890-13579-1001")
	if err != nil {
		t.Fatal(err)
	}
	invalidUTF8 := append(append([]byte(nil), canonical...), 0xff)
	for name, input := range map[string][]byte{
		"invalid_utf8":        invalidUTF8,
		"utf8_bom":            append([]byte{0xef, 0xbb, 0xbf}, canonical...),
		"wrong_declaration":   bytes.Replace(canonical, []byte(taskUTF8Declaration), []byte(taskUTF16Declaration), 1),
		"missing_declaration": canonical[len(taskUTF8Declaration):],
		"truncated_xml":       canonical[:len(canonical)-8],
		"wrong_root":          []byte(taskUTF8Declaration + `<Other xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"/>`),
		"external_directive":  bytes.Replace(canonical, []byte("\n<Task"), []byte("\n<!DOCTYPE Task SYSTEM \"https://unexpected.example/task.dtd\">\n<Task"), 1),
		"oversized":           append(append([]byte(nil), canonical...), bytes.Repeat([]byte(" "), maxTaskXMLBytes)...),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := EncodeTaskImportXML(input); err == nil {
				t.Fatal("malformed task import accepted")
			}
		})
	}
	importXML, err := EncodeTaskImportXML(canonical)
	if err != nil {
		t.Fatal(err)
	}
	for name, input := range map[string][]byte{
		"odd_utf16_length":      append(append([]byte(nil), importXML...), 0),
		"unpaired_surrogate":    append(append([]byte(nil), importXML...), 0x00, 0xd8),
		"unexpected_endian_bom": append([]byte{0xfe, 0xff}, importXML[2:]...),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := normalizeTaskXML(input); err == nil {
				t.Fatal("malformed query encoding accepted")
			}
		})
	}
}

func TestWindowsTaskRecoveryRecognizesOnlyKnownAfterSemantics(t *testing.T) {
	const manager = `C:\Users\예시 사용자 🧠\OpenSocrates\opensocrates.exe`
	generated, err := WindowsTask(manager, "S-1-5-21-12345-67890-13579-1001")
	if err != nil {
		t.Fatal(err)
	}
	// Task Scheduler exports XML with indentation, rearranged xs:all children,
	// its registration URI and documented default settings made explicit.
	exported := bytes.Replace(generated, []byte("<Settings>"), []byte(`<Settings><AllowHardTerminate>true</AllowHardTerminate><AllowStartOnDemand>true</AllowStartOnDemand><RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><WakeToRun>false</WakeToRun><Hidden>false</Hidden><Priority>7</Priority><RunOnlyIfIdle>false</RunOnlyIfIdle><IdleSettings><Duration>PT10M</Duration><WaitTimeout>PT1H</WaitTimeout><StopOnIdleEnd>true</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>`), 1)
	exported = bytes.Replace(exported, []byte("</RegistrationInfo>"), []byte(`<URI>\`+TaskName+`</URI></RegistrationInfo>`), 1)
	exported = bytes.ReplaceAll(exported, []byte("><"), []byte(">\r\n    <"))
	importXML, err := EncodeTaskImportXML(exported)
	if err != nil {
		t.Fatal(err)
	}
	if !TaskDocumentMatches(importXML, generated, manager) {
		t.Fatal("known after-state changed only by encoding, formatting and schema defaults was rejected")
	}
	normalized, err := normalizeTaskXML(importXML)
	if err != nil {
		t.Fatal(err)
	}
	adapter := NewSchedulerAdapter("windows", t.TempDir(), manager, t.TempDir())
	// These are the same conflict guards called by Replace after interrupted
	// activation, with generated After becoming Before during rollback.
	if !adapter.knownDocument(string(normalized), string(generated)) {
		t.Fatal("interrupted registration cannot roll back its known after-state")
	}
	if !adapter.knownDocument(string(normalized), string(normalized)) {
		t.Fatal("captured exact before-state not recognized")
	}
	differentlyFormattedCapture := bytes.ReplaceAll(normalized, []byte("\r\n    "), nil)
	if !adapter.knownDocument(string(differentlyFormattedCapture), string(normalized)) {
		t.Fatal("captured before-state values changed only by formatting were rejected")
	}
	metadataCapture := bytes.Replace(normalized, []byte("</RegistrationInfo>"), []byte("<Author>original author</Author><Date>2026-10-12T00:00:00Z</Date></RegistrationInfo>"), 1)
	changedAuthor := bytes.Replace(metadataCapture, []byte("original author"), []byte("foreign author"), 1)
	if adapter.knownDocument(string(changedAuthor), string(metadataCapture)) {
		t.Fatal("captured before-state author modification accepted")
	}
	removedDefault := bytes.Replace(normalized, []byte("<WakeToRun>false</WakeToRun>"), nil, 1)
	if adapter.knownDocument(string(removedDefault), string(normalized)) {
		t.Fatal("captured before-state unexpectedly received generated-after default allowances")
	}
	equivalentDuration := bytes.Replace(generated, []byte("<Interval>PT24H</Interval>"), []byte("<Interval>P1D</Interval>"), 1)
	if !TaskDocumentMatches(equivalentDuration, generated, manager) || !ownedTask(equivalentDuration, manager) {
		t.Fatal("equivalent schema day/hour interval was not recognized")
	}
}

func TestWindowsTaskRecoveryRejectsModifiedForeignDefinitions(t *testing.T) {
	const manager = `C:\Users\example\OpenSocrates\opensocrates.exe`
	generated, err := WindowsTask(manager, "S-1-5-21-12345-67890-13579-1001")
	if err != nil {
		t.Fatal(err)
	}
	changes := map[string][]byte{
		"changed_default":          bytes.Replace(generated, []byte("<Settings>"), []byte("<Settings><WakeToRun>true</WakeToRun>"), 1),
		"changed_explicit_setting": bytes.Replace(generated, []byte("<StartWhenAvailable>true"), []byte("<StartWhenAvailable>false"), 1),
		"changed_execution_limit":  bytes.Replace(generated, []byte("<ExecutionTimeLimit>PT10M"), []byte("<ExecutionTimeLimit>PT72H"), 1),
		"extra_setting":            bytes.Replace(generated, []byte("<Settings>"), []byte("<Settings><UnknownSetting>false</UnknownSetting>"), 1),
		"extra_trigger":            bytes.Replace(generated, []byte("</Triggers>"), []byte("<TimeTrigger><Enabled>true</Enabled></TimeTrigger></Triggers>"), 1),
		"changed_trigger":          bytes.Replace(generated, []byte("<Delay>PT5M"), []byte("<Delay>PT6M"), 1),
		"extra_exec_action":        bytes.Replace(generated, []byte("</Actions>"), []byte("<Exec><Command>foreign.exe</Command></Exec></Actions>"), 1),
		"changed_exec_directory":   bytes.Replace(generated, []byte("</Exec>"), []byte(`<WorkingDirectory>C:\foreign</WorkingDirectory></Exec>`), 1),
		"changed_principal":        bytes.Replace(generated, []byte("LeastPrivilege"), []byte("HighestAvailable"), 1),
		"extra_principal_property": bytes.Replace(generated, []byte("</Principal>"), []byte("<ProcessTokenSidType>None</ProcessTokenSidType></Principal>"), 1),
		"foreign_uri":              bytes.Replace(generated, []byte("</RegistrationInfo>"), []byte(`<URI>\foreign-task</URI></RegistrationInfo>`), 1),
	}
	for name, document := range changes {
		t.Run(name, func(t *testing.T) {
			if TaskDocumentMatches(document, generated, manager) {
				t.Fatal("modified foreign task matched generated after-state")
			}
		})
	}
}

func TestWindowsObservedExportDefaultsOwnershipAndRecovery(t *testing.T) {
	const manager = `C:\Users\예시 사용자 🧠\OpenSocrates\opensocrates.exe`
	const sid = "S-1-5-21-12345-67890-13579-1001"
	generated, err := WindowsTask(manager, sid)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(generated, []byte("<UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>")) {
		t.Fatal("Task 1.4 engine choice must be explicit")
	}
	// This projection follows the actual Windows 11 export observed after native
	// UTF-16 import: absent default-valued RunLevel/Enabled/AllowStartOnDemand,
	// P1D interval, exact task URI, and its two exported IdleSettings defaults.
	queried := bytes.ReplaceAll(generated, []byte("<RunLevel>LeastPrivilege</RunLevel>"), nil)
	queried = bytes.ReplaceAll(queried, []byte("<Enabled>true</Enabled>"), nil)
	queried = bytes.ReplaceAll(queried, []byte("<StopAtDurationEnd>false</StopAtDurationEnd>"), nil)
	queried = bytes.ReplaceAll(queried, []byte("<Interval>PT24H</Interval>"), []byte("<Interval>P1D</Interval>"))
	queried = bytes.Replace(queried, []byte("</Settings>"), []byte("<IdleSettings><StopOnIdleEnd>true</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings></Settings>"), 1)
	queried = bytes.Replace(queried, []byte("</RegistrationInfo>"), []byte(`<URI>\`+TaskName+`</URI></RegistrationInfo>`), 1)
	queried = bytes.ReplaceAll(queried, []byte("><"), []byte(">\r\n  <"))
	if !ownedTask(queried, manager) {
		t.Fatal("Inspect's ownership gate rejected absent least-privilege/enabled defaults")
	}
	wire, err := EncodeTaskImportXML(queried)
	if err != nil {
		t.Fatal(err)
	}
	normalized, err := normalizeTaskXML(wire)
	if err != nil || !TaskDocumentMatches(normalized, generated, manager) {
		t.Fatal("actual exported default subset does not match generated after-state")
	}
	restoreWire, err := EncodeTaskImportXML(normalized)
	if err != nil {
		t.Fatal(err)
	}
	restored, err := normalizeTaskXML(restoreWire)
	if err != nil || !TaskDocumentMatches(restored, normalized, manager) || !ownedTask(restored, manager) {
		t.Fatal("captured before-state import/query restoration lost ownership or fields")
	}
	for name, field := range map[string]string{
		"higher_privilege": "<RunLevel>HighestAvailable</RunLevel>",
		"empty_privilege":  "<RunLevel></RunLevel>",
	} {
		t.Run(name, func(t *testing.T) {
			foreign := bytes.Replace(queried, []byte("</Principal>"), []byte(field+"</Principal>"), 1)
			if ownedTask(foreign, manager) || TaskDocumentMatches(foreign, generated, manager) {
				t.Fatal("explicit elevated or empty privilege was treated as an absent default")
			}
		})
	}
	for name, field := range map[string]string{
		"disabled_settings":      "<Enabled>false</Enabled>",
		"empty_enabled_settings": "<Enabled></Enabled>",
		"disallowed_demand":      "<AllowStartOnDemand>false</AllowStartOnDemand>",
	} {
		t.Run(name, func(t *testing.T) {
			foreign := bytes.Replace(queried, []byte("</Settings>"), []byte(field+"</Settings>"), 1)
			if ownedTask(foreign, manager) || TaskDocumentMatches(foreign, generated, manager) {
				t.Fatal("explicit disabled or empty setting was treated as an absent default")
			}
		})
	}
	disabledTrigger := bytes.Replace(queried, []byte("<LogonTrigger>"), []byte("<LogonTrigger><Enabled>false</Enabled>"), 1)
	if ownedTask(disabledTrigger, manager) || TaskDocumentMatches(disabledTrigger, generated, manager) {
		t.Fatal("disabled trigger accepted")
	}
	changedEngine := bytes.Replace(queried, []byte("<UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>"), []byte("<UseUnifiedSchedulingEngine>false</UseUnifiedSchedulingEngine>"), 1)
	if TaskDocumentMatches(changedEngine, generated, manager) || TaskDocumentMatches(changedEngine, normalized, manager) {
		t.Fatal("explicit engine change ignored during activation or restoration")
	}
	foreignSetting := bytes.Replace(queried, []byte("</Settings>"), []byte("<ForeignSetting>ignored</ForeignSetting></Settings>"), 1)
	if TaskDocumentMatches(foreignSetting, generated, manager) || TaskDocumentMatches(foreignSetting, normalized, manager) {
		t.Fatal("foreign setting ignored")
	}
}

func TestWindowsTaskResolvedTriggerAliasAndForeignRejection(t *testing.T) {
	const manager = `C:\Users\예시 사용자\OpenSocrates\opensocrates.exe`
	const sid = "S-1-5-21-12345-67890-13579-1001"
	const alias = `MACHINE\예시 사용자`
	generated, err := WindowsTask(manager, sid)
	if err != nil {
		t.Fatal(err)
	}
	exported := bytes.Replace(generated, []byte("<UserId>"+sid+"</UserId><Delay>"), []byte("<UserId>"+alias+"</UserId><Delay>"), 1)
	resolver := func(identity string) (string, error) {
		switch identity {
		case alias:
			return sid, nil
		case `OTHERDOMAIN\예시 사용자`:
			return "S-1-5-21-12345-67890-13579-2002", nil
		default:
			return "", closed("verification", "scheduler_identity")
		}
	}
	if !ownedTaskWithResolver(exported, manager, resolver) || !TaskDocumentMatchesWithResolver(exported, generated, manager, resolver) {
		t.Fatal("OS-resolved current-user alias not accepted by ownership/generated-after recovery")
	}
	if !TaskUserIdentityMatchesWithResolver(alias, sid, resolver) || TaskUserIdentityMatchesWithResolver(`OTHERDOMAIN\예시 사용자`, sid, resolver) {
		t.Fatal("domain-qualified accounts were guessed rather than resolved")
	}
	// Captured before-state preserves the exact account spelling. A restored
	// query may be reformatted, but its identity must not silently be rewritten.
	formatted := bytes.ReplaceAll(exported, []byte("><"), []byte(">\r\n  <"))
	if !TaskDocumentMatchesWithResolver(formatted, exported, manager, resolver) {
		t.Fatal("captured alias field failed representation-only restoration")
	}
	if TaskDocumentMatchesWithResolver(generated, exported, manager, resolver) {
		t.Fatal("captured before-state alias was silently replaced with SID")
	}
	for name, identity := range map[string]string{"foreign_domain": `OTHERDOMAIN\예시 사용자`, "unknown": "unknown-account", "foreign_sid": "S-1-5-21-12345-67890-13579-2002", "empty": ""} {
		t.Run(name, func(t *testing.T) {
			foreign := bytes.Replace(exported, []byte("<UserId>"+alias+"</UserId><Delay>"), []byte("<UserId>"+identity+"</UserId><Delay>"), 1)
			if ownedTaskWithResolver(foreign, manager, resolver) || TaskDocumentMatchesWithResolver(foreign, generated, manager, resolver) {
				t.Fatal("unresolved or foreign trigger identity accepted")
			}
		})
	}
	tooLong := strings.Repeat("x", 257)
	for _, identity := range []string{"", tooLong, "name\x00extra", "name\nextra"} {
		if TaskUserIdentityMatchesWithResolver(identity, sid, func(string) (string, error) { return sid, nil }) {
			t.Fatal("malformed identity passed resolver boundary")
		}
	}
	if TaskUserIdentityMatchesWithResolver(alias, sid, func(string) (string, error) { return sid, closed("verification", "scheduler_identity") }) {
		t.Fatal("lookup failure accepted despite SID result")
	}
}

func TestWindowsNativeCurrentAccountTriggerAlias(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("native Windows account-to-SID API required")
	}
	current, err := user.Current()
	if err != nil || !windowsSID(current.Uid) || current.Username == "" {
		t.Fatal("current Windows account identity unavailable")
	}
	resolved, err := ResolveAccountSID(current.Username)
	if err != nil || resolved != current.Uid || !TaskUserIdentityMatches(current.Username, current.Uid) {
		t.Fatal("Windows LookupAccountName alias did not resolve to current SID")
	}
	manager := filepath.Join(t.TempDir(), "opensocrates.exe")
	generated, err := WindowsTask(manager, current.Uid)
	if err != nil {
		t.Fatal(err)
	}
	query := bytes.Replace(generated, []byte("<UserId>"+current.Uid+"</UserId><Delay>"), []byte("<UserId>"+escape(current.Username)+"</UserId><Delay>"), 1)
	if !ownedTask(query, manager) || !TaskDocumentMatches(query, generated, manager) {
		t.Fatal("native exported current-account trigger alias rejected")
	}
	if TaskDocumentMatches(generated, query, manager) {
		t.Fatal("captured native before-state alias was rewritten")
	}
	if TaskUserIdentityMatches(current.Username, "S-1-5-21-1-2-3-4294967294") {
		t.Fatal("current alias incorrectly matched a foreign SID")
	}
}
