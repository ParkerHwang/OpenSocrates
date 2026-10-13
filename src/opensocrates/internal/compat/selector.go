package compat

import (
	"bufio"
	"context"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

// Selector uses a user-provided external native Codex 0.144.4 binary. OpenSocrates
// does not redistribute Codex or start its login flow. CodexHome is read only
// to privately copy already-existing OAuth into a fresh disposable home.
type Selector struct {
	Binary, CodexHome string
	mu                sync.Mutex
	closed            bool
	active            map[uint64]context.CancelFunc
	next              uint64
}

func (*Selector) String() string { return "CodexReasoningSelector(<isolated>)" }
func (s *Selector) Cancel() {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, cancel := range s.active {
		cancel()
	}
}
func (s *Selector) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.closed = true
	for _, cancel := range s.active {
		cancel()
	}
}

func (s *Selector) Select(parent context.Context, r Request) (*Candidate, error) {
	if os.Getenv(RecursionEnvironment) != "" {
		return nil, outcomeFailure(diagnostics.Unsupported, "request_rejected")
	}
	if !contextAvailable() {
		return nil, outcomeFailure(diagnostics.Unsupported, "request_rejected")
	}
	if domain.ResolveLocale(r.TrustedExplicitLocale, r.StoredPreference, r.Prompt, false) == "" || !validText(r.Prompt, MaxPromptBytes, true) || !validText(r.Catalog, MaxCatalogBytes, true) || r.Deadline < time.Second || r.Deadline > 30*time.Second || r.ReasoningEffort != "medium" {
		return nil, outcomeFailure(diagnostics.Verification, "request_rejected")
	}
	catalog, err := contracts.Decode([]byte(r.Catalog))
	if err != nil {
		return nil, failure(diagnostics.Verification)
	}
	if _, ok := catalog.(map[string]any); !ok {
		return nil, failure(diagnostics.Verification)
	}
	hard, cancel := context.WithTimeout(parent, r.Deadline)
	defer cancel()
	s.mu.Lock()
	if s.closed {
		s.mu.Unlock()
		return nil, outcomeFailure(diagnostics.HostUnavailable, "selector_closed")
	}
	s.next++
	id := s.next
	if s.active == nil {
		s.active = map[uint64]context.CancelFunc{}
	}
	s.active[id] = cancel
	s.mu.Unlock()
	defer func() { s.mu.Lock(); delete(s.active, id); s.mu.Unlock() }()
	root, err := platform.MkdirTemp(systemTempDirectory(), "opensocrates-selector-")
	if err != nil {
		return nil, failure(diagnostics.Permission)
	}
	defer os.RemoveAll(root)
	env, workspace, err := isolatedEnvironment(root)
	if err != nil {
		return nil, err
	}
	home := s.CodexHome
	if home == "" {
		home = os.Getenv("CODEX_HOME")
		if home == "" {
			h, e := os.UserHomeDir()
			if e != nil {
				return nil, failure(diagnostics.HostUnavailable)
			}
			home = filepath.Join(h, ".codex")
		}
	}
	auth, err := existingOAuth(home)
	if err != nil {
		return nil, err
	}
	defer func() {
		for i := range auth {
			auth[i] = 0
		}
	}()
	// Never retain user credentials beyond the selector call or write refreshed
	// credentials into the user's actual host home.
	if err = platform.AtomicWrite(filepath.Join(root, "codex-home", "auth.json"), auth, 0600); err != nil {
		return nil, failure(diagnostics.Permission)
	}
	for i := range auth {
		auth[i] = 0
	}
	binary := s.Binary
	if binary == "" {
		binary, err = exec.LookPath("codex")
		if err != nil {
			return nil, outcomeFailure(diagnostics.HostUnavailable, "executable_missing")
		}
	}
	if !filepath.IsAbs(binary) {
		return nil, failure(diagnostics.Permission)
	}
	version, err := platform.Run(hard, binary, []string{"--version"}, platform.RunOptions{Dir: workspace, Env: env, OutputLimit: 4096})
	if err != nil {
		return nil, failure(diagnostics.HostUnavailable)
	}
	if strings.TrimSpace(string(version.Stdout)) != "codex-cli "+CodexVersion {
		return nil, failure(diagnostics.ProtocolIncompatible)
	}
	grace := r.Deadline / 5
	if grace > 3*time.Second {
		grace = 3 * time.Second
	}
	if grace < 250*time.Millisecond {
		grace = 250 * time.Millisecond
	}
	run, cancelRun := context.WithTimeout(hard, r.Deadline-grace)
	defer cancelRun()
	conn, err := startConnection(hard, binary, configArgs(env), env, workspace, NewContextAccessor(r.Context))
	if err != nil {
		return nil, err
	}
	defer conn.close()
	result, err := conn.selectTurn(run, r, workspace)
	if err != nil {
		conn.interrupt(hard)
		if run.Err() == context.DeadlineExceeded || hard.Err() == context.DeadlineExceeded {
			return nil, outcomeFailure(diagnostics.HostUnavailable, "timeout")
		}
		if run.Err() != nil || hard.Err() != nil {
			return nil, outcomeFailure(diagnostics.HostUnavailable, "selector_closed")
		}
		return nil, err
	}
	return result, nil
}

