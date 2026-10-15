package verification

import (
	"encoding/json"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"sort"
	"strings"
)

type TraceChronology struct {
	Sequence   int    `json:"sequence"`
	OccurredAt string `json:"occurred_at"`
	Kind       string `json:"kind"`
	Summary    string `json:"summary"`
	Effect     string `json:"effect"`
}
type TraceMethods struct {
	Status               string   `json:"status"`
	ActivationStatus     string   `json:"activation_status"`
	PrimaryMethod        *string  `json:"primary_method"`
	ComplementMethod     *string  `json:"complement_method"`
	SelectionSource      *string  `json:"selection_source"`
	ConfirmedActivations []string `json:"confirmed_activations"`
	ComplementCue        *string  `json:"complement_cue"`
}
type TraceView struct {
	Schema          string                   `json:"schema"`
	TaskID          string                   `json:"task_id"`
	PublicShortID   string                   `json:"public_short_id"`
	Status          domain.TaskState         `json:"status"`
	TerminalReason  *string                  `json:"terminal_reason"`
	Locale          string                   `json:"locale"`
	Framing         *domain.Framing          `json:"framing"`
	Chronology      []TraceChronology        `json:"chronology"`
	Methods         TraceMethods             `json:"methods"`
	ClaimHistory    []domain.ClaimVersion    `json:"claim_history"`
	Conflicts       []domain.Conflict        `json:"conflicts"`
	Alternatives    []domain.Alternative     `json:"alternatives"`
	Completion      *domain.CompletionResult `json:"completion"`
	CurrentCard     *domain.ConclusionCard   `json:"current_card"`
	CapabilityNotes []string                 `json:"capability_notes"`
}

func modelPayload[T any](payload map[string]any, key string) (T, error) {
	var result T
	raw, e := contracts.CanonicalCompact(payload[key])
	if e != nil {
		return result, e
	}
	e = json.Unmarshal(raw, &result)
	return result, e
}
func traceString(m map[string]any, key string) string { s, _ := m[key].(string); return s }
func tracePointer(m map[string]any, key string) *string {
	if s, ok := m[key].(string); ok {
		return &s
	}
	return nil
}
func ProjectTrace(events []map[string]any, dataState string, currentCard *domain.ConclusionCard) (TraceView, error) {
	v := TraceView{Schema: "opensocrates.trace-view/1.0.0", Chronology: []TraceChronology{}, ClaimHistory: []domain.ClaimVersion{}, Conflicts: []domain.Conflict{}, Alternatives: []domain.Alternative{}, CapabilityNotes: []string{}, Methods: TraceMethods{Status: "none", ActivationStatus: "none", ConfirmedActivations: []string{}}}
	if !contains([]string{"recorded", "not_recorded", "unavailable", "partial", "corrupt"}, dataState) {
		return v, contracts.ErrInvalid
	}
	p, e := domain.ReduceEvents(events)
	if e != nil {
		return v, e
	}
	if p == nil {
		return v, contracts.ErrInvalid
	}
	v.TaskID = p.TaskID
	if len(p.TaskID) < 8 {
		return v, contracts.ErrInvalid
	}
	v.PublicShortID = p.TaskID[len(p.TaskID)-8:]
	v.Status = p.State
	v.TerminalReason = p.TerminalReason
	v.Locale = p.Locale
	v.CurrentCard = currentCard
	if currentCard != nil && (currentCard.TaskID != p.TaskID || currentCard.Locale != p.Locale) {
		return v, contracts.ErrInvalid
	}
	notes := map[string]bool{}
	for _, note := range p.CapabilityGaps {
		notes[note] = true
	}
	if dataState != "recorded" {
		key := map[string]string{"not_recorded": "trace.not_recorded", "unavailable": "trace.unavailable", "partial": "trace.record.partial", "corrupt": "trace.record.corrupt"}[dataState]
		notes[key] = true
	}
	unavailable := false
	for _, key := range []string{"method_invocation_observation", "method_skill_invocation", "model_initiated_method_skill_activation"} {
		unavailable = unavailable || notes[key]
	}
	if unavailable {
		v.Methods.Status = "unavailable"
		v.Methods.ActivationStatus = "unavailable"
	}
	activations := []string{}
	for _, event := range events {
		kind := traceString(event, "event_type")
		payload, _ := event["payload"].(map[string]any)
		sequence, _ := contracts.Int(event["sequence"])
		entry := TraceChronology{Sequence: int(sequence), OccurredAt: traceString(event, "occurred_at"), Kind: kind}
		switch kind {
		case "framing_published":
			value, e := modelPayload[domain.Framing](payload, "framing")
			if e != nil {
				return v, e
			}
			v.Framing = &value
			continue
		case "method_selected":
			v.Methods.PrimaryMethod = tracePointer(payload, "primary_method")
			v.Methods.ComplementMethod = tracePointer(payload, "secondary_method")
			v.Methods.ComplementCue = v.Methods.ComplementMethod
			v.Methods.SelectionSource = tracePointer(payload, "selection_source")
			v.Methods.Status = "selected"
			v.Methods.ActivationStatus = "not_recorded"
			if unavailable {
				v.Methods.ActivationStatus = "unavailable"
			}
			entry.Summary = traceString(payload, "primary_method")
		case "method_activated":
			id := traceString(payload, "method_id")
			activations = append(activations, id)
			entry.Summary = id
		case "judgment_started":
			n, _ := contracts.Int(payload["version"])
			entry.Summary = fmt.Sprintf("%s v%d", traceString(payload, "judgment_id"), n)
		case "intervention_published":
			entry.Summary = traceString(payload, "summary")
			entry.Effect = traceString(payload, "action")
		case "claim_published":
			value, e := modelPayload[domain.ClaimVersion](payload, "claim_version")
			if e != nil {
				return v, e
			}
			v.ClaimHistory = append(v.ClaimHistory, value)
			entry.Summary = value.Text
		case "source_published":
			value, e := modelPayload[domain.SourceReference](payload, "source_reference")
			if e != nil {
				return v, e
			}
			entry.Summary = value.DisplayName
		case "conflict_published":
			value, e := modelPayload[domain.Conflict](payload, "conflict")
			if e != nil {
				return v, e
			}
			v.Conflicts = append(v.Conflicts, value)
			entry.Summary = value.Summary
		case "conflict_resolved":
			entry.Summary = traceString(payload, "public_reason")
		case "alternative_published":
			value, e := modelPayload[domain.Alternative](payload, "alternative")
			if e != nil {
				return v, e
			}
			v.Alternatives = append(v.Alternatives, value)
			entry.Summary = value.Name
			entry.Effect = value.Reason
		case "conclusion_published":
			value, e := modelPayload[domain.JudgmentVersion](payload, "judgment_version")
			if e != nil {
				return v, e
			}
			if value.Conclusion != nil {
				entry.Summary = *value.Conclusion
			}
			if value.ChangeReason != nil {
				entry.Effect = *value.ChangeReason
			}
		case "cross_exam_completed":
			entry.Summary = traceString(payload, "findings_summary")
		case "completion_checked":
			value, e := modelPayload[domain.CompletionResult](payload, "completion_result")
			if e != nil {
				return v, e
			}
			v.Completion = &value
		case "verification_failed":
			entry.Summary = traceString(payload, "reason")
		case "task_insufficient":
			items, _ := payload["missing_items"].([]any)
			parts := []string{}
			for _, item := range items {
				if s, ok := item.(string); ok {
					parts = append(parts, s)
				}
			}
			entry.Summary = strings.Join(parts, "; ")
		}
		v.Chronology = append(v.Chronology, entry)
	}
	if v.Methods.PrimaryMethod != nil {
		for _, id := range activations {
			if id == *v.Methods.PrimaryMethod {
				v.Methods.ConfirmedActivations = append(v.Methods.ConfirmedActivations, id)
			}
		}
		if len(v.Methods.ConfirmedActivations) > 0 {
			v.Methods.Status = "confirmed"
			v.Methods.ActivationStatus = "confirmed"
		}
	}
	for note := range notes {
		v.CapabilityNotes = append(v.CapabilityNotes, note)
	}
	sort.Strings(v.CapabilityNotes)
	return v, nil
}

