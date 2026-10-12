package management

import (
	"context"
	"debug/buildinfo"
	"debug/macho"
	"debug/pe"
	"path/filepath"
	"strings"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

const moduleIdentity = "github.com/ParkerHwang/OpenSocrates"

func verifyGoExecutable(path, target, name string) error {
	if e := platform.GuardOwned(path); e != nil {
		return e
	}
	info, e := buildinfo.ReadFile(path)
	if e != nil || info.Main.Path != moduleIdentity || info.Path != moduleIdentity+"/src/opensocrates/cmd/"+name {
		return diagnostics.New(diagnostics.Verification, "native-runtime")
	}
	switch target {
	case "darwin-arm64":
		f, e := macho.Open(path)
		if e != nil {
			return diagnostics.New(diagnostics.Verification, "native-runtime")
		}
		defer f.Close()
		if f.Cpu != macho.CpuArm64 {
			return diagnostics.New(diagnostics.Verification, "native-runtime")
		}
	case "windows-x64":
		f, e := pe.Open(path)
		if e != nil {
			return diagnostics.New(diagnostics.Verification, "native-runtime")
		}
		defer f.Close()
		if f.Machine != pe.IMAGE_FILE_MACHINE_AMD64 {
			return diagnostics.New(diagnostics.Verification, "native-runtime")
		}
	default:
		return diagnostics.New(diagnostics.Unsupported, "native-runtime")
	}
	return nil
}
func probeIdentity(ctx context.Context, path string, p transport.Manifest) error {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	version, e := platform.Run(ctx, path, []string{"--version"}, platform.RunOptions{OutputLimit: 64 << 10})
	if e != nil {
		return diagnostics.New(diagnostics.Verification, "runtime-version")
	}
	tokens := strings.Fields(string(version.Stdout))
	if len(tokens) == 0 || tokens[len(tokens)-1] != p.ProductVersion {
		return diagnostics.New(diagnostics.Verification, "runtime-version")
	}
	output, e := platform.Run(ctx, path, []string{"package-identity"}, platform.RunOptions{OutputLimit: 64 << 10})
	if e != nil {
		return diagnostics.New(diagnostics.Verification, "runtime-identity")
	}
	value, e := contracts.Decode(output.Stdout)
	if e != nil {
		return diagnostics.New(diagnostics.Verification, "runtime-identity")
	}
	obj, e := contracts.Object(value, "product_version", "content_revision", "source_tree_hash", "normalized_semantic_hash", "state_schema_version")
	if e != nil {
		return diagnostics.New(diagnostics.Verification, "runtime-identity")
	}
	revision := ""
	if s, ok := obj["content_revision"].(string); ok {
		revision = s
	} else if n, ok := contracts.Integer(obj["content_revision"]); ok {
		revision = n.String()
	}
	schema, ok := contracts.Int(obj["state_schema_version"])
	if !ok || schema != 1 || obj["product_version"] != p.ProductVersion || revision != p.ContentRevision || obj["source_tree_hash"] != p.SourceTreeHash || obj["normalized_semantic_hash"] != p.NormalizedSemanticHash {
		return diagnostics.New(diagnostics.Verification, "runtime-identity")
	}
	return nil
}

// Candidate probing happens only for explicitly supplied local installation
// assets or authenticated signed updates, never unauthenticated verify/export.
func probePackage(ctx context.Context, p transport.Package, target string) error {
	for _, row := range p.Manifest.Files {
		switch strings.ToLower(filepath.Ext(row.Path)) {
		case ".sh", ".ps1", ".cmd", ".bat", ".py", ".pyc", ".js", ".mjs", ".cjs", ".dll", ".node", ".com":
			return diagnostics.New(diagnostics.Verification, "non-go-runtime")
		}
	}
	binaries := map[string]string{}
	if p.Manifest.Host == "codex" || p.Manifest.Host == "claude" {
		suffix := ""
		if target == "windows-x64" {
			suffix = ".exe"
		}
		runtimePath := filepath.Join(p.Root, "runtime", target, "opensocrates"+suffix)
		binaries[runtimePath] = "opensocrates"
	}
	if p.BundleRoot != "" {
		suffix := ""
		if target == "windows-x64" {
			suffix = ".exe"
		}
		binaries[filepath.Join(p.BundleRoot, "bin", "opensocrates"+suffix)] = "opensocrates"
		binaries[filepath.Join(p.BundleRoot, "bin", "opensocrates-update-helper"+suffix)] = "opensocrates-update-helper"
	}
	for _, path := range sortedKeys(binaries) {
		name := binaries[path]
		if e := verifyGoExecutable(path, target, name); e != nil {
			return e
		}
		if name == "opensocrates" {
			if e := probeIdentity(ctx, path, p.Manifest); e != nil {
				return e
			}
		}
	}
	return nil
}
