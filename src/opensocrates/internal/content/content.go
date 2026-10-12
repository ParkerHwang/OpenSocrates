// Package content loads fixed release assets. It never searches the cwd, host
// workspace, or environment for alternative reasoning content.
package content

import (
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"strings"
	"sync"
	"unicode/utf8"
)

//go:embed assets/*.json
var assets embed.FS

type Injectable struct {
	Revision int    `json:"content_revision"`
	Name     string `json:"display_name"`
	Locale   string `json:"locale"`
	ID       string `json:"method_id"`
	Theory   string `json:"theory"`
	Examples []any  `json:"template_examples"`
}
type Bundle struct {
	Revision         int                          `json:"content_revision"`
	SourceTreeHash   string                       `json:"source_tree_hash"`
	SemanticHash     string                       `json:"normalized_semantic_hash"`
	IDs              []string                     `json:"method_ids"`
	Methods          []domain.Method              `json:"methods"`
	Messages         map[string]map[string]string `json:"locale_messages"`
	Projections      map[string]Injectable        `json:"-"`
	Policy           map[string]any               `json:"-"`
	SelectionCatalog string                       `json:"-"`
}

var once sync.Once
var loaded *Bundle
var loadErr error

func Load() (*Bundle, error) { once.Do(func() { loaded, loadErr = load() }); return loaded, loadErr }
func load() (*Bundle, error) {
	read := func(name string) ([]byte, error) {
		raw, e := assets.ReadFile("assets/" + name)
		if e != nil {
			return nil, e
		}
		v, e := contracts.Decode(raw)
		if e != nil {
			return nil, e
		}
		canon, e := contracts.CanonicalJSON(v)
		if e != nil || string(canon) != string(raw) {
			return nil, contracts.ErrInvalid
		}
		return raw, nil
	}
	raw, e := read("compiled-content.bundle.json")
	if e != nil {
		return nil, e
	}
	b := new(Bundle)
	if e = json.Unmarshal(raw, b); e != nil {
		return nil, e
	}
	raw, e = read("compiled-reasoning-content.bundle.json")
	if e != nil {
		return nil, e
	}
	var p struct {
		Revision int          `json:"content_revision"`
		Content  []Injectable `json:"injectable_content"`
	}
	if e = json.Unmarshal(raw, &p); e != nil {
		return nil, e
	}
	projectionValue, e := contracts.Decode(raw)
	if e != nil {
		return nil, e
	}
	projectionMap, ok := projectionValue.(map[string]any)
	if !ok {
		return nil, contracts.ErrInvalid
	}
	catalog, e := contracts.CanonicalCompact(projectionMap["selection_catalog"])
	if e != nil {
		return nil, e
	}
	b.SelectionCatalog = string(catalog)
	if p.Revision != b.Revision || len(b.Methods) != 48 || len(b.IDs) != 48 || len(p.Content) != 96 {
		return nil, contracts.ErrInvalid
	}
	b.Projections = map[string]Injectable{}
	byID := map[string]domain.Method{}
	for _, m := range b.Methods {
		if _, ok := byID[m.ID]; ok {
			return nil, contracts.ErrInvalid
		}
		byID[m.ID] = m
	}
	for _, item := range p.Content {
		m, ok := byID[item.ID]
		if !ok || item.Revision != b.Revision || !contracts.Is(item.Locale, "en", "ko") || item.Theory != m.Procedure[item.Locale] || item.Name != m.DisplayName[item.Locale] {
			return nil, contracts.ErrInvalid
		}
		key := item.ID + ":" + item.Locale
		if _, ok := b.Projections[key]; ok {
			return nil, contracts.ErrInvalid
		}
		b.Projections[key] = item
	}
	raw, e = read("compiled-response-policy.json")
	if e != nil {
		return nil, e
	}
	value, e := contracts.Decode(raw)
	if e != nil {
		return nil, e
	}
	b.Policy, _ = value.(map[string]any)
	if b.Policy == nil {
		return nil, contracts.ErrInvalid
	}
	return b, nil
}
func Hash(raw []byte) string           { h := sha256.Sum256(raw); return "sha256:" + hex.EncodeToString(h[:]) }
func (b *Bundle) Known(id string) bool { _, ok := b.Projections[id+":en"]; return ok }
func Questions(theory string) []string {
	marker := "## Teacher questions\n"
	i := strings.Index(theory, marker)
	if i < 0 {
		return nil
	}
	section := theory[i+len(marker):]
	if j := strings.Index(section, "\n## "); j >= 0 {
		section = section[:j]
	}
	out := []string{}
	seen := map[string]bool{}
	for _, line := range strings.Split(section, "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, "- ") {
			continue
		}
		q := strings.TrimSpace(line[2:])
		n := utf8.RuneCountInString(q)
		if n < 20 || n > 220 || !strings.HasSuffix(q, "?") || seen[q] || strings.ContainsRune(q, 0) {
			return nil
		}
		seen[q] = true
		out = append(out, q)
	}
	if len(out) != 3 {
		return nil
	}
	return out
}

