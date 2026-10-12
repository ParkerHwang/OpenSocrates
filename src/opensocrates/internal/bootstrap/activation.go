package bootstrap

import (
	"context"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/management"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

// ScheduleManagerReplacement is called after the management transaction commits.
// The helper comes from the newly verified bundle, so updating the updater and
// helper never overwrites an executable currently loaded from an older bundle.
func ScheduleManagerReplacement() (bool, error) {
	if runtime.GOOS != "windows" {
		return false, nil
	}
	dir, err := stateDir()
	if err != nil {
		return false, err
	}
	if _, err = os.Lstat(filepath.Join(dir, "manager-pending.json")); os.IsNotExist(err) {
		return false, nil
	}
	pending, err := management.ReadPendingManager(dir)
	if err != nil {
		return false, err
	}
	state, err := management.ReadState(dir)
	if err != nil {
		return false, err
	}
	active, root, err := readActive(dir, platformTarget(runtime.GOOS, runtime.GOARCH))
	if err != nil {
		return false, err
	}
	if active.Bundle != pending.Bundle || active.Version != state.ManagerVersion {
		return false, diagnostics.New(diagnostics.Verification, "manager-pending")
	}
	helper := filepath.Join(root, "bin", "opensocrates-update-helper.exe")
	hash, err := platform.SHA256File(helper, lifecycle.MaxFileBytes)
	if err != nil {
		return false, err
	}
	parent := os.Getpid()
	parentExecutable := ""
	if value := os.Getenv(ParentPIDEnv); value != "" {
		parent, err = strconv.Atoi(value)
		if err != nil || parent < 1 {
			return false, diagnostics.New(diagnostics.Verification, "manager-parent")
		}
	} else {
		parentExecutable, err = os.Executable()
		if err != nil {
			return false, diagnostics.New(diagnostics.HostUnavailable, "manager-parent")
		}
		if _, err = replacementParent(dir, parentExecutable); err != nil {
			return false, err
		}
	}
	if _, err = platform.SpawnManagerActivationHelper(helper, dir, parent, hash, parentExecutable); err != nil {
		return false, err
	}
	return true, nil
}

// Activator executes the same recoverable lifecycle engine used by installs and
// updates. WaitParent is replaceable only in isolated transaction fixtures.
type Activator struct {
	StateDir, GOOS, GOARCH string
	ParentExecutable       string
	WaitParent             func(context.Context, int, string) error
	Engine                 *lifecycle.Engine
}

func ActivateManager(ctx context.Context, dir string, parentPID int) error {
	return ActivateManagerForParent(ctx, dir, parentPID, "")
}

func ActivateManagerForParent(ctx context.Context, dir string, parentPID int, parentExecutable string) error {
	if runtime.GOOS != "windows" || runtime.GOARCH != "amd64" {
		return diagnostics.New(diagnostics.Unsupported, "manager-activation")
	}
	_, root, err := readActive(dir, "windows-x64")
	if err != nil {
		return err
	}
	executable, err := os.Executable()
	if err != nil || !samePath(executable, filepath.Join(root, "bin", "opensocrates-update-helper.exe"), "windows") {
		return diagnostics.New(diagnostics.Verification, "manager-helper")
	}
	return (&Activator{StateDir: dir, GOOS: "windows", GOARCH: "amd64", ParentExecutable: parentExecutable}).Activate(ctx, parentPID)
}

func replacementParent(dir, executable string) (string, error) {
	stable := managerPath(dir, "windows")
	if executable == "" || samePath(executable, stable, "windows") {
		return stable, nil
	}
	if !filepath.IsAbs(executable) {
		return "", diagnostics.New(diagnostics.Verification, "manager-parent")
	}
	pending, err := management.ReadPendingManager(dir)
	if err != nil {
		return "", err
	}
	snapshot, err := lifecycle.Inspect(executable)
	if err != nil {
		return "", err
	}
	active, _, err := readActive(dir, "windows-x64")
	if err != nil || active.Bundle != pending.Bundle {
		return "", diagnostics.New(diagnostics.Verification, "manager-parent")
	}
	// Publication verifies that this standalone native installer has exactly the
	// bytes of the signed bundle's manager. It has no sibling manifest; bind its
	// complete snapshot to the already verified candidate instead.
	standalone := "opensocrates-v" + active.Version + "-windows-x64.exe"
	if strings.EqualFold(filepath.Base(executable), standalone) && lifecycle.Equal(snapshot, pending.After) {
		return executable, nil
	}
	if !strings.EqualFold(filepath.Base(executable), "opensocrates.exe") || !strings.EqualFold(filepath.Base(filepath.Dir(executable)), "bin") {
		return "", diagnostics.New(diagnostics.Verification, "manager-parent")
	}
	// Direct release and versioned executables may be the parent. Bind them to a
	// complete owned bundle and one of the exact pending manager snapshots, rather
	// than accepting an environment-supplied executable as a trust assertion.
	root := filepath.Dir(filepath.Dir(executable))
	if _, err := transport.VerifyBundle(root, "", "windows-x64"); err != nil {
		return "", err
	}
	if !lifecycle.Equal(snapshot, pending.Before) && !lifecycle.Equal(snapshot, pending.After) {
		return "", diagnostics.New(diagnostics.Verification, "manager-parent")
	}
	return executable, nil
}

func (a *Activator) Activate(ctx context.Context, parentPID int) error {
	if a.GOOS != "windows" || a.GOARCH != "amd64" || parentPID < 1 || !filepath.IsAbs(a.StateDir) {
		return diagnostics.New(diagnostics.Verification, "manager-activation")
	}
	dir := a.StateDir
	stable := managerPath(dir, a.GOOS)
	parentExecutable, err := replacementParent(dir, a.ParentExecutable)
	if err != nil {
		return err
	}
	wait := a.WaitParent
	if wait == nil {
		wait = platform.WaitOwnedProcess
	}
	if err := wait(ctx, parentPID, parentExecutable); err != nil {
		return err
	}
	engine := a.Engine
	if engine == nil {
		engine = &lifecycle.Engine{StateDir: dir}
	}
	if engine.StateDir != dir {
		return diagnostics.New(diagnostics.Verification, "manager-engine")
	}
	// Interrupted activation is first rolled back with verified recovery bytes.
	// Other host transactions need their own registration adapters and cannot be
	// recovered by this narrow detached helper.
	journals, err := engine.Pending()
	if err != nil {
		return err
	}
	for _, journal := range journals {
		if !activationJournal(journal, dir, stable) {
			return diagnostics.New(diagnostics.Locked, "recovery-required")
		}
		if _, err = engine.Recover(ctx, journal.ID); err != nil {
			return err
		}
	}
	unlock, err := engine.Lock()
	if err != nil {
		return err
	}
	defer unlock()
	if journals, err = engine.Pending(); err != nil {
		return err
	} else if len(journals) != 0 {
		return diagnostics.New(diagnostics.Locked, "recovery-required")
	}
	pendingPath := filepath.Join(dir, "manager-pending.json")
	if _, err = os.Lstat(pendingPath); os.IsNotExist(err) {
		return nil
	}
	pending, err := management.ReadPendingManager(dir)
	if err != nil {
		return err
	}
	state, err := management.ReadState(dir)
	if err != nil {
		return err
	}
	active, root, err := readActive(dir, platformTarget(a.GOOS, a.GOARCH))
	if err != nil {
		return err
	}
	if pending.Bundle != active.Bundle || active.Version != state.ManagerVersion || pending.Source != "bin/opensocrates.exe" {
		return diagnostics.New(diagnostics.Verification, "manager-pending")
	}
	current, err := lifecycle.Inspect(stable)
	if err != nil {
		return err
	}
	manager, ok := state.Installations["manager"]
	expected, hasSnapshot := manager.Targets[stable]
	if !ok || !hasSnapshot || manager.Bundle != pending.Bundle || !lifecycle.Equal(current, pending.Before) || !lifecycle.Equal(expected, pending.Before) {
		return diagnostics.New(diagnostics.Verification, "manager-ownership")
	}
	source := filepath.Join(root, filepath.FromSlash(pending.Source))
	after, err := lifecycle.Inspect(source)
	if err != nil {
		return err
	}
	if !lifecycle.Equal(after, pending.After) {
		return diagnostics.New(diagnostics.Verification, "manager-candidate")
	}
	stateSnapshot, err := lifecycle.Inspect(filepath.Join(dir, "native-state.json"))
	if err != nil {
		return err
	}
	pendingSnapshot, err := lifecycle.Inspect(pendingPath)
	if err != nil {
		return err
	}
	manager.Version = active.Version
	manager.Targets = map[string]lifecycle.Snapshot{stable: after}
	manager.Integrity = "verified"
	manager.Activation = "fresh_session_or_host_reload"
	state.Installations["manager"] = manager
	stateBytes, err := management.StateBytes(state)
	if err != nil {
		return err
	}
	scratch, err := os.MkdirTemp(dir, ".manager-activation-")
	if err != nil {
		return diagnostics.New(diagnostics.Permission, "manager-stage")
	}
	defer platform.RemoveTree(scratch)
	stateSource := filepath.Join(scratch, "native-state.json")
	if err = platform.AtomicWrite(stateSource, stateBytes, 0600); err != nil {
		return err
	}
	_, err = engine.ExecuteHeld(ctx, lifecycle.Plan{
		Action: "activate-manager", Host: "manager", Scope: "global", Version: active.Version,
		Mutations: []lifecycle.Mutation{
			{Target: stable, Source: source, Expected: &current},
			{Target: filepath.Join(dir, "native-state.json"), Source: stateSource, Expected: &stateSnapshot},
			{Target: pendingPath, Remove: true, Expected: &pendingSnapshot},
		},
	})
	return err
}

func activationJournal(j lifecycle.Journal, dir, stable string) bool {
	if j.Schema != lifecycle.JournalSchema || j.Action != "activate-manager" || j.Host != "manager" || j.Scope != "global" || len(j.Registrations) != 0 || len(j.Files) != 3 {
		return false
	}
	allowed := map[string]bool{stable: true, filepath.Join(dir, "native-state.json"): true, filepath.Join(dir, "manager-pending.json"): true}
	for _, file := range j.Files {
		if !allowed[file.Target] {
			return false
		}
		delete(allowed, file.Target)
	}
	return len(allowed) == 0
}
