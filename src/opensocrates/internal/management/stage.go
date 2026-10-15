package management

import (
	"encoding/json"
	"path/filepath"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

func copyTree(from, to string) error {
	s, e := lifecycle.Inspect(from)
	if e != nil {
		return e
	}
	if e := platform.Mkdir(filepath.Dir(to)); e != nil {
		return e
	}
	return lifecycle.CopyVerified(from, to, s)
}
func writeJSON(path string, value any) error {
	b, e := json.MarshalIndent(value, "", "  ")
	if e != nil {
		return e
	}
	if e := platform.Mkdir(filepath.Dir(path)); e != nil {
		return e
	}
	return platform.AtomicWrite(path, append(b, '\n'), 0600)
}
func stageHost(scratch string, p Paths, host string, pack transport.Package, enabled bool) (map[string]string, error) {
	root := filepath.Join(scratch, "host")
	if e := platform.Mkdir(root); e != nil {
		return nil, e
	}
	sources := map[string]string{p.Root: root}
	if host == "codex" {
		plugin := filepath.Join(root, "build/generated/plugins/codex")
		if e := copyTree(pack.Root, plugin); e != nil {
			return nil, e
		}
		market := codexMarketplace()
		if e := writeJSON(filepath.Join(root, ".agents/plugins/marketplace.json"), market); e != nil {
			return nil, e
		}
		if e := writeJSON(filepath.Join(root, MarkerName), map[string]any{"schemaVersion": 1, "marketplaceName": "opensocrates", "pluginName": "opensocrates"}); e != nil {
			return nil, e
		}
		return sources, nil
	}
	if host == "claude" {
		if e := copyTree(pack.Root, filepath.Join(root, "plugin")); e != nil {
			return nil, e
		}
		market := map[string]any{"name": "opensocrates-macos", "owner": map[string]string{"name": "OpenSocrates"}, "plugins": []any{map[string]string{"name": "opensocrates", "source": "./plugin", "version": pack.Manifest.ProductVersion}}}
		if e := writeJSON(filepath.Join(root, ".claude-plugin/marketplace.json"), market); e != nil {
			return nil, e
		}
		s, e := lifecycle.Inspect(root)
		if e != nil {
			return nil, e
		}
		if e := writeJSON(filepath.Join(root, MarkerName), Marker{Schema: MarkerSchema, Host: host, Scope: p.Scope, Version: pack.Manifest.ProductVersion, Enabled: enabled, Hashes: files(s)}); e != nil {
			return nil, e
		}
		return sources, nil
	}
	if e := copyTree(filepath.Join(pack.Root, "release-manifest.json"), filepath.Join(root, "release-manifest.json")); e != nil {
		return nil, e
	}
	rule := filepath.Join(scratch, "rule.md")
	skill := filepath.Join(scratch, "skill")
	if !enabled {
		rule = filepath.Join(root, "disabled/rule.md")
		skill = filepath.Join(root, "disabled/skill")
	}
	if e := copyTree(filepath.Join(pack.Root, ".agents/rules/opensocrates.md"), rule); e != nil {
		return nil, e
	}
	if e := copyTree(filepath.Join(pack.Root, ".agents/skills/opensocrates"), skill); e != nil {
		return nil, e
	}
	if enabled {
		sources[p.Rule] = rule
		sources[p.Skill] = skill
	} else {
		sources[p.Rule] = ""
		sources[p.Skill] = ""
	}
	if e := writeJSON(filepath.Join(root, MarkerName), Marker{Schema: MarkerSchema, Host: host, Scope: p.Scope, Version: pack.Manifest.ProductVersion, Enabled: enabled, Hashes: pack.Hashes}); e != nil {
		return nil, e
	}
	return sources, nil
}

func codexMarketplace() map[string]any {
	return map[string]any{"name": "opensocrates", "interface": map[string]any{"displayName": "OpenSocrates"}, "plugins": []any{map[string]any{"name": "opensocrates", "source": map[string]any{"source": "local", "path": "./build/generated/plugins/codex"}, "policy": map[string]any{"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}}}
}
