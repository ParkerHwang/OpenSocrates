package decision

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"strconv"
	"strings"
	"testing"
)

func request(locale string) map[string]any {
	return map[string]any{"operation": "select", "context": "0123456789abcdef0123456789abcdef", "epoch": contracts.Number(0), "decision": "D1", "revision": contracts.Number(0), "locale": locale, "participation": "judgment", "routing": map[string]any{"schema": "opensocrates.routing-features/1.0.0", "answer_shape": "direct_judgment", "features": []any{}, "classification_confidence": "high", "explicit_method": "critical-thinking"}}
}
func TestVolatileDeliveryAndScope(t *testing.T) {
	b, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	s := New(b)
	r := request("ko")
	first := s.Handle(r)
	if first["status"] != "selected" || first["selector_model_calls"] != 0 {
		t.Fatal(first)
	}
	methods := first["methods"].([]any)
	method := methods[0].(map[string]any)
	digest := method["sha256"].(string)
	if method["delivery"] != "emitted" {
		t.Fatal(method)
	}
	ack := s.Handle(map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": contracts.Number(0), "digests": []any{digest}})
	if ack["status"] != "acknowledged" {
		t.Fatal(ack)
	}
	again := s.Handle(r)
	m := again["methods"].([]any)[0].(map[string]any)
	if again["selection_reused"] != true || m["instructions"] != nil || m["delivery"] != "reused_agent_reported_available" {
		t.Fatal(again)
	}
	r["epoch"] = contracts.Number(1)
	next := s.Handle(r)
	if next["methods"].([]any)[0].(map[string]any)["instructions"] == nil {
		t.Fatal("new epoch retained old assertion")
	}
	r["epoch"] = contracts.Number(0)
	if s.Handle(r)["status"] != "unavailable" {
		t.Fatal("rollback accepted")
	}
}
func TestMalformedRequestCannotResetScope(t *testing.T) {
	b, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	s := New(b)
	r := request("en")
	first := s.Handle(r)
	digest := first["methods"].([]any)[0].(map[string]any)["sha256"].(string)
	s.Handle(map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": contracts.Number(0), "digests": []any{digest}})
	malformed := request("en")
	malformed["epoch"] = contracts.Number(1)
	malformed["participation"] = "bad"
	if s.Handle(malformed)["status"] != "unavailable" {
		t.Fatal("invalid request accepted")
	}
	again := s.Handle(r)
	if again["methods"].([]any)[0].(map[string]any)["instructions"] != nil {
		t.Fatal("invalid request erased scope")
	}
}
func TestDecisionContractsAreClosed(t *testing.T) {
	b, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	for _, mutate := range []func(map[string]any){func(r map[string]any) { r["epoch"] = true }, func(r map[string]any) { r["revision"] = contracts.Number(-1) }, func(r map[string]any) { r["prompt"] = "private" }, func(r map[string]any) { r["decision"] = "판단" }, func(r map[string]any) { r["routing"].(map[string]any)["features"] = nil }, func(r map[string]any) {
		r["routing"].(map[string]any)["features"] = []any{map[string]any{"key": "foreign", "strength": contracts.Number(1), "basis": "task_shape"}}
	}} {
		r := request("en")
		mutate(r)
		if New(b).Handle(r)["status"] != "unavailable" {
			t.Fatal("invalid request accepted")
		}
	}
	r := request("en")
	r["participation"] = "mechanical"
	response := New(b).Handle(r)
	if response["status"] != "no_intervention" || response["presentation"] != nil || len(response["methods"].([]any)) != 0 {
		t.Fatal(response)
	}
}

func TestDecisionCatalogAndDeliveryAllReleasedLocales(t *testing.T) {
	b, e := content.Load()
	if e != nil {
		t.Fatal(e)
	}
	for _, locale := range []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"} {
		s := New(b)
		catalog := s.Handle(map[string]any{"operation": "catalog", "locale": locale})
		if catalog["status"] != "catalog" || len(catalog["methods"].([]any)) != 48 {
			t.Fatal(locale, catalog)
		}
		for _, raw := range catalog["methods"].([]any) {
			if strings.TrimSpace(raw.(map[string]any)["use_for"].(string)) == "" {
				t.Fatal("missing localized catalog entry", locale)
			}
		}
		response := s.Handle(request(locale))
		if response["status"] != "selected" || response["selector_model_calls"] != 0 {
			t.Fatal(locale, response)
		}
		method := response["methods"].([]any)[0].(map[string]any)
		expected, e := b.Assemble([]string{"critical-thinking"}, locale)
		if e != nil || method["locale"] != locale || method["instructions"] != expected {
			t.Fatal("localized instructions mismatch", locale, e)
		}
	}
	for _, locale := range []string{"follow", "zh-CN", "JA", "fr-FR", "pt-BR", "th-TH", "ru", ""} {
		if got := New(b).Handle(request(locale)); got["status"] != "unavailable" {
			t.Fatal("decision accepted unsupported locale", locale)
		}
	}
}

func assertRequestFault(t *testing.T, got map[string]any, field, code, expected string) {
	t.Helper()
	for key, value := range Failure("invalid_decision_request") {
		if got[key] != value {
			t.Fatalf("failure contract %s: got %v", key, got)
		}
	}
	if got["field"] != field || got["error"] != code || got["repair"] != "correct_field_once" {
		t.Fatalf("wanted %s/%s, got %v", field, code, got)
	}
	wantFields := 8
	if expected != "" {
		wantFields++
		if got["expected"] != expected {
			t.Fatalf("expected guidance: got %v", got)
		}
	} else if _, exists := got["expected"]; exists {
		t.Fatalf("unexpected guidance: %v", got)
	}
	if len(got) != wantFields {
		t.Fatalf("unexpected response fields: %v", got)
	}
}

func sessionState(t *testing.T, s *Session) string {
	t.Helper()
	raw, err := contracts.CanonicalCompact(map[string]any{
		"context": s.context, "epoch": s.epoch, "key": s.lastKey,
		"route": s.lastRoute, "delivered": s.delivered, "available": s.available,
	})
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}

func featureEntry(key string) map[string]any {
	return map[string]any{"key": key, "strength": contracts.Number(3), "basis": "decision_need"}
}

// Mutate only authored synthetic requests; no host prompts or logs are fixtures.
func editRequest(r map[string]any, path string, value any, remove bool) {
	parts := strings.Split(path, ".")
	var target any = r
	for _, part := range parts[:len(parts)-1] {
		switch v := target.(type) {
		case map[string]any:
			target = v[part]
		case []any:
			i, _ := strconv.Atoi(part)
			target = v[i]
		}
	}
	last := parts[len(parts)-1]
	switch v := target.(type) {
	case map[string]any:
		if remove {
			delete(v, last)
		} else {
			v[last] = value
		}
	case []any:
		i, _ := strconv.Atoi(last)
		v[i] = value
	}
}

func TestSelectRepairContractPreservesEntireSession(t *testing.T) {
	b, err := content.Load()
	if err != nil {
		t.Fatal(err)
	}
	s := New(b)
	original := request("ko")
	original["epoch"] = contracts.Number(2)
	first := s.Handle(original)
	if first["status"] != "selected" {
		t.Fatal(first)
	}
	digest := first["methods"].([]any)[0].(map[string]any)["sha256"]
	if ack := s.Handle(map[string]any{"operation": "acknowledge", "context": original["context"], "epoch": contracts.Number(2), "digests": []any{digest}}); ack["status"] != "acknowledged" {
		t.Fatal(ack)
	}
	before := sessionState(t, s)
	for _, tc := range []struct {
		name, path, field, code, expected string
		value                             any
		remove                            bool
	}{
		{"context type", "context", "context", "invalid_type", "32 lowercase hexadecimal characters [0-9a-f]", true, false},
		{"context UUID", "context", "context", "invalid_format", "32 lowercase hexadecimal characters [0-9a-f]", "3F2B8C1E-7D4A-4E9B-A6C2-1F0E9D8B7A6C", false},
		{"epoch type", "epoch", "epoch", "invalid_type", "integer >= 0, never lower than the previous epoch for this context", "3", false},
		{"epoch negative", "epoch", "epoch", "invalid_value", "integer >= 0, never lower than the previous epoch for this context", contracts.Number(-1), false},
		{"decision type", "decision", "decision", "invalid_type", "1-64 ASCII letters or digits, no hyphen, underscore or space", nil, false},
		{"decision hyphen", "decision", "decision", "invalid_format", "1-64 ASCII letters or digits, no hyphen, underscore or space", "tessellate-priority", false},
		{"decision underscore", "decision", "decision", "invalid_format", "1-64 ASCII letters or digits, no hyphen, underscore or space", "next_priorities", false},
		{"decision non ASCII", "decision", "decision", "invalid_format", "1-64 ASCII letters or digits, no hyphen, underscore or space", "우선순위", false},
		{"decision empty", "decision", "decision", "invalid_format", "1-64 ASCII letters or digits, no hyphen, underscore or space", "", false},
		{"decision too long", "decision", "decision", "invalid_format", "1-64 ASCII letters or digits, no hyphen, underscore or space", strings.Repeat("D", 65), false},
		{"revision missing", "revision", "revision", "missing_field", "integer >= 0", nil, true},
		{"revision boolean", "revision", "revision", "invalid_type", "integer >= 0", true, false},
		{"revision negative", "revision", "revision", "invalid_value", "integer >= 0", contracts.Number(-1), false},
		{"locale region", "locale", "locale", "invalid_value", "one of en, ko, zh, ja, fr, de, it, es, pt, th", "ko-KR", false},
		{"participation spelling", "participation", "participation", "invalid_value", "one of judgment, mixed, mechanical", "judgement", false},
		{"unknown envelope key", "syntheticPrivateKey", "request", "unknown_field", "one JSON object with exactly the documented keys for its operation", "synthetic-private-value", false},
		{"routing type", "routing", "routing", "invalid_type", "", []any{}, false},
		{"routing missing", "routing.explicit_method", "routing.explicit_method", "missing_field", "null, or a catalog method ID the user requested", nil, true},
		{"routing unknown key", "routing.syntheticPrivateKey", "routing", "unknown_field", "", "synthetic-private-value", false},
		{"routing schema", "routing.schema", "routing.schema", "invalid_value", "opensocrates.routing-features/1.0.0", "opensocrates.routing-features/2.0.0", false},
		{"answer shape", "routing.answer_shape", "routing.answer_shape", "invalid_value", "a value from features.json answer_shapes", "synthetic-shape", false},
		{"confidence", "routing.classification_confidence", "routing.classification_confidence", "invalid_value", "one of high, medium, low", contracts.Number(1), false},
		{"explicit type", "routing.explicit_method", "routing.explicit_method", "invalid_type", "null, or a catalog method ID the user requested", []any{}, false},
		{"explicit format", "routing.explicit_method", "routing.explicit_method", "invalid_format", "null, or a catalog method ID the user requested", "invalid_method", false},
		{"features type", "routing.features", "routing.features", "invalid_type", "a list of at most 16 entries with key, strength and basis", nil, false},
		{"too many features", "routing.features", "routing.features", "too_many_features", "a list of at most 16 entries with key, strength and basis", make([]any, 17), false},
		{"entry type", "routing.features.0", "routing.features[0]", "invalid_type", "", "synthetic-private-value", false},
		{"entry missing", "routing.features.0.basis", "routing.features[0].basis", "missing_field", "a value from features.json basis", nil, true},
		{"entry unknown key", "routing.features.0.syntheticPrivateKey", "routing.features[0]", "unknown_field", "", "synthetic-private-value", false},
		{"unknown feature", "routing.features.0.key", "routing.features[0].key", "unknown_feature", "a value from features.json features, used once", "synthetic-private-feature", false},
		{"duplicate feature", "routing.features.1.key", "routing.features[1].key", "duplicate_feature", "a value from features.json features, used once", "choose", false},
		{"basis value", "routing.features.0.basis", "routing.features[0].basis", "invalid_value", "a value from features.json basis", "synthetic-private-basis", false},
		{"strength boolean", "routing.features.0.strength", "routing.features[0].strength", "invalid_type", "integer 1, 2 or 3", true, false},
		{"strength zero", "routing.features.0.strength", "routing.features[0].strength", "invalid_value", "integer 1, 2 or 3", contracts.Number(0), false},
		{"strength catalog weight", "routing.features.0.strength", "routing.features[0].strength", "invalid_value", "integer 1, 2 or 3", contracts.Number(5), false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			r := request("en")
			r["context"], r["epoch"] = strings.Repeat("b", 32), contracts.Number(3)
			r["routing"].(map[string]any)["features"] = []any{featureEntry("choose"), featureEntry("multiple_options")}
			editRequest(r, tc.path, tc.value, tc.remove)
			got := s.Handle(r)
			assertRequestFault(t, got, tc.field, tc.code, tc.expected)
			wire, err := contracts.CanonicalCompact(got)
			if err != nil || strings.Contains(string(wire), "synthetic-private") || strings.Contains(string(wire), "syntheticPrivateKey") {
				t.Fatal("repair response exposed synthetic submitted content")
			}
			if sessionState(t, s) != before {
				t.Fatal("rejected input changed session state")
			}
		})
	}
	again := s.Handle(original)
	if again["selection_reused"] != true || again["methods"].([]any)[0].(map[string]any)["instructions"] != nil {
		t.Fatal("rejected inputs lost prior selection or availability")
	}
}

