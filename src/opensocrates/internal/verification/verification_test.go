package verification

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"math/big"
	"strings"
	"testing"
)

func pointer[T any](v T) *T { return &v }
func TestPrivacyRejectsNormalizedKeysAndSecrets(t *testing.T) {
	for _, v := range []any{map[string]any{"ｔｏｋｅｎ": "opaque"}, map[string]any{" safe ": map[string]any{"raw-output": "x"}}, "Bearer abcdefghijklmnop0123", "https://example.com/data?api-key=abcdef", "-----BEGIN RSA PRIVATE KEY-----"} {
		if e := RejectPublic(v); e == nil {
			t.Fatalf("unsafe artifact admitted: %T", v)
		}
	}
	if e := RejectPublic(map[string]any{"summary": "The public ground changed", "value": "42"}); e != nil {
		t.Fatal(e)
	}
}
func TestMarkdownUnicodeAndSourceSecurity(t *testing.T) {
	for _, u := range []string{"https://user:password@example.com", "http://example.com", "https://127.0.0.1", "https://example.com/?access_token=x", "https://example.com/%zz"} {
		if e := ValidatePublicURL(u); e == nil {
			t.Fatal("unsafe URL", u)
		}
	}
	if e := ValidatePublicURL("http://127.0.0.1:8136/public-fixture"); e != nil {
		t.Fatal(e)
	}
	if e := ValidateScalarText("e\u0301", 20, false); e == nil {
		t.Fatal("non-NFC accepted")
	}
	value := "한글 😀 [x] `code`"
	escaped, e := EscapeInline(value, true)
	if e != nil {
		t.Fatal(e)
	}
	parsed, e := UnescapeInline(escaped)
	if e != nil || parsed != value {
		t.Fatal(parsed, e)
	}
	if _, e := ValidateCardMarkdown(strings.Repeat("한", 2201)); e == nil {
		t.Fatal("Unicode scalar budget ignored")
	}
}
func calculation(expression, result, rounding, unit string, operands ...domain.CalculationOperand) domain.Calculation {
	return domain.Calculation{Expression: expression, Result: result, Rounding: rounding, Unit: unit, Operands: operands}
}
func TestArithmeticExactPrecisionRoundingUnitsAndProvenance(t *testing.T) {
	source := pointer("E1")
	cases := []domain.Calculation{calculation("price * volume", "9007199254740993123456789", "none", "USD", domain.CalculationOperand{Name: "price", Value: "9007199254740993123456789", Unit: "USD", SourceID: source}, domain.CalculationOperand{Name: "volume", Value: "1", Unit: "1", SourceID: source}), calculation("cost / count", "2.5", "half_even_1", "USD", domain.CalculationOperand{Name: "cost", Value: "10", Unit: "USD", SourceID: source}, domain.CalculationOperand{Name: "count", Value: "4", Unit: "1", SourceID: source}), calculation("rate% * amount", "25", "none", "USD", domain.CalculationOperand{Name: "rate", Value: "25", Unit: "1", SourceID: source}, domain.CalculationOperand{Name: "amount", Value: "100", Unit: "USD", SourceID: source})}
	for _, c := range cases {
		result := VerifyCalculation(c, nil, nil, true)
		if !result.OK() {
			t.Fatalf("%s: %+v", c.Expression, result.Failures)
		}
	}
	for _, tt := range []struct{ value, mode, want string }{{"2.5", "half_even_0", "2"}, {"3.5", "half_even_0", "4"}, {"-2.1", "floor", "-3"}, {"-2.1", "ceiling", "-2"}, {"1.235", "half_even_2", "1.24"}} {
		v, _ := new(big.Rat).SetString(tt.value)
		got, e := RoundDecimal(v, tt.mode)
		want, _ := new(big.Rat).SetString(tt.want)
		if e != nil || got.Cmp(want) != 0 {
			t.Fatal(tt, got, e)
		}
	}
	invalid := []struct {
		c    domain.Calculation
		code string
	}{{calculation("1 / 0", "0", "none", "1"), "division_by_zero"}, {calculation("+1", "1", "none", "1"), "unsupported_syntax"}, {calculation("01", "1", "none", "1"), "invalid_token"}, {calculation("a + b", "3", "none", "USD", domain.CalculationOperand{Name: "a", Value: "1", Unit: "USD"}, domain.CalculationOperand{Name: "b", Value: "2", Unit: "day"}), "unit_mismatch"}, {calculation("a", "1", "none", "USD", domain.CalculationOperand{Name: "a", Value: "1", Unit: "USD"}, domain.CalculationOperand{Name: "b", Value: "2", Unit: "USD"}), "unused_operand"}}
	for _, tt := range invalid {
		result := VerifyCalculation(tt.c, nil, nil, false)
		if result.OK() || len(result.Failures) != 1 || result.Failures[0].Code != tt.code {
			t.Fatal(tt.c.Expression, result)
		}
	}
	c := calculation("a", "1", "none", "USD", domain.CalculationOperand{Name: "a", Value: "1", Unit: "USD"})
	result := VerifyCalculation(c, nil, nil, true)
	if result.Failures[0].Code != "provenance_missing" {
		t.Fatal(result)
	}
}
func TestStoredAdmissionPreservesLegacyGrammar(t *testing.T) {
	c := calculation("+001 + a", "2", "none", "USD", domain.CalculationOperand{Name: "a", Value: "1", Unit: "days"}, domain.CalculationOperand{Name: "unused", Value: "1", Unit: "1"})
	if e := ValidateStoredCalculation(c); e != nil {
		t.Fatal(e)
	}
	if VerifyCalculation(c, nil, nil, false).OK() {
		t.Fatal("completion accepted legacy-only syntax")
	}
	c = calculation("a / 3", "0.3333333333333333333333333333", "none", "1", domain.CalculationOperand{Name: "a", Value: "1", Unit: "1"})
	if e := ValidateStoredCalculation(c); e != nil {
		t.Fatal("28-digit context drift", e)
	}
}
func validCard(locale string) domain.ConclusionCard {
	return domain.ConclusionCard{Schema: "opensocrates.conclusion-card/1.0.0", Locale: locale, TaskID: "01JA12E00FCB7B218EB17A1C56", JudgmentID: "J000001", JudgmentVersion: 1, Conclusion: "Choose the lower cost option.", Strength: domain.Supported, Grounds: []domain.ConclusionGround{{ClaimID: "C000001", Text: "The quote is lower", State: domain.Verified, SourceRefs: []domain.CardSourceReference{{DisplayName: "Supplier quote", URI: pointer("https://example.com/quote")}}}}, Uncertainties: []string{}, FlipConditions: []domain.FlipCondition{{Schema: "opensocrates.flip-condition/1.0.0", Condition: "If cost exceeds 20 USD", Direction: "reverse", Check: "Obtain the supplier quote"}}, AlternativesSummary: "The other offer was rejected because its price is higher.", RenderedAt: "2026-10-12T00:00:00.000Z"}
}
func TestCardsRoundTripAllReleasedLocalesAndTrustedIdentity(t *testing.T) {
	bundle, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		card := validCard(locale)
		rendered, e := RenderCard(card, bundle.Messages[locale], 2)
		if e != nil {
			t.Fatal(locale, e, CardViolations(card, nil))
		}
		parsed, e := ParseCard(rendered, locale, bundle.Messages[locale], TrustedCardContext{TaskID: card.TaskID, JudgmentID: card.JudgmentID, ClaimIDs: []string{"C000001"}, JudgmentVersion: 1, RenderedAt: card.RenderedAt})
		if e != nil || parsed.Conclusion != card.Conclusion || parsed.Grounds[0].ClaimID != "C000001" || parsed.FlipConditions[0].Check != card.FlipConditions[0].Check {
			t.Fatal(locale, parsed, e)
		}
		if _, e := ParseCard(rendered, locale, bundle.Messages[locale], TrustedCardContext{TaskID: card.TaskID, JudgmentID: card.JudgmentID, ClaimIDs: []string{"C000001", "C000002"}, JudgmentVersion: 1}); e == nil {
			t.Fatal("trusted ground count mismatch accepted")
		}
	}
}
func TestCompletionDoesNotInferSafetyOrUserConstraints(t *testing.T) {
	card := validCard("en")
	claim := domain.ClaimVersion{ID: "C000001", Version: 1, Text: card.Grounds[0].Text, Materiality: "material", EvidenceState: domain.Verified, SourceIDs: []string{"E1"}, Active: true}
	framing := domain.Framing{CompletionCriteria: []domain.Criterion{{ID: "K1", Text: "The card has its required structure", Kind: "card_contract", Required: true}, {ID: "K2", Text: "The user's constraint is satisfied", Kind: "user_constraint", Required: true}}}
	j := domain.JudgmentVersion{JudgmentID: "J000001", Version: 1, Strength: card.Strength, Conclusion: &card.Conclusion, GroundClaimIDs: []string{"C000001"}}
	request := VerificationRequest{Card: &card, Task: &TaskContext{TaskID: card.TaskID, Locale: "en", State: domain.TaskVerifying}, Framing: &framing, CurrentJudgment: &j, Claims: []domain.ClaimVersion{claim}, CandidateSequence: 1}
	result := VerifyCompletion(request)
	if result.Outcome != domain.Insufficient {
		t.Fatal(result)
	}
	request.CriterionStatuses = map[string]domain.CompletionCriterion{"K2": {ID: "K2", Status: domain.Met, Reason: "The public constraint was checked", Required: true}}
	result = VerifyCompletion(request)
	if result.Outcome != domain.Pass {
		t.Fatal(result.Outcome, result.Violations)
	}
	j.Version = 2
	result = VerifyCompletion(request)
	if result.Outcome != domain.Repair {
		t.Fatal(result.Outcome, result.Violations)
	}
	request.RepairCountBefore = 1
	result = VerifyCompletion(request)
	if result.Outcome != domain.Degraded || result.CompletionResult.MayContinue {
		t.Fatal(result)
	}
}
func TestTraceProjectionPreservesPrimaryActivationAndVersionHistory(t *testing.T) {
	task := domain.NewTaskID()
	hostSession := "sha256:" + strings.Repeat("0", 64)
	events := []map[string]any{}
	add := func(kind string, payload map[string]any) {
		events = append(events, map[string]any{"schema": "opensocrates.judgment-event/1.0.0", "event_id": domain.NewMessageID(), "task_id": task, "sequence": contracts.Number(int64(len(events) + 1)), "event_type": kind, "occurred_at": "2026-10-12T00:00:00.000Z", "host": "codex_cli", "host_version": "1.0.0", "adapter_version": "1.6.0", "locale": "en", "payload": payload})
	}
	add("task_started", map[string]any{"requested_rigor": "quiet", "effective_rigor": "together", "capability_gaps": []any{}, "participation_reason": "judgment_choice", "host_session_key": hostSession})
	add("method_selected", map[string]any{"primary_method": "critical-thinking", "secondary_method": "trade-off-analysis", "selection_source": "automatic"})
	add("method_activated", map[string]any{"method_id": "critical-thinking", "activation_source": "automatic", "turn_tag": hostSession})
	view, e := ProjectTrace(events, "recorded", nil)
	if e != nil {
		t.Fatal(e)
	}
	if view.Methods.Status != "confirmed" || len(view.Methods.ConfirmedActivations) != 1 || view.Methods.ConfirmedActivations[0] != "critical-thinking" || view.Methods.ComplementCue == nil || *view.Methods.ComplementCue != "trade-off-analysis" {
		t.Fatal(view.Methods)
	}
	bundle, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	text, e := RenderTrace(view, bundle.Messages["en"], true)
	if e != nil || !strings.Contains(text, bundle.Messages["en"]["trace.private_reasoning"]) {
		t.Fatal(text, e)
	}
	events[1]["sequence"] = contracts.Number(4)
	if _, e := ProjectTrace(events, "recorded", nil); e == nil {
		t.Fatal("noncontiguous events projected")
	}
}

