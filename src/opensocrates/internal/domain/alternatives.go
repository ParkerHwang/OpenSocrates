package domain

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"golang.org/x/text/cases"
	"regexp"
	"strings"
)

type Alternative struct {
	Schema           string   `json:"schema"`
	ID               string   `json:"alternative_id"`
	Name             string   `json:"name"`
	Disposition      string   `json:"disposition"`
	Reason           string   `json:"reason"`
	MaterialClaimIDs []string `json:"material_claim_ids"`
}
type AlternativeRequirement struct {
	ChoiceRequired             bool
	GenuineBinary              bool
	NoAlternativeJustification *string
}
type AlternativeSufficiency struct {
	Status           string
	SelectedCount    int
	NonSelectedCount int
	PublicReason     string
}

func ValidateAlternatives(items []Alternative) error {
	if len(items) > 3 {
		return contracts.ErrInvalid
	}
	names := map[string]bool{}
	selected := 0
	for _, a := range items {
		if !publicText(a.Name, 160) || !publicText(a.Reason, 400) || !Has([]string{"selected", "rejected", "deferred", "not_comparable"}, a.Disposition) {
			return contracts.ErrInvalid
		}
		key := cases.Fold().String(strings.TrimSpace(a.Name))
		if names[key] {
			return contracts.ErrInvalid
		}
		names[key] = true
		if a.Disposition == "selected" {
			selected++
		}
	}
	if selected > 1 {
		return contracts.ErrInvalid
	}
	return nil
}
func AssessAlternativeSufficiency(items []Alternative, r AlternativeRequirement) AlternativeSufficiency {
	result := AlternativeSufficiency{}
	if e := ValidateAlternatives(items); e != nil {
		return AlternativeSufficiency{Status: "invalid", PublicReason: "invalid alternative set"}
	}
	for _, a := range items {
		if a.Disposition == "selected" {
			result.SelectedCount++
		} else {
			result.NonSelectedCount++
		}
	}
	switch {
	case !r.ChoiceRequired:
		result.Status = "not_required"
		result.PublicReason = "a choice/recommendation comparison is not required"
	case result.SelectedCount != 1:
		result.Status = "missing_selected"
		result.PublicReason = "exactly one selected alternative is required"
	case result.NonSelectedCount > 0:
		result.Status = "sufficient"
		result.PublicReason = "at least one real non-selected alternative is present"
	case r.GenuineBinary && r.NoAlternativeJustification != nil && publicText(*r.NoAlternativeJustification, 400):
		result.Status = "justified_binary"
		result.PublicReason = "framing records a genuine binary/no-alternative judgment"
	default:
		result.Status = "missing_non_selected"
		result.PublicReason = "a real non-selected alternative or public binary justification is required"
	}
	return result
}

type FlipCondition struct {
	Schema             string  `json:"schema"`
	Condition          string  `json:"condition"`
	AffectedConclusion *string `json:"affected_conclusion"`
	Direction          string  `json:"direction"`
	Check              string  `json:"check"`
}

var vagueConditions = []string{"if circumstances change", "if the circumstances change", "if new information emerges", "if new information appears", "if new information comes", "if the analysis is wrong", "if things change", "if the situation changes", "if the conditions change", "if the facts change", "if more information becomes available", "if more information emerges", "if more data becomes available", "if more data emerges", "if something changes"}
var observableMarkers = []string{"measure", "measured", "measurement", "check", "checked", "monitor", "observe", "observed", "obtain", "quote", "quoted", "threshold", "exceed", "exceeds", "above", "below", "under", "over", "at least", "at most", "falls", "drops", "rises", "reaches", "remains", "reports", "shows", "confirm", "validate", "test", "review", "compare", "metric", "renewal", "contract", "매출", "비용", "측정", "확인", "검증", "기준"}
var numberOrDate = regexp.MustCompile(`(?i)([0-9%$€£¥]|\b(usd|krw|eur|gbp|days?|weeks?|months?|quarters?|years?)\b)`)

func ObservableFlipText(text string) bool {
	lower := cases.Fold().String(strings.Join(strings.Fields(text), " "))
	for _, p := range vagueConditions {
		if strings.Contains(lower, p) {
			return false
		}
	}
	if numberOrDate.MatchString(lower) {
		return true
	}
	for _, p := range observableMarkers {
		if strings.Contains(lower, p) {
			return true
		}
	}
	return false
}
func ValidateFlipCondition(f FlipCondition) error {
	if !publicText(f.Condition, 300) || !publicText(f.Check, 240) || !Has([]string{"strengthen", "weaken", "reverse", "hold"}, f.Direction) || f.AffectedConclusion != nil && !publicText(*f.AffectedConclusion, 240) || !ObservableFlipText(f.Condition) || !ObservableFlipText(f.Check) {
		return contracts.ErrInvalid
	}
	return nil
}
func ValidateFlipConditions(items []FlipCondition) error {
	if len(items) > 2 {
		return contracts.ErrInvalid
	}
	keys := map[string]bool{}
	for _, f := range items {
		if e := ValidateFlipCondition(f); e != nil {
			return e
		}
		key := cases.Fold().String(f.Condition + "\x1f" + f.Check)
		if keys[key] {
			return contracts.ErrInvalid
		}
		keys[key] = true
	}
	return nil
}