func TestRequestFaultOrderAndRepairToCanonicalDelivery(t *testing.T) {
	b, err := content.Load()
	if err != nil {
		t.Fatal(err)
	}
	s := New(b)
	r := request("ko")
	r["context"], r["decision"] = "3F2B8C1E-7D4A-4E9B-A6C2-1F0E9D8B7A6C", "tessellate-priority"
	assertRequestFault(t, s.Handle(r), "context", "invalid_format", "32 lowercase hexadecimal characters [0-9a-f]")
	r["context"] = "3f2b8c1e7d4a4e9ba6c21f0e9d8b7a6c"
	assertRequestFault(t, s.Handle(r), "decision", "invalid_format", "1-64 ASCII letters or digits, no hyphen, underscore or space")
	r["decision"] = strings.Repeat("Ab09", 16)
	got := s.Handle(r)
	expected, err := b.Assemble([]string{"critical-thinking"}, "ko")
	if err != nil || got["status"] != "selected" || got["applied"] != "unverified" || got["selector_model_calls"] != 0 {
		t.Fatal("corrected request did not reach canonical selection", err, got)
	}
	method := got["methods"].([]any)[0].(map[string]any)
	if method["instructions"] != expected || method["locale"] != "ko" || method["read"] != "unverified" {
		t.Fatal("corrected request did not deliver exact locale without claiming a read")
	}
	r["epoch"], r["decision"] = contracts.Number(2), "D2"
	if s.Handle(r)["status"] != "selected" {
		t.Fatal("valid epoch advance rejected")
	}
	before := sessionState(t, s)
	r["epoch"], r["decision"] = contracts.Number(1), "bad-id"
	assertRequestFault(t, s.Handle(r), "epoch", "stale_epoch", "integer >= 0, never lower than the previous epoch for this context")
	if sessionState(t, s) != before {
		t.Fatal("stale epoch changed state")
	}
	// Missing envelope fields precede unknown keys, in envelope order.
	r = request("en")
	delete(r, "context")
	delete(r, "epoch")
	r["syntheticPrivateKey"] = "synthetic-private-value"
	assertRequestFault(t, s.Handle(r), "context", "missing_field", "32 lowercase hexadecimal characters [0-9a-f]")
	// Missing nested fields use Python #130's sorted-key order.
	r = request("en")
	delete(r["routing"].(map[string]any), "schema")
	delete(r["routing"].(map[string]any), "answer_shape")
	assertRequestFault(t, s.Handle(r), "routing.answer_shape", "missing_field", "a value from features.json answer_shapes")
	// Structural faults later in a list take precedence over unknown/duplicate keys.
	r = request("en")
	bad := featureEntry("choose")
	bad["strength"] = true
	r["routing"].(map[string]any)["features"] = []any{featureEntry("synthetic-private-feature"), bad}
	assertRequestFault(t, s.Handle(r), "routing.features[1].strength", "invalid_type", "integer 1, 2 or 3")
	r["routing"].(map[string]any)["features"] = []any{featureEntry("choose"), featureEntry("choose")}
	r["routing"].(map[string]any)["explicit_method"] = "invalid_method"
	assertRequestFault(t, s.Handle(r), "routing.explicit_method", "invalid_format", "null, or a catalog method ID the user requested")
}

