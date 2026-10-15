package management

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/compat"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/pelletier/go-toml/v2"
	"github.com/pelletier/go-toml/v2/unstable"
)

const codexTrustPrefix = "opensocrates@opensocrates:hooks/hooks.json:"
const maxCodexConfigBytes = 16 << 20

var codexTrustEvents = []string{"pre_tool_use", "post_tool_use", "pre_compact", "session_start", "session_end", "user_prompt_submit", "stop"}

type TrustReset struct {
	Contents      []byte
	RemovedEvents []string
}
type trustSpan struct{ start, end int }

func trustFailure() error { return diagnostics.New(diagnostics.Verification, "codex-trust-reset") }

// StripCodexTrust removes only the seven canonical v1 hook-state syntax spans.
// The actual TOML parser resolves Unicode escapes and enforces TOML validity;
// its AST supplies original byte offsets, preserving every unrelated byte,
// comment, BOM and newline rather than reserializing a user's configuration.
func StripCodexTrust(original []byte) (TrustReset, error) {
	if len(original) > maxCodexConfigBytes || !utf8.Valid(original) {
		return TrustReset{}, trustFailure()
	}
	bom := []byte{}
	source := original
	if bytes.HasPrefix(source, []byte{239, 187, 191}) {
		bom = source[:3]
		source = source[3:]
	}
	var document map[string]any
	if toml.Unmarshal(source, &document) != nil {
		return TrustReset{}, trustFailure()
	}
	var parser unstable.Parser
	parser.Reset(source)
	var table []string
	var spans []trustSpan
	found := map[string]bool{}
	target := ""
	hashSeen := false
	finish := func() bool { return target == "" || hashSeen }
	for parser.NextExpression() {
		node := parser.Expression()
		if node.Kind == unstable.Comment {
			continue
		}
		keys := []string{}
		it := node.Key()
		for it.Next() {
			keys = append(keys, string(it.Node().Data))
		}
		if node.Kind == unstable.Table || node.Kind == unstable.ArrayTable {
			if !finish() {
				return TrustReset{}, trustFailure()
			}
			target = ""
			hashSeen = false
			table = keys
			if len(keys) >= 3 && keys[0] == "hooks" && keys[1] == "state" && strings.HasPrefix(keys[2], codexTrustPrefix) {
				if node.Kind != unstable.Table || len(keys) != 3 {
					return TrustReset{}, trustFailure()
				}
				event := strings.TrimPrefix(keys[2], codexTrustPrefix)
				event = strings.TrimSuffix(event, ":0:0")
				if keys[2] != codexTrustPrefix+event+":0:0" || !containsString(codexTrustEvents, event) || found[event] {
					return TrustReset{}, trustFailure()
				}
				first := node.Child()
				start := int(first.Raw.Offset) - 1
				encoded, _ := json.Marshal(keys[2])
				syntax := []byte("[hooks.state." + string(encoded) + "]")
				if start < 0 || start+len(syntax) > len(source) || !bytes.Equal(source[start:start+len(syntax)], syntax) {
					return TrustReset{}, trustFailure()
				}
				spans = append(spans, trustSpan{start, start + len(syntax)})
				target = event
				found[event] = true
			}
			continue
		}
		if target != "" {
			value := node.Value()
			raw := parser.Raw(value.Raw)
			if len(keys) != 1 || keys[0] != "trusted_hash" || hashSeen || value.Kind != unstable.String || len(raw) < 2 || raw[0] != '"' || bytes.HasPrefix(raw, []byte(`"""`)) || bytes.ContainsAny(raw, "\r\n") {
				return TrustReset{}, trustFailure()
			}
			hashSeen = true
			spans = append(spans, trustSpan{int(node.Raw.Offset), int(node.Raw.Offset + node.Raw.Length)})
		} else {
			path := append(append([]string{}, table...), keys...)
			if len(path) >= 3 && path[0] == "hooks" && path[1] == "state" && strings.HasPrefix(path[2], codexTrustPrefix) {
				return TrustReset{}, trustFailure()
			}
		}
	}
	if parser.Error() != nil || !finish() {
		return TrustReset{}, trustFailure()
	}
	// Inline/dotted forms are not eligible for mutation even if the semantic
	// document has the same values. Require every matching semantic entry to be
	// accounted for by one exact canonical header above.
	if hooks, ok := document["hooks"].(map[string]any); ok {
		if state, ok := hooks["state"].(map[string]any); ok {
			for key := range state {
				if strings.HasPrefix(key, codexTrustPrefix) {
					event := strings.TrimSuffix(strings.TrimPrefix(key, codexTrustPrefix), ":0:0")
					if !found[event] || key != codexTrustPrefix+event+":0:0" {
						return TrustReset{}, trustFailure()
					}
				}
			}
		}
	}
	result := TrustReset{Contents: append([]byte{}, bom...), RemovedEvents: []string{}}
	cursor := 0
	for _, span := range spans {
		if span.start < cursor || span.end > len(source) {
			return TrustReset{}, trustFailure()
		}
		result.Contents = append(result.Contents, source[cursor:span.start]...)
		cursor = span.end
	}
	result.Contents = append(result.Contents, source[cursor:]...)
	for _, event := range codexTrustEvents {
		if found[event] {
			result.RemovedEvents = append(result.RemovedEvents, event)
		}
	}
	var candidate map[string]any
	if toml.Unmarshal(result.Contents[len(bom):], &candidate) != nil {
		return TrustReset{}, trustFailure()
	}
	return result, nil
}
func containsString(values []string, value string) bool {
	for _, v := range values {
		if v == value {
			return true
		}
	}
	return false
}
func (m *Manager) validateTrustConfig(ctx context.Context, contents []byte) error {
	binary := "codex"
	lookup := m.LookupEnv
	if lookup == nil {
		lookup = os.Getenv
	}
	if configured := lookup("CODEX_BIN"); configured != "" {
		binary = configured
	}
	if m.TrustConfigValidator != nil {
		return m.TrustConfigValidator(ctx, binary, contents)
	}
	return compat.ValidateConfig(ctx, binary, contents)
}

