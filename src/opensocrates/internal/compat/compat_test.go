package compat

import (
	"bufio"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// The Go test executable doubles as a native, deterministic app-server. No
// Python, shell, npm, network or credentials are required by protocol tests.
func TestMain(m *testing.M) {
	if os.Getenv(RecursionEnvironment) == "1" {
		if len(os.Args) == 2 && os.Args[1] == "--version" {
			fmt.Println("codex-cli " + CodexVersion)
			os.Exit(0)
		}
		if len(os.Args) == 3 && os.Args[1] == "app-server" && os.Args[2] == "--help" {
			fmt.Println("Usage: codex app-server [OPTIONS]\n  --listen <TRANSPORT_URL>\n  --strict-config")
			os.Exit(0)
		}
		for _, a := range os.Args[1:] {
			if a == "app-server" {
				fixtureServer()
				os.Exit(0)
			}
		}
	}
	os.Exit(m.Run())
}
func fixtureServer() {
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 4096), 1<<20)
	send := func(v any) { b, _ := json.Marshal(v); fmt.Println(string(b)) }
	for scanner.Scan() {
		var m wireMessage
		if json.Unmarshal(scanner.Bytes(), &m) != nil {
			return
		}
		switch m.Method {
		case "initialize":
			var p struct {
				ClientInfo struct {
					Name string `json:"name"`
				} `json:"clientInfo"`
				Capabilities struct {
					Experimental bool `json:"experimentalApi"`
				} `json:"capabilities"`
			}
			if json.Unmarshal(m.Params, &p) != nil {
				return
			}
			if p.ClientInfo.Name == "opensocrates_config_validation" {
				fixtureConfigInitialize(m, send)
				continue
			}
			if !p.Capabilities.Experimental {
				return
			}
			send(map[string]any{"id": json.RawMessage(m.ID), "result": map[string]string{"userAgent": "codex-cli/" + CodexVersion}})
		case "account/read":
			send(map[string]any{"id": json.RawMessage(m.ID), "result": map[string]any{"account": map[string]string{"type": "chatgpt"}}})
		case "thread/start":
			var p map[string]json.RawMessage
			_ = json.Unmarshal(m.Params, &p)
			if string(p["environments"]) != "[]" || string(p["ephemeral"]) != "true" || string(p["approvalPolicy"]) != `"never"` || string(p["sandbox"]) != `"read-only"` {
				return
			}
			send(map[string]any{"id": json.RawMessage(m.ID), "result": map[string]any{"thread": map[string]string{"id": "fixture-thread"}}})
		case "turn/start":
			var wire struct {
				Policy struct {
					Type    string `json:"type"`
					Network bool   `json:"networkAccess"`
				} `json:"sandboxPolicy"`
				Effort string `json:"effort"`
			}
			if json.Unmarshal(m.Params, &wire) != nil || wire.Policy.Type != "readOnly" || wire.Policy.Network || wire.Effort != "medium" {
				return
			}
			send(map[string]any{"id": json.RawMessage(m.ID), "result": map[string]any{"turn": map[string]string{"id": "fixture-turn"}}})
			if strings.Contains(string(m.Params), "__hang__") {
				for scanner.Scan() {
					var stop wireMessage
					_ = json.Unmarshal(scanner.Bytes(), &stop)
					if stop.Method == "turn/interrupt" {
						return
					}
				}
				return
			}
			if strings.Contains(string(m.Params), "__approval__") {
				send(map[string]any{"id": "approval-1", "method": "item/commandExecution/requestApproval", "params": map[string]string{"threadId": "fixture-thread", "turnId": "fixture-turn"}})
				if !scanner.Scan() {
					return
				}
				var denied map[string]json.RawMessage
				_ = json.Unmarshal(scanner.Bytes(), &denied)
				if len(denied["error"]) == 0 {
					return
				}
			}
			if strings.Contains(string(m.Params), "__context__") {
				send(map[string]any{"id": "tool-1", "method": "item/tool/call", "params": map[string]any{"threadId": "fixture-thread", "turnId": "fixture-turn", "callId": "call-1", "namespace": nil, "tool": "read_context", "arguments": map[string]any{"operation": "read_workspace_file", "relative_path": "data.txt", "offset": 0}}})
				if !scanner.Scan() {
					return
				}
				var tool struct {
					Result struct {
						Success bool `json:"success"`
					} `json:"result"`
				}
				_ = json.Unmarshal(scanner.Bytes(), &tool)
				if !tool.Result.Success {
					return
				}
			}
			text := `{"intervene":true,"selected_reasoning_systems":["first-principles"],"instructions":"canonical_assembly_required"}`
			if strings.Contains(string(m.Params), "__invalid__") {
				text = `{"intervene":true,"selected_reasoning_systems":null,"instructions":"private text"}`
			}
			if strings.Contains(string(m.Params), "__oversize__") {
				text = strings.Repeat("x", MaxResponseBytes+1)
			}
			// Completion may legally precede the turn/start response in other fixtures;
			// this fixture deliberately includes unrelated notifications in the lane.
			send(map[string]any{"method": "item/agentMessage/delta", "params": map[string]string{"threadId": "fixture-thread", "turnId": "fixture-turn", "delta": "discarded raw output"}})
			send(map[string]any{"method": "item/completed", "params": map[string]any{"threadId": "fixture-thread", "turnId": "fixture-turn", "item": map[string]string{"id": "message-1", "type": "agentMessage", "text": text}}})
			status := "completed"
			if strings.Contains(string(m.Params), "__failed__") {
				status = "failed"
			}
			send(map[string]any{"method": "turn/completed", "params": map[string]any{"threadId": "fixture-thread", "turn": map[string]string{"id": "fixture-turn", "status": status}}})
		case "turn/interrupt":
			return
		}
	}
}
func privateDirectory(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	if os.Chmod(dir, 0700) != nil {
		t.Fatal("private test dir unavailable")
	}
	return dir
}
func selectorFixture(t *testing.T) (*Selector, Request) {
	t.Helper()
	if runtime.GOOS == "windows" {
		t.Skip("legacy auth/context explicitly POSIX only")
	}
	home := privateDirectory(t)
	if os.WriteFile(filepath.Join(home, "auth.json"), []byte(`{"tokens":{"access_token":"synthetic-only"}}`), 0600) != nil {
		t.Fatal("fixture auth unavailable")
	}
	binary, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	s := &Selector{Binary: binary, CodexHome: home}
	t.Cleanup(s.Close)
	return s, Request{Prompt: "Select a useful method", Catalog: `{"content_revision":1,"entries":[]}`, Context: Handles{TranscriptAccessEnabled: true}, Deadline: 3 * time.Second, ReasoningEffort: "medium"}
}
func TestNativeProtocolSuccessful(t *testing.T) {
	s, r := selectorFixture(t)
	c, err := s.Select(context.Background(), r)
	if err != nil || c == nil || !c.Intervene || len(c.SelectedReasoningSystems) != 1 {
		t.Fatalf("native protocol: %v %v", c, err)
	}
}
func TestNativeProtocolBoundaries(t *testing.T) {
	for _, prompt := range []string{"__invalid__", "__failed__", "__oversize__"} {
		t.Run(prompt, func(t *testing.T) {
			s, r := selectorFixture(t)
			r.Prompt = prompt
			c, err := s.Select(context.Background(), r)
			if err == nil || c != nil {
				t.Fatal("untrusted/failed output accepted")
			}
			if strings.Contains(err.Error(), "private text") {
				t.Fatal("content in error")
			}
		})
	}
}
func TestNativeProtocolDeniesApprovals(t *testing.T) {
	s, r := selectorFixture(t)
	r.Prompt = "__approval__"
	if c, err := s.Select(context.Background(), r); err != nil || c == nil {
		t.Fatalf("approval denial: %v", err)
	}
}
func TestNativeProtocolReadTool(t *testing.T) {
	s, r := selectorFixture(t)
	dir := privateDirectory(t)
	_ = os.WriteFile(filepath.Join(dir, "data.txt"), []byte("한글 bounded context"), 0600)
	r.Context.WorkspacePath = dir
	r.Prompt = "__context__"
	if c, err := s.Select(context.Background(), r); err != nil || c == nil {
		t.Fatalf("dynamic read tool: %v", err)
	}
}
func TestSelectorDeadlineAndClose(t *testing.T) {
	s, r := selectorFixture(t)
	r.Prompt = "__hang__"
	r.Deadline = time.Second
	started := time.Now()
	c, err := s.Select(context.Background(), r)
	if err == nil || c != nil || time.Since(started) > 2*time.Second {
		t.Fatalf("deadline cleanup: %v elapsed %v", err, time.Since(started))
	}
	s.Close()
	if c, err = s.Select(context.Background(), r); err == nil || c != nil {
		t.Fatal("closed selector accepted turn")
	}
}
func TestSelectorExplicitCancellation(t *testing.T) {
	s, r := selectorFixture(t)
	r.Prompt = "__hang__"
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { _, err := s.Select(ctx, r); done <- err }()
	time.Sleep(100 * time.Millisecond)
	cancel()
	select {
	case err := <-done:
		if err == nil {
			t.Fatal("canceled selector accepted turn")
		}
	case <-time.After(time.Second):
		t.Fatal("child not canceled")
	}
}
func TestSelectorIsolation(t *testing.T) {
	root := privateDirectory(t)
	env, workspace, err := isolatedEnvironment(root)
	if err != nil {
		t.Fatal(err)
	}
	joined := strings.Join(env, "\n")
	if strings.Contains(joined, "OPENAI_API_KEY") || !strings.Contains(joined, RecursionEnvironment+"=1") || filepath.Dir(workspace) != root {
		t.Fatal("parent environment exposed")
	}
	args := strings.Join(configArgs(env), " ")
	for _, name := range []string{"hooks", "plugins", "shell_tool", "multi_agent"} {
		if !strings.Contains(args, "features."+name+"=false") {
			t.Fatal("unbounded feature enabled")
		}
	}
	if strings.Contains(args, "shell_environment_policy.set.CODEX_HOME") {
		t.Fatal("credential home exposed to tools")
	}
}
func TestSelectorRecursion(t *testing.T) {
	s, r := selectorFixture(t)
	t.Setenv(RecursionEnvironment, "1")
	if c, err := s.Select(context.Background(), r); err == nil || c != nil {
		t.Fatal("recursive selector accepted")
	}
}
func TestPinnedProtocolFixture(t *testing.T) {
	raw, err := os.ReadFile("testdata/protocol-completed.jsonl")
	if err != nil {
		t.Fatal(err)
	}
	scanner := bufio.NewScanner(strings.NewReader(string(raw)))
	count := 0
	for scanner.Scan() {
		var m wireMessage
		if _, err = contracts.Decode(scanner.Bytes()); err != nil {
			t.Fatal("invalid pinned fixture")
		}
		if json.Unmarshal(scanner.Bytes(), &m) != nil {
			t.Fatal("unreadable fixture")
		}
		if m.Method == "item/completed" {
			var p struct {
				Item struct{ Text string } `json:"item"`
			}
			_ = json.Unmarshal(m.Params, &p)
			if _, err = DecodeCandidate([]byte(p.Item.Text)); err != nil {
				t.Fatal("candidate wire mismatch")
			}
		}
		count++
	}
	if scanner.Err() != nil || count != 6 {
		t.Fatal("incomplete protocol fixture")
	}
}
func TestCandidateUnicodeNullPrecision(t *testing.T) {
	good := `{"intervene":false,"selected_reasoning_systems":[],"instructions":""}`
	if _, err := DecodeCandidate([]byte(good)); err != nil {
		t.Fatal(err)
	}
	for _, raw := range []string{`{"intervene":null,"selected_reasoning_systems":[],"instructions":""}`, `{"intervene":false,"selected_reasoning_systems":null,"instructions":""}`, `{"intervene":false,"selected_reasoning_systems":[],"instructions":"","other":9007199254740993}`, `{"intervene":false,"intervene":false,"selected_reasoning_systems":[],"instructions":""}`, `{"intervene":true,"selected_reasoning_systems":["first-principles","first-principles"],"instructions":"x"}`, `{"intervene":true,"selected_reasoning_systems":["first-principles"],"instructions":"\ud800"}`} {
		if _, err := DecodeCandidate([]byte(raw)); err == nil {
			t.Fatal("malformed candidate accepted")
		}
	}
	if Locale("한글") != "ko" || Locale("가a") != "en" {
		t.Fatal("locale policy changed")
	}
}

