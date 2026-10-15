package registration

import (
	"bytes"
	"crypto/sha256"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/pelletier/go-toml/v2"
	"github.com/pelletier/go-toml/v2/unstable"
)

const settingsKey = "codex_plugin_settings"
const rawSettingsKey = "codex_plugin_source"

type configRange struct{ start, end int }

func (n *Native) configPath(root string) string {
	return filepath.Join(filepath.Dir(filepath.Dir(root)), "config.toml")
}
func pluginMap(raw []byte, id string) (map[string]any, error) {
	var config map[string]any
	if toml.Unmarshal(raw, &config) != nil {
		return nil, diagnostics.New(diagnostics.ProtocolIncompatible, "host-configuration")
	}
	plugins, ok := config["plugins"].(map[string]any)
	if !ok {
		return nil, nil
	}
	value, exists := plugins[id]
	if !exists {
		return nil, nil
	}
	plugin, ok := value.(map[string]any)
	if !ok {
		return nil, diagnostics.New(diagnostics.ProtocolIncompatible, "plugin-settings")
	}
	return plugin, nil
}
func canonicalSettings(plugin map[string]any, id string) (string, error) {
	if plugin == nil {
		return "", nil
	}
	b, e := toml.Marshal(map[string]any{"plugins": map[string]any{id: plugin}})
	if e != nil || len(b) > 128<<10 {
		return "", diagnostics.New(diagnostics.Verification, "plugin-settings")
	}
	return string(b), nil
}
func expressionKeys(node *unstable.Node) []string {
	var keys []string
	it := node.Key()
	for it.Next() {
		keys = append(keys, string(it.Node().Data))
	}
	return keys
}
func managedPrefix(keys []string, id string) bool {
	return len(keys) >= 2 && keys[0] == "plugins" && keys[1] == id
}
func expressionEnd(raw []byte, node *unstable.Node) int {
	end := int(node.Raw.Offset + node.Raw.Length)
	for end < len(raw) && raw[end] != '\n' {
		end++
	}
	if end < len(raw) {
		end++
	}
	return end
}