// prepareTrustReset appends a config replacement to the shared transaction.
// Validation runs in a private, unauthenticated Codex home before any purge
// mutation; the lifecycle engine rechecks the bound original immediately
// before replacement and restores it on registration or verification failure.
func (m *Manager) prepareTrustReset(ctx context.Context, p Paths, scratch string, plan *lifecycle.Plan) (TrustReset, error) {
	target := filepath.Join(p.Base, "config.toml")
	before, e := lifecycle.Inspect(target)
	if e != nil {
		return TrustReset{}, e
	}
	if !before.Exists {
		return TrustReset{RemovedEvents: []string{}}, nil
	}
	original, e := platform.ReadOwnedFile(target, maxCodexConfigBytes)
	if e != nil {
		return TrustReset{}, e
	}
	reset, e := StripCodexTrust(original)
	if e != nil {
		return TrustReset{}, e
	}
	if e := m.validateTrustConfig(ctx, original); e != nil {
		return TrustReset{}, e
	}
	if len(reset.RemovedEvents) == 0 {
		current, e := lifecycle.Inspect(target)
		if e != nil {
			return TrustReset{}, e
		}
		if !lifecycle.Equal(current, before) {
			return TrustReset{}, trustFailure()
		}
		return reset, nil
	}
	if e := m.validateTrustConfig(ctx, reset.Contents); e != nil {
		return TrustReset{}, e
	}
	source := filepath.Join(scratch, "config-candidate.toml")
	mode := os.FileMode(before.Entries[0].Mode)
	if e := platform.AtomicWrite(source, reset.Contents, mode); e != nil {
		return TrustReset{}, e
	}
	plan.Mutations = append(plan.Mutations, lifecycle.Mutation{Target: target, Source: source, Expected: &before})
	return reset, nil
}
