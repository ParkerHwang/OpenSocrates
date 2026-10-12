// Package application composes pure domain policies and typed persistence
// ports. Host-native serialization remains outside this layer.
package application

import (
	"encoding/json"
	"errors"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/verification"
	"math/big"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"time"
)

type TurnRepository interface {
	Key() []byte
	WithTurn(string, func(map[string]any) (map[string]any, bool, error)) error
}
type ControlRecordRepository interface {
	Events(string) ([]map[string]any, error)
	AppendEvents(string, []map[string]any) error
}
type ControlSettingsRepository interface {
	Load() domain.UserSettings
	Mutate(func(domain.UserSettings) (domain.UserSettings, error)) (domain.UserSettings, error)
}
type ControlRequest struct {
	Raw                     []byte
	CurrentEvent            map[string]any
	PublicArtifactConfirmed bool
	DirectUserAuthority     bool
	CapabilityProfile       map[string]any
}
type ControlApplication struct {
	Turns             TurnRepository
	Records           ControlRecordRepository
	Settings          ControlSettingsRepository
	Bundle            *content.Bundle
	Clock             func() time.Time
	Locale            string
	HostVersion       string
	AdapterVersion    string
	CapabilityProfile map[string]any
}

func (a *ControlApplication) now() time.Time {
	if a.Clock != nil {
		return a.Clock().UTC()
	}
	return time.Now().UTC()
}
func controlError(id, code string) domain.ControlResult {
	r := domain.NewControlResult(id)
	r.ErrorCode = domain.Pointer(code)
	if code == "store_unavailable" || code == "capacity_exhausted" {
		r.ReasonCode = domain.Pointer(code)
	}
	return r
}
func controlCode(e error) string {
	if e == nil {
		return "internal_error"
	}
	for _, v := range strings.Fields("invalid_json oversized unknown_schema invalid_token expired_token replayed_with_different_payload unknown_message_type invalid_payload invalid_state_transition stale_reference store_unavailable capacity_exhausted internal_error") {
		if e.Error() == v {
			return v
		}
	}
	return "store_unavailable"
}
func (a *ControlApplication) Apply(request ControlRequest) domain.ControlResult {
	c, e := domain.ParseControl(request.Raw)
	if e != nil {
		return controlError(c.MessageID, controlCode(e))
	}
	if a.Turns == nil {
		return controlError(c.MessageID, "store_unavailable")
	}
	result := controlError(c.MessageID, "internal_error")
	e = a.Turns.WithTurn(c.TurnToken, func(state map[string]any) (map[string]any, bool, error) {
		if state == nil {
			return nil, false, errors.New("invalid_token")
		}
		if e := domain.RequireActiveTurn(state, a.now()); e != nil {
			if errors.Is(e, domain.ErrExpiredTurn) {
				result = controlError(c.MessageID, "expired_token")
				return nil, true, nil
			}
			return nil, false, e
		}
		if request.CurrentEvent != nil {
			if e := contracts.Validate("normalized-event", request.CurrentEvent); e != nil {
				return nil, false, domain.ErrControl
			}
			if request.CurrentEvent["host_session_key"] != state["host_session_key"] || request.CurrentEvent["host_turn_key"] != state["host_turn_key"] {
				return nil, false, errors.New("stale_reference")
			}
		}
		tag, e := domain.PayloadTag(map[string]any{"message_type": c.MessageType, "published": c.Published, "payload": c.Payload}, a.Turns.Key())
		if e != nil {
			return nil, false, e
		}
		if prior := domain.AcceptedControl(state, c.MessageID); prior != nil {
			if prior["payload_tag"] != tag {
				return nil, false, errors.New("replayed_with_different_payload")
			}
			b, _ := contracts.CanonicalCompact(prior["result"])
			if e = json.Unmarshal(b, &result); e != nil {
				return nil, false, errors.New("store_unavailable")
			}
			result.Status = "replayed"
			return nil, false, nil
		}
		accepted := state["accepted_controls"].([]any)
		if len(accepted) >= domain.MaxAcceptedControls {
			return nil, false, domain.ErrCapacity
		}
		phase, _ := state["task_state"].(string)
		if !domain.LegalControlTransition(c.MessageType, phase) {
			return nil, false, errors.New("invalid_state_transition")
		}
		next, e := domain.Normalize(state)
		if e != nil {
			return nil, false, e
		}
		result = domain.NewControlResult(c.MessageID)
		result.Status = "accepted_not_recorded"
		result.EffectiveRigor = domain.Pointer(state["effective_rigor"].(string))
		profile := request.CapabilityProfile
		if profile == nil {
			profile = a.CapabilityProfile
		}
		result.CapabilityLimitations = controlLimitations(profile)
		var events []map[string]any
		priorEvents := []map[string]any{}
		task, _ := state["task_id"].(string)
		if task != "" {
			if a.Records == nil {
				return nil, false, errors.New("store_unavailable")
			}
			priorEvents, e = a.Records.Events(task)
			if e != nil {
				return nil, false, errors.New("store_unavailable")
			}
		}
		if e = validateReferences(c, priorEvents); e != nil {
			return nil, false, e
		}
		switch c.MessageType {
		case "begin_judgment":
			events, e = a.begin(next, c, &result, request, priorEvents)
		case "intervention_feedback":
			if !request.DirectUserAuthority || request.CurrentEvent == nil || request.CurrentEvent["event_type"] != "user_prompt_submitted" {
				e = domain.ErrControl
				break
			}
			if a.Settings == nil {
				e = errors.New("store_unavailable")
				break
			}
			p := c.Payload
			day := a.now().Format("2006-01-02")
			if s, ok := request.CurrentEvent["occurred_at"].(string); ok && len(s) >= 10 {
				day = s[:10]
			}
			_, e = a.Settings.Mutate(func(current domain.UserSettings) (domain.UserSettings, error) {
				next := current.Normalize()
				prefs := next.Value["intervention_preferences"].(map[string]any)
				pref := prefs[p["class"].(string)].(map[string]any)
				sequence, ok := contracts.Integer(pref["next_sequence"])
				if !ok {
					return current, domain.ErrControl
				}
				ring := pref["recent_feedback"].([]any)
				ring = append(ring, map[string]any{"sequence": json.Number(sequence.String()), "day": day, "outcome": p["outcome"]})
				if len(ring) > 20 {
					ring = ring[len(ring)-20:]
				}
				pref["recent_feedback"], pref["next_sequence"] = ring, json.Number(new(big.Int).Add(sequence, big.NewInt(1)).String())
				next.Value["revision"] = current.NextRevision()
				return next, nil
			})
			if e == nil {
				result.DurableMutation = true
			}
		default:
			nextPhase, err := domain.NextControlState(c.MessageType, phase)
			if err != nil {
				e = err
				break
			}
			next["task_state"] = nextPhase
			record, _ := state["recording_eligible"].(bool)
			confirmed := request.PublicArtifactConfirmed && (profile == nil || controlCapability(profile, "published_artifact_confirmation"))
			if c.MessageType == "cancel_judgment" {
				confirmed = true
			}
			if record && confirmed {
				events, e = a.publicEvents(next, c, &result, request, priorEvents)
			} else {
				reason := "recording_off"
				if record && !confirmed {
					reason = "public_artifact_unconfirmed"
				} else if state["onboarding_disclosure_turn"] == true {
					reason = "onboarding_disclosure_turn"
				}
				result.ReasonCode = domain.Pointer(reason)
			}
			if c.MessageType == "hold_judgment" || c.MessageType == "cancel_judgment" {
				result.NextAction = "stop_control_calls"
			}
		}
		if e != nil {
			return nil, false, e
		}
		if len(events) > 0 {
			for i, event := range events {
				normalized, e := domain.Normalize(event)
				if e != nil {
					return nil, false, e
				}
				events[i] = normalized
			}
			if a.Records == nil {
				return nil, false, errors.New("store_unavailable")
			}
			task, _ = next["task_id"].(string)
			if e = a.Records.AppendEvents(task, events); e != nil {
				return nil, false, errors.New("store_unavailable")
			}
			result.DurableMutation = true
		}
		if result.DurableMutation {
			result.Status = "accepted"
			result.ReasonCode = nil
		}
		result.EffectiveRigor = domain.Pointer(next["effective_rigor"].(string))
		boundedResult(&result)
		phase, _ = next["task_state"].(string)
		if result.NextAction == "stop_control_calls" || domain.Has([]string{"cancelled", "insufficient", "concluded", "bypassed"}, phase) {
			return nil, true, nil
		}
		if e = domain.AppendAcceptedControl(next, c.MessageID, tag, result); e != nil {
			return nil, false, e
		}
		return next, false, nil
	})
	if e != nil {
		return controlError(c.MessageID, controlCode(e))
	}
	return result
}
func boundedResult(r *domain.ControlResult) {
	raw, e := contracts.CanonicalJSON(r)
	if e != nil || len(raw) > 1536 {
		r.Route = nil
		r.CapabilityLimitations = []string{}
	}
}
func controlCapability(profile map[string]any, key string) bool {
	caps, _ := profile["capabilities"].(map[string]any)
	entry, _ := caps[key].(map[string]any)
	return entry["status"] == "supported"
}
func controlLimitations(profile map[string]any) []string {
	if profile == nil {
		return []string{}
	}
	caps, _ := profile["capabilities"].(map[string]any)
	out := []string{}
	seen := map[string]bool{}
	for _, key := range []string{"local_control_execution", "published_artifact_confirmation", "local_record_write", "method_skill_invocation"} {
		entry, _ := caps[key].(map[string]any)
		if entry["status"] != "supported" {
			limitation := stringValue(entry["limitation_key"])
			if limitation == "" {
				limitation = key
			}
			runes := []rune(limitation)
			if len(runes) > 128 {
				limitation = string(runes[:128])
			}
			if !seen[limitation] && !strings.ContainsRune(limitation, 0) {
				out = append(out, limitation)
				seen[limitation] = true
			}
		}
	}
	sort.Strings(out)
	return out
}
func stringValue(v any) string { s, _ := v.(string); return s }
func (a *ControlApplication) begin(state map[string]any, c domain.Control, result *domain.ControlResult, request ControlRequest, prior []map[string]any) ([]map[string]any, error) {
	p := c.Payload
	participation := p["participation"].(map[string]any)
	rigor := p["rigor"].(map[string]any)
	part := participation["participation"].(string)
	if part == "mechanical" || state["participation"] != nil && state["participation"] != part {
		return nil, domain.ErrControl
	}
	stored := state["effective_rigor"]
	if a.Settings != nil {
		stored = a.Settings.Load().Rigor()
	} else if state["recording_eligible"] == true {
		return nil, errors.New("store_unavailable")
	}
	if rigor["stored_rigor"] != stored {
		return nil, domain.ErrControl
	}
	f, e := domain.ParseRouting(p["routing_features"])
	if e != nil {
		return nil, e
	}
	bundle := a.Bundle
	if bundle == nil {
		bundle, e = content.Load()
		if e != nil {
			return nil, errors.New("store_unavailable")
		}
	}
	route := domain.RouteFeatures(part, f, bundle.Methods)
	wire := map[string]any{"schema": "opensocrates.router-decision/1.0.0", "router_version": "1.1.0", "primary_method": nil, "secondary_method": nil, "primary_family": nil, "secondary_family": nil, "answer_shape": f.AnswerShape, "reason_code": route.Reason, "explicit_invocation": f.ExplicitMethod != nil, "prompt_bundle_hash": bundle.SemanticHash}
	for i, id := range route.Selected {
		which := "primary"
		if i == 1 {
			which = "secondary"
		}
		wire[which+"_method"] = id
		for _, method := range bundle.Methods {
			if method.ID == id {
				wire[which+"_family"] = method.Family
				break
			}
		}
	}
	result.Route = wire
	state["task_state"], state["participation"], state["effective_rigor"] = "framing", part, rigor["effective_rigor"]
	state["primary_method"], state["secondary_method"] = wire["primary_method"], wire["secondary_method"]
	if len(route.Selected) > 0 {
		result.NextAction = "activate_primary_skill"
	}
	if state["recording_eligible"] != true {
		reason := "recording_off"
		if state["onboarding_disclosure_turn"] == true {
			reason = "onboarding_disclosure_turn"
		}
		result.ReasonCode = domain.Pointer(reason)
		return nil, nil
	}
	task := stringValue(state["task_id"])
	if task == "" {
		task = domain.NewTaskID()
		state["task_id"] = task
	}
	judgment := stringValue(state["judgment_id"])
	if judgment == "" {
		judgment = allocate(prior, "J")
		state["judgment_id"] = judgment
	}
	result.AssignedIDs.TaskID = domain.Pointer(task)
	result.AssignedIDs.JudgmentID = domain.Pointer(judgment)
	events := []map[string]any{}
	add := func(kind string, payload map[string]any) {
		events = append(events, a.event(state, request, len(prior)+len(events)+1, kind, payload))
	}
	add("task_started", map[string]any{"requested_rigor": stored, "effective_rigor": state["effective_rigor"], "capability_gaps": result.CapabilityLimitations, "participation_reason": participation["reason_code"], "host_session_key": state["host_session_key"]})
	if len(route.Selected) > 0 {
		source := "automatic"
		if f.ExplicitMethod != nil {
			source = "explicit"
		}
		add("method_selected", map[string]any{"primary_method": wire["primary_method"], "secondary_method": wire["secondary_method"], "selection_source": source})
	}
	add("judgment_started", map[string]any{"judgment_id": judgment, "version": contracts.Number(1)})
	return events, nil
}
func (a *ControlApplication) event(state map[string]any, request ControlRequest, seq int, kind string, payload map[string]any) map[string]any {
	locale := a.Locale
	if locale != "ko" {
		locale = "en"
	}
	occurred := a.now().Format(domain.TimestampFormat)
	hostVersion := a.HostVersion
	if hostVersion == "" {
		hostVersion = "unknown"
	}
	adapter := a.AdapterVersion
	if adapter == "" {
		adapter = "1.0.0"
	}
	if request.CurrentEvent != nil {
		if s, ok := request.CurrentEvent["occurred_at"].(string); ok {
			occurred = s
		}
		if s, ok := request.CurrentEvent["host_version"].(string); ok {
			hostVersion = s
		}
		if s, ok := request.CurrentEvent["adapter_version"].(string); ok {
			adapter = s
		}
		payload, _ := request.CurrentEvent["payload"].(map[string]any)
		if contracts.Is(payload["locale"], "en", "ko") {
			locale = payload["locale"].(string)
		}
	}
	return map[string]any{"schema": "opensocrates.judgment-event/1.0.0", "event_id": domain.NewMessageID(), "task_id": state["task_id"], "sequence": contracts.Number(int64(seq)), "event_type": kind, "occurred_at": occurred, "host": state["host"], "host_version": hostVersion, "adapter_version": adapter, "locale": locale, "payload": payload}
}
func knownIDs(events []map[string]any) map[string]bool {
	ids := map[string]bool{}
	var walk func(any)
	walk = func(v any) {
		switch x := v.(type) {
		case map[string]any:
			for key, val := range x {
				if key == "judgment_id" || key == "claim_id" || key == "source_id" || key == "criterion_id" || key == "alternative_id" {
					if s, ok := val.(string); ok {
						ids[s] = true
					}
				}
				walk(val)
			}
		case []any:
			for _, v := range x {
				walk(v)
			}
		}
	}
	for _, event := range events {
		walk(event["payload"])
	}
	return ids
}
func allocate(events []map[string]any, prefix string) string {
	max := 0
	for id := range knownIDs(events) {
		if strings.HasPrefix(id, prefix) {
			n, e := strconv.Atoi(strings.TrimPrefix(id, prefix))
			if e == nil && n > max {
				max = n
			}
		}
	}
	return fmt.Sprintf("%s%06d", prefix, max+1)
}
func currentClaim(events []map[string]any, id string) map[string]any {
	var current map[string]any
	for _, event := range events {
		p, _ := event["payload"].(map[string]any)
		claim, _ := p["claim_version"].(map[string]any)
		if claim["claim_id"] == id {
			current = claim
		}
	}
	return current
}
func validateReferences(c domain.Control, events []map[string]any) error {
	if c.MessageType == "publish_conflict" {
		if e := domain.ValidateControlConflictModel(c.Payload["conflict"]); e != nil {
			return domain.ErrControl
		}
	}
	if c.MessageType == "publish_claim" && c.Payload["conflict"] != nil {
		if e := domain.ValidateControlConflictModel(c.Payload["conflict"]); e != nil {
			return domain.ErrControl
		}
	}
	known := knownIDs(events)
	var walk func(any) error
	walk = func(v any) error {
		switch x := v.(type) {
		case map[string]any:
			for key, val := range x {
				if key == "existing_id" {
					if s, ok := val.(string); !ok || !known[s] {
						return errors.New("stale_reference")
					}
				}
				if strings.HasSuffix(key, "_claim_ids") || key == "source_ids" || key == "alternative_ids" || key == "affected_ids" {
					a, _ := val.([]any)
					for _, v := range a {
						if s, ok := v.(string); !ok || !known[s] {
							return errors.New("stale_reference")
						}
					}
				}
				if e := walk(val); e != nil {
					return e
				}
			}
		case []any:
			for _, v := range x {
				if e := walk(v); e != nil {
					return e
				}
			}
		}
		return nil
	}
	if e := walk(c.Payload); e != nil {
		return e
	}
	if c.MessageType == "publish_claim" && c.Payload["claim_ref"] != nil {
		claim := currentClaim(events, c.Payload["claim_ref"].(string))
		if claim == nil || claim["version"] != c.Payload["expected_current_version"] {
			return errors.New("stale_reference")
		}
	}
	return nil
}
func (a *ControlApplication) publicEvents(state map[string]any, c domain.Control, result *domain.ControlResult, request ControlRequest, prior []map[string]any) ([]map[string]any, error) {
	if state["task_id"] == nil || state["judgment_id"] == nil {
		return nil, domain.ErrControl
	}
	result.AssignedIDs.TaskID = domain.Pointer(state["task_id"].(string))
	result.AssignedIDs.JudgmentID = domain.Pointer(state["judgment_id"].(string))
	p := c.Payload
	events := []map[string]any{}
	add := func(kind string, payload map[string]any) {
		events = append(events, a.event(state, request, len(prior)+len(events)+1, kind, payload))
	}
	switch c.MessageType {
	case "publish_framing":
		fr := map[string]any{"schema": "opensocrates.framing/1.0.0", "judgment_id": state["judgment_id"], "decision_question": p["decision_question"], "assumptions": p["assumptions"], "decisive_evidence": p["decisive_evidence"]}
		criteria := []any{}
		id := allocate(prior, "K")
		start, _ := strconv.Atoi(id[1:])
		for i, raw := range p["completion_criteria"].([]any) {
			item, _ := domain.Normalize(raw)
			key := fmt.Sprintf("K%06d", start+i)
			item["criterion_id"] = key
			criteria = append(criteria, item)
			result.AssignedIDs.CriterionIDs = append(result.AssignedIDs.CriterionIDs, key)
		}
		fr["completion_criteria"] = criteria
		add("framing_published", map[string]any{"framing": fr})
	case "publish_claim":
		sources := []string{}
		newSources := map[int64]string{}
		startID := allocate(prior, "E")
		start, _ := strconv.Atoi(startID[1:])
		for i, raw := range p["new_sources"].([]any) {
			src, _ := domain.Normalize(raw)
			id := fmt.Sprintf("E%06d", start+i)
			src["schema"], src["source_id"] = "opensocrates.source-reference/1.0.0", id
			if src["uri"] != nil {
				sanitized, e := sanitizeControlURI(src["uri"].(string))
				if e != nil {
					return nil, e
				}
				src["uri"] = sanitized
			}
			newSources[int64(i)] = id
			sources = append(sources, id)
			add("source_published", map[string]any{"source_reference": src})
		}
		refID := func(raw any) (any, error) {
			if raw == nil {
				return nil, nil
			}
			ref := raw.(map[string]any)
			if s, ok := ref["existing_id"].(string); ok {
				return s, nil
			}
			index, ok := contracts.Int(ref["new_index"])
			if !ok {
				return nil, errors.New("stale_reference")
			}
			id, ok := newSources[index]
			if !ok {
				return nil, errors.New("stale_reference")
			}
			return id, nil
		}
		for _, raw := range p["source_refs"].([]any) {
			value, e := refID(raw)
			if e != nil {
				return nil, e
			}
			id := value.(string)
			if !domain.Has(sources, id) {
				sources = append(sources, id)
			}
		}
		id := allocate(prior, "C")
		version := int64(1)
		if p["claim_ref"] != nil {
			id = p["claim_ref"].(string)
			old := currentClaim(prior, id)
			version, _ = contracts.Int(old["version"])
			version++
		}
		var calculation any
		if p["calculation"] != nil {
			calc, _ := domain.Normalize(p["calculation"])
			operands := []any{}
			for _, raw := range calc["operands"].([]any) {
				op, _ := domain.Normalize(raw)
				source, e := refID(op["source_ref"])
				if e != nil {
					return nil, e
				}
				delete(op, "source_ref")
				op["source_id"] = source
				operands = append(operands, op)
			}
			calc["operands"] = operands
			calculation = calc
		}
		claim := map[string]any{"schema": "opensocrates.claim-version/1.0.0", "claim_id": id, "version": contracts.Number(version), "text": p["text"], "materiality": p["materiality"], "evidence_state": p["evidence_state"], "source_ids": sources, "basis_claim_ids": p["basis_claim_ids"], "calculation": calculation, "conflict": p["conflict"], "active": true}
		add("claim_published", map[string]any{"claim_version": claim})
		result.AssignedIDs.ClaimIDs = []string{id}
		result.AssignedIDs.SourceIDs = sources
	case "publish_conflict":
		add("conflict_published", map[string]any{"conflict": p["conflict"], "affected_claim_ids": p["affected_claim_ids"]})
	case "publish_alternative":
		alternative, _ := domain.Normalize(p)
		id := allocate(prior, "A")
		alternative["schema"], alternative["alternative_id"] = "opensocrates.alternative/1.0.0", id
		add("alternative_published", map[string]any{"alternative": alternative})
		result.AssignedIDs.AlternativeIDs = []string{id}
	case "revise_judgment":
		version := int64(0)
		for _, event := range prior {
			payload, _ := event["payload"].(map[string]any)
			if payload["judgment_id"] == state["judgment_id"] {
				n, _ := contracts.Int(payload["version"])
				if n > version {
					version = n
				}
			}
			j, _ := payload["judgment_version"].(map[string]any)
			if j["judgment_id"] == state["judgment_id"] {
				n, _ := contracts.Int(j["version"])
				if n > version {
					version = n
				}
			}
		}
		j, _ := domain.Normalize(p)
		j["judgment_id"], j["version"], j["state"] = state["judgment_id"], contracts.Number(version+1), "revised"
		j["supersedes_version"] = nil
		if version > 0 {
			j["supersedes_version"] = contracts.Number(version)
		} else {
			j["change_reason"] = nil
		}
		add("conclusion_published", map[string]any{"judgment_version": j})
	case "complete_cross_exam":
		add("cross_exam_completed", p)
	case "hold_judgment":
		add("task_insufficient", map[string]any{"terminal_reason": p["reason_code"], "missing_items": p["missing_items"]})
	case "cancel_judgment":
		add("task_cancelled", p)
	default:
		return nil, domain.ErrControl
	}
	for _, event := range events {
		normalized, e := domain.Normalize(event)
		if e != nil {
			return nil, e
		}
		for k, v := range normalized {
			event[k] = v
		}
		if e = domain.ValidateRecord(event); e != nil {
			return nil, domain.ErrControl
		}
		payload, _ := event["payload"].(map[string]any)
		claim, _ := payload["claim_version"].(map[string]any)
		if claim["calculation"] != nil {
			raw, _ := contracts.CanonicalCompact(claim["calculation"])
			var calculation domain.Calculation
			if json.Unmarshal(raw, &calculation) != nil || verification.ValidateStoredCalculation(calculation) != nil {
				return nil, domain.ErrControl
			}
		}
	}
	return events, nil
}

func sanitizeControlURI(raw string) (any, error) {
	u, e := url.Parse(raw)
	if e != nil || u.User != nil || u.Host == "" || strings.ToLower(u.Scheme) != "https" && strings.ToLower(u.Scheme) != "http" {
		return nil, domain.ErrControl
	}
	if strings.ToLower(u.Scheme) == "http" && !domain.Has([]string{"localhost", "127.0.0.1", "::1"}, strings.ToLower(u.Hostname())) {
		return nil, domain.ErrControl
	}
	for key := range u.Query() {
		if domain.Has([]string{"token", "key", "secret", "signature", "sig", "auth", "code", "session"}, strings.ToLower(key)) {
			return nil, nil
		}
	}
	return raw, nil
}
