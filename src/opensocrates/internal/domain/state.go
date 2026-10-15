package domain

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"sort"
)

type TaskState string

const (
	TaskNew            TaskState = "new"
	TaskFraming        TaskState = "framing"
	TaskWorking        TaskState = "working"
	TaskRejudging      TaskState = "rejudging"
	TaskCrossExamining TaskState = "cross_examining"
	TaskVerifying      TaskState = "verifying"
	TaskBypassed       TaskState = "bypassed"
	TaskConcluded      TaskState = "concluded"
	TaskCancelled      TaskState = "cancelled"
	TaskInsufficient   TaskState = "insufficient"
	TaskDegraded       TaskState = "degraded"
)

func TerminalTaskState(s TaskState) bool {
	return s == TaskBypassed || s == TaskConcluded || s == TaskCancelled || s == TaskInsufficient
}
func LegalEvent(event string, s TaskState) bool {
	if event == "recovered_from_torn_tail" {
		return true
	}
	if TerminalTaskState(s) {
		return false
	}
	switch event {
	case "task_started":
		return s == TaskNew
	case "framing_published":
		return s == TaskFraming
	case "method_selected", "method_activated", "judgment_started", "observation_check_requested", "intervention_published", "claim_published", "source_published", "alternative_published":
		return s == TaskFraming || s == TaskWorking || s == TaskRejudging
	case "conflict_published", "conclusion_published":
		return s == TaskWorking || s == TaskRejudging
	case "conflict_resolved":
		return s == TaskRejudging
	case "cross_exam_completed":
		return s == TaskCrossExamining
	case "completion_checked", "repair_requested", "verification_failed":
		return s == TaskVerifying
	case "capability_degraded":
		return s != TaskNew && s != TaskBypassed
	case "task_concluded", "task_insufficient":
		return Has([]string{"framing", "working", "rejudging", "cross_examining", "verifying", "degraded"}, string(s))
	case "task_cancelled":
		return s != TaskNew
	}
	return false
}

// TransitionInput carries only fields which affect the state machine. Payload
// validation and persistence remain separate boundaries.
type TransitionInput struct {
	ParticipationReason string
	TerminalReason      string
}

func TransitionState(s TaskState, event string, p TransitionInput) (TaskState, error) {
	if !LegalEvent(event, s) {
		return "", contracts.ErrInvalid
	}
	switch event {
	case "task_started":
		if Has(mechanicalReasons, p.ParticipationReason) {
			return TaskBypassed, nil
		}
		return TaskFraming, nil
	case "framing_published", "conflict_resolved", "repair_requested":
		return TaskWorking, nil
	case "conflict_published":
		return TaskRejudging, nil
	case "conclusion_published":
		return TaskCrossExamining, nil
	case "cross_exam_completed":
		return TaskVerifying, nil
	case "verification_failed", "task_insufficient":
		return TaskInsufficient, nil
	case "capability_degraded":
		if s == TaskVerifying {
			return TaskDegraded, nil
		}
	case "task_cancelled":
		return TaskCancelled, nil
	case "task_concluded":
		switch p.TerminalReason {
		case "mechanical":
			return TaskBypassed, nil
		case "user_cancelled":
			return TaskCancelled, nil
		case "criteria_satisfied":
			return TaskConcluded, nil
		case "capability_missing", "verifier_unavailable":
			return TaskDegraded, nil
		case "evidence_missing", "evidence_conflict", "completion_criteria_unmet", "verifier_failed", "method_unavailable", "record_unavailable", "runtime_error":
			return TaskInsufficient, nil
		default:
			return "", contracts.ErrInvalid
		}
	}
	return s, nil
}

type TaskProjection struct {
	Schema            string    `json:"schema"`
	TaskID            string    `json:"task_id"`
	State             TaskState `json:"state"`
	TerminalReason    *string   `json:"terminal_reason"`
	Locale            string    `json:"locale"`
	RequestedRigor    Rigor     `json:"requested_rigor"`
	EffectiveRigor    Rigor     `json:"effective_rigor"`
	Host              string    `json:"host"`
	HostSessionKey    string    `json:"host_session_key"`
	CurrentJudgmentID *string   `json:"current_judgment_id"`
	RepairCount       int       `json:"repair_count"`
	CapabilityGaps    []string  `json:"capability_gaps"`
	LatestSequence    int       `json:"latest_sequence"`
	CreatedAt         string    `json:"created_at"`
	UpdatedAt         string    `json:"updated_at"`
}