func TestTraceAndMetricClosedLocalesAcrossReleasedLanguages(t *testing.T) {
	bundle, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		task := domain.NewTaskID()
		event := map[string]any{"schema": "opensocrates.judgment-event/1.0.0", "event_id": domain.NewMessageID(), "task_id": task, "sequence": contracts.Number(1), "event_type": "task_started", "occurred_at": "2026-10-12T00:00:00.000Z", "host": "codex_cli", "host_version": "1.0.0", "adapter_version": "1.6.0", "locale": locale, "payload": map[string]any{"requested_rigor": "quiet", "effective_rigor": "together", "capability_gaps": []any{}, "participation_reason": "judgment_choice", "host_session_key": "sha256:" + strings.Repeat("0", 64)}}
		if e := domain.ValidateRecord(event); e != nil {
			t.Fatal("record locale rejected", locale, e)
		}
		view, e := ProjectTrace([]map[string]any{event}, "recorded", nil)
		if e != nil || view.Locale != locale {
			t.Fatal("trace locale changed", locale, e)
		}
		text, e := RenderTrace(view, bundle.Messages[locale], false)
		if e != nil || !strings.Contains(text, bundle.Messages[locale]["trace.title"]) {
			t.Fatal("localized trace failed", locale, e)
		}
		metric, e := domain.BuildLocalMetric("card_rendered", "codex_cli", locale, domain.Together, domain.MetricAttributes{}, "2026-10-12", "1.6.0", nil, true, nil)
		if e != nil || metric == nil || domain.ValidateLocalMetric(*metric) != nil {
			t.Fatal("metric locale rejected", locale, e)
		}
		raw, e := contracts.CanonicalCompact(metric)
		if e != nil {
			t.Fatal(e)
		}
		wire, e := contracts.Decode(raw)
		if e != nil || domain.ValidateLocalMetricWire(wire) != nil {
			t.Fatal("wire metric rejected", locale, e)
		}
		event["locale"] = "zh-CN"
		if domain.ValidateRecord(event) == nil {
			t.Fatal("record locale alias admitted")
		}
		view.Locale = "ja-JP"
		if _, e := RenderTrace(view, bundle.Messages[locale], false); e == nil {
			t.Fatal("trace locale alias admitted")
		}
	}
	card := validCard("ru")
	if len(CardViolations(card, nil)) == 0 {
		t.Fatal("unsupported card locale admitted")
	}
}
