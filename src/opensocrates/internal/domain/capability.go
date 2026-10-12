package domain

import "github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"

var CapabilityKeys = []string{"prompt_context_injection", "local_control_execution", "method_skill_invocation", "model_initiated_method_skill_activation", "method_invocation_observation", "post_tool_observation", "post_tool_batch_observation", "completion_candidate_observation", "bounded_completion_continuation", "compaction_reinjection", "published_artifact_confirmation", "local_record_write", "deterministic_trace_render", "rich_card_widget"}

type CapabilityStatus string

const (
	CapabilitySupported   CapabilityStatus = "supported"
	CapabilityDegraded    CapabilityStatus = "degraded"
	CapabilityUnavailable CapabilityStatus = "unavailable"
	CapabilityUnknown     CapabilityStatus = "unknown"
)

type CapabilityEntry struct {
	Status          CapabilityStatus `json:"status"`
	EvidenceKind    string           `json:"evidence_kind"`
	SourceURL       *string          `json:"source_url"`
	SourceCheckedAt string           `json:"source_checked_at"`
	LiveProbeID     *string          `json:"live_probe_id"`
	LimitationKey   *string          `json:"limitation_key"`
}
type CapabilityProfile struct {
	Schema           string                     `json:"schema"`
	Host             string                     `json:"host"`
	HostVersionRange string                     `json:"host_version_range"`
	CheckedAt        string                     `json:"checked_at"`
	AdapterVersion   string                     `json:"adapter_version"`
	ComputedTier     string                     `json:"computed_tier"`
	Capabilities     map[string]CapabilityEntry `json:"capabilities"`
}

func DeriveCapabilityTier(c map[string]CapabilityEntry) (string, error) {
	if len(c) != 14 {
		return "", contracts.ErrInvalid
	}
	for _, k := range CapabilityKeys {
		v, ok := c[k]
		if !ok || !Has([]string{"supported", "degraded", "unavailable", "unknown"}, string(v.Status)) {
			return "", contracts.ErrInvalid
		}
	}
	a := true
	for _, k := range CapabilityKeys {
		if k != "rich_card_widget" && c[k].Status != CapabilitySupported {
			a = false
		}
	}
	if a {
		return "A", nil
	}
	b := true
	for _, k := range []string{"prompt_context_injection", "local_control_execution", "method_skill_invocation", "completion_candidate_observation", "bounded_completion_continuation", "local_record_write", "deterministic_trace_render"} {
		if c[k].Status != CapabilitySupported {
			b = false
		}
	}
	observation := c["post_tool_observation"].Status
	if b && (observation == CapabilitySupported || observation == CapabilityDegraded) {
		return "B", nil
	}
	for _, k := range []string{"prompt_context_injection", "method_skill_invocation"} {
		if c[k].Status == CapabilitySupported || c[k].Status == CapabilityDegraded {
			return "C", nil
		}
	}
	return "unsupported", nil
}
func ValidateCapabilityProfile(p CapabilityProfile) error {
	raw, e := contracts.CanonicalCompact(p)
	if e != nil {
		return e
	}
	wire, e := contracts.Decode(raw)
	if e != nil {
		return e
	}
	if e = contracts.Validate("capability-profile", wire); e != nil {
		return e
	}
	tier, e := DeriveCapabilityTier(p.Capabilities)
	if e != nil {
		return e
	}
	if tier != p.ComputedTier {
		return contracts.ErrInvalid
	}
	return nil
}
