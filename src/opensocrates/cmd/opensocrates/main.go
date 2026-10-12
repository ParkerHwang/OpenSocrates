package main

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/bootstrap"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/management"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/managercli"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/runtimecli"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/version"
	"os"
	"strings"
)

func run() int {
	args := os.Args[1:]
	if handled, code := bootstrap.Forward(args, os.Stdin, os.Stdout, os.Stderr); handled {
		return code
	}
	if len(args) == 0 {
		return runtimecli.Run(args, os.Stdin, os.Stdout, os.Stderr)
	}
	var code int
	mutation := false
	switch args[0] {
	case "--version":
		if len(args) != 1 {
			return 2
		}
		return runtimecli.Run([]string{"version"}, os.Stdin, os.Stdout, os.Stderr)
	case "package-identity":
		if len(args) != 1 {
			return 2
		}
		bundle, err := content.Load()
		if err != nil {
			fmt.Fprintln(os.Stderr, "package identity: unavailable")
			return 1
		}
		raw, err := contracts.CanonicalJSON(map[string]any{"product_version": version.ProductVersion, "content_revision": bundle.Revision, "source_tree_hash": bundle.SourceTreeHash, "normalized_semantic_hash": bundle.SemanticHash, "state_schema_version": 1})
		if err != nil {
			return 1
		}
		if _, err = os.Stdout.Write(raw); err != nil {
			return 1
		}
		return 0
	case "--help", "help":
		fmt.Fprintln(os.Stdout, "OpenSocrates native manager and runtime\ninstall | adopt | status | remove | verify | export | recover\nupdate | auto-update enable|status|disable|run\nmanage diagnose | decision [--stream] | hook | claude-hook\nrigor | control | metrics | records | capabilities | trace | version")
		return 0
	case "manage":
		code = management.Run(args[1:], os.Stdin, os.Stdout, os.Stderr)
		if len(args) > 1 {
			mutation = isMutation(args[1])
		}
	case "install", "adopt", "status", "remove", "uninstall", "enable", "disable", "verify", "export", "recover":
		code = management.Run(args, os.Stdin, os.Stdout, os.Stderr)
		mutation = isMutation(args[0])
	case "auto-update":
		code = managercli.RunUpdate(args, os.Stdout, os.Stderr)
		mutation = len(args) > 1 && args[1] == "run"
	case "update":
		local := false
		for _, a := range args[1:] {
			if a == "--package" || a == "--asset" || a == "--codex-asset" || strings.HasPrefix(a, "--package=") || strings.HasPrefix(a, "--asset=") || strings.HasPrefix(a, "--codex-asset=") {
				local = true
			}
		}
		if local {
			code = management.Run(args, os.Stdin, os.Stdout, os.Stderr)
		} else {
			code = managercli.RunUpdate(args, os.Stdout, os.Stderr)
		}
		mutation = true
	default:
		code = runtimecli.Run(args, os.Stdin, os.Stdout, os.Stderr)
	}
	if code == 0 && mutation {
		if _, err := bootstrap.ScheduleManagerReplacement(); err != nil {
			fmt.Fprintln(os.Stderr, "manager replacement: deferred")
			return 1
		}
	}
	return code
}
func isMutation(command string) bool {
	return command == "install" || command == "adopt" || command == "update" || command == "recover"
}
func main() { os.Exit(run()) }