var TraceLocaleKeys = []string{"trace.title", "trace.heading.framing", "trace.heading.what_changed", "trace.heading.methods_used", "trace.heading.evidence_changes", "trace.heading.conflicts_and_responses", "trace.heading.alternatives", "trace.heading.completion_check", "trace.heading.current_conclusion", "trace.label.decision_question", "trace.label.assumptions_published", "trace.label.completion_criteria", "trace.label.source", "trace.label.resolution", "trace.method.activation_confirmed", "trace.method.selected_not_confirmed", "trace.completion.met", "trace.completion.unmet", "trace.completion.unverified", "trace.completion.not_applicable", "trace.private_reasoning", "trace.record.partial", "trace.record.corrupt", "trace.not_recorded", "trace.unavailable", "trace.none", "trace.primary", "trace.secondary"}

func RenderTrace(v TraceView, messages map[string]string, privateRequested bool) (string, error) {
	raw, e := contracts.CanonicalCompact(v)
	if e != nil {
		return "", e
	}
	wire, e := contracts.Decode(raw)
	if e != nil {
		return "", e
	}
	if e = contracts.Validate("trace-view", wire); e != nil {
		return "", e
	}
	if e = RejectPublic(wire); e != nil {
		return "", e
	}
	if !domain.SupportedLocale(v.Locale) {
		return "", contracts.ErrInvalid
	}
	for _, k := range TraceLocaleKeys {
		if e := ValidateScalarText(messages[k], 4000, false); e != nil {
			return "", e
		}
	}
	inline := func(s string) string {
		s = strings.ReplaceAll(strings.ReplaceAll(s, "\r\n", " "), "\n", " ")
		escaped, _ := EscapeInline(s, false)
		return escaped
	}
	empty := messages["trace.none"]
	for _, k := range []string{"trace.record.corrupt", "trace.record.partial", "trace.unavailable", "trace.not_recorded"} {
		if contains(v.CapabilityNotes, k) {
			empty = messages[k]
			break
		}
	}
	lines := []string{"# " + messages["trace.title"]}
	if privateRequested {
		lines = append(lines, "- "+messages["trace.private_reasoning"])
	}
	section := func(key string, body []string) {
		lines = append(lines, "", "## "+messages[key])
		if len(body) == 0 {
			body = []string{"- " + empty}
		}
		lines = append(lines, body...)
	}
	body := []string{}
	if v.Framing != nil {
		assumptions, criteria := []string{}, []string{}
		for _, a := range v.Framing.Assumptions {
			assumptions = append(assumptions, inline(a.Text))
		}
		for _, c := range v.Framing.CompletionCriteria {
			criteria = append(criteria, inline(c.Text))
		}
		a, c := strings.Join(assumptions, "; "), strings.Join(criteria, "; ")
		if a == "" {
			a = messages["trace.none"]
		}
		if c == "" {
			c = messages["trace.none"]
		}
		body = []string{"- " + messages["trace.label.decision_question"] + ": " + inline(v.Framing.DecisionQuestion), "- " + messages["trace.label.assumptions_published"] + ": " + a, "- " + messages["trace.label.completion_criteria"] + ": " + c}
	}
	section("trace.heading.framing", body)
	body = []string{}
	for _, c := range v.Chronology {
		if c.Summary == "" && c.Effect == "" {
			continue
		}
		summary := inline(c.Summary)
		if summary == "" {
			summary = messages["trace.none"]
		}
		line := fmt.Sprintf("- %d — %s — %s", c.Sequence, inline(c.OccurredAt), summary)
		if c.Effect != "" {
			line += " — " + inline(c.Effect)
		}
		body = append(body, line)
	}
	section("trace.heading.what_changed", body)
	body = []string{}
	if v.Methods.Status == "selected" || v.Methods.Status == "confirmed" {
		if v.Methods.PrimaryMethod == nil {
			return "", contracts.ErrInvalid
		}
		body = append(body, "- "+messages["trace.primary"]+": "+inline(*v.Methods.PrimaryMethod))
		if v.Methods.ComplementMethod != nil {
			if contains(v.Methods.ConfirmedActivations, *v.Methods.ComplementMethod) {
				return "", contracts.ErrInvalid
			}
			body = append(body, "- "+messages["trace.secondary"]+": "+inline(*v.Methods.ComplementMethod))
		}
		key := map[string]string{"confirmed": "trace.method.activation_confirmed", "unavailable": "trace.unavailable", "not_recorded": "trace.method.selected_not_confirmed"}[v.Methods.ActivationStatus]
		if key == "" {
			return "", contracts.ErrInvalid
		}
		body = append(body, "- "+messages[key])
	} else {
		key := map[string]string{"none": "trace.none", "unavailable": "trace.unavailable", "not_recorded": "trace.not_recorded"}[v.Methods.Status]
		if key == "" {
			return "", contracts.ErrInvalid
		}
		body = append(body, "- "+messages[key])
	}
	section("trace.heading.methods_used", body)
	body = []string{}
	for _, c := range v.ClaimHistory {
		state := messages["card.state."+string(c.EvidenceState)]
		if state == "" {
			return "", contracts.ErrInvalid
		}
		line := "- " + inline(c.Text) + " — " + state
		if len(c.SourceIDs) > 0 {
			line += " — " + messages["trace.label.source"] + ": " + strings.Join(c.SourceIDs, ", ")
		}
		body = append(body, line)
	}
	section("trace.heading.evidence_changes", body)
	body = []string{}
	for _, c := range v.Conflicts {
		reason := messages["trace.none"]
		if c.ResolutionReason != nil {
			reason = inline(*c.ResolutionReason)
		}
		body = append(body, "- "+inline(c.Summary)+" — "+messages["trace.label.resolution"]+": "+reason)
	}
	section("trace.heading.conflicts_and_responses", body)
	body = []string{}
	for _, a := range v.Alternatives {
		body = append(body, "- "+inline(a.Name)+" — "+inline(a.Reason))
	}
	section("trace.heading.alternatives", body)
	body = []string{}
	if v.Completion != nil {
		for _, c := range v.Completion.Criteria {
			key := "trace.completion." + string(c.Status)
			if c.Status == domain.NotRecorded {
				key = "trace.not_recorded"
			}
			if messages[key] == "" {
				return "", contracts.ErrInvalid
			}
			body = append(body, "- "+inline(c.Reason)+" — "+messages[key])
		}
	}
	section("trace.heading.completion_check", body)
	body = []string{}
	if v.CurrentCard != nil {
		card, e := RenderCard(*v.CurrentCard, messages, 3)
		if e != nil {
			return "", e
		}
		body = append(body, card)
	}
	section("trace.heading.current_conclusion", body)
	return strings.Join(lines, "\n"), nil
}
