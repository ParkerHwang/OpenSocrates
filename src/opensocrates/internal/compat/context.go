package compat

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"unicode/utf8"
)

type ContextAccessor struct {
	handles      Handles
	mu           sync.Mutex
	calls, bytes int
}

func NewContextAccessor(h Handles) *ContextAccessor {
	h.ReferencedFiles = append([]string(nil), h.ReferencedFiles...)
	if !h.TranscriptAccessEnabled {
		h.TranscriptPath = ""
		h.ReferencedFiles = nil
	}
	return &ContextAccessor{handles: h}
}
func (*ContextAccessor) String() string { return "SelectorContextAccessor(<transient-redacted>)" }
func (a *ContextAccessor) Operations() []string {
	out := []string{}
	if !contextAvailable() {
		return out
	}
	if a.handles.TranscriptAccessEnabled && a.handles.TranscriptPath != "" {
		out = append(out, "read_transcript")
	}
	if a.handles.WorkspacePath != "" {
		out = append(out, "list_workspace", "read_workspace_file")
	}
	if a.handles.TranscriptAccessEnabled && len(a.handles.ReferencedFiles) > 0 {
		out = append(out, "read_referenced_file")
	}
	return out
}
func (a *ContextAccessor) Usage() (int, int) {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.calls, a.bytes
}
func relativeParts(s string, empty bool) ([]string, bool) {
	if !utf8.ValidString(s) || strings.ContainsRune(s, 0) || len(s) > 4096 || filepath.IsAbs(s) {
		return nil, false
	}
	if s == "" {
		return nil, empty
	}
	parts := []string{}
	// PurePath in the released implementation normalizes repeated separators
	// and dot components, but never authorizes a parent component.
	for _, p := range strings.Split(s, string(os.PathSeparator)) {
		if p == ".." {
			return nil, false
		}
		if p != "" && p != "." {
			parts = append(parts, p)
		}
	}
	return parts, len(parts) > 0 || empty
}
func contextFailure() map[string]any {
	return map[string]any{"contentItems": []any{}, "success": false}
}
func contextSuccess(kind string, v any) map[string]any {
	b, err := json.Marshal(map[string]any{"kind": kind, "untrusted_data": v})
	if err != nil {
		return contextFailure()
	}
	return map[string]any{"contentItems": []any{map[string]any{"type": "inputText", "text": string(b)}}, "success": true}
}
func integer(m map[string]json.RawMessage, k string) (int64, bool) {
	raw, ok := m[k]
	if !ok {
		return 0, true
	}
	var n int64
	if json.Unmarshal(raw, &n) != nil || string(raw) == "null" || n < 0 {
		return 0, false
	}
	return n, true
}
func textArg(m map[string]json.RawMessage, k string, optional bool) (string, bool) {
	raw, ok := m[k]
	if !ok {
		return "", optional
	}
	var s string
	if json.Unmarshal(raw, &s) != nil || string(raw) == "null" {
		return "", false
	}
	return s, true
}
func allowedArguments(m map[string]json.RawMessage, keys ...string) bool {
	allowed := map[string]bool{"operation": true}
	for _, k := range keys {
		allowed[k] = true
	}
	for k := range m {
		if !allowed[k] {
			return false
		}
	}
	return true
}

