package compat

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/persistence"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type HookServices struct {
	Application             Application
	TranscriptAccessEnabled bool
	// SettingsRoot is read only on the explicitly enabled legacy selector path.
	SettingsRoot          string
	TrustedExplicitLocale *string
}

// CleanupExistingArtifacts is safe on the default decision path: no content,
// model, auth, process, settings mutation or installation-key creation occurs.
func CleanupExistingArtifacts(root, session string) error {
	if !identity(session) || !filepath.IsAbs(root) {
		return nil
	}
	key, err := platform.ReadFile(filepath.Join(root, "installation.key"), 32)
	if err != nil || len(key) != 32 {
		return nil
	}
	s, err := NewArtifactStore(key, "", "")
	if err != nil {
		return nil
	}
	s.SweepExpired()
	s.DeleteSession(session)
	return nil
}
func NewHookServices(root string) (*HookServices, error) {
	store, err := persistence.ExistingTurnStore(root)
	if err != nil {
		return nil, failure(diagnostics.HostUnavailable)
	}
	b, err := content.Load()
	if err != nil {
		return nil, failure(diagnostics.Verification)
	}
	artifacts, err := NewArtifactStore(store.Key(), "", "")
	if err != nil {
		return nil, err
	}
	record := func(label string) { _, _ = persistence.IncrementOutcomes(root, map[string]int64{label: 1}) }
	return &HookServices{Application: Application{Selector: &Selector{Binary: os.Getenv("OPENSOCRATES_CODEX_BINARY")}, Bundle: b, Artifacts: artifacts, OnOutcome: record}, TranscriptAccessEnabled: os.Getenv("OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS") != "off", SettingsRoot: root}, nil
}
func (h *HookServices) CleanupExisting(session string) error {
	if h.Application.Artifacts != nil {
		h.Application.Artifacts.DeleteSession(session)
	}
	return nil
}
func nativeString(m map[string]any, key string) string { s, _ := m[key].(string); return s }
func nativeIntPointer(m map[string]any, key string) (*int64, bool) {
	value, exists := m[key]
	if !exists || value == nil {
		return nil, true
	}
	n, ok := contracts.Int(value)
	return &n, ok
}
func endMarker(value any, depth int) bool {
	if depth > 4 {
		return false
	}
	switch v := value.(type) {
	case string:
		return strings.Contains(v, ArtifactEndMarker)
	case map[string]any:
		if depth >= 4 {
			return false
		}
		count := 0
		for _, child := range v {
			if count >= 128 {
				break
			}
			count++
			if endMarker(child, depth+1) {
				return true
			}
		}
	case []any:
		if depth >= 4 {
			return false
		}
		for i, child := range v {
			if i >= 256 {
				break
			}
			if endMarker(child, depth+1) {
				return true
			}
		}
	}
	return false
}
func hookContext(event, text string) map[string]any {
	return map[string]any{"hookSpecificOutput": map[string]any{"hookEventName": event, "additionalContext": text}}
}

// HandleLegacy is called only after the native adapter has validated the host
// lane and trust/disabled settings. It repeats identity and content limits and
// returns nil for literal empty stdout on every unavailable or failed path.
func (h *HookServices) HandleLegacy(raw []byte, event string) (map[string]any, error) {
	if os.Getenv(RecursionEnvironment) != "" || h.Application.Artifacts == nil {
		return nil, nil
	}
	maximum := 32768
	if event == "PostToolUse" {
		maximum = 2 << 20
	}
	if len(raw) > maximum {
		return nil, nil
	}
	value, err := contracts.Decode(raw)
	if err != nil {
		return nil, nil
	}
	m, ok := value.(map[string]any)
	if !ok || m["hook_event_name"] != event {
		return nil, nil
	}
	session := nativeString(m, "session_id")
	turn := nativeString(m, "turn_id")
	if turn == "" {
		turn = nativeString(m, "prompt_id")
	}
	if turn == "" {
		turn = session
	}
	if !identity(session) || !identity(turn) {
		return nil, nil
	}
	workspace := nativeString(m, "cwd")
	store := h.Application.Artifacts
	// Match the old workspace-first read location, retaining the same tagged
	// system-temp fallback so prior installed artifacts remain discoverable.
	if workspace != "" {
		if replacement, err := NewArtifactStore(store.key[:], "", workspace); err == nil {
			replacement.Now = store.Now
			store = replacement
		}
	}
	application := h.Application
	application.Artifacts = store
	switch event {
	case "SessionStart":
		if m["source"] == "compact" {
			store.SweepExpired()
			if a := store.Latest(session); a != nil {
				if reference, err := a.ReferenceMessage(); err == nil {
					return hookContext(event, reference), nil
				}
			}
		}
	case "UserPromptSubmit":
		prompt, ok := m["prompt"].(string)
		if !ok || !validText(prompt, MaxPromptBytes, true) || application.Bundle == nil {
			return nil, nil
		}
		handles := Handles{WorkspacePath: workspace, TranscriptAccessEnabled: h.TranscriptAccessEnabled}
		if handles.TranscriptAccessEnabled {
			handles.TranscriptPath = nativeString(m, "transcript_path")
		}
		store.SweepExpired()
		store.DeleteSupersededTurns(session, turn)
		var preference *string
		if h.SettingsRoot != "" {
			settings := (persistence.SettingsStore{Root: h.SettingsRoot}).Load()
			preference = settings.LocalePreference()
		}
		decision := application.Select(context.Background(), Request{TrustedExplicitLocale: h.TrustedExplicitLocale, StoredPreference: preference, Prompt: prompt, Catalog: application.Bundle.SelectionCatalog, Context: handles, Deadline: 30 * time.Second, ReasoningEffort: "medium"}, session, turn)
		if decision == nil {
			store.DeleteTurn(session, turn)
			return nil, nil
		}
		return hookContext(event, decision.Instructions), nil
	case "PostToolUse":
		if m["tool_name"] != "Read" {
			return nil, nil
		}
		response, present := m["tool_response"]
		if !present || response == nil || !endMarker(response, 0) {
			return nil, nil
		}
		for _, key := range []string{"tool_exit_code", "exit_code"} {
			if value, exists := m[key]; exists {
				n, ok := contracts.Int(value)
				if !ok || n != 0 {
					return nil, nil
				}
			}
		}
		input, ok := m["tool_input"].(map[string]any)
		if !ok {
			return nil, nil
		}
		offset, ok := nativeIntPointer(input, "offset")
		if !ok {
			return nil, nil
		}
		limit, ok := nativeIntPointer(input, "limit")
		if !ok {
			return nil, nil
		}
		store.RecordCompleteRead(ReadCallback{Session: session, Turn: turn, FilePath: nativeString(input, "file_path"), ToolUseID: nativeString(m, "tool_use_id"), Offset: offset, Limit: limit, EndMarkerSeen: true})
	case "Stop":
		active, _ := m["stop_hook_active"].(bool)
		if !active {
			if artifact := store.Latest(session); artifact != nil {
				read := store.HasCompleteReadReceipt(artifact)
				message := nativeString(m, "last_assistant_message")
				if len(message) > MaxResponseBytes {
					return nil, nil
				}
				lines := strings.Split(strings.TrimRight(message, "\r\n\t "), "\n")
				footer := len(lines) > 0 && strings.TrimSpace(lines[len(lines)-1]) == AttributionFooter
				if !read || !footer {
					return map[string]any{"decision": "block", "reason": artifact.GroundingRepairMessage(!read, !footer)}, nil
				}
			}
		}
		store.DeleteTurn(session, turn)
	case "SessionEnd":
		store.DeleteSession(session)
	}
	return nil, nil
}
