package management

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"path/filepath"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

// Run is deliberately limited to argument/output assembly; lifecycle owns changes.
func Run(args []string, in io.Reader, out, errOut io.Writer) int {
	return (&Manager{}).Run(args, in, out, errOut)
}
func (m *Manager) Run(args []string, _ io.Reader, out, errOut io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(errOut, "management: unsupported")
		return 2
	}
	if args[0] == "help" || args[0] == "--help" {
		fmt.Fprintln(out, "opensocrates install|adopt|update --host codex|all|claude|antigravity --package ABS_PATH [--workspace ABS_PATH]\nopensocrates status|diagnose|remove|enable|disable --host HOST [--workspace ABS_PATH]\nopensocrates verify --host HOST --package ABS_PATH\nopensocrates export --host claude-chat --package ABS_PATH --output ABS_ZIP\nopensocrates recover --transaction ID")
		return 0
	}
	r := Request{Action: args[0], Host: "codex"}
	flags := flag.NewFlagSet("opensocrates", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	flags.StringVar(&r.Host, "host", "codex", "")
	flags.StringVar(&r.Package, "package", "", "")
	flags.StringVar(&r.Package, "asset", "", "")
	flags.StringVar(&r.Package, "codex-asset", "", "")
	flags.StringVar(&r.Package, "asset-codex", "", "")
	flags.StringVar(&r.Workspace, "workspace", "", "")
	flags.StringVar(&r.Version, "version", "", "")
	flags.StringVar(&r.Output, "output", "", "")
	flags.StringVar(&r.Transaction, "transaction", "", "")
	var checksum string
	flags.StringVar(&checksum, "checksum", "", "")
	flags.StringVar(&checksum, "codex-checksum", "", "")
	flags.StringVar(&checksum, "checksum-codex", "", "")
	flags.BoolVar(&r.Purge, "purge", false, "")
	flags.BoolVar(&r.ResetTrust, "reset-trust", false, "")
	var yes, silent bool
	flags.BoolVar(&yes, "yes", false, "")
	flags.BoolVar(&silent, "silent", false, "")
	if flags.Parse(args[1:]) != nil || flags.NArg() != 0 {
		fmt.Fprintln(errOut, "arguments: verification")
		return 2
	}
	if (r.Purge || r.ResetTrust) && r.Action != "remove" && r.Action != "uninstall" || r.ResetTrust && !r.Purge || (r.Purge || r.ResetTrust) && r.Host != "codex" && r.Host != "all" {
		fmt.Fprintln(errOut, "arguments: unsupported")
		return 2
	}
	if r.Package != "" {
		p, e := filepath.Abs(r.Package)
		if e != nil {
			fmt.Fprintln(errOut, "arguments: verification")
			return 2
		}
		r.Package = filepath.Clean(p)
	}
	if r.Output != "" {
		p, e := filepath.Abs(r.Output)
		if e != nil {
			fmt.Fprintln(errOut, "arguments: verification")
			return 2
		}
		r.Output = filepath.Clean(p)
	}
	if checksum != "" {
		if r.Package == "" {
			fmt.Fprintln(errOut, "checksum: verification")
			return 2
		}
		p, e := filepath.Abs(checksum)
		if e != nil {
			fmt.Fprintln(errOut, "checksum: verification")
			return 2
		}
		b, e := platform.ReadOwnedFile(p, 64<<10)
		if e != nil {
			fmt.Fprintln(errOut, "checksum: verification")
			return 1
		}
		parts := strings.Fields(strings.TrimSpace(string(b)))
		if len(parts) != 2 || strings.TrimPrefix(parts[1], "*") != filepath.Base(r.Package) {
			fmt.Fprintln(errOut, "checksum: verification")
			return 1
		}
		want, e := transport.Digest(parts[0])
		if e != nil {
			fmt.Fprintln(errOut, "checksum: verification")
			return 1
		}
		got, e := platform.SHA256File(r.Package, 2<<30)
		if e != nil || got != want {
			fmt.Fprintln(errOut, "checksum: verification")
			return 1
		}
	}
	result, e := m.Handle(context.Background(), r)
	if e != nil {
		var category *diagnostics.Error
		if errors.As(e, &category) {
			fmt.Fprintln(errOut, category.Error())
			result.Reason = category.Code
		} else {
			fmt.Fprintln(errOut, "management: verification")
			result.Reason = diagnostics.Verification
		}
		if result.Host != "" || result.Transaction != "" || result.Purge != nil {
			result.Integrity = "unverified"
			result.Installation = "unavailable"
			result.Activation = "unknown"
			encoder := json.NewEncoder(out)
			encoder.SetEscapeHTML(false)
			encoder.Encode(result)
		}
		return 1
	}
	encoder := json.NewEncoder(out)
	encoder.SetEscapeHTML(false)
	if encoder.Encode(result) != nil {
		return 1
	}
	return 0
}
