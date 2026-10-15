// Package managercli composes the signed updater with the shared host lifecycle.
// No runtime hook or default decision imports this package.
package managercli

import (
	"context"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/management"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/version"
)

func emit(out io.Writer, value any) int {
	data, err := contracts.CanonicalJSON(value)
	if err != nil {
		return 1
	}
	if _, err = out.Write(data); err != nil {
		return 1
	}
	return 0
}

func failure(out io.Writer, err error) int {
	emit(out, map[string]any{"status": "unavailable", "error_code": diagnostics.CodeOf(err)})
	return 1
}

func RunUpdate(args []string, out, errout io.Writer) int {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	return RunUpdateContext(ctx, args, out, errout)
}

func RunUpdateContext(ctx context.Context, args []string, out, errout io.Writer) int {
	if len(args) == 0 {
		return 2
	}
	operation := "run"
	scheduled, force := false, false
	remaining := args[1:]
	if args[0] == "auto-update" {
		if len(remaining) == 0 {
			fmt.Fprintln(errout, "usage: opensocrates auto-update enable|status|disable|run")
			return 2
		}
		operation = remaining[0]
		remaining = remaining[1:]
	} else if args[0] != "update" {
		return 2
	}
	var stateDir, host, channel string
	var loginDelay int
	f := flag.NewFlagSet("native-update", flag.ContinueOnError)
	f.SetOutput(io.Discard)
	f.StringVar(&stateDir, "state-dir", "", "private management state")
	f.StringVar(&host, "host", "codex", "registered Codex installation")
	f.StringVar(&channel, "channel", "stable", "stable channel")
	f.BoolVar(&scheduled, "scheduled", false, "scheduled run")
	f.BoolVar(&force, "force", false, "explicit check before next scheduled time")
	f.IntVar(&loginDelay, "login-delay", 0, "login coalescing delay")
	f.Bool("json", false, "JSON output")
	if f.Parse(remaining) != nil || f.NArg() != 0 || host != "codex" && host != "all" || channel != "stable" || loginDelay != 0 && loginDelay != 300 {
		fmt.Fprintln(errout, "update arguments: unsupported")
		return 2
	}
	if operation != "enable" && operation != "disable" && operation != "status" && operation != "run" {
		fmt.Fprintln(errout, "update operation: unsupported")
		return 2
	}
	if operation != "run" && (scheduled || force || loginDelay != 0) {
		fmt.Fprintln(errout, "update arguments: unsupported")
		return 2
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return failure(out, diagnostics.New(diagnostics.HostUnavailable, "home"))
	}
	if stateDir == "" {
		stateDir = os.Getenv("OPENSOCRATES_STATE_DIR")
	}
	if stateDir == "" {
		stateDir = filepath.Join(home, ".opensocrates")
	}
	stateDir, err = filepath.Abs(stateDir)
	if err != nil {
		return failure(out, diagnostics.New(diagnostics.Verification, "state"))
	}
	m := management.Manager{Home: home, StateDir: stateDir, Version: version.ProductVersion, GOOS: runtime.GOOS, GOARCH: runtime.GOARCH}
	scheduler := update.NewSchedulerAdapter(m.GOOS, m.Home, m.ManagerPath(), m.StateDir)
	engine := update.Engine{StateDir: stateDir, Version: version.ProductVersion, OS: runtime.GOOS, Arch: runtime.GOARCH, Repository: update.DefaultRepository()}
	engine.Apply = func(ctx context.Context, candidate update.Candidate) (update.ApplyResult, error) {
		trust := update.DefaultNativeTrust()
		result, err := m.ApplyPackage(ctx, management.Request{Action: "update", Host: "codex", Package: candidate.Archive, Version: candidate.Release.Version, ExpectedContentRevision: candidate.Release.ContentRevision, NativeTrustPolicy: &trust})
		return update.ApplyResult{Version: result.Version, Pending: result.Activation != "active"}, err
	}
	if operation == "status" {
		status, err := engine.Status(ctx, scheduler)
		if err != nil {
			return failure(out, err)
		}
		// Scheduler documents and user filesystem paths stay in local recovery state.
		return emit(out, map[string]any{"status": "ok", "update": status})
	}
	if operation == "enable" || operation == "disable" {
		configuration, err := engine.PrepareConfiguration(ctx, operation == "enable", scheduler)
		if err != nil {
			return failure(out, err)
		}
		if err = m.ApplyUpdateConfiguration(ctx, configuration); err != nil {
			return failure(out, err)
		}
		return emit(out, map[string]any{"status": "ok", "enabled": operation == "enable", "channel": "stable", "host": "codex", "update_owner": update.Owner})
	}
	if loginDelay != 0 {
		if err = update.LoginWait(ctx); err != nil {
			return failure(out, err)
		}
	}
	receipt, err := engine.Run(ctx, scheduled, force)
	if err != nil {
		emit(out, receipt)
		return 1
	}
	return emit(out, receipt)
}
