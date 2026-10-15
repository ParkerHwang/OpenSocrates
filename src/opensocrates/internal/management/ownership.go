package management

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/transport"
)

type Paths struct{ Base, Root, Rule, Skill, Scope string }

func (m *Manager) Paths(host, workspace string) (Paths, error) {
	switch host {
	case "codex":
		base := m.Env("CODEX_HOME", filepath.Join(m.Home, ".codex"))
		return Paths{Base: base, Root: filepath.Join(base, "managed-marketplaces", "opensocrates"), Scope: "global"}, nil
	case "claude":
		if workspace != "" {
			return Paths{}, diagnostics.New(diagnostics.Unsupported, "scope")
		}
		base := m.Env("CLAUDE_CONFIG_DIR", filepath.Join(m.Home, ".claude"))
		return Paths{Base: base, Root: filepath.Join(base, "managed-marketplaces", "opensocrates-macos"), Scope: "global"}, nil
	case "antigravity":
		base := m.Env("ANTIGRAVITY_CONFIG_DIR", filepath.Join(m.Home, ".gemini", "config"))
		scope := "global"
		if workspace != "" {
			if !filepath.IsAbs(workspace) {
				return Paths{}, diagnostics.New(diagnostics.Verification, "scope")
			}
			i, e := os.Lstat(workspace)
			if e != nil || !i.IsDir() || platform.GuardOwned(workspace) != nil {
				return Paths{}, diagnostics.New(diagnostics.Permission, "scope")
			}
			base = filepath.Join(workspace, ".agents")
			scope = "workspace"
		}
		return Paths{Base: base, Root: filepath.Join(base, ".opensocrates-managed", "antigravity"), Rule: filepath.Join(base, "rules", "opensocrates.md"), Skill: filepath.Join(base, "skills", "opensocrates"), Scope: scope}, nil
	}
	return Paths{}, diagnostics.New(diagnostics.Unsupported, "host")
}
func antiPhysical(p Paths, name string, enabled bool) (string, error) {
	if !transport.SafeRelative(name) {
		return "", diagnostics.New(diagnostics.Verification, "ownership")
	}
	if name == "release-manifest.json" {
		return filepath.Join(p.Root, name), nil
	}
	if name == ".agents/rules/opensocrates.md" {
		if enabled {
			return p.Rule, nil
		}
		return filepath.Join(p.Root, "disabled", "rule.md"), nil
	}
	prefix := ".agents/skills/opensocrates/"
	if !strings.HasPrefix(name, prefix) {
		return "", diagnostics.New(diagnostics.Verification, "ownership")
	}
	base := p.Skill
	if !enabled {
		base = filepath.Join(p.Root, "disabled", "skill")
	}
	return filepath.Join(base, filepath.FromSlash(strings.TrimPrefix(name, prefix))), nil
}
func owned(p Paths, host string) (*Marker, map[string]lifecycle.Snapshot, error) {
	root, e := lifecycle.Inspect(p.Root)
	if e != nil {
		return nil, nil, e
	}
	targets := map[string]lifecycle.Snapshot{p.Root: root}
	if !root.Exists {
		if host == "antigravity" {
			for _, path := range []string{p.Rule, p.Skill} {
				s, e := lifecycle.Inspect(path)
				if e != nil {
					return nil, nil, e
				}
				if s.Exists {
					return nil, nil, diagnostics.New(diagnostics.Verification, "foreign-target")
				}
				targets[path] = s
			}
		}
		return nil, targets, nil
	}
	if host == "codex" {
		b, e := platform.ReadOwnedFile(filepath.Join(p.Root, MarkerName), 8<<20)
		if e != nil {
			return nil, nil, e
		}
		var marker map[string]any
		if _, e := contracts.Decode(b); e != nil {
			return nil, nil, diagnostics.New(diagnostics.Verification, "ownership")
		}
		if json.Unmarshal(b, &marker) != nil || len(marker) != 3 || marker["schemaVersion"] != float64(1) || marker["marketplaceName"] != "opensocrates" || marker["pluginName"] != "opensocrates" {
			return nil, nil, diagnostics.New(diagnostics.Verification, "ownership")
		}
		plugin := filepath.Join(p.Root, "build", "generated", "plugins", "codex")
		pack, e := transport.Verify(plugin, "codex", "", "")
		if e != nil {
			return nil, nil, e
		}
		b, e = platform.ReadOwnedFile(filepath.Join(p.Root, ".agents/plugins/marketplace.json"), 8<<20)
		if e != nil {
			return nil, nil, e
		}
		marketValue, e := contracts.Decode(b)
		if e != nil {
			return nil, nil, diagnostics.New(diagnostics.Verification, "marketplace")
		}
		actualMarket, e := contracts.CanonicalCompact(marketValue)
		if e != nil {
			return nil, nil, diagnostics.New(diagnostics.Verification, "marketplace")
		}
		expectedMarket, e := contracts.CanonicalCompact(codexMarketplace())
		if e != nil || string(actualMarket) != string(expectedMarket) {
			return nil, nil, diagnostics.New(diagnostics.Verification, "foreign-marketplace")
		}
		var market map[string]json.RawMessage
		if json.Unmarshal(b, &market) != nil {
			return nil, nil, diagnostics.New(diagnostics.Verification, "marketplace")
		}
		var name string
		json.Unmarshal(market["name"], &name)
		var plugins []map[string]json.RawMessage
		json.Unmarshal(market["plugins"], &plugins)
		if name != "opensocrates" || len(plugins) != 1 {
			return nil, nil, diagnostics.New(diagnostics.Verification, "marketplace")
		}
		var pn string
		var source struct {
			Source string `json:"source"`
			Path   string `json:"path"`
		}
		json.Unmarshal(plugins[0]["name"], &pn)
		json.Unmarshal(plugins[0]["source"], &source)
		if pn != "opensocrates" || source.Source != "local" || source.Path != "./build/generated/plugins/codex" {
			return nil, nil, diagnostics.New(diagnostics.Verification, "marketplace")
		}
		expected := map[string]string{MarkerName: files(root)[MarkerName], ".agents/plugins/marketplace.json": files(root)[".agents/plugins/marketplace.json"]}
		for name, hash := range pack.Hashes {
			expected["build/generated/plugins/codex/"+name] = hash
		}
		if !eqHashes(expected, files(root)) {
			return nil, nil, diagnostics.New(diagnostics.Verification, "owned-modified")
		}
		return &Marker{Host: host, Scope: p.Scope, Version: pack.Manifest.ProductVersion, Enabled: true, Hashes: expected}, targets, nil
	}
	marker, e := readMarker(p.Root, host, p.Scope)
	if e != nil {
		return nil, nil, e
	}
	for name, hash := range marker.Hashes {
		if !transport.SafeRelative(name) {
			return nil, nil, diagnostics.New(diagnostics.Verification, "ownership")
		}
		h, e := transport.Digest(hash)
		if e != nil {
			return nil, nil, e
		}
		marker.Hashes[name] = h
	}
	if host == "claude" {
		actual := files(root)
		delete(actual, MarkerName)
		if !eqHashes(actual, marker.Hashes) {
			return nil, nil, diagnostics.New(diagnostics.Verification, "owned-modified")
		}
		if _, e := transport.Verify(filepath.Join(p.Root, "plugin"), "claude", marker.Version, ""); e != nil {
			return nil, nil, e
		}
		return &marker, targets, nil
	}
	if host != "antigravity" {
		return nil, nil, diagnostics.New(diagnostics.Unsupported, "ownership")
	}
	if _, e := os.Lstat(filepath.Join(p.Base, "plugins", "opensocrates")); e == nil {
		return nil, nil, diagnostics.New(diagnostics.Verification, "legacy-collision")
	}
	actual := map[string]string{}
	for name := range marker.Hashes {
		path, e := antiPhysical(p, name, marker.Enabled)
		if e != nil {
			return nil, nil, e
		}
		hash, e := platform.SHA256File(path, lifecycle.MaxFileBytes)
		if e != nil {
			return nil, nil, e
		}
		actual[name] = hash
	}
	if !eqHashes(actual, marker.Hashes) {
		return nil, nil, diagnostics.New(diagnostics.Verification, "owned-modified")
	}
	expectedStore := map[string]string{"release-manifest.json": marker.Hashes["release-manifest.json"]}
	expectedSkill := map[string]string{}
	for name, h := range marker.Hashes {
		prefix := ".agents/skills/opensocrates/"
		if strings.HasPrefix(name, prefix) {
			rel := strings.TrimPrefix(name, prefix)
			expectedSkill[rel] = h
			if !marker.Enabled {
				expectedStore["disabled/skill/"+rel] = h
			}
		}
	}
	if !marker.Enabled {
		expectedStore["disabled/rule.md"] = marker.Hashes[".agents/rules/opensocrates.md"]
	}
	store := files(root)
	delete(store, MarkerName)
	if !eqHashes(store, expectedStore) {
		return nil, nil, diagnostics.New(diagnostics.Verification, "owned-modified")
	}
	for _, path := range []string{p.Rule, p.Skill} {
		s, e := lifecycle.Inspect(path)
		if e != nil {
			return nil, nil, e
		}
		targets[path] = s
		if !marker.Enabled && s.Exists {
			return nil, nil, diagnostics.New(diagnostics.Verification, "foreign-target")
		}
	}
	skill := p.Skill
	if !marker.Enabled {
		skill = filepath.Join(p.Root, "disabled", "skill")
	}
	s, e := lifecycle.Inspect(skill)
	if e != nil {
		return nil, nil, e
	}
	if !eqHashes(files(s), expectedSkill) {
		return nil, nil, diagnostics.New(diagnostics.Verification, "owned-modified")
	}
	return &marker, targets, nil
}