func TestOtherOperationRepairFaultsAreAtomic(t *testing.T) {
	b, err := content.Load()
	if err != nil {
		t.Fatal(err)
	}
	s := New(b)
	assertRequestFault(t, s.Handle(map[string]any{"operation": "acknowledge", "context": "", "epoch": contracts.Number(0), "digests": []any{}}), "context", "invalid_value", "32 lowercase hexadecimal characters [0-9a-f]")
	r := request("en")
	first := s.Handle(r)
	if first["status"] != "selected" {
		t.Fatal(first)
	}
	digest := first["methods"].([]any)[0].(map[string]any)["sha256"]
	before := sessionState(t, s)
	for _, tc := range []struct {
		name, field, code, expected string
		value                       any
	}{
		{"not object", "request", "invalid_type", "one JSON object with exactly the documented keys for its operation", []any{}},
		{"null", "request", "invalid_type", "one JSON object with exactly the documented keys for its operation", nil},
		{"missing operation", "operation", "missing_field", "one of catalog, select, acknowledge, reset", map[string]any{}},
		{"unknown operation", "operation", "unknown_operation", "one of catalog, select, acknowledge, reset", map[string]any{"operation": "synthetic-private-operation"}},
		{"reset unknown key", "request", "unknown_field", "one JSON object with exactly the documented keys for its operation", map[string]any{"operation": "reset", "syntheticPrivateKey": "synthetic-private-value"}},
		{"catalog missing locale", "locale", "missing_field", "one of en, ko, zh, ja, fr, de, it, es, pt, th", map[string]any{"operation": "catalog"}},
		{"catalog locale type", "locale", "invalid_value", "one of en, ko, zh, ja, fr, de, it, es, pt, th", map[string]any{"operation": "catalog", "locale": []any{"ko"}}},
		{"ack missing digests", "digests", "missing_field", "", map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": contracts.Number(0)}},
		{"ack epoch type", "epoch", "invalid_type", "integer >= 0, never lower than the previous epoch for this context", map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": true, "digests": []any{}}},
		{"ack context", "context", "invalid_value", "32 lowercase hexadecimal characters [0-9a-f]", map[string]any{"operation": "acknowledge", "context": strings.Repeat("b", 32), "epoch": contracts.Number(0), "digests": []any{}}},
		{"ack epoch", "epoch", "invalid_value", "integer >= 0, never lower than the previous epoch for this context", map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": contracts.Number(1), "digests": []any{}}},
		{"ack digests type", "digests", "invalid_type", "", map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": contracts.Number(0), "digests": nil}},
		{"ack too many digests", "digests", "invalid_type", "", map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": contracts.Number(0), "digests": make([]any, len(b.Methods)+1)}},
		{"ack no partial availability", "digests", "invalid_value", "", map[string]any{"operation": "acknowledge", "context": r["context"], "epoch": contracts.Number(0), "digests": []any{digest, "synthetic-private-digest"}}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			assertRequestFault(t, s.Handle(tc.value), tc.field, tc.code, tc.expected)
			if sessionState(t, s) != before {
				t.Fatal("invalid operation changed session state")
			}
		})
	}
	// Unknown methods and lock contention remain unavailable, without input repair.
	r["routing"].(map[string]any)["explicit_method"] = "not-a-method"
	if got := s.Handle(r); got["reason"] != "unknown_method" || len(got) != 5 {
		t.Fatal(got)
	}
	if sessionState(t, s) != before {
		t.Fatal("unknown method changed state")
	}
	s.mu.Lock()
	got := s.Handle(request("en"))
	s.mu.Unlock()
	if got["reason"] != "recursive_request" || len(got) != 5 {
		t.Fatal(got)
	}
}