// Dispatch accepts only the one pinned read_context tool; approval, command,
// write, namespace and unknown requests can never grant a capability.
func (a *ContextAccessor) Dispatch(params json.RawMessage) map[string]any {
	if _, err := contracts.Decode(params); err != nil {
		return contextFailure()
	}
	var p struct {
		Tool      string          `json:"tool"`
		Namespace json.RawMessage `json:"namespace"`
		Arguments json.RawMessage `json:"arguments"`
	}
	if json.Unmarshal(params, &p) != nil || p.Tool != "read_context" || (len(p.Namespace) > 0 && string(p.Namespace) != "null") {
		return contextFailure()
	}
	var args map[string]json.RawMessage
	if json.Unmarshal(p.Arguments, &args) != nil {
		return contextFailure()
	}
	op, ok := textArg(args, "operation", false)
	if !ok {
		return contextFailure()
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.calls >= MaxContextCalls || !contextAvailable() {
		return contextFailure()
	}
	a.calls++
	offset, valid := integer(args, "offset")
	if !valid {
		return contextFailure()
	}
	var f *os.File
	var err error
	kind := ""
	switch op {
	case "read_transcript":
		if !allowedArguments(args, "offset") || !a.handles.TranscriptAccessEnabled || a.handles.TranscriptPath == "" {
			return contextFailure()
		}
		f, err = openExactContext(a.handles.TranscriptPath, false)
		kind = "transcript"
	case "read_referenced_file":
		idx, ok := integer(args, "index")
		if !ok || args["index"] == nil || !allowedArguments(args, "index", "offset") || !a.handles.TranscriptAccessEnabled || idx >= int64(len(a.handles.ReferencedFiles)) {
			return contextFailure()
		}
		f, err = openExactContext(a.handles.ReferencedFiles[idx], false)
		kind = "referenced_files"
	case "read_workspace_file", "list_workspace":
		listing := op == "list_workspace"
		relative, ok := textArg(args, "relative_path", listing)
		if !ok || a.handles.WorkspacePath == "" {
			return contextFailure()
		}
		if listing && !allowedArguments(args, "relative_path") || !listing && !allowedArguments(args, "relative_path", "offset") {
			return contextFailure()
		}
		parts, ok := relativeParts(relative, listing)
		if !ok {
			return contextFailure()
		}
		f, err = openBeneathContext(a.handles.WorkspacePath, parts, listing)
		kind = "workspace"
		if err == nil && listing {
			defer f.Close()
			return a.directory(f)
		}
	default:
		return contextFailure()
	}
	if err != nil || f == nil {
		return contextFailure()
	}
	defer f.Close()
	return a.read(f, kind, offset)
}
func (a *ContextAccessor) read(f *os.File, kind string, offset int64) map[string]any {
	info, err := f.Stat()
	if err != nil || !info.Mode().IsRegular() || offset > info.Size() {
		return contextFailure()
	}
	remaining := MaxContextTotalBytes - a.bytes
	if remaining <= 0 {
		return contextFailure()
	}
	if remaining > MaxContextReadBytes {
		remaining = MaxContextReadBytes
	}
	b := make([]byte, remaining)
	n, err := f.ReadAt(b, offset)
	if err != nil && err != io.EOF {
		return contextFailure()
	}
	b = b[:n]
	// Only a trailing incomplete rune may be trimmed. Invalid interior bytes
	// never become replacement characters, and offsets remain byte offsets.
	for i := 0; i < len(b); {
		r, n := utf8.DecodeRune(b[i:])
		if r == utf8.RuneError && n == 1 {
			if !utf8.FullRune(b[i:]) {
				b = b[:i]
				break
			}
			return contextFailure()
		}
		i += n
	}
	a.bytes += len(b)
	next := offset + int64(len(b))
	return contextSuccess(kind, map[string]any{"data": string(b), "has_more": next < info.Size(), "next_offset": next, "offset": offset})
}
func (a *ContextAccessor) directory(f *os.File) map[string]any {
	entries, err := f.ReadDir(MaxDirectoryEntries + 1)
	if err != nil && err != io.EOF {
		return contextFailure()
	}
	more := len(entries) > MaxDirectoryEntries
	if more {
		entries = entries[:MaxDirectoryEntries]
	}
	out := []map[string]string{}
	used := 0
	for _, entry := range entries {
		name := entry.Name()
		if !utf8.ValidString(name) {
			return contextFailure()
		}
		if used+len(name) > MaxContextTotalBytes-a.bytes {
			more = true
			break
		}
		kind := "other"
		if entry.Type()&os.ModeSymlink != 0 {
			kind = "symlink"
		} else if entry.IsDir() {
			kind = "directory"
		} else if entry.Type().IsRegular() {
			kind = "file"
		}
		out = append(out, map[string]string{"kind": kind, "name": name})
		used += len(name)
	}
	sort.Slice(out, func(i, j int) bool { return out[i]["name"] < out[j]["name"] })
	a.bytes += used
	return contextSuccess("workspace", map[string]any{"entries": out, "has_more": more})
}