func eventString(m map[string]any, key string) string { s, _ := m[key].(string); return s }
func eventStrings(v any) []string {
	result := []string{}
	if items, ok := v.([]any); ok {
		for _, item := range items {
			if s, ok := item.(string); ok {
				result = append(result, s)
			}
		}
	}
	return result
}
func ReduceEvents(events []map[string]any) (*TaskProjection, error) {
	if len(events) == 0 {
		return nil, nil
	}
	seen := map[string]bool{}
	var p *TaskProjection
	for _, event := range events {
		if e := ValidateRecord(event); e != nil {
			return nil, e
		}
		id := eventString(event, "event_id")
		if seen[id] {
			return nil, contracts.ErrInvalid
		}
		seen[id] = true
		sequence, ok := contracts.Int(event["sequence"])
		if !ok {
			return nil, contracts.ErrInvalid
		}
		payload, _ := event["payload"].(map[string]any)
		kind := eventString(event, "event_type")
		if p == nil {
			if kind != "task_started" || sequence != 1 {
				return nil, contracts.ErrInvalid
			}
			state := TaskFraming
			var terminal *string
			if Has(mechanicalReasons, eventString(payload, "participation_reason")) {
				state = TaskBypassed
				reason := "mechanical"
				terminal = &reason
			}
			p = &TaskProjection{Schema: "opensocrates.task-projection/1.0.0", TaskID: eventString(event, "task_id"), State: state, TerminalReason: terminal, Locale: eventString(event, "locale"), RequestedRigor: Rigor(eventString(payload, "requested_rigor")), EffectiveRigor: Rigor(eventString(payload, "effective_rigor")), Host: eventString(event, "host"), HostSessionKey: eventString(payload, "host_session_key"), CapabilityGaps: eventStrings(payload["capability_gaps"]), LatestSequence: 1, CreatedAt: eventString(event, "occurred_at"), UpdatedAt: eventString(event, "occurred_at")}
			continue
		}
		if sequence != int64(p.LatestSequence+1) || eventString(event, "task_id") != p.TaskID || eventString(event, "host") != p.Host {
			return nil, contracts.ErrInvalid
		}
		state, e := TransitionState(p.State, kind, TransitionInput{ParticipationReason: eventString(payload, "participation_reason"), TerminalReason: eventString(payload, "terminal_reason")})
		if e != nil {
			return nil, e
		}
		p.State = state
		p.LatestSequence = int(sequence)
		p.Locale = eventString(event, "locale")
		p.UpdatedAt = eventString(event, "occurred_at")
		switch kind {
		case "judgment_started":
			id := eventString(payload, "judgment_id")
			p.CurrentJudgmentID = &id
		case "conclusion_published":
			j, _ := payload["judgment_version"].(map[string]any)
			id := eventString(j, "judgment_id")
			if id != "" {
				p.CurrentJudgmentID = &id
			}
		case "repair_requested":
			n, ok := contracts.Int(payload["repair_count"])
			if !ok || n != 1 || p.RepairCount >= 1 {
				return nil, contracts.ErrInvalid
			}
			p.RepairCount = 1
		case "capability_degraded":
			key := eventString(payload, "capability_key")
			if !Has(p.CapabilityGaps, key) {
				p.CapabilityGaps = append(p.CapabilityGaps, key)
			}
		case "task_concluded", "task_insufficient":
			reason := eventString(payload, "terminal_reason")
			p.TerminalReason = &reason
		case "task_cancelled":
			reason := "user_cancelled"
			p.TerminalReason = &reason
		case "verification_failed":
			reason := "verifier_failed"
			p.TerminalReason = &reason
		}
	}
	sort.Strings(p.CapabilityGaps)
	return p, nil
}
