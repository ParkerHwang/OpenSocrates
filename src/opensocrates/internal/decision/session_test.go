package decision

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
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
