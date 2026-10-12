package content

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"strings"
	"testing"
)

func TestReleasedCatalogContentAndCanonicalAssembly(t *testing.T) {
	b, e := Load()
	if e != nil {
		t.Fatal(e)
	}
	if b.Revision != 3 || len(b.Methods) != 48 || len(b.Projections) != 96 || len(b.SourceTreeHash) != 71 || len(b.SemanticHash) != 71 {
		t.Fatalf("baseline incomplete: %+v", b)
	}
	for _, method := range b.Methods {
		for _, locale := range []string{"en", "ko"} {
			instructions, e := b.Assemble([]string{method.ID}, locale)
			if e != nil {
				t.Fatalf("%s/%s: %v", method.ID, locale, e)
			}
			projection := b.Projections[method.ID+":"+locale]
			if !strings.Contains(instructions, projection.Theory) || !strings.Contains(instructions, projection.Name) || !strings.HasSuffix(instructions, "\n") {
				t.Fatalf("canonical procedure missing %s/%s", method.ID, locale)
			}
			questions := Questions(projection.Theory)
			if len(questions) != 3 {
				t.Fatalf("teacher questions missing %s/%s", method.ID, locale)
			}
			for _, question := range questions {
				if !strings.Contains(instructions, question) {
					t.Fatal("question omitted")
				}
			}
			if strings.Contains(instructions, "method not found") {
				t.Fatal("placeholder emitted")
			}
		}
	}
	for _, ids := range [][]string{nil, {"unknown-method"}, {"critical-thinking", "critical-thinking"}} {
		if _, e := b.Assemble(ids, "en"); e == nil {
			t.Fatal("invalid assembly accepted")
		}
	}
}
func TestGeneratedEmbedIsCanonicalFixedContent(t *testing.T) {
	for _, name := range []string{"compiled-content.bundle.json", "compiled-reasoning-content.bundle.json", "compiled-response-policy.json"} {
		raw, e := assets.ReadFile("assets/" + name)
		if e != nil {
			t.Fatal(e)
		}
		value, e := contracts.Decode(raw)
		if e != nil {
			t.Fatal(e)
		}
		canonical, e := contracts.CanonicalJSON(value)
		if e != nil || string(raw) != string(canonical) {
			t.Fatalf("asset %s not canonical", name)
		}
	}
}
func TestExactResponsePolicyGuidance(t *testing.T) {
	b, e := Load()
	if e != nil {
		t.Fatal(e)
	}
	for _, locale := range []string{"en", "ko"} {
		for _, shape := range []string{"direct_judgment", "decision_memo", "diagnostic", "completion_review"} {
			value := b.Guidance(locale, shape)
			m, ok := value.(map[string]any)
			if !ok || m["application"] != "unverified" || m["enforcement"] != "guided" || m["locale"] != locale {
				t.Fatal(value)
			}
			locales := b.Policy["locales"].(map[string]any)
			source := locales[locale].(map[string]any)
			if !strings.HasPrefix(m["instructions"].(string), source["protected_rule"].(string)) {
				t.Fatal("protected rule omitted")
			}
		}
	}
}