func contextCall(a *ContextAccessor, args map[string]any) map[string]any {
	p, _ := json.Marshal(map[string]any{"tool": "read_context", "namespace": nil, "arguments": args})
	return a.Dispatch(p)
}
func TestContextPrivacyTraversalAndBudget(t *testing.T) {
	if !contextAvailable() {
		t.Skip("POSIX context")
	}
	dir := privateDirectory(t)
	_ = os.WriteFile(filepath.Join(dir, "data.txt"), []byte(strings.Repeat("한", MaxContextReadBytes)), 0600)
	_ = os.Symlink(filepath.Join(dir, "data.txt"), filepath.Join(dir, "link"))
	a := NewContextAccessor(Handles{WorkspacePath: dir, TranscriptPath: filepath.Join(dir, "data.txt"), TranscriptAccessEnabled: false})
	if len(a.Operations()) != 2 {
		t.Fatal("transcript opt out bypassed")
	}
	for _, path := range []string{"../data.txt", "/data.txt", "link"} {
		if contextCall(a, map[string]any{"operation": "read_workspace_file", "relative_path": path})["success"] != false {
			t.Fatal("escaped authorized root")
		}
	}
	for i := 0; i < MaxContextCalls; i++ {
		contextCall(a, map[string]any{"operation": "read_workspace_file", "relative_path": "data.txt"})
	}
	calls, n := a.Usage()
	if calls != 8 || n > MaxContextTotalBytes {
		t.Fatal("context budget not enforced")
	}
	if contextCall(a, map[string]any{"operation": "read_workspace_file", "relative_path": "data.txt"})["success"] != false {
		t.Fatal("call budget exceeded")
	}
}
func TestContextRejectsInteriorInvalidUTF8(t *testing.T) {
	if !contextAvailable() {
		t.Skip("POSIX context")
	}
	dir := privateDirectory(t)
	_ = os.WriteFile(filepath.Join(dir, "bad"), []byte{0xff}, 0600)
	a := NewContextAccessor(Handles{WorkspacePath: dir})
	if contextCall(a, map[string]any{"operation": "read_workspace_file", "relative_path": "bad"})["success"] != false {
		t.Fatal("invalid UTF8 changed to text")
	}
}
func TestContextRejectsWrongNumericTypesAndUnknownFields(t *testing.T) {
	if !contextAvailable() {
		t.Skip("POSIX context")
	}
	dir := privateDirectory(t)
	_ = os.WriteFile(filepath.Join(dir, "data.txt"), []byte("text"), 0600)
	for _, suffix := range []string{`"offset":true`, `"offset":null`, `"offset":9007199254740993`, `"offset":0.5`, `"offset":0,"write":true`} {
		a := NewContextAccessor(Handles{WorkspacePath: dir})
		raw := json.RawMessage(`{"namespace":null,"tool":"read_context","arguments":{"operation":"read_workspace_file","relative_path":"data.txt",` + suffix + `}}`)
		if a.Dispatch(raw)["success"] != false {
			t.Fatal("invalid context number or capability accepted")
		}
	}
}
func TestContextUTF8ByteOffsets(t *testing.T) {
	if !contextAvailable() {
		t.Skip("POSIX context")
	}
	dir := privateDirectory(t)
	_ = os.WriteFile(filepath.Join(dir, "data.txt"), []byte(strings.Repeat("a", MaxContextReadBytes-1)+"한글"), 0600)
	a := NewContextAccessor(Handles{WorkspacePath: dir})
	first := contextCall(a, map[string]any{"operation": "read_workspace_file", "relative_path": "data.txt"})
	if first["success"] != true {
		t.Fatal("valid bounded read rejected")
	}
	items := first["contentItems"].([]any)
	item := items[0].(map[string]any)
	value, err := contracts.Decode([]byte(item["text"].(string)))
	if err != nil {
		t.Fatal(err)
	}
	data := value.(map[string]any)["untrusted_data"].(map[string]any)
	offset, ok := contracts.Int(data["next_offset"])
	if !ok || offset != MaxContextReadBytes-1 {
		t.Fatal("UTF8 chunk split changed byte offset")
	}
	second := contextCall(a, map[string]any{"operation": "read_workspace_file", "relative_path": "data.txt", "offset": offset})
	if second["success"] != true {
		t.Fatal("UTF8 next chunk rejected")
	}
}
func TestAuthPermissionsAndSymlink(t *testing.T) {
	if !contextAvailable() {
		t.Skip("POSIX auth")
	}
	home := privateDirectory(t)
	auth := filepath.Join(home, "auth.json")
	_ = os.WriteFile(auth, []byte("{}"), 0644)
	if _, err := existingOAuth(home); err == nil {
		t.Fatal("shared credential accepted")
	}
	_ = os.Remove(auth)
	_ = os.Symlink(filepath.Join(home, "foreign"), auth)
	if _, err := existingOAuth(home); err == nil {
		t.Fatal("credential symlink accepted")
	}
}

