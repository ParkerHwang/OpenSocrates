package application_test

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/application"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/persistence"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const controlToken = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

func controlFixture(t *testing.T, recording bool) (*application.ControlApplication, *persistence.TurnStore) {
	t.Helper()
	root := t.TempDir()
	store, e := persistence.NewTurnStore(root)
	if e != nil {
		t.Fatal(e)
	}
	tag, _ := store.TokenTag(controlToken)
	state := map[string]any{"schema": "opensocrates.ephemeral-turn-state/1.0.0", "token_tag": tag, "host_session_key": "sha256:" + strings.Repeat("1", 64), "host_turn_key": nil, "host": "codex_cli", "issued_at": "2026-10-12T00:00:00.000Z", "expires_at": "2026-10-12T06:00:00.000Z", "recording_eligible": recording, "onboarding_disclosure_turn": false, "task_id": nil, "judgment_id": nil, "task_state": "new", "participation": nil, "effective_rigor": "together", "primary_method": nil, "secondary_method": nil, "repair_count": contracts.Number(0), "accepted_controls": []any{}, "observation_tags": []any{}}
	if e = store.Issue(state); e != nil {
		t.Fatal(e)
	}
	app := &application.ControlApplication{Turns: store, Records: persistence.RecordStore{Root: root}, Settings: persistence.SettingsStore{Root: root}, Clock: func() time.Time { return time.Date(2026, 10, 12, 1, 0, 0, 0, time.UTC) }}
	return app, store
}
func beginPayload() map[string]any {
	return map[string]any{"participation": map[string]any{"schema": "opensocrates.participation-decision/1.0.0", "participation": "judgment", "reason_code": "judgment_choice", "judgment_targets": []any{"Choose an option"}, "mechanical_targets": []any{}, "confidence_basis": "rule_plus_model_policy", "explicit_method": nil}, "rigor": map[string]any{"schema": "opensocrates.rigor-decision/1.0.0", "stored_rigor": "together", "task_override": nil, "risk_floor": "together", "risk_reason": "ordinary_judgment", "effective_rigor": "together", "show_raise_notice": false}, "routing_features": map[string]any{"schema": "opensocrates.routing-features/1.0.0", "answer_shape": "direct_judgment", "classification_confidence": "high", "explicit_method": nil, "features": []any{}}}
}
func request(kind string, p map[string]any, confirmed bool) application.ControlRequest {
	raw, _ := contracts.CanonicalCompact(map[string]any{"schema": "opensocrates.host-control/1.0.0", "message_id": domain.NewMessageID(), "turn_token": controlToken, "message_type": kind, "published": true, "payload": p})
	return application.ControlRequest{Raw: raw, PublicArtifactConfirmed: confirmed}
}
func resultOK(t *testing.T, r domain.ControlResult, durable bool) {
	t.Helper()
	want := "accepted_not_recorded"
	if durable {
		want = "accepted"
	}
	if r.Status != want || r.DurableMutation != durable {
		t.Fatalf("unexpected result: %+v", r)
	}
	v, e := domain.Normalize(r)
	if e != nil || contracts.Validate("host-control-result", v) != nil {
		t.Fatalf("invalid result %+v: %v", r, e)
	}
}
func framingPayload() map[string]any {
	return map[string]any{"decision_question": "Which option meets the requirement?", "assumptions": []any{}, "decisive_evidence": []any{}, "completion_criteria": []any{map[string]any{"text": "The selected option meets the requirement", "required": true, "kind": "structural", "evidence_claim_ids": []any{}}}}
}
func TestControlFullPublicGraph(t *testing.T) {
	app, store := controlFixture(t, true)
	begin := app.Apply(request("begin_judgment", beginPayload(), false))
	resultOK(t, begin, true)
	if begin.AssignedIDs.TaskID == nil || begin.Route["prompt_bundle_hash"] == nil {
		t.Fatal("begin lost task or frozen content identity")
	}
	task := *begin.AssignedIDs.TaskID
	framing := app.Apply(request("publish_framing", framingPayload(), true))
	resultOK(t, framing, true)
	if len(framing.AssignedIDs.CriterionIDs) != 1 || framing.AssignedIDs.CriterionIDs[0] != "K000001" {
		t.Fatal("criterion allocation changed")
	}
	source := map[string]any{"kind": "web", "display_name": "Public reference", "uri": "https://example.com/reference?token=private-value", "safe_locator": nil, "published_at": nil, "checked_at": "2026-10-12T00:30:00.000Z", "content_hash": nil}
	claimP := map[string]any{"claim_ref": nil, "expected_current_version": nil, "text": "The documented option meets the requirement", "materiality": "material", "evidence_state": "verified", "source_refs": []any{map[string]any{"new_index": contracts.Number(0)}}, "new_sources": []any{source}, "basis_claim_ids": []any{}, "calculation": nil, "conflict": nil}
	claim := app.Apply(request("publish_claim", claimP, true))
	resultOK(t, claim, true)
	if claim.AssignedIDs.ClaimIDs[0] != "C000001" || claim.AssignedIDs.SourceIDs[0] != "E000001" {
		t.Fatal("local source/claim IDs changed")
	}
	alternative := app.Apply(request("publish_alternative", map[string]any{"name": "Other option", "disposition": "rejected", "reason": "The requirement is unmet", "material_claim_ids": []any{"C000001"}}, true))
	resultOK(t, alternative, true)
	conflict := map[string]any{"schema": "opensocrates.conflict/1.0.0", "summary": "The evidence disagrees", "subject": "Option suitability", "source_ids": []any{}, "affected_claim_ids": []any{"C000001"}, "material": true, "resolution": "unresolved", "resolution_reason": nil}
	resultOK(t, app.Apply(request("publish_conflict", map[string]any{"conflict": conflict, "affected_claim_ids": []any{"C000001"}}, true)), true)
	revision := map[string]any{"conclusion": "Use the documented option provisionally", "strength": "provisional", "change_reason": "The new evidence creates uncertainty", "ground_claim_ids": []any{"C000001"}, "uncertainty_claim_ids": []any{}, "alternative_ids": []any{"A000001"}, "flip_conditions": []any{}}
	resultOK(t, app.Apply(request("revise_judgment", revision, true)), true)
	resultOK(t, app.Apply(request("complete_cross_exam", map[string]any{"findings_summary": "The alternate evidence was considered", "affected_ids": []any{"J000001", "C000001"}}, true)), true)
	resultOK(t, app.Apply(request("hold_judgment", map[string]any{"missing_items": []any{"A decisive public source"}, "reason_code": "evidence_missing"}, true)), true)
	state, e := store.Load(controlToken)
	if e != nil || state != nil {
		t.Fatal("terminal token survived", e)
	}
	events, e := app.Records.Events(task)
	if e != nil || len(events) != 11 {
		t.Fatalf("public event count %d: %v", len(events), e)
	}
	for _, event := range events {
		p := event["payload"].(map[string]any)
		if event["event_type"] == "source_published" && p["source_reference"].(map[string]any)["uri"] != nil {
			t.Fatal("credential URI persisted")
		}
		if event["event_type"] == "conclusion_published" {
			j := p["judgment_version"].(map[string]any)
			if _, exists := j["schema"]; exists {
				t.Fatal("foreign schema added to stored JudgmentVersion")
			}
			n, _ := contracts.Int(j["version"])
			if n != 2 {
				t.Fatal("revision did not supersede active version")
			}
		}
	}
}
func TestControlReplayAndStaleReference(t *testing.T) {
	app, _ := controlFixture(t, false)
	req := request("begin_judgment", beginPayload(), false)
	first := app.Apply(req)
	resultOK(t, first, false)
	second := app.Apply(req)
	if second.Status != "replayed" || second.DurableMutation {
		t.Fatalf("replay changed durability %+v", second)
	}
	decoded, _ := contracts.Decode(req.Raw)
	wire := decoded.(map[string]any)
	wire["published"] = false
	req.Raw, _ = contracts.CanonicalCompact(wire)
	different := app.Apply(req)
	if different.ErrorCode == nil || *different.ErrorCode != "replayed_with_different_payload" {
		t.Fatalf("bad replay %+v", different)
	}
	p := framingPayload()
	p["completion_criteria"].([]any)[0].(map[string]any)["evidence_claim_ids"] = []any{"C000001"}
	bad := app.Apply(request("publish_framing", p, false))
	if bad.ErrorCode == nil || *bad.ErrorCode != "stale_reference" {
		t.Fatalf("discarded public prose bypassed reference guards %+v", bad)
	}
	resultOK(t, app.Apply(request("publish_framing", framingPayload(), false)), false)
}
func TestControlCancellationExpiryAndCapacity(t *testing.T) {
	app, store := controlFixture(t, false)
	resultOK(t, app.Apply(request("begin_judgment", beginPayload(), false)), false)
	cancel := app.Apply(request("cancel_judgment", map[string]any{"reason": "user_cancelled"}, false))
	resultOK(t, cancel, false)
	if cancel.NextAction != "stop_control_calls" {
		t.Fatal("cancel did not stop")
	}
	if state, _ := store.Load(controlToken); state != nil {
		t.Fatal("cancel retained turn")
	}
	app, store = controlFixture(t, false)
	app.Clock = func() time.Time { return time.Date(2026, 10, 12, 6, 0, 0, 0, time.UTC) }
	expired := app.Apply(request("begin_judgment", beginPayload(), false))
	if expired.ErrorCode == nil || *expired.ErrorCode != "expired_token" {
		t.Fatalf("expiry %+v", expired)
	}
	if state, _ := store.Load(controlToken); state != nil {
		t.Fatal("expired state retained")
	}
	app, store = controlFixture(t, false)
	original, _ := store.Load(controlToken)
	next, _ := domain.Normalize(original)
	for i := 0; i < domain.MaxAcceptedControls; i++ {
		id := domain.NewMessageID()
		r := domain.NewControlResult(id)
		r.Status = "accepted_not_recorded"
		if e := domain.AppendAcceptedControl(next, id, "sha256:"+strings.Repeat("2", 64), r); e != nil {
			t.Fatal(e)
		}
	}
	if e := store.CompareAndSwap(original, next); e != nil {
		t.Fatal(e)
	}
	capacity := app.Apply(request("begin_judgment", beginPayload(), false))
	if capacity.ErrorCode == nil || *capacity.ErrorCode != "capacity_exhausted" {
		t.Fatalf("capacity %+v", capacity)
	}
}
func TestControlFeedbackAuthorityAndLargeRevision(t *testing.T) {
	app, store := controlFixture(t, false)
	settings := app.Settings.(persistence.SettingsStore)
	_, e := settings.Mutate(func(current domain.UserSettings) (domain.UserSettings, error) {
		next := current.Clone()
		next.Value["revision"] = current.NextRevision()
		return next, nil
	})
	if e != nil {
		t.Fatal(e)
	}
	req := request("intervention_feedback", map[string]any{"class": "reframe", "outcome": "dismissed"}, false)
	unauthorized := app.Apply(req)
	if unauthorized.ErrorCode == nil || *unauthorized.ErrorCode != "invalid_payload" {
		t.Fatalf("model feedback granted authority %+v", unauthorized)
	}
	state, _ := store.Load(controlToken)
	req.DirectUserAuthority = true
	req.CurrentEvent = map[string]any{"schema": "opensocrates.normalized-event/1.0.0", "event_id": domain.NewMessageID(), "event_type": "user_prompt_submitted", "occurred_at": "2026-10-12T01:00:00.000Z", "host": "codex_cli", "host_version": "1.0.0", "adapter_version": "1.0.0", "host_session_key": state["host_session_key"], "host_turn_key": state["host_turn_key"], "payload": map[string]any{}}
	resultOK(t, app.Apply(req), true)
	after := settings.Load()
	pref := after.Value["intervention_preferences"].(map[string]any)["reframe"].(map[string]any)
	ring := pref["recent_feedback"].([]any)
	if len(ring) != 1 || ring[0].(map[string]any)["outcome"] != "dismissed" {
		t.Fatal("explicit feedback lost")
	}
	rawSettings := after.Clone()
	rawSettings.Value["revision"] = json.Number("9007199254740993123456789")
	rawSettings.Value["intervention_preferences"].(map[string]any)["reframe"].(map[string]any)["next_sequence"] = json.Number("9007199254740993123456789")
	encoded, _ := contracts.CanonicalJSON(rawSettings.Value)
	if e = platform.AtomicWrite(filepath.Join(store.Root, "settings.json"), encoded, 0600); e != nil {
		t.Fatal(e)
	}
	req = request("intervention_feedback", map[string]any{"class": "reframe", "outcome": "accepted"}, false)
	req.DirectUserAuthority = true
	req.CurrentEvent = map[string]any{"schema": "opensocrates.normalized-event/1.0.0", "event_id": domain.NewMessageID(), "event_type": "user_prompt_submitted", "occurred_at": "2026-10-12T01:00:00.000Z", "host": "codex_cli", "host_version": "1.0.0", "adapter_version": "1.0.0", "host_session_key": state["host_session_key"], "host_turn_key": nil, "payload": map[string]any{}}
	resultOK(t, app.Apply(req), true)
	after = settings.Load()
	if after.Value["revision"] != json.Number("9007199254740993123456790") {
		t.Fatal("feedback revision lost precision")
	}
	pref = after.Value["intervention_preferences"].(map[string]any)["reframe"].(map[string]any)
	if pref["next_sequence"] != json.Number("9007199254740993123456790") {
		t.Fatal("feedback sequence lost precision")
	}
}
