// Package bootstrap forwards an owned stable entry point to one verified,
// immutable bundle. A running decision stream retains that bundle for its life.
package bootstrap

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/hosts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/management"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

const ParentPIDEnv = "OPENSOCRATES_BOOTSTRAP_PID"

type activeReference struct {
	Schema  string `json:"schema"`
	Bundle  string `json:"bundle"`
	Version string `json:"version"`
	Target  string `json:"target"`
}

type pinnedBundle struct{ root, manager, version, target string }

// Bootstrap's optional paths support isolated acceptance fixtures; the process
// default always obtains its executable from the operating system.
type Bootstrap struct {
	StateDir, Executable, GOOS, GOARCH string
	Environment                        []string
	once                               sync.Once
	pinned                             pinnedBundle
	pinErr                             error
}

var processBootstrap Bootstrap

func Forward(args []string, in io.Reader, out, errOut io.Writer) (bool, int) {
	return processBootstrap.Forward(args, in, out, errOut)
}

func stateDir() (string, error) {
	if value := os.Getenv("OPENSOCRATES_STATE_DIR"); value != "" {
		return filepath.Abs(value)
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return "", diagnostics.New(diagnostics.HostUnavailable, "home")
	}
	return filepath.Join(home, ".opensocrates"), nil
}

func managerPath(dir, goos string) string {
	name := "opensocrates"
	if goos == "windows" {
		name += ".exe"
	}
	return filepath.Join(dir, "bin", name)
}

func platformTarget(goos, goarch string) string { return hosts.DistributionTarget(goos, goarch) }

func samePath(a, b, goos string) bool {
	if goos == "windows" {
		return strings.EqualFold(filepath.Clean(a), filepath.Clean(b))
	}
	return filepath.Clean(a) == filepath.Clean(b)
}

func readActive(dir, target string) (activeReference, string, error) {
	var active activeReference
	data, err := platform.ReadFile(filepath.Join(dir, "active.json"), 64<<10)
	if err != nil {
		return active, "", err
	}
	value, err := contracts.Decode(data)
	if err != nil {
		return active, "", diagnostics.New(diagnostics.Verification, "active")
	}
	if _, err = contracts.Object(value, "schema", "bundle", "version", "target"); err != nil {
		return active, "", diagnostics.New(diagnostics.Verification, "active")
	}
	if json.Unmarshal(data, &active) != nil || active.Schema != "opensocrates.active-bundle/1.0.0" || active.Version == "" || active.Target != target {
		return active, "", diagnostics.New(diagnostics.Verification, "active")
	}
	root, err := management.PinActiveBundle(dir)
	if err != nil {
		return active, "", err
	}
	if filepath.Base(root) != active.Bundle {
		return active, "", diagnostics.New(diagnostics.Verification, "active")
	}
	if _, err = transport.VerifyBundle(root, active.Version, target); err != nil {
		return active, "", err
	}
	return active, root, nil
}

func pin(dir, goos, goarch string) (pinnedBundle, error) {
	engine := lifecycle.Engine{StateDir: dir}
	unlock, err := engine.Lock()
	if err != nil {
		return pinnedBundle{}, err
	}
	defer unlock()
	state, err := management.ReadState(dir)
	if err != nil {
		return pinnedBundle{}, err
	}
	stable := managerPath(dir, goos)
	actual, err := lifecycle.Inspect(stable)
	if err != nil {
		return pinnedBundle{}, err
	}
	manager, exists := state.Installations["manager"]
	expected, hasSnapshot := manager.Targets[stable]
	if !exists || !hasSnapshot || !actual.Exists || !lifecycle.Equal(actual, expected) {
		return pinnedBundle{}, diagnostics.New(diagnostics.Verification, "manager-ownership")
	}
	target := platformTarget(goos, goarch)
	active, root, err := readActive(dir, target)
	if err != nil {
		return pinnedBundle{}, err
	}
	if state.ManagerVersion != active.Version || manager.Bundle != active.Bundle {
		return pinnedBundle{}, diagnostics.New(diagnostics.Verification, "active-state")
	}
	executable := filepath.Join(root, "bin", filepath.Base(stable))
	info, err := os.Lstat(executable)
	if err != nil || !info.Mode().IsRegular() {
		return pinnedBundle{}, diagnostics.New(diagnostics.Verification, "manager")
	}
	return pinnedBundle{root: root, manager: executable, version: active.Version, target: target}, nil
}

func fail(args []string, err error, errOut io.Writer) (bool, int) {
	fmt.Fprintln(errOut, err)
	if len(args) > 0 && (args[0] == "hook" || args[0] == "claude-hook") {
		return true, 0
	}
	return true, 1
}

func (b *Bootstrap) Forward(args []string, in io.Reader, out, errOut io.Writer) (bool, int) {
	goos, goarch := b.GOOS, b.GOARCH
	if goos == "" {
		goos = runtime.GOOS
	}
	if goarch == "" {
		goarch = runtime.GOARCH
	}
	dir := b.StateDir
	if dir == "" {
		var err error
		dir, err = stateDir()
		if err != nil {
			return fail(args, err, errOut)
		}
	}
	executable := b.Executable
	if executable == "" {
		var err error
		executable, err = os.Executable()
		if err != nil {
			return fail(args, diagnostics.New(diagnostics.HostUnavailable, "executable"), errOut)
		}
	}
	// Extracted installers, versioned managers and repository development tools
	// execute directly. Only the owned installed stable path acts as a bootstrap.
	if !samePath(executable, managerPath(dir, goos), goos) {
		return false, 0
	}
	b.once.Do(func() { b.pinned, b.pinErr = pin(dir, goos, goarch) })
	if b.pinErr != nil {
		return fail(args, b.pinErr, errOut)
	}
	env := b.Environment
	if env == nil {
		env = os.Environ()
	}
	childEnv := make([]string, 0, len(env)+2)
	for _, value := range env {
		key := strings.SplitN(value, "=", 2)[0]
		if strings.EqualFold(key, ParentPIDEnv) || strings.EqualFold(key, "OPENSOCRATES_STATE_DIR") {
			continue
		}
		childEnv = append(childEnv, value)
	}
	childEnv = append(childEnv, ParentPIDEnv+"="+strconv.Itoa(os.Getpid()), "OPENSOCRATES_STATE_DIR="+dir)
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	process, err := platform.StartTrusted(ctx, b.pinned.manager, args, platform.RunOptions{Env: childEnv, Stdin: in, Stdout: out, Stderr: errOut})
	if err != nil {
		return fail(args, err, errOut)
	}
	err = process.Wait()
	if process.Cmd.ProcessState != nil {
		code := process.Cmd.ProcessState.ExitCode()
		if code >= 0 {
			if code != 0 && len(args) > 0 && (args[0] == "hook" || args[0] == "claude-hook") {
				return fail(args, diagnostics.New(diagnostics.HostUnavailable, "manager"), errOut)
			}
			return true, code
		}
	}
	if err != nil {
		return fail(args, err, errOut)
	}
	return true, 0
}
