package compat

import (
	"bytes"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

const ArtifactEndMarker = "<!-- OPENSOCRATES_INSTRUCTION_END -->"
const AttributionFooter = "Powered by OpenSocrates"
const MaxArtifactBytes = 1024 * 1024
const ArtifactTTL = 24 * time.Hour
const headerPrefix = "<!-- OPENSOCRATES_ARTIFACT_V2 "
const headerSuffix = " -->"
const receiptName = ".grounding-receipt.json"

var artifactName = regexp.MustCompile(`^instruction-[A-Za-z0-9_-]{6,64}\.md$`)
var privateTag = regexp.MustCompile(`^[0-9a-f]{64}$`)

type Artifact struct {
	Path       string   `json:"-"`
	Schema     string   `json:"schema"`
	Revision   int      `json:"content_revision"`
	Locale     string   `json:"locale"`
	IDs        []string `json:"selected_reasoning_systems"`
	Names      []string `json:"selected_display_names"`
	Guardrails []string `json:"inline_guardrails"`
	Questions  []string `json:"inline_teacher_questions"`
}

func (Artifact) String() string { return "InstructionArtifact(<redacted>)" }

type ArtifactStore struct {
	key                [32]byte
	roots              []string
	workspaceContainer string
	Now                func() time.Time
}

func (*ArtifactStore) String() string { return "InstructionFileStore(<private-temporary-root>)" }
func NewArtifactStore(key []byte, directory, workspace string) (*ArtifactStore, error) {
	if len(key) != 32 {
		return nil, failure(diagnostics.Verification)
	}
	s := &ArtifactStore{Now: time.Now}
	copy(s.key[:], key)
	if directory != "" {
		if !filepath.IsAbs(directory) {
			return nil, failure(diagnostics.Permission)
		}
		s.roots = []string{directory}
		return s, nil
	}
	tag := s.tag("instruction-artifact-root")
	if workspace != "" && filepath.IsAbs(workspace) {
		resolved, err := filepath.EvalSymlinks(workspace)
		if err == nil {
			info, err := os.Stat(resolved)
			if err == nil && info.IsDir() {
				s.workspaceContainer = filepath.Join(resolved, ".opensocrates")
				s.roots = append(s.roots, filepath.Join(s.workspaceContainer, tag))
			}
		}
	}
	temp, err := filepath.EvalSymlinks(os.TempDir())
	if err != nil {
		return nil, failure(diagnostics.Permission)
	}
	s.roots = append(s.roots, filepath.Join(temp, "opensocrates-"+tag))
	return s, nil
}
func (s *ArtifactStore) Directory() string { return s.roots[0] }
func (s *ArtifactStore) tag(label string, values ...string) string {
	h := hmac.New(sha256.New, s.key[:])
	h.Write([]byte(label))
	for _, v := range values {
		h.Write([]byte{0})
		var length [4]byte
		binary.BigEndian.PutUint32(length[:], uint32(len(v)))
		h.Write(length[:])
		h.Write([]byte(v))
	}
	return hex.EncodeToString(h.Sum(nil))
}
func identity(s string) bool { return validText(s, 512, true) }
func (s *ArtifactStore) turnDirectory(root, session, turn string) (string, error) {
	if !identity(session) || !identity(turn) {
		return "", failure(diagnostics.Verification)
	}
	return filepath.Join(root, s.tag("instruction-artifact-session", session), s.tag("instruction-artifact-turn", session, turn)), nil
}
func (s *ArtifactStore) ensureRoot(root string) error {
	if s.workspaceContainer != "" && filepath.Dir(root) == s.workspaceContainer {
		if err := platform.Mkdir(s.workspaceContainer); err != nil {
			return err
		}
		ignore := filepath.Join(s.workspaceContainer, ".gitignore")
		if _, err := os.Lstat(ignore); os.IsNotExist(err) {
			if err = platform.AtomicWrite(ignore, []byte("*\n"), 0600); err != nil {
				return err
			}
		} else {
			b, err := platform.ReadFile(ignore, 2)
			if err != nil || string(b) != "*\n" {
				return failure(diagnostics.Permission)
			}
		}
	}
	if err := platform.Mkdir(root); err != nil {
		return err
	}
	return platform.Guard(root)
}
func artifactValid(a Artifact) bool {
	if !filepath.IsAbs(a.Path) || a.Revision < 1 || !domain.SupportedLocale(a.Locale) || len(a.IDs) == 0 || len(a.Names) != len(a.IDs) || len(a.Guardrails) > 0 && len(a.Guardrails) != len(a.IDs) {
		return false
	}
	seen := map[string]bool{}
	for i, id := range a.IDs {
		if !validMethodID(id) || seen[id] || !validText(a.Names[i], 512, true) || strings.TrimSpace(a.Names[i]) == "" {
			return false
		}
		seen[id] = true
	}
	for _, set := range [][]string{a.Guardrails, a.Questions} {
		size := 0
		for _, v := range set {
			if !validText(v, 32768, true) || strings.TrimSpace(v) == "" {
				return false
			}
			size += len(v)
		}
		if size > 32768 {
			return false
		}
	}
	return true
}
func section(theory, title string) string {
	marker := "## " + title + "\n"
	i := strings.Index(theory, marker)
	if i < 0 {
		return ""
	}
	body := theory[i+len(marker):]
	if j := strings.Index(body, "\n## "); j >= 0 {
		body = body[:j]
	}
	return strings.TrimSpace(body)
}
func estimated(s string) int { return (len(s) + 3) / 4 }
func assembledArtifact(b *content.Bundle, ids []string, locale string) (Artifact, string, error) {
	locale, err := b.ResolveLocale(ids, locale)
	if err != nil {
		return Artifact{}, "", failure(diagnostics.Verification)
	}
	text, err := b.Assemble(ids, locale)
	if err != nil {
		return Artifact{}, "", failure(diagnostics.Verification)
	}
	a := Artifact{Schema: "opensocrates.instruction-artifact/3", Revision: b.Revision, Locale: locale, IDs: append([]string{}, ids...), Names: []string{}, Guardrails: []string{}, Questions: []string{}}
	allGuardrails := true
	allQuestions := []string{}
	for _, id := range ids {
		p, ok := b.Projections[id+":"+locale]
		if !ok {
			return Artifact{}, "", failure(diagnostics.Verification)
		}
		a.Names = append(a.Names, p.Name)
		allQuestions = append(allQuestions, content.Questions(p.Theory)...)
		no, stop := section(p.Theory, "Do not use when"), section(p.Theory, "Stop conditions")
		if no == "" || stop == "" {
			allGuardrails = false
			continue
		}
		title, noTitle, stopTitle := "Blocking rules", "Do not use when", "Stop conditions"
		switch locale {
		case "ko":
			title, noTitle, stopTitle = "차단 규칙", "사용하지 않는 조건", "중단 조건"
		case "zh":
			title, noTitle, stopTitle = "阻断规则", "不适用条件", "停止条件"
		case "ja":
			title, noTitle, stopTitle = "適用を制限する規則", "使用しない条件", "停止条件"
		}
		a.Guardrails = append(a.Guardrails, fmt.Sprintf("### %s: %s (`%s`@%d)\n\n**%s**\n\n%s\n\n**%s**\n\n%s", title, p.Name, id, b.Revision, noTitle, no, stopTitle, stop))
	}
	if !allGuardrails || estimated(strings.Join(a.Guardrails, "\n\n")) >= 1200 {
		a.Guardrails = []string{}
	}
	for _, q := range allQuestions {
		candidate := append(append([]string{}, a.Questions...), q)
		listed := []string{}
		for _, v := range candidate {
			listed = append(listed, "- "+v)
		}
		if estimated(strings.Join(listed, "\n")) >= 1000 {
			break
		}
		a.Questions = candidate
	}
	return a, text, nil
}
func (s *ArtifactStore) Create(session, turn string, ids []string, locale string, b *content.Bundle) (*Artifact, error) {
	if b == nil {
		return nil, failure(diagnostics.Verification)
	}
	a, body, err := assembledArtifact(b, ids, locale)
	if err != nil {
		return nil, err
	}
	metadata, err := contracts.CanonicalCompact(a)
	if err != nil || len(metadata) > 48<<10 {
		return nil, failure(diagnostics.Verification)
	}
	data := []byte(headerPrefix + base64.URLEncoding.EncodeToString(metadata) + headerSuffix + "\n\n" + body + "\n\n" + ArtifactEndMarker + "\n")
	if len(data) > MaxArtifactBytes {
		return nil, failure(diagnostics.Verification)
	}
	for _, root := range s.roots {
		if s.ensureRoot(root) != nil {
			continue
		}
		dir, err := s.turnDirectory(root, session, turn)
		if err != nil {
			return nil, err
		}
		if platform.Mkdir(dir) != nil {
			continue
		}
		nonce := make([]byte, 18)
		if _, err = rand.Read(nonce); err != nil {
			return nil, failure(diagnostics.Permission)
		}
		a.Path = filepath.Join(dir, "instruction-"+base64.RawURLEncoding.EncodeToString(nonce)+".md")
		if !artifactValid(a) {
			return nil, failure(diagnostics.Verification)
		}
		if _, err = a.ReferenceMessage(); err != nil {
			return nil, err
		}
		if _, err = os.Lstat(a.Path); !os.IsNotExist(err) {
			continue
		}
		if platform.AtomicWrite(a.Path, data, 0600) != nil {
			continue
		}
		return &a, nil
	}
	return nil, failure(diagnostics.Permission)
}
func (s *ArtifactStore) rootFor(path string) (string, bool) {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return "", false
	}
	for _, root := range s.roots {
		relative, err := filepath.Rel(root, path)
		if err != nil {
			continue
		}
		p := strings.Split(relative, string(os.PathSeparator))
		if len(p) == 3 && privateTag.MatchString(p[0]) && privateTag.MatchString(p[1]) && artifactName.MatchString(p[2]) {
			return root, true
		}
	}
	return "", false
}
func (s *ArtifactStore) AcceptsArtifactPath(path string) bool { _, ok := s.rootFor(path); return ok }
func decodeArtifact(path string, data []byte) (*Artifact, error) {
	first, _, _ := bytes.Cut(data, []byte{'\n'})
	if len(first) > 64<<10 || !bytes.HasPrefix(first, []byte(headerPrefix)) || !bytes.HasSuffix(first, []byte(headerSuffix)) {
		return nil, failure(diagnostics.Verification)
	}
	metadata, err := base64.URLEncoding.DecodeString(string(first[len(headerPrefix) : len(first)-len(headerSuffix)]))
	if err != nil {
		return nil, failure(diagnostics.Verification)
	}
	value, err := contracts.Decode(metadata)
	if err != nil {
		return nil, failure(diagnostics.Verification)
	}
	m, ok := value.(map[string]any)
	if !ok {
		return nil, failure(diagnostics.Verification)
	}
	schema, _ := m["schema"].(string)
	expected := 7
	if schema == "opensocrates.instruction-artifact/2" {
		expected = 6
	} else if schema != "opensocrates.instruction-artifact/3" {
		return nil, failure(diagnostics.Verification)
	}
	if len(m) != expected {
		return nil, failure(diagnostics.Verification)
	}
	for _, key := range []string{"schema", "content_revision", "locale", "selected_reasoning_systems", "selected_display_names", "inline_guardrails"} {
		if _, ok = m[key]; !ok || m[key] == nil {
			return nil, failure(diagnostics.Verification)
		}
	}
	if expected == 7 && m["inline_teacher_questions"] == nil {
		return nil, failure(diagnostics.Verification)
	}
	var a Artifact
	if json.Unmarshal(metadata, &a) != nil {
		return nil, failure(diagnostics.Verification)
	}
	a.Path = path
	if a.Questions == nil {
		a.Questions = []string{}
	}
	if !artifactValid(a) {
		return nil, failure(diagnostics.Verification)
	}
	return &a, nil
}
func (s *ArtifactStore) Latest(session string) *Artifact {
	if !identity(session) {
		return nil
	}
	type candidate struct {
		path  string
		mtime time.Time
	}
	candidates := []candidate{}
	for _, root := range s.roots {
		dir := filepath.Join(root, s.tag("instruction-artifact-session", session))
		if platform.Guard(dir) != nil {
			continue
		}
		turns, err := os.ReadDir(dir)
		if err != nil {
			continue
		}
		for _, turn := range turns {
			td := filepath.Join(dir, turn.Name())
			if !privateTag.MatchString(turn.Name()) || !turn.IsDir() || platform.Guard(td) != nil {
				continue
			}
			files, err := os.ReadDir(td)
			if err != nil {
				continue
			}
			for _, f := range files {
				if !artifactName.MatchString(f.Name()) {
					continue
				}
				path := filepath.Join(td, f.Name())
				if platform.Guard(path) != nil {
					continue
				}
				info, err := f.Info()
				if err == nil {
					candidates = append(candidates, candidate{path, info.ModTime()})
				}
			}
		}
	}
	sort.Slice(candidates, func(i, j int) bool {
		if candidates[i].mtime.Equal(candidates[j].mtime) {
			return candidates[i].path > candidates[j].path
		}
		return candidates[i].mtime.After(candidates[j].mtime)
	})
	for _, c := range candidates {
		b, err := platform.ReadFile(c.path, MaxArtifactBytes)
		if err != nil {
			continue
		}
		a, err := decodeArtifact(c.path, b)
		if err != nil {
			continue
		}
		if _, err = a.ReferenceMessage(); err == nil {
			return a
		}
	}
	return nil
}

