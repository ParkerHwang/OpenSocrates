package domain

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"strings"
	"testing"
)

func wireControl(kind string, published bool, payload map[string]any) []byte {
	raw, _ := contracts.CanonicalCompact(map[string]any{"schema": "opensocrates.host-control/1.0.0", "message_id": "019a0000-0000-7000-8000-000000000001", "turn_token": strings.Repeat("A", 43), "message_type": kind, "published": published, "payload": payload})
	return raw
}
func TestControlJSONBoundary(t *testing.T) {
	valid := wireControl("cancel_judgment", false, map[string]any{"reason": "user_cancelled"})
	if _, e := ParseControl(valid); e != nil {
		t.Fatal(e)
	}
	for name, raw := range map[string][]byte{"duplicate": []byte(strings.Replace(string(valid), `"published":false`, `"published":false,"published":true`, 1)), "unknown": []byte(strings.Replace(string(valid), `"payload":`, `"foreign":null,"payload":`, 1)), "utf8": append(valid, 0xff), "surrogate": []byte(strings.Replace(string(valid), "user_cancelled", `\ud800`, 1)), "null_boolean": []byte(strings.Replace(string(valid), `"published":false`, `"published":null`, 1)), "oversized": append(valid, []byte(strings.Repeat(" ", MaxControlBytes))...)} {
		t.Run(name, func(t *testing.T) {
			if _, e := ParseControl(raw); e == nil {
				t.Fatal("accepted invalid control")
			}
		})
	}
}
func TestControlUnicodeAndContentGuard(t *testing.T) {
	for _, v := range []any{map[string]any{"Ｐｒｏｍｐｔ": "x"}, map[string]any{"payload": map[string]any{"chain-of-thought": "x"}}, "e\u0301", "x\x00"} {
		if e := GuardControlTree(v, 0); e == nil {
			t.Fatal("accepted prohibited input")
		}
	}
	if e := GuardControlTree(map[string]any{"decision_question": "어떤 선택이 좋은가?"}, 0); e != nil {
		t.Fatal(e)
	}
}
func TestTurnTagDomainSeparation(t *testing.T) {
	key := make([]byte, 32)
	token := strings.Repeat("A", 43)
	a, e := TokenTag(token, key)
	if e != nil {
		t.Fatal(e)
	}
	b, _ := TokenTag(token, append([]byte{1}, key[1:]...))
	c, _ := PayloadTag(map[string]any{"id": token}, key)
	d, _ := ObservationTag(token, "observation", key)
	if a == b || a == c || a == d || c == d {
		t.Fatal("domain or installation tags collided")
	}
	if _, e = TokenTag(token, key[:31]); e == nil {
		t.Fatal("short key accepted")
	}
	if strings.Contains(a, token) {
		t.Fatal("raw token retained")
	}
}
func TestClaimRevisionArbitraryPrecision(t *testing.T) {
	payload := map[string]any{"claim_ref": "C000001", "expected_current_version": json.Number("9007199254740993123456789"), "text": "Public claim", "materiality": "material", "evidence_state": "unverified", "source_refs": []any{}, "new_sources": []any{}, "basis_claim_ids": []any{}, "calculation": nil, "conflict": nil}
	if _, e := ParseControl(wireControl("publish_claim", true, payload)); e != nil {
		t.Fatal(e)
	}
	delete(payload, "calculation")
	if _, e := ParseControl(wireControl("publish_claim", true, payload)); e == nil {
		t.Fatal("omitted required null accepted")
	}
}
func TestControlTransitions(t *testing.T) {
	for _, tc := range []struct{ kind, from, to string }{{"publish_framing", "framing", "working"}, {"publish_conflict", "working", "rejudging"}, {"revise_judgment", "rejudging", "cross_examining"}, {"complete_cross_exam", "cross_examining", "verifying"}, {"hold_judgment", "verifying", "insufficient"}, {"cancel_judgment", "degraded", "cancelled"}} {
		next, e := NextControlState(tc.kind, tc.from)
		if e != nil || next != tc.to {
			t.Fatalf("%+v: %s %v", tc, next, e)
		}
	}
	if _, e := NextControlState("publish_framing", "new"); e == nil {
		t.Fatal("illegal phase accepted")
	}
}
func TestExpiryCanonicalSixHours(t *testing.T) {
	issued := "2026-10-12T00:00:00.000Z"
	expiry, e := ExpiryFor(issued)
	if e != nil || expiry != "2026-10-12T06:00:00.000Z" {
		t.Fatalf("%s %v", expiry, e)
	}
	for _, s := range []string{"2026-10-12T00:00:00Z", "2026-13-12T00:00:00.000Z", "2026-10-12T00:00:00.00Z"} {
		if _, e := ExpiryFor(s); e == nil {
			t.Fatal(s)
		}
	}
}

func TestControlRootErrorCategories(t *testing.T) {
	for _, tc := range []struct{ raw, want string }{
		{`[]`, "invalid_json"}, {`[{}]`, "invalid_json"}, {`null`, "invalid_json"},
		{`"control"`, "invalid_json"}, {`true`, "invalid_json"}, {`false`, "invalid_json"},
		{`0`, "invalid_json"}, {`1.5`, "invalid_json"},
		{`{}`, "invalid_payload"}, {`{"schema":null}`, "invalid_payload"},
	} {
		t.Run(tc.raw, func(t *testing.T) {
			_, e := ParseControl([]byte(tc.raw))
			if e == nil || e.Error() != tc.want {
				t.Fatalf("error=%v want=%s", e, tc.want)
			}
		})
	}
}
