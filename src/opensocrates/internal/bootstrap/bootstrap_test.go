package bootstrap

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/management"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

// The test executable itself is a native fixture manager, avoiding shell scripts
// and dependence on a user's development toolchain during forwarding tests.
func TestMain(m *testing.M) {
	if os.Getenv("OPENSOCRATES_BOOTSTRAP_TEST_CHILD") == "1" {
		exe, _ := os.Executable()
		fmt.Fprintln(os.Stdout, filepath.Base(filepath.Dir(filepath.Dir(exe))))
		fmt.Fprintln(os.Stdout, strings.Join(os.Args[1:], "|"))
		fmt.Fprintln(os.Stdout, os.Getenv(ParentPIDEnv))
		if len(os.Args) > 1 && os.Args[1] == "exit7" {
			os.Exit(7)
		}
		if len(os.Args) > 1 && os.Args[1] == "decision" {
			io.Copy(os.Stdout, os.Stdin)
		}
		os.Exit(0)
	}
	os.Exit(m.Run())
}

func put(t *testing.T, path string, data []byte, mode os.FileMode) {
	t.Helper()
	if err := platform.Mkdir(filepath.Dir(path)); err != nil {
		t.Fatal(err)
	}
	if err := platform.AtomicWrite(path, data, mode); err != nil {
		t.Fatal(err)
	}
}

func putJSON(t *testing.T, path string, value any) {
	t.Helper()
	data, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	put(t, path, data, 0600)
}

func privateFixtureDir(t *testing.T) string {
	t.Helper()
	// Go's test temp root may inherit an Administrators owner on Windows. Create
	// a new current-user private child rather than changing that foreign root.
	dir := filepath.Join(t.TempDir(), "private")
	if err := platform.Mkdir(dir); err != nil {
		t.Fatal(err)
	}
	return dir
}

func fixtureBundle(t *testing.T, dir, version, goos, goarch string, binary []byte) string {
	t.Helper()
	id := version + "-" + platformTarget(goos, goarch) + "-fixture"
	root := filepath.Join(dir, "bundles", id)
	name := filepath.Base(managerPath(dir, goos))
	put(t, filepath.Join(root, "bin", name), binary, 0755)
	put(t, filepath.Join(root, "bin", "opensocrates-update-helper.exe"), []byte("native-helper-"+version), 0755)
	put(t, filepath.Join(root, "content.json"), []byte(`{"unicode":"한글😀","precision":9007199254740993}`), 0644)
	inventory, err := lifecycle.Inspect(root)
	if err != nil {
		t.Fatal(err)
	}
	manifest := transport.Manifest{Schema: transport.BundleSchema, ProductVersion: version, ContentRevision: "3", Target: platformTarget(goos, goarch), Files: []transport.File{}}
	for _, entry := range inventory.Entries {
		if !entry.Directory {
			manifest.Files = append(manifest.Files, transport.File{Path: entry.Path, SHA256: entry.SHA256, Mode: entry.Mode, Size: entry.Size})
		}
	}
	putJSON(t, filepath.Join(root, "bundle-manifest.json"), manifest)
	return id
}

func writeActive(t *testing.T, dir, id, version, goos, goarch string, stable lifecycle.Snapshot) {
	t.Helper()
	putJSON(t, filepath.Join(dir, "active.json"), activeReference{Schema: "opensocrates.active-bundle/1.0.0", Bundle: id, Version: version, Target: platformTarget(goos, goarch)})
	putJSON(t, filepath.Join(dir, "native-state.json"), management.State{
		Schema: management.StateSchema, UpdateOwner: "native", ManagerVersion: version,
		Installations: map[string]management.Installation{"manager": {
			Host: "manager", Version: "1.6.0", Bundle: id,
			Targets: map[string]lifecycle.Snapshot{managerPath(dir, goos): stable},
		}},
	})
}