type ReadCallback struct {
	Session, Turn, FilePath, ToolUseID string
	Offset, Limit                      *int64
	EndMarkerSeen                      bool
}

func (s *ArtifactStore) receiptCore(a *Artifact, hash, instance, tool string) map[string]any {
	return map[string]any{"schema": "opensocrates.instruction-read-receipt/2", "artifact_sha256": hash, "artifact_instance_tag": instance, "content_revision": a.Revision, "selected_reasoning_systems": a.IDs, "tool_use_tag": tool}
}
func (s *ArtifactStore) receiptAuth(core any) string {
	b, err := contracts.CanonicalCompact(core)
	if err != nil {
		return ""
	}
	h := hmac.New(sha256.New, s.key[:])
	h.Write([]byte("instruction-read-receipt\x00"))
	h.Write(b)
	return hex.EncodeToString(h.Sum(nil))
}
func (s *ArtifactStore) instance(a *Artifact) string {
	root, ok := s.rootFor(a.Path)
	if !ok {
		return ""
	}
	relative, _ := filepath.Rel(root, a.Path)
	return s.tag("instruction-artifact-instance", filepath.ToSlash(relative))
}
func (s *ArtifactStore) RecordCompleteRead(cb ReadCallback) bool {
	a := s.Latest(cb.Session)
	if a == nil || !cb.EndMarkerSeen || cb.FilePath != a.Path || !identity(cb.ToolUseID) || cb.Offset != nil && *cb.Offset != 0 && *cb.Offset != 1 {
		return false
	}
	root, ok := s.rootFor(a.Path)
	if !ok {
		return false
	}
	dir, err := s.turnDirectory(root, cb.Session, cb.Turn)
	if err != nil || filepath.Dir(a.Path) != dir {
		return false
	}
	b, err := platform.ReadFile(a.Path, MaxArtifactBytes)
	if err != nil {
		return false
	}
	lines := bytes.Count(b, []byte{'\n'})
	if len(b) > 0 && b[len(b)-1] != '\n' {
		lines++
	}
	if cb.Limit != nil && (*cb.Limit < 1 || *cb.Limit < int64(lines)) {
		return false
	}
	core := s.receiptCore(a, content.Hash(b), s.instance(a), s.tag("instruction-read-tool-use", cb.ToolUseID))
	core["authentication_tag"] = s.receiptAuth(core)
	data, err := contracts.CanonicalCompact(core)
	if err != nil || len(data) > 16<<10 {
		return false
	}
	return platform.AtomicWrite(filepath.Join(dir, receiptName), data, 0600) == nil
}
func (s *ArtifactStore) HasCompleteReadReceipt(a *Artifact) bool {
	if a == nil || !artifactValid(*a) || !s.AcceptsArtifactPath(a.Path) {
		return false
	}
	data, err := platform.ReadFile(filepath.Join(filepath.Dir(a.Path), receiptName), 16<<10)
	if err != nil {
		return false
	}
	value, err := contracts.Decode(data)
	if err != nil {
		return false
	}
	m, err := contracts.Object(value, "schema", "artifact_sha256", "artifact_instance_tag", "content_revision", "selected_reasoning_systems", "tool_use_tag", "authentication_tag")
	if err != nil {
		return false
	}
	tool, ok := m["tool_use_tag"].(string)
	if !ok || !privateTag.MatchString(tool) {
		return false
	}
	auth, ok := m["authentication_tag"].(string)
	if !ok || !privateTag.MatchString(auth) {
		return false
	}
	b, err := platform.ReadFile(a.Path, MaxArtifactBytes)
	if err != nil {
		return false
	}
	core := s.receiptCore(a, content.Hash(b), s.instance(a), tool)
	expected, err := contracts.CanonicalCompact(core)
	if err != nil {
		return false
	}
	delete(m, "authentication_tag")
	actual, err := contracts.CanonicalCompact(m)
	if err != nil || !bytes.Equal(actual, expected) {
		return false
	}
	return hmac.Equal([]byte(auth), []byte(s.receiptAuth(core)))
}