// managedRanges uses parsed expression ranges: text in comments, multiline
// strings and similarly named plugin identities can never select a table.
func managedRanges(raw []byte, id string) ([]configRange, string, error) {
	var parser unstable.Parser
	parser.Reset(raw)
	var current []string
	var ranges []configRange
	var source bytes.Buffer
	tableStart, tableEnd := -1, -1
	flush := func() {
		if tableStart >= 0 {
			source.Write(raw[tableStart:tableEnd])
			if tableEnd > tableStart && raw[tableEnd-1] != '\n' {
				source.WriteByte('\n')
			}
			tableStart, tableEnd = -1, -1
		}
	}
	for parser.NextExpression() {
		node := parser.Expression()
		if node.Kind == unstable.Table || node.Kind == unstable.ArrayTable {
			flush()
			current = expressionKeys(node)
			own := managedPrefix(current, id)
			if own && node.Kind == unstable.ArrayTable {
				return nil, "", diagnostics.New(diagnostics.ProtocolIncompatible, "plugin-settings")
			}
			if own {
				start := int(node.Raw.Offset)
				end := expressionEnd(raw, node)
				ranges = append(ranges, configRange{start, end})
				tableStart, tableEnd = start, end
			}
			continue
		}
		if node.Kind != unstable.KeyValue {
			continue
		}
		keys := append(append([]string{}, current...), expressionKeys(node)...)
		if managedPrefix(keys, id) {
			start := int(node.Raw.Offset)
			end := expressionEnd(raw, node)
			ranges = append(ranges, configRange{start, end})
			if tableStart >= 0 {
				tableEnd = end
			} else { // Dotted/inline declarations use the canonical scoped fallback.
				source.Reset()
			}
		}
	}
	flush()
	if parser.Error() != nil {
		return nil, "", diagnostics.New(diagnostics.ProtocolIncompatible, "host-configuration")
	}
	sort.Slice(ranges, func(i, j int) bool { return ranges[i].start < ranges[j].start })
	return ranges, source.String(), nil
}
func (n *Native) readSettings(root string) (map[string]string, error) {
	if n.Host != "codex" {
		return nil, nil
	}
	p := n.configPath(root)
	if _, e := os.Lstat(p); os.IsNotExist(e) {
		return nil, nil
	}
	raw, e := platform.ReadOwnedFile(p, 4<<20)
	if e != nil {
		return nil, e
	}
	plugin, e := pluginMap(raw, n.id())
	if e != nil {
		return nil, e
	}
	settings, e := canonicalSettings(plugin, n.id())
	if e != nil {
		return nil, e
	}
	if settings == "" {
		return nil, nil
	}
	_, source, e := managedRanges(raw, n.id())
	if e != nil {
		return nil, e
	}
	if source != "" {
		scoped, e := pluginMap([]byte(source), n.id())
		if e != nil {
			source = ""
		} else if canonical, e := canonicalSettings(scoped, n.id()); e != nil || canonical != settings {
			source = ""
		}
	}
	if source == "" {
		source = settings
	}
	return map[string]string{settingsKey: settings, rawSettingsKey: source}, nil
}
func (n *Native) restoreSettings(root string, want map[string]string) error {
	if n.Host != "codex" || want[settingsKey] == "" {
		return nil
	}
	path := n.configPath(root)
	raw, e := platform.ReadOwnedFile(path, 4<<20)
	if e != nil {
		return e
	}
	plugin, e := pluginMap(raw, n.id())
	if e != nil {
		return e
	}
	current, e := canonicalSettings(plugin, n.id())
	if e != nil {
		return e
	}
	if current == want[settingsKey] {
		return nil
	}
	// Only the known enable=true entry emitted by plugin add may be replaced.
	// Changed custom plugin settings are preserved for manual recovery.
	if plugin != nil {
		if len(plugin) != 1 || plugin["enabled"] != true {
			return diagnostics.New(diagnostics.RollbackIncomplete, "modified-plugin-settings")
		}
	}
	ranges, _, e := managedRanges(raw, n.id())
	if e != nil {
		return e
	}
	if plugin != nil && len(ranges) == 0 {
		return diagnostics.New(diagnostics.RollbackIncomplete, "inline-plugin-settings")
	}
	var candidate bytes.Buffer
	at := 0
	for _, r := range ranges {
		if r.start < at || r.end > len(raw) {
			return diagnostics.New(diagnostics.Verification, "plugin-settings")
		}
		candidate.Write(raw[at:r.start])
		at = r.end
	}
	candidate.Write(raw[at:])
	if candidate.Len() > 0 && !strings.HasSuffix(candidate.String(), "\n") {
		candidate.WriteByte('\n')
	}
	candidate.WriteByte('\n')
	candidate.WriteString(want[rawSettingsKey])
	proposed := candidate.Bytes()
	restored, e := pluginMap(proposed, n.id())
	if e != nil {
		return e
	}
	canonical, e := canonicalSettings(restored, n.id())
	if e != nil || canonical != want[settingsKey] {
		return diagnostics.New(diagnostics.RollbackIncomplete, "plugin-settings")
	}
	// All unrelated source bytes remain in the same order and spelling; no whole
	// config marshal, credential capture or host hook trust edit occurs here.
	expected := sha256.Sum256(raw)
	again, e := platform.ReadOwnedFile(path, 4<<20)
	if e != nil {
		return e
	}
	actual := sha256.Sum256(again)
	if expected != actual {
		return diagnostics.New(diagnostics.RollbackIncomplete, "modified-configuration")
	}
	return platform.AtomicWrite(path, proposed, 0600)
}
func settingsEquivalent(a, b map[string]string) bool {
	want, defined := b[settingsKey]
	return !defined || a[settingsKey] == want
}
func (n *Native) RestoreOwnedSettings(ctxRoot string, state State) error {
	return n.restoreSettings(ctxRoot, state.Data)
}
