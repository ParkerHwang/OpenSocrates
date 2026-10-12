package domain

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"math"
	"time"
)

// MetricAttributes is a closed union encoded as the existing attributes object.
// It cannot carry free text, prompts, paths, source URIs, or model output.
type MetricAttributes struct {
	FirstSession  *bool
	FromRigor     *Rigor
	ToRigor       *Rigor
	Class         *string
	CapabilityKey *string
}

func (a MetricAttributes) MarshalJSON() ([]byte, error) {
	m := map[string]any{}
	if a.FirstSession != nil {
		m["first_session"] = *a.FirstSession
	}
	if a.FromRigor != nil {
		m["from_rigor"] = *a.FromRigor
	}
	if a.ToRigor != nil {
		m["to_rigor"] = *a.ToRigor
	}
	if a.Class != nil {
		m["class"] = *a.Class
	}
	if a.CapabilityKey != nil {
		m["capability_key"] = *a.CapabilityKey
	}
	return json.Marshal(m)
}

type LocalMetric struct {
	Schema         string           `json:"schema"`
	Event          string           `json:"event"`
	Day            string           `json:"occurred_at_day"`
	ProductVersion string           `json:"product_version"`
	Host           string           `json:"host"`
	Locale         string           `json:"locale"`
	Rigor          Rigor            `json:"rigor"`
	DurationBucket *string          `json:"duration_bucket_ms"`
	Attributes     MetricAttributes `json:"attributes"`
}

func DurationBucket(milliseconds *float64) (*string, error) {
	if milliseconds == nil {
		return nil, nil
	}
	n := *milliseconds
	if math.IsNaN(n) || math.IsInf(n, 0) || n < 0 {
		return nil, contracts.ErrInvalid
	}
	s := "1000_plus"
	switch {
	case n < 50:
		s = "under_50"
	case n < 100:
		s = "50_99"
	case n < 250:
		s = "100_249"
	case n < 1000:
		s = "250_999"
	}
	return &s, nil
}
func ValidateMetricAttributes(event string, a MetricAttributes) error {
	first := a.FirstSession != nil
	rigors := a.FromRigor != nil || a.ToRigor != nil
	class := a.Class != nil
	capability := a.CapabilityKey != nil
	switch event {
	case "judgment_started", "card_rendered", "conclusion_changed", "trace_requested":
		if first || rigors || class || capability {
			return contracts.ErrInvalid
		}
	case "card_validated":
		if rigors || class || capability {
			return contracts.ErrInvalid
		}
	case "rigor_changed":
		if first || class || capability || a.FromRigor == nil || a.ToRigor == nil {
			return contracts.ErrInvalid
		}
		if _, e := RigorOrdinal(*a.FromRigor); e != nil {
			return e
		}
		if _, e := RigorOrdinal(*a.ToRigor); e != nil {
			return e
		}
	case "intervention_emitted", "intervention_explicitly_accepted", "intervention_explicitly_dismissed":
		if first || rigors || capability || !class || !Has([]string{"reframe", "conflict", "weak_evidence", "missing_alternative", "completion_gap"}, *a.Class) {
			return contracts.ErrInvalid
		}
	case "runtime_degraded":
		if first || rigors || class || !capability || !Has(CapabilityKeys, *a.CapabilityKey) {
			return contracts.ErrInvalid
		}
	default:
		return contracts.ErrInvalid
	}
	return nil
}
func BuildLocalMetric(event, host, locale string, rigor Rigor, a MetricAttributes, day, version string, duration *float64, recordingEnabled bool, taskScoped *bool) (*LocalMetric, error) {
	if e := ValidateMetricAttributes(event, a); e != nil {
		return nil, e
	}
	scoped := event != "runtime_degraded"
	if taskScoped != nil {
		scoped = *taskScoped
	}
	if scoped && !recordingEnabled {
		return nil, nil
	}
	if !Has([]string{"codex_cli", "codex_desktop"}, host) || !Has([]string{"en", "ko"}, locale) {
		return nil, contracts.ErrInvalid
	}
	if _, e := RigorOrdinal(rigor); e != nil {
		return nil, e
	}
	if _, e := time.Parse("2006-01-02", day); e != nil {
		return nil, contracts.ErrInvalid
	}
	bucket, e := DurationBucket(duration)
	if e != nil {
		return nil, e
	}
	return &LocalMetric{"opensocrates.local-metric/1.0.0", event, day, version, host, locale, rigor, bucket, a}, nil
}
func ValidateLocalMetric(m LocalMetric) error {
	if m.Schema != "opensocrates.local-metric/1.0.0" || !Has([]string{"codex_cli", "codex_desktop"}, m.Host) || !Has([]string{"en", "ko"}, m.Locale) {
		return contracts.ErrInvalid
	}
	if _, e := RigorOrdinal(m.Rigor); e != nil {
		return e
	}
	if _, e := time.Parse("2006-01-02", m.Day); e != nil {
		return contracts.ErrInvalid
	}
	if m.DurationBucket != nil && !Has([]string{"under_50", "50_99", "100_249", "250_999", "1000_plus"}, *m.DurationBucket) {
		return contracts.ErrInvalid
	}
	return ValidateMetricAttributes(m.Event, m.Attributes)
}
func ValidateLocalMetricWire(value any) error {
	if e := contracts.Validate("local-metric", value); e != nil {
		return e
	}
	m, ok := value.(map[string]any)
	if !ok {
		return contracts.ErrInvalid
	}
	day, ok := m["occurred_at_day"].(string)
	if !ok {
		return contracts.ErrInvalid
	}
	if _, e := time.Parse("2006-01-02", day); e != nil {
		return contracts.ErrInvalid
	}
	if !contracts.Is(m["locale"], "en", "ko") {
		return contracts.ErrInvalid
	}
	attrs, ok := m["attributes"].(map[string]any)
	if !ok {
		return contracts.ErrInvalid
	}
	a := MetricAttributes{}
	for k, v := range attrs {
		switch k {
		case "first_session":
			b, ok := v.(bool)
			if !ok {
				return contracts.ErrInvalid
			}
			a.FirstSession = &b
		case "from_rigor", "to_rigor":
			s, ok := v.(string)
			if !ok {
				return contracts.ErrInvalid
			}
			r := Rigor(s)
			if k == "from_rigor" {
				a.FromRigor = &r
			} else {
				a.ToRigor = &r
			}
		case "class", "capability_key":
			s, ok := v.(string)
			if !ok {
				return contracts.ErrInvalid
			}
			if k == "class" {
				a.Class = &s
			} else {
				a.CapabilityKey = &s
			}
		default:
			return contracts.ErrInvalid
		}
	}
	event, ok := m["event"].(string)
	if !ok {
		return contracts.ErrInvalid
	}
	return ValidateMetricAttributes(event, a)
}