type wireMessage struct {
	ID     json.RawMessage `json:"id"`
	Method string          `json:"method"`
	Params json.RawMessage `json:"params"`
	Result json.RawMessage `json:"result"`
	Error  json.RawMessage `json:"error"`
}
type boundedDiscard struct {
	mu     sync.Mutex
	n      int
	cancel context.CancelFunc
}

func (w *boundedDiscard) Write(b []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.n += len(b)
	if w.n > MaxResponseBytes {
		w.cancel()
		return 0, failure(diagnostics.Verification)
	}
	return len(b), nil
}

type connection struct {
	process          *platform.Process
	cancel           context.CancelFunc
	input            *os.File
	output           *os.File
	messages         chan wireMessage
	readError        chan error
	stop             chan struct{}
	once             sync.Once
	writeMu          sync.Mutex
	next             int
	backlog          []wireMessage
	accessor         *ContextAccessor
	threadID, turnID string
}

func startConnection(ctx context.Context, binary string, args, env []string, dir string, a *ContextAccessor) (*connection, error) {
	inRead, inWrite, err := os.Pipe()
	if err != nil {
		return nil, failure(diagnostics.HostUnavailable)
	}
	outRead, outWrite, err := os.Pipe()
	if err != nil {
		inRead.Close()
		inWrite.Close()
		return nil, failure(diagnostics.HostUnavailable)
	}
	processContext, cancel := context.WithCancel(ctx)
	p, err := platform.Start(processContext, binary, args, platform.RunOptions{Dir: dir, Env: env, Stdin: inRead, Stdout: outWrite, Stderr: &boundedDiscard{cancel: cancel}})
	inRead.Close()
	outWrite.Close()
	if err != nil {
		cancel()
		inWrite.Close()
		outRead.Close()
		return nil, failure(diagnostics.HostUnavailable)
	}
	c := &connection{process: p, cancel: cancel, input: inWrite, output: outRead, messages: make(chan wireMessage, 32), readError: make(chan error, 1), stop: make(chan struct{}), accessor: a}
	go c.read()
	return c, nil
}
func (c *connection) close() {
	c.once.Do(func() {
		close(c.stop)
		c.cancel()
		c.input.Close()
		c.output.Close()
		c.process.Close()
		c.process.Wait()
	})
}
func (c *connection) read() {
	scanner := bufio.NewScanner(c.output)
	scanner.Buffer(make([]byte, 4096), 1<<20)
	total, count := 0, 0
	for scanner.Scan() {
		b := scanner.Bytes()
		total += len(b)
		count++
		if total > 4<<20 || count > 4096 || !utf8.Valid(b) {
			c.readError <- failure(diagnostics.Verification)
			return
		}
		if _, err := contracts.Decode(b); err != nil {
			c.readError <- failure(diagnostics.ProtocolIncompatible)
			return
		}
		var m wireMessage
		if json.Unmarshal(b, &m) != nil {
			c.readError <- failure(diagnostics.ProtocolIncompatible)
			return
		}
		select {
		case c.messages <- m:
		case <-c.stop:
			return
		}
	}
	select {
	case c.readError <- failure(diagnostics.HostUnavailable):
	default:
	}
}
func (c *connection) send(ctx context.Context, v any) error {
	b, err := json.Marshal(v)
	if err != nil || len(b) > 1<<20 {
		return failure(diagnostics.Verification)
	}
	b = append(b, '\n')
	c.writeMu.Lock()
	defer c.writeMu.Unlock()
	deadline, ok := ctx.Deadline()
	if !ok {
		deadline = time.Now().Add(time.Second)
	}
	if ctx.Err() != nil {
		return failure(diagnostics.HostUnavailable)
	}
	if c.input.SetWriteDeadline(deadline) != nil {
		return failure(diagnostics.HostUnavailable)
	}
	for len(b) > 0 {
		n, err := c.input.Write(b)
		if err != nil || n == 0 {
			return failure(diagnostics.HostUnavailable)
		}
		b = b[n:]
	}
	return nil
}
func (c *connection) receive(ctx context.Context) (wireMessage, error) {
	select {
	case m := <-c.messages:
		return m, nil
	case err := <-c.readError:
		return wireMessage{}, err
	case <-ctx.Done():
		return wireMessage{}, failure(diagnostics.HostUnavailable)
	}
}
func (c *connection) respond(ctx context.Context, m wireMessage) error {
	if m.Method == "item/tool/call" {
		var p struct {
			Thread string `json:"threadId"`
			Turn   string `json:"turnId"`
		}
		result := contextFailure()
		if json.Unmarshal(m.Params, &p) == nil && p.Thread == c.threadID && (c.turnID == "" || p.Turn == c.turnID) && p.Turn != "" {
			result = c.accessor.Dispatch(m.Params)
		}
		return c.send(ctx, map[string]any{"id": json.RawMessage(m.ID), "result": result})
	}
	// Unknown server requests, including all approval requests, fail closed.
	return c.send(ctx, map[string]any{"id": json.RawMessage(m.ID), "error": map[string]any{"code": -32601, "message": "unsupported request"}})
}
func (c *connection) rpc(ctx context.Context, method string, params any) (json.RawMessage, error) {
	c.next++
	id := c.next
	if err := c.send(ctx, map[string]any{"id": id, "method": method, "params": params}); err != nil {
		return nil, err
	}
	for {
		m, err := c.receive(ctx)
		if err != nil {
			return nil, err
		}
		if m.Method != "" && len(m.ID) > 0 {
			if err = c.respond(ctx, m); err != nil {
				return nil, err
			}
			continue
		}
		if m.Method != "" {
			if len(c.backlog) >= 128 {
				return nil, failure(diagnostics.Verification)
			}
			c.backlog = append(c.backlog, m)
			continue
		}
		var got int
		if json.Unmarshal(m.ID, &got) != nil || got != id {
			return nil, failure(diagnostics.ProtocolIncompatible)
		}
		if len(m.Error) > 0 && string(m.Error) != "null" {
			return nil, failure(diagnostics.ProtocolIncompatible)
		}
		return m.Result, nil
	}
}
func (c *connection) selectTurn(ctx context.Context, r Request, workspace string) (*Candidate, error) {
	_, err := c.rpc(ctx, "initialize", map[string]any{"clientInfo": map[string]string{"name": "opensocrates_legacy_selector", "title": "OpenSocrates", "version": "1.6.0"}, "capabilities": map[string]bool{"experimentalApi": true}})
	if err != nil {
		return nil, err
	}
	if err = c.send(ctx, map[string]any{"method": "initialized"}); err != nil {
		return nil, err
	}
	account, err := c.rpc(ctx, "account/read", map[string]bool{"refreshToken": false})
	if err != nil {
		return nil, err
	}
	var auth struct {
		Account *struct {
			Type string `json:"type"`
		} `json:"account"`
	}
	if json.Unmarshal(account, &auth) != nil || auth.Account == nil || auth.Account.Type != "chatgpt" {
		return nil, failure(diagnostics.HostUnavailable)
	}
	started, err := c.rpc(ctx, "thread/start", threadParams(c.accessor, workspace))
	if err != nil {
		return nil, err
	}
	var thread struct {
		Thread struct {
			ID string `json:"id"`
		} `json:"thread"`
	}
	if json.Unmarshal(started, &thread) != nil || !validText(thread.Thread.ID, 512, true) {
		return nil, failure(diagnostics.ProtocolIncompatible)
	}
	c.threadID = thread.Thread.ID
	turn, err := c.rpc(ctx, "turn/start", map[string]any{"threadId": c.threadID, "input": []any{map[string]any{"type": "text", "text": turnInput(r, c.accessor)}}, "cwd": workspace, "approvalPolicy": "never", "sandboxPolicy": map[string]any{"type": "readOnly", "networkAccess": false}, "effort": "medium", "outputSchema": outputSchema()})
	if err != nil {
		return nil, err
	}
	var t struct {
		Turn struct {
			ID string `json:"id"`
		} `json:"turn"`
	}
	if json.Unmarshal(turn, &t) != nil || !validText(t.Turn.ID, 512, true) {
		return nil, failure(diagnostics.ProtocolIncompatible)
	}
	c.turnID = t.Turn.ID
	final := ""
	itemID := ""
	for {
		var m wireMessage
		if len(c.backlog) > 0 {
			m = c.backlog[0]
			c.backlog = c.backlog[1:]
		} else {
			m, err = c.receive(ctx)
			if err != nil {
				return nil, err
			}
		}
		if m.Method != "" && len(m.ID) > 0 {
			if err = c.respond(ctx, m); err != nil {
				return nil, err
			}
			continue
		}
		var p struct {
			Thread string                          `json:"threadId"`
			TurnID string                          `json:"turnId"`
			Item   struct{ ID, Type, Text string } `json:"item"`
			Turn   struct{ ID, Status string }     `json:"turn"`
		}
		if json.Unmarshal(m.Params, &p) != nil {
			return nil, failure(diagnostics.ProtocolIncompatible)
		}
		if p.Thread != "" && p.Thread != c.threadID {
			continue
		}
		switch m.Method {
		case "item/completed":
			if p.TurnID == c.turnID && p.Item.Type == "agentMessage" {
				if len(p.Item.Text) > MaxResponseBytes {
					return nil, failure(diagnostics.Verification)
				}
				final = p.Item.Text
				itemID = p.Item.ID
			}
		case "turn/completed":
			if p.Turn.ID != c.turnID {
				continue
			}
			if p.Turn.Status != "completed" || itemID == "" {
				return nil, failure(diagnostics.HostUnavailable)
			}
			return DecodeCandidate([]byte(final))
		}
	}
}
func (c *connection) interrupt(ctx context.Context) {
	if c.threadID == "" || c.turnID == "" {
		return
	}
	interrupt, cancel := context.WithTimeout(ctx, 250*time.Millisecond)
	defer cancel()
	_ = c.send(interrupt, map[string]any{"id": 2147483647, "method": "turn/interrupt", "params": map[string]string{"threadId": c.threadID, "turnId": c.turnID}})
}

func turnInput(r Request, a *ContextAccessor) string {
	p, _ := json.Marshal(r.Prompt)
	caps, _ := json.Marshal(map[string]any{"transcript_access_enabled": r.Context.TranscriptAccessEnabled, "operations": a.Operations()})
	return "CURRENT_PROMPT_UNTRUSTED_DATA\n" + string(p) + "\n\nSELECTION_CATALOG_CANONICAL_DATA\n" + r.Catalog + "\n\nCONTEXT_CAPABILITIES_UNTRUSTED_METADATA\n" + string(caps)
}