func artifactFixture(t *testing.T) (*ArtifactStore, *content.Bundle, *Artifact) {
	t.Helper()
	b, err := content.Load()
	if err != nil {
		t.Fatal(err)
	}
	s, err := NewArtifactStore([]byte(strings.Repeat("k", 32)), filepath.Join(privateDirectory(t), "artifacts"), "")
	if err != nil {
		t.Fatal(err)
	}
	a, err := s.Create("session-private", "turn-private", []string{b.IDs[0]}, "ko", b)
	if err != nil {
		t.Fatal(err)
	}
	return s, b, a
}
func TestArtifactsCanonicalContentAndReceipt(t *testing.T) {
	s, b, a := artifactFixture(t)
	raw, err := os.ReadFile(a.Path)
	if err != nil {
		t.Fatal(err)
	}
	body, err := b.Assemble(a.IDs, a.Locale)
	if err != nil || !strings.Contains(string(raw), body) || !strings.Contains(string(raw), ArtifactEndMarker) || strings.Contains(a.Path, "session-private") {
		t.Fatal("canonical artifact mismatch")
	}
	latest := s.Latest("session-private")
	if latest == nil || latest.Path != a.Path {
		t.Fatal("latest artifact missing")
	}
	if s.HasCompleteReadReceipt(a) {
		t.Fatal("unobserved read claimed")
	}
	if s.RecordCompleteRead(ReadCallback{Session: "session-private", Turn: "turn-private", FilePath: a.Path, ToolUseID: "read-1", EndMarkerSeen: false}) {
		t.Fatal("incomplete read accepted")
	}
	if !s.RecordCompleteRead(ReadCallback{Session: "session-private", Turn: "turn-private", FilePath: a.Path, ToolUseID: "read-1", EndMarkerSeen: true}) || !s.HasCompleteReadReceipt(a) {
		t.Fatal("complete receipt missing")
	}
	_ = os.WriteFile(a.Path, append(raw, []byte("modified")...), 0600)
	if s.HasCompleteReadReceipt(a) {
		t.Fatal("receipt survived content change")
	}
}
func TestArtifactReceiptInstanceReplay(t *testing.T) {
	s, b, a := artifactFixture(t)
	if !s.RecordCompleteRead(ReadCallback{Session: "session-private", Turn: "turn-private", FilePath: a.Path, ToolUseID: "read-1", EndMarkerSeen: true}) {
		t.Fatal("receipt creation")
	}
	second, err := s.Create("session-private", "turn-private", a.IDs, a.Locale, b)
	if err != nil {
		t.Fatal(err)
	}
	if s.HasCompleteReadReceipt(second) {
		t.Fatal("receipt replayed across artifact instance")
	}
	if s.RecordCompleteRead(ReadCallback{Session: "session-private", Turn: "wrong", FilePath: second.Path, ToolUseID: "read-2", EndMarkerSeen: true}) {
		t.Fatal("receipt bound to wrong turn")
	}
}
func TestArtifactV2HeaderCompatibility(t *testing.T) {
	s, _, a := artifactFixture(t)
	metadata := map[string]any{"schema": "opensocrates.instruction-artifact/2", "content_revision": a.Revision, "locale": a.Locale, "selected_reasoning_systems": a.IDs, "selected_display_names": a.Names, "inline_guardrails": a.Guardrails}
	encoded, err := contracts.CanonicalCompact(metadata)
	if err != nil {
		t.Fatal(err)
	}
	raw := []byte(headerPrefix + base64.URLEncoding.EncodeToString(encoded) + headerSuffix + "\n\ncanonical body\n\n" + ArtifactEndMarker + "\n")
	decoded, err := decodeArtifact(a.Path, raw)
	if err != nil || decoded == nil || len(decoded.Questions) != 0 {
		t.Fatal("retained v2 artifact rejected")
	}
	if !s.AcceptsArtifactPath(a.Path) || s.AcceptsArtifactPath(filepath.Join(filepath.Dir(a.Path), "..", "foreign.md")) {
		t.Fatal("artifact address grammar changed")
	}
}
func TestArtifactCleanupAndForeignPreservation(t *testing.T) {
	s, _, a := artifactFixture(t)
	foreign := filepath.Join(filepath.Dir(a.Path), "foreign.txt")
	_ = os.WriteFile(foreign, []byte("owned outside contract"), 0600)
	s.DeleteTurn("session-private", "turn-private")
	if _, err := os.Stat(a.Path); !os.IsNotExist(err) {
		t.Fatal("turn artifact retained")
	}
	if _, err := os.Stat(foreign); err != nil {
		t.Fatal("foreign file deleted")
	}
}
func TestArtifactExpiry(t *testing.T) {
	s, _, a := artifactFixture(t)
	past := time.Now().Add(-25 * time.Hour)
	_ = os.Chtimes(a.Path, past, past)
	s.SweepExpired()
	if _, err := os.Stat(a.Path); !os.IsNotExist(err) {
		t.Fatal("expired artifact retained")
	}
}

