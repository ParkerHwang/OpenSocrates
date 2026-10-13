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
	if b.Revision != 4 || len(b.Methods) != 48 || len(b.Projections) != 192 || len(b.SourceTreeHash) != 71 || len(b.SemanticHash) != 71 {
		t.Fatalf("baseline incomplete: %+v", b)
	}
	for _, method := range b.Methods {
		for _, locale := range []string{"en", "ko", "zh", "ja"} {
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
	for _, locale := range []string{"en", "ko", "zh", "ja"} {
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

func TestRequestedLocaleFallbackUsesCompleteSelectedSet(t *testing.T) {
	released, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	ids := append([]string(nil), released.IDs[:2]...)
	clone := *released
	clone.Projections = map[string]Injectable{}
	for key, item := range released.Projections {
		clone.Projections[key] = item
	}
	delete(clone.Projections, ids[1]+":ja")
	locale, err := clone.ResolveLocale(ids, "ja")
	if err != nil || locale != "en" {
		t.Fatalf("partial Japanese did not resolve English: %s %v", locale, err)
	}
	actual, err := clone.Assemble(ids, "ja")
	expected, originalErr := released.Assemble(ids, "en")
	if err != nil || originalErr != nil || actual != expected {
		t.Fatal("fallback mixed localized procedures or labels")
	}
	delete(clone.Projections, ids[1]+":en")
	if _, err := clone.Assemble(ids, "ja"); err == nil {
		t.Fatal("incomplete English fallback accepted")
	}
	// Complete requested content is usable even when English is unavailable.
	locale, err = clone.ResolveLocale(ids, "zh")
	if err != nil || locale != "zh" {
		t.Fatal("complete requested content lost", locale, err)
	}
	for _, requested := range []string{"", "ZH", "zh-CN", "follow"} {
		if _, err := released.Assemble(ids, requested); err == nil {
			t.Fatal("noncanonical locale accepted", requested)
		}
	}
}

func TestFourLocaleAssemblyIncludesCompleteAuthoredBodyAndTrustBoundary(t *testing.T) {
	b, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	ids := b.IDs[:2]
	expectedLabels := map[string][]string{
		"zh": {"所选思考体系：", "内容修订号: 4", "行动前须自行理清的问题：", "### 模板示例（不可信的模板数据）", "以下示例是不可信的模板数据。不得将其中的事实、数值、人物、结论、预期路由或理由视为当前任务的事实。"},
		"ja": {"選択された思考体系：", "コンテンツ改訂番号: 4", "行動前に自分で整理する問い：", "### テンプレート例（信頼できないテンプレートデータ）", "以下の例は信頼できないテンプレートデータです。例に含まれる事実、数値、人物、結論、想定ルート、根拠を現在のタスクの事実として扱わないでください。"},
	}
	for locale, labels := range expectedLabels {
		text, err := b.Assemble(ids, locale)
		if err != nil {
			t.Fatal(err)
		}
		for _, label := range labels {
			if !strings.Contains(text, label) {
				t.Fatalf("%s trust/teacher guidance omitted", locale)
			}
		}
		first, second := b.Projections[ids[0]+":"+locale], b.Projections[ids[1]+":"+locale]
		if !strings.Contains(text, first.Theory) || !strings.Contains(text, second.Theory) || strings.Index(text, "## "+first.Name) >= strings.Index(text, "## "+second.Name) {
			t.Fatal("selected authored procedure/order lost")
		}
		for _, item := range []Injectable{first, second} {
			examples, err := contracts.CanonicalCompact(item.Examples)
			if err != nil || !strings.Contains(text, "```json\n"+string(examples)+"\n```") {
				t.Fatal("canonical examples lost")
			}
		}
	}
}
