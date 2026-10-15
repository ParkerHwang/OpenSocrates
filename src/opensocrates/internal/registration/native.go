package registration

import (
	"context"
	"encoding/json"
	"path/filepath"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

// Runner is injectable at the external process boundary; production uses bounded
// platform processes and does not save command output or alter host trust.
type Runner interface {
	Run(context.Context, string, []string) ([]byte, error)
}
type ProcessRunner struct{}

func (ProcessRunner) Run(ctx context.Context, binary string, args []string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()
	r, e := platform.Run(ctx, binary, args, platform.RunOptions{OutputLimit: 8 << 20})
	if e != nil {
		return nil, diagnostics.New(diagnostics.HostUnavailable, "registration")
	}
	return r.Stdout, nil
}

type Native struct {
	Host   string
	Binary string
	Runner Runner
}

func (n *Native) runner() Runner {
	if n.Runner != nil {
		return n.Runner
	}
	return ProcessRunner{}
}
func (n *Native) namespace() string {
	if n.Host == "claude" {
		return "opensocrates-macos"
	}
	return "opensocrates"
}
func (n *Native) id() string { return "opensocrates@" + n.namespace() }
func (n *Native) command(ctx context.Context, args ...string) ([]byte, error) {
	return n.runner().Run(ctx, n.Binary, args)
}
func decodeRows(b []byte, key string) ([]map[string]json.RawMessage, error) {
	if _, e := contracts.Decode(b); e != nil {
		return nil, diagnostics.New(diagnostics.ProtocolIncompatible, "registration")
	}
	var direct []map[string]json.RawMessage
	if json.Unmarshal(b, &direct) == nil && direct != nil {
		return direct, nil
	}
	var wrap map[string]json.RawMessage
	if json.Unmarshal(b, &wrap) != nil {
		return nil, diagnostics.New(diagnostics.ProtocolIncompatible, "registration")
	}
	if json.Unmarshal(wrap[key], &direct) != nil || direct == nil {
		return nil, diagnostics.New(diagnostics.ProtocolIncompatible, "registration")
	}
	return direct, nil
}
func field(row map[string]json.RawMessage, key string) string {
	var s string
	json.Unmarshal(row[key], &s)
	return s
}
func boolField(row map[string]json.RawMessage, key string) (bool, bool) {
	var b bool
	e := json.Unmarshal(row[key], &b)
	return b, e == nil
}
func (n *Native) Inspect(ctx context.Context, root string) (State, error) {
	if n.Host != "codex" && n.Host != "claude" || !filepath.IsAbs(root) {
		return State{}, diagnostics.New(diagnostics.Unsupported, "registration")
	}
	b, e := n.command(ctx, "plugin", "marketplace", "list", "--json")
	if e != nil {
		return State{}, e
	}
	rows, e := decodeRows(b, "marketplaces")
	if e != nil {
		return State{}, e
	}
	state := State{Root: root}
	matches := 0
	for _, row := range rows {
		if field(row, "name") != n.namespace() {
			continue
		}
		matches++
		if matches > 1 {
			return state, diagnostics.New(diagnostics.Verification, "foreign-registration")
		}
		path := field(row, "root")
		if n.Host == "claude" {
			path = field(row, "path")
			var source map[string]json.RawMessage
			if json.Unmarshal(row["source"], &source) == nil && field(source, "path") != "" {
				path = field(source, "path")
			}
			if path == "" {
				path = field(row, "installLocation")
			}
			if scope := field(row, "scope"); scope != "" && scope != "user" {
				return state, diagnostics.New(diagnostics.Verification, "foreign-registration")
			}
		}
		if path == "" || !filepath.IsAbs(path) || !samePath(path, root) {
			return state, diagnostics.New(diagnostics.Verification, "foreign-registration")
		}
		state.Registered = true
	}
	args := []string{"plugin", "list", "--json"}
	key := "plugins"
	if n.Host == "codex" {
		args = []string{"plugin", "list", "--marketplace", n.namespace(), "--available", "--json"}
		if !state.Registered {
			args = []string{"plugin", "list", "--json"}
		}
		key = "installed"
	}
	b, e = n.command(ctx, args...)
	if e != nil {
		return state, e
	}
	rows, e = decodeRows(b, key)
	if e != nil {
		return state, e
	}
	matches = 0
	for _, row := range rows {
		id := field(row, "pluginId")
		if id == "" {
			id = field(row, "id")
		}
		if id == "" {
			id = field(row, "name")
		}
		if id != n.id() {
			continue
		}
		matches++
		if matches > 1 || !state.Registered {
			return state, diagnostics.New(diagnostics.Verification, "foreign-registration")
		}
		if n.Host == "claude" && field(row, "scope") != "user" {
			return state, diagnostics.New(diagnostics.Verification, "foreign-registration")
		}
		state.Installed = true
		state.Version = field(row, "version")
		if state.Version == "" {
			return state, diagnostics.New(diagnostics.ProtocolIncompatible, "registration-version")
		}
		enabled, ok := boolField(row, "enabled")
		if !ok {
			return state, diagnostics.New(diagnostics.ProtocolIncompatible, "registration-enabled")
		}
		state.Enabled = enabled
	}
	settings, e := n.readSettings(root)
	if e != nil {
		return state, e
	}
	state.Data = settings
	return state, nil
}
func samePath(a, b string) bool {
	a = filepath.Clean(a)
	b = filepath.Clean(b)
	if aa, e := filepath.EvalSymlinks(a); e == nil {
		a = aa
	}
	if bb, e := filepath.EvalSymlinks(b); e == nil {
		b = bb
	}
	return a == b
}
func (n *Native) Verify(ctx context.Context, want State) error {
	actual, e := n.Inspect(ctx, want.Root)
	if e != nil {
		return e
	}
	if !statesEqual(actual, want) {
		return diagnostics.New(diagnostics.Verification, "registration-verify")
	}
	return nil
}
func statesEqual(a, b State) bool {
	return samePath(a.Root, b.Root) && a.Registered == b.Registered && a.Installed == b.Installed && (!a.Installed || a.Enabled == b.Enabled && a.Version == b.Version) && settingsEquivalent(a.Data, b.Data)
}
func (n *Native) Replace(ctx context.Context, before, after State) error {
	if !samePath(before.Root, after.Root) {
		return diagnostics.New(diagnostics.Verification, "registration-path")
	}
	current, e := n.Inspect(ctx, before.Root)
	if e != nil {
		return e
	}
	if statesEqual(current, after) {
		return nil
	}
	if n.Host == "codex" && current.Installed && after.Installed {
		// Existing local marketplace packages are refreshed by Codex on restart.
		// Calling plugin add would force enabled=true; remove deletes plugin settings.
		return diagnostics.New(diagnostics.Unsupported, "codex-reload-required")
	}
	if n.Host == "claude" && current.Registered && current.Installed && after.Registered && after.Installed {
		if current.Version != after.Version {
			if _, e := n.command(ctx, "plugin", "update", n.id(), "--scope", "user"); e != nil {
				return e
			}
		}
		if current.Enabled != after.Enabled {
			action := "disable"
			if after.Enabled {
				action = "enable"
			}
			if _, e := n.command(ctx, "plugin", action, n.id(), "--scope", "user"); e != nil {
				return e
			}
		}
		return n.Verify(ctx, after)
	}
	// Interrupted commands may have left the exact owned marketplace without its
	// plugin. Inspect has already rejected every foreign root, scope and duplicate.
	if !statesEqual(current, before) && !statesEqual(current, after) {
		if !current.Registered && current.Installed || current.Installed && current.Version != before.Version && current.Version != after.Version {
			return diagnostics.New(diagnostics.Verification, "registration-changed")
		}
	}
	if n.Host == "codex" && after.Installed && after.Data[settingsKey] != "" {
		// Recovery never calls add for a disabled integration. Its cached owned
		// payload is reused; an unavailable cache remains explicit manual recovery.
		if !current.Registered && after.Registered {
			if _, e := n.command(ctx, "plugin", "marketplace", "add", after.Root, "--json"); e != nil {
				return e
			}
		}
		if !current.Installed && after.Enabled {
			if _, e := n.command(ctx, "plugin", "add", n.id(), "--json"); e != nil {
				return e
			}
		}
		if e := n.restoreSettings(after.Root, after.Data); e != nil {
			return e
		}
		return n.Verify(ctx, after)
	}
	if n.Host == "codex" && after.Installed && !after.Enabled {
		return diagnostics.New(diagnostics.Unsupported, "codex-disabled-registration")
	}
	if current.Installed {
		args := []string{"plugin", "remove", n.id(), "--json"}
		if n.Host == "claude" {
			args = []string{"plugin", "uninstall", n.id(), "--scope", "user"}
		}
		if _, e := n.command(ctx, args...); e != nil {
			return e
		}
	}
	if current.Registered {
		args := []string{"plugin", "marketplace", "remove", n.namespace(), "--json"}
		if n.Host == "claude" {
			args = []string{"plugin", "marketplace", "remove", n.namespace(), "--scope", "user"}
		}
		if _, e := n.command(ctx, args...); e != nil {
			return e
		}
	}
	if after.Registered {
		args := []string{"plugin", "marketplace", "add", after.Root, "--json"}
		if n.Host == "claude" {
			args = []string{"plugin", "marketplace", "add", after.Root, "--scope", "user"}
		}
		if _, e := n.command(ctx, args...); e != nil {
			return e
		}
	}
	if after.Installed {
		args := []string{"plugin", "add", n.id(), "--json"}
		if n.Host == "claude" {
			args = []string{"plugin", "install", n.id(), "--scope", "user"}
		}
		if _, e := n.command(ctx, args...); e != nil {
			return e
		}
		if !after.Enabled {
			if _, e := n.command(ctx, "plugin", "disable", n.id(), "--scope", "user"); e != nil {
				return e
			}
		}
	}
	return n.Verify(ctx, after)
}

// SetEnabled avoids unregistering native Claude or resetting its trust.
func (n *Native) SetEnabled(ctx context.Context, before State, enabled bool) error {
	if n.Host != "claude" {
		return diagnostics.New(diagnostics.Unsupported, "enabled-control")
	}
	if e := n.Verify(ctx, before); e != nil {
		return e
	}
	action := "disable"
	if enabled {
		action = "enable"
	}
	if _, e := n.command(ctx, "plugin", action, n.id(), "--scope", "user"); e != nil {
		return e
	}
	after := before
	after.Enabled = enabled
	return n.Verify(ctx, after)
}