type fakeSelector struct{ candidate *Candidate }

func (f fakeSelector) Select(context.Context, Request) (*Candidate, error) { return f.candidate, nil }
func TestApplicationDiscardsModelInstructions(t *testing.T) {
	s, b, _ := artifactFixture(t)
	app := Application{Selector: fakeSelector{&Candidate{Intervene: true, SelectedReasoningSystems: []string{b.IDs[0]}, Instructions: "private arbitrary model instructions"}}, Bundle: b, Artifacts: s}
	d := app.Select(context.Background(), Request{Prompt: "한국어"}, "session-2", "turn-2")
	if d == nil || strings.Contains(d.Instructions, "arbitrary model") {
		t.Fatal("model text injected")
	}
	a := s.Latest("session-2")
	if a == nil {
		t.Fatal("canonical artifact missing")
	}
	raw, _ := os.ReadFile(a.Path)
	if strings.Contains(string(raw), "arbitrary model") {
		t.Fatal("model text retained")
	}
}
func TestLegacyHooksOneRepairAndCleanup(t *testing.T) {
	s, b, a := artifactFixture(t)
	h := &HookServices{Application: Application{Bundle: b, Artifacts: s}}
	payload := map[string]any{"hook_event_name": "Stop", "session_id": "session-private", "turn_id": "turn-private", "stop_hook_active": false, "last_assistant_message": "answer"}
	raw, _ := contracts.CanonicalCompact(payload)
	result, err := h.HandleLegacy(raw, "Stop")
	if err != nil || result["decision"] != "block" {
		t.Fatal("grounding backstop missing")
	}
	payload["stop_hook_active"] = true
	raw, _ = contracts.CanonicalCompact(payload)
	result, err = h.HandleLegacy(raw, "Stop")
	if err != nil || result != nil {
		t.Fatal("second repair emitted")
	}
	if _, err = os.Stat(a.Path); !os.IsNotExist(err) {
		t.Fatal("completed repair retained artifact")
	}
}