func executableBytes(t *testing.T) []byte {
	t.Helper()
	exe, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(exe)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func TestForwardVersionPinArgumentsAndExit(t *testing.T) {
	dir := privateFixtureDir(t)
	binary := executableBytes(t)
	stable := managerPath(dir, runtime.GOOS)
	put(t, stable, binary, 0755)
	snapshot, err := lifecycle.Inspect(stable)
	if err != nil {
		t.Fatal(err)
	}
	first := fixtureBundle(t, dir, "1.6.0", runtime.GOOS, runtime.GOARCH, binary)
	writeActive(t, dir, first, "1.6.0", runtime.GOOS, runtime.GOARCH, snapshot)
	bootstrap := &Bootstrap{StateDir: dir, Executable: stable, Environment: append(os.Environ(), "OPENSOCRATES_BOOTSTRAP_TEST_CHILD=1")}
	var output, diagnostics bytes.Buffer
	handled, code := bootstrap.Forward([]string{"exit7", "한글😀", "argument with spaces"}, strings.NewReader(""), &output, &diagnostics)
	if !handled || code != 7 || !strings.Contains(output.String(), first+"\nexit7|한글😀|argument with spaces\n") {
		t.Fatalf("forward: %v/%d %q %q", handled, code, output.String(), diagnostics.String())
	}
	if strings.TrimSpace(strings.Split(output.String(), "\n")[2]) == "" {
		t.Fatal("stable parent PID not propagated")
	}
	second := fixtureBundle(t, dir, "1.6.1", runtime.GOOS, runtime.GOARCH, binary)
	writeActive(t, dir, second, "1.6.1", runtime.GOOS, runtime.GOARCH, snapshot)
	output.Reset()
	if handled, code = bootstrap.Forward([]string{"decision", "--stream"}, strings.NewReader("retained stream\n"), &output, &diagnostics); !handled || code != 0 || !strings.HasPrefix(output.String(), first+"\n") || !strings.Contains(output.String(), "retained stream") {
		t.Fatalf("process pin: %v/%d %q", handled, code, output.String())
	}
	output.Reset()
	nextProcess := &Bootstrap{StateDir: dir, Executable: stable, Environment: bootstrap.Environment}
	if handled, code = nextProcess.Forward([]string{"version"}, strings.NewReader(""), &output, &diagnostics); !handled || code != 0 || !strings.HasPrefix(output.String(), second+"\n") {
		t.Fatalf("next process: %v/%d %q", handled, code, output.String())
	}
}

func TestForwardRejectsBundleModificationAndKeepsHooksFailOpen(t *testing.T) {
	dir := privateFixtureDir(t)
	binary := executableBytes(t)
	stable := managerPath(dir, runtime.GOOS)
	put(t, stable, binary, 0755)
	snapshot, _ := lifecycle.Inspect(stable)
	id := fixtureBundle(t, dir, "1.6.0", runtime.GOOS, runtime.GOARCH, binary)
	writeActive(t, dir, id, "1.6.0", runtime.GOOS, runtime.GOARCH, snapshot)
	put(t, filepath.Join(dir, "bundles", id, "content.json"), []byte("modified unrelated package content"), 0644)
	var output, diagnostics bytes.Buffer
	b := &Bootstrap{StateDir: dir, Executable: stable}
	if handled, code := b.Forward([]string{"version"}, strings.NewReader(""), &output, &diagnostics); !handled || code == 0 || output.Len() != 0 {
		t.Fatalf("modified bundle executed: %v/%d %q", handled, code, output.String())
	}
	if handled, code := b.Forward([]string{"hook", "observe"}, strings.NewReader(""), &output, &diagnostics); !handled || code != 0 {
		t.Fatal("bootstrap verification must leave hooks fail open")
	}
	if handled, _ := (&Bootstrap{StateDir: dir, Executable: filepath.Join(dir, "extracted", "opensocrates")}).Forward([]string{"version"}, nil, &output, &diagnostics); handled {
		t.Fatal("extracted source incorrectly intercepted")
	}
}

func TestForwardRejectsModifiedStableManager(t *testing.T) {
	dir := privateFixtureDir(t)
	binary := executableBytes(t)
	stable := managerPath(dir, runtime.GOOS)
	put(t, stable, binary, 0755)
	snapshot, err := lifecycle.Inspect(stable)
	if err != nil {
		t.Fatal(err)
	}
	id := fixtureBundle(t, dir, "1.6.0", runtime.GOOS, runtime.GOARCH, binary)
	writeActive(t, dir, id, "1.6.0", runtime.GOOS, runtime.GOARCH, snapshot)
	foreign := []byte("modified stable executable")
	put(t, stable, foreign, 0755)
	var output, diagnostics bytes.Buffer
	b := &Bootstrap{StateDir: dir, Executable: stable}
	if handled, code := b.Forward([]string{"version"}, strings.NewReader(""), &output, &diagnostics); !handled || code == 0 || output.Len() != 0 {
		t.Fatal("foreign stable manager forwarded")
	}
	actual, err := os.ReadFile(stable)
	if err != nil || !bytes.Equal(actual, foreign) {
		t.Fatal("foreign stable bytes changed", err)
	}
}

func activationFixture(t *testing.T) (*Activator, string, lifecycle.Snapshot, lifecycle.Snapshot) {
	t.Helper()
	dir := privateFixtureDir(t)
	stable := managerPath(dir, "windows")
	put(t, stable, []byte("old native manager"), 0755)
	before, err := lifecycle.Inspect(stable)
	if err != nil {
		t.Fatal(err)
	}
	id := fixtureBundle(t, dir, "1.6.1", "windows", "amd64", []byte("new native manager"))
	after, err := lifecycle.Inspect(filepath.Join(dir, "bundles", id, "bin", "opensocrates.exe"))
	if err != nil {
		t.Fatal(err)
	}
	writeActive(t, dir, id, "1.6.1", "windows", "amd64", before)
	putJSON(t, filepath.Join(dir, "manager-pending.json"), management.ManagerReplacement{Schema: "opensocrates.manager-replacement/1.0.0", Bundle: id, Source: "bin/opensocrates.exe", Before: before, After: after})
	return &Activator{StateDir: dir, GOOS: "windows", GOARCH: "amd64", WaitParent: func(context.Context, int, string) error { return nil }}, stable, before, after
}

func TestManagerActivationTransaction(t *testing.T) {
	a, stable, before, after := activationFixture(t)
	if err := a.Activate(context.Background(), 123); err != nil {
		t.Fatal(err)
	}
	actual, err := lifecycle.Inspect(stable)
	if err != nil || !lifecycle.Equal(actual, after) {
		t.Fatal("manager not replaced", err)
	}
	state, err := management.ReadState(a.StateDir)
	if err != nil || state.Installations["manager"].Version != "1.6.1" || !lifecycle.Equal(state.Installations["manager"].Targets[stable], after) {
		t.Fatal("manager state not committed", err)
	}
	if _, err := os.Lstat(filepath.Join(a.StateDir, "manager-pending.json")); !os.IsNotExist(err) {
		t.Fatal("pending manager not removed", err)
	}
	journals, err := os.ReadDir(filepath.Join(a.StateDir, "transactions"))
	if err != nil || len(journals) != 1 {
		t.Fatal("durable manager journal missing", err)
	}
	data, err := os.ReadFile(filepath.Join(a.StateDir, "transactions", journals[0].Name()))
	var journal lifecycle.Journal
	if err != nil || json.Unmarshal(data, &journal) != nil || journal.Stage != "committed" {
		t.Fatal("manager transaction not committed", err)
	}
	backup, err := lifecycle.Inspect(journal.Files[0].Backup)
	if err != nil || !lifecycle.Equal(backup, before) {
		t.Fatal("verified previous manager backup missing", err)
	}
	if err := a.Activate(context.Background(), 123); err != nil {
		t.Fatal("activation not idempotent", err)
	}
}

func TestInterruptedManagerActivationRecoversBeforeRetry(t *testing.T) {
	a, stable, _, after := activationFixture(t)
	interruptAfterManagerActivation(t, a)
	if err := a.Activate(context.Background(), 123); err != nil {
		t.Fatal("recover-and-retry failed", err)
	}
	actual, err := lifecycle.Inspect(stable)
	if err != nil || !lifecycle.Equal(actual, after) {
		t.Fatal("recovered manager not verified", err)
	}
}

func interruptAfterManagerActivation(t *testing.T, a *Activator) lifecycle.Journal {
	t.Helper()
	engine := &lifecycle.Engine{StateDir: a.StateDir}
	a.Engine = engine
	engine.Fault = func(stage string) error {
		if stage != "applying" {
			return nil
		}
		entries, err := os.ReadDir(filepath.Join(a.StateDir, "transactions"))
		if err != nil || len(entries) == 0 {
			return nil
		}
		data, _ := os.ReadFile(filepath.Join(a.StateDir, "transactions", entries[0].Name()))
		var journal lifecycle.Journal
		if json.Unmarshal(data, &journal) == nil && journal.Files[0].Phase == "applied" {
			panic("simulated process loss")
		}
		return nil
	}
	interrupted := false
	func() {
		defer func() {
			if recover() != nil {
				interrupted = true
			}
		}()
		a.Activate(context.Background(), 123)
	}()
	if !interrupted {
		t.Fatal("fixture did not interrupt activated manager")
	}
	engine.Fault = nil
	journals, err := engine.Pending()
	if err != nil || len(journals) != 1 {
		t.Fatal("interrupted activation journal missing", err)
	}
	return journals[0]
}

func TestInterruptedManagerActivationPreservesModifiedBackup(t *testing.T) {
	a, stable, _, after := activationFixture(t)
	journal := interruptAfterManagerActivation(t, a)
	backup := journal.Files[0].Backup
	foreign := []byte("modified foreign recovery bytes")
	put(t, backup, foreign, 0755)
	if err := a.Activate(context.Background(), 123); err == nil {
		t.Fatal("modified backup accepted for rollback")
	}
	actual, err := os.ReadFile(backup)
	if err != nil || !bytes.Equal(actual, foreign) {
		t.Fatal("modified recovery bytes lost", err)
	}
	current, err := lifecycle.Inspect(stable)
	if err != nil || !lifecycle.Equal(current, after) {
		t.Fatal("target changed before unsafe rollback rejected", err)
	}
}

func TestManagerActivationPreservesForeignMutation(t *testing.T) {
	a, stable, _, _ := activationFixture(t)
	foreign := []byte("modified foreign target")
	put(t, stable, foreign, 0755)
	if err := a.Activate(context.Background(), 123); err == nil {
		t.Fatal("foreign manager replaced")
	}
	actual, err := os.ReadFile(stable)
	if err != nil || !bytes.Equal(actual, foreign) {
		t.Fatal("foreign bytes changed", err)
	}
	if _, err := os.Lstat(filepath.Join(a.StateDir, "manager-pending.json")); err != nil {
		t.Fatal("pending evidence removed", err)
	}
}

func TestManagerActivationVerifiesEntireCandidateBundle(t *testing.T) {
	a, stable, before, _ := activationFixture(t)
	pending, err := management.ReadPendingManager(a.StateDir)
	if err != nil {
		t.Fatal(err)
	}
	put(t, filepath.Join(a.StateDir, "bundles", pending.Bundle, "content.json"), []byte("unlisted content change"), 0644)
	if err = a.Activate(context.Background(), 123); err == nil {
		t.Fatal("unverified full bundle activated")
	}
	actual, err := lifecycle.Inspect(stable)
	if err != nil || !lifecycle.Equal(actual, before) {
		t.Fatal("stable manager changed", err)
	}
}

func TestManagerActivationRejectsParentBeforeMutation(t *testing.T) {
	a, stable, before, _ := activationFixture(t)
	a.WaitParent = func(context.Context, int, string) error { return fmt.Errorf("permission: manager-parent") }
	if err := a.Activate(context.Background(), 123); err == nil {
		t.Fatal("foreign parent accepted")
	}
	actual, err := lifecycle.Inspect(stable)
	if err != nil || !lifecycle.Equal(actual, before) {
		t.Fatal("target changed before parent verification", err)
	}
}

func TestManagerActivationAcceptsVerifiedVersionedParent(t *testing.T) {
	a, _, _, _ := activationFixture(t)
	pending, err := management.ReadPendingManager(a.StateDir)
	if err != nil {
		t.Fatal(err)
	}
	parent := filepath.Join(a.StateDir, "bundles", pending.Bundle, "bin", "opensocrates.exe")
	a.ParentExecutable = parent
	observed := ""
	a.WaitParent = func(_ context.Context, _ int, executable string) error { observed = executable; return nil }
	if err = a.Activate(context.Background(), 123); err != nil {
		t.Fatal(err)
	}
	if observed != parent {
		t.Fatal("parent process identity did not bind to versioned executable")
	}
}

func TestManagerActivationAcceptsExactStandaloneInstaller(t *testing.T) {
	a, _, _, _ := activationFixture(t)
	parent := filepath.Join(a.StateDir, "downloads", "opensocrates-v1.6.1-windows-x64.exe")
	put(t, parent, []byte("new native manager"), 0755)
	a.ParentExecutable = parent
	observed := ""
	a.WaitParent = func(_ context.Context, _ int, executable string) error { observed = executable; return nil }
	if err := a.Activate(context.Background(), 123); err != nil {
		t.Fatal(err)
	}
	if observed != parent {
		t.Fatal("standalone parent identity lost")
	}
}

func TestManagerActivationRejectsUnverifiedDevelopmentParent(t *testing.T) {
	a, stable, before, _ := activationFixture(t)
	parent := filepath.Join(a.StateDir, "development", "opensocrates.exe")
	put(t, parent, []byte("new native manager"), 0755)
	a.ParentExecutable = parent
	if err := a.Activate(context.Background(), 123); err == nil {
		t.Fatal("unverified development parent accepted")
	}
	actual, err := lifecycle.Inspect(stable)
	if err != nil || !lifecycle.Equal(actual, before) {
		t.Fatal("development parent changed installation", err)
	}
}