// Cleanup traverses only the store's known session/turn grammar. Foreign files,
// symbolic links, changed permissions and reparse points are preserved.
func (s *ArtifactStore) removeTurn(dir string) int {
	if platform.Guard(dir) != nil {
		return 0
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return 0
	}
	removed := 0
	for _, entry := range entries {
		if artifactName.MatchString(entry.Name()) || entry.Name() == receiptName {
			path := filepath.Join(dir, entry.Name())
			if platform.Guard(path) == nil && platform.Remove(path) == nil {
				removed++
			}
		}
	}
	if platform.Remove(dir) == nil {
		removed++
	}
	return removed
}
func (s *ArtifactStore) DeleteTurn(session, turn string) int {
	n := 0
	for _, root := range s.roots {
		dir, err := s.turnDirectory(root, session, turn)
		if err != nil {
			continue
		}
		n += s.removeTurn(dir)
		if platform.Remove(filepath.Dir(dir)) == nil {
			n++
		}
	}
	return n
}
func (s *ArtifactStore) DeleteSupersededTurns(session, active string) int {
	n := 0
	for _, root := range s.roots {
		keep, err := s.turnDirectory(root, session, active)
		if err != nil {
			continue
		}
		sd := filepath.Dir(keep)
		if platform.Guard(sd) != nil {
			continue
		}
		entries, err := os.ReadDir(sd)
		if err != nil {
			continue
		}
		for _, entry := range entries {
			if privateTag.MatchString(entry.Name()) && entry.Name() != filepath.Base(keep) {
				n += s.removeTurn(filepath.Join(sd, entry.Name()))
			}
		}
	}
	return n
}
func (s *ArtifactStore) DeleteSession(session string) int {
	if !identity(session) {
		return 0
	}
	n := 0
	for _, root := range s.roots {
		sd := filepath.Join(root, s.tag("instruction-artifact-session", session))
		if platform.Guard(sd) != nil {
			continue
		}
		turns, err := os.ReadDir(sd)
		if err != nil {
			continue
		}
		for _, turn := range turns {
			if privateTag.MatchString(turn.Name()) {
				n += s.removeTurn(filepath.Join(sd, turn.Name()))
			}
		}
		if platform.Remove(sd) == nil {
			n++
		}
	}
	return n
}
func (s *ArtifactStore) SweepExpired() int {
	cutoff := s.Now().Add(-ArtifactTTL)
	n := 0
	for _, root := range s.roots {
		if platform.Guard(root) != nil {
			continue
		}
		sessions, err := os.ReadDir(root)
		if err != nil {
			continue
		}
		for _, session := range sessions {
			sd := filepath.Join(root, session.Name())
			if !privateTag.MatchString(session.Name()) || platform.Guard(sd) != nil {
				continue
			}
			turns, err := os.ReadDir(sd)
			if err != nil {
				continue
			}
			for _, turn := range turns {
				td := filepath.Join(sd, turn.Name())
				if !privateTag.MatchString(turn.Name()) || platform.Guard(td) != nil {
					continue
				}
				files, err := os.ReadDir(td)
				if err != nil {
					continue
				}
				hasInstructions := false
				for _, f := range files {
					if !artifactName.MatchString(f.Name()) {
						continue
					}
					path := filepath.Join(td, f.Name())
					info, err := f.Info()
					if err != nil || platform.Guard(path) != nil {
						hasInstructions = true
						continue
					}
					if !info.ModTime().After(cutoff) && platform.Remove(path) == nil {
						n++
					} else {
						hasInstructions = true
					}
				}
				if !hasInstructions {
					if platform.Remove(filepath.Join(td, receiptName)) == nil {
						n++
					}
					if platform.Remove(td) == nil {
						n++
					}
				}
			}
			if platform.Remove(sd) == nil {
				n++
			}
		}
	}
	return n
}