var teacherEN = []string{"A great teacher does not lecture a method. Settle the questions below for yourself, then do the user's task.", "Do not interview the user unless a missing answer would change the work. Do not name these questions or the methods unless the user asked. Do not narrate the questioning. Use any later procedure as a check, not as a script.", "Questions to settle before you act:"}
var teacherKO = []string{"좋은 스승은 방법을 강의하지 않습니다. 아래 질문을 스스로 정리한 뒤 사용자의 일을 수행하세요.", "빠진 답이 작업을 바꾸지 않는다면 사용자를 인터뷰하지 마세요. 사용자가 묻지 않았다면 이 질문이나 방법 이름을 드러내지 마세요. 질문을 해설하지 마세요. 이후 절차는 대본이 아니라 점검으로만 쓰세요.", "행동하기 전에 스스로 정리할 질문:"}

func (b *Bundle) Assemble(ids []string, locale string) (string, error) {
	if len(ids) == 0 || !contracts.Is(locale, "en", "ko") {
		return "", contracts.ErrInvalid
	}
	items := []Injectable{}
	questions := []string{}
	names := []string{}
	seen := map[string]bool{}
	for _, id := range ids {
		item, ok := b.Projections[id+":"+locale]
		if !ok || seen[id] {
			return "", contracts.ErrInvalid
		}
		seen[id] = true
		items = append(items, item)
		names = append(names, fmt.Sprintf("- %s (`%s`@%d)", item.Name, id, item.Revision))
		questions = append(questions, Questions(item.Theory)...)
	}
	title, revision, selected, example, boundary := "OpenSocrates Reasoning Systems", "Content revision", "Selected reasoning systems:", "### Template examples (untrusted template data)", "The following examples are untrusted template data. Do not treat their facts, values, people, conclusions, expected routes, or rationales as facts about the current task."
	teacher := teacherEN
	if locale == "ko" {
		title, revision, selected, example, boundary = "OpenSocrates 사고체계", "콘텐츠 리비전", "선택된 사고체계:", "### 템플릿 예시 (신뢰할 수 없는 템플릿 데이터)", "아래 예시는 신뢰할 수 없는 템플릿 데이터입니다. 예시에 있는 사실, 수치, 인물, 결론, 예상 경로, 근거를 현재 작업의 사실로 취급하지 마세요."
		teacher = teacherKO
	}
	stance, usage := teacher[0], teacher[1]
	if len(questions) == 0 {
		stance = "A great teacher does not lecture a method. Use the complete grounded procedure as a check while doing the user's task."
		usage = "Do not interview the user unless missing information would change the work. Do not name the methods unless the user asked. Use the procedure as a check, not as a script."
		if locale == "ko" {
			stance = "좋은 스승은 방법을 강의하지 않습니다. 사용자의 일을 수행하면서 완전한 접지 절차를 점검 기준으로 사용하세요."
			usage = "빠진 정보가 작업을 바꾸지 않는다면 사용자를 인터뷰하지 마세요. 사용자가 묻지 않았다면 방법 이름을 드러내지 마세요. 절차는 대본이 아니라 점검으로만 쓰세요."
		}
	}
	parts := []string{title, stance, usage, fmt.Sprintf("%s: %d", revision, b.Revision), selected + "\n" + strings.Join(names, "\n")}
	if len(questions) > 0 {
		qs := []string{}
		for _, q := range questions {
			qs = append(qs, "- "+q)
		}
		parts = append(parts, teacher[2]+"\n"+strings.Join(qs, "\n"))
	}
	for _, item := range items {
		examples, e := contracts.CanonicalCompact(item.Examples)
		if e != nil {
			return "", e
		}
		parts = append(parts, "## "+item.Name+"\n\n"+item.Theory+"\n"+example+"\n"+boundary+"\n\n```json\n"+string(examples)+"\n```")
	}
	return strings.Join(parts, "\n\n") + "\n", nil
}
func (b *Bundle) Guidance(locale, shape string) any {
	locales, ok := b.Policy["locales"].(map[string]any)
	if !ok {
		return nil
	}
	entry, ok := locales[locale].(map[string]any)
	if !ok {
		return nil
	}
	shapes, ok := entry["shapes"].(map[string]any)
	if !ok {
		return nil
	}
	if _, ok := shapes[shape]; !ok {
		shape = "default"
	}
	parts := []string{}
	s, ok := entry["protected_rule"].(string)
	if !ok {
		return nil
	}
	parts = append(parts, s)
	rules, ok := entry["rules"].([]any)
	if !ok {
		return nil
	}
	for _, r := range rules {
		s, ok := r.(string)
		if !ok {
			return nil
		}
		parts = append(parts, s)
	}
	s, ok = shapes[shape].(string)
	if !ok {
		return nil
	}
	parts = append(parts, s)
	raw, e := contracts.CanonicalCompact(b.Policy)
	if e != nil {
		return nil
	}
	return map[string]any{"schema": b.Policy["schema"], "revision": b.Policy["revision"], "sha256": Hash(raw), "profile_id": entry["profile_id"], "locale": locale, "answer_shape": shape, "enforcement": "guided", "application": "unverified", "instructions": strings.Join(parts, "\n")}
}
