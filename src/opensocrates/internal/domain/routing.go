// Package domain contains pure policy; it performs no I/O or host discovery.
package domain

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"sort"
	"strings"
)

type Feature struct {
	Key      string
	Strength int
	Basis    string
}
type RoutingFeatures struct {
	AnswerShape    string
	Features       []Feature
	Confidence     string
	ExplicitMethod *string
}
type Method struct {
	ID          string            `json:"id"`
	Family      string            `json:"family"`
	DisplayName map[string]string `json:"display_name"`
	PlainAction map[string]string `json:"plain_action"`
	Procedure   map[string]string `json:"procedure"`
	Routing     struct {
		Positive          map[string]int `json:"positive_features"`
		Negative          map[string]int `json:"negative_features"`
		Minimum           int            `json:"minimum_score"`
		Contraindications []string       `json:"contraindications"`
	} `json:"routing"`
	Participation struct {
		Shapes []string `json:"allowed_answer_shapes"`
	} `json:"participation"`
	Complements struct {
		Preferred    []string `json:"preferred"`
		Incompatible []string `json:"incompatible_secondary"`
	} `json:"complements"`
	OutputContract struct {
		Sections []string `json:"required_sections"`
	} `json:"output_contract"`
}

var Shapes = []string{"direct_judgment", "decision_memo", "diagnostic", "critique", "risk_assessment", "evidence_reconciliation", "structured_plan", "completion_review"}
var featureKeys = strings.Fields("judgment mechanical mixed explicit_method choose diagnose explain critique forecast reconcile_evidence plan review_completion ambiguous_terms boundary_sensitive tangled_hierarchy category_overlap argument_dispute competing_explanations explicit_rules exception_prone_rule repeated_observations source_quality conflicting_sources new_evidence weak_sample testable_claim causal_question recurring_failure feedback_delay confounding multiple_options multiple_objectives single_feasible_option sequential_choice information_purchase irreversible_choice deep_uncertainty sensitive_inputs reference_cases unknown_probability chosen_plan failure_risk dismissed_opposition hidden_assumptions stale_options human_need technical_contradiction combinable_dimensions duties_rights value_conflict practical_consequence user_progress testable_hypothesis repeat_iteration governing_rule prioritized_assumptions interacting_actors macro_environment stakeholder_conflict context_disorder binding_rule_without_discretion no_defensible_reference_class no_defensible_prior_basis no_likelihood_direction no_testable_implication no_meaningful_interdependence no_coherent_dimensions safety_critical_validation decisive_input_missing")
var bases = []string{"task_shape", "evidence_need", "causal_need", "decision_need", "uncertainty_need", "challenge_need", "learning_need", "strategy_need", "explicit_user"}

func Has(items []string, s string) bool {
	for _, v := range items {
		if v == s {
			return true
		}
	}
	return false
}
func ParseRouting(value any) (RoutingFeatures, error) {
	m, e := contracts.Object(value, "schema", "answer_shape", "features", "classification_confidence", "explicit_method")
	if e != nil {
		return RoutingFeatures{}, e
	}
	if m["schema"] != "opensocrates.routing-features/1.0.0" || !contracts.Is(m["answer_shape"], Shapes...) || !contracts.Is(m["classification_confidence"], "high", "medium", "low") {
		return RoutingFeatures{}, contracts.ErrInvalid
	}
	f := RoutingFeatures{AnswerShape: m["answer_shape"].(string), Confidence: m["classification_confidence"].(string)}
	if m["explicit_method"] != nil {
		s, ok := m["explicit_method"].(string)
		if !ok || !MethodID(s) {
			return f, contracts.ErrInvalid
		}
		f.ExplicitMethod = &s
	}
	list, ok := m["features"].([]any)
	if !ok || len(list) > 16 {
		return f, contracts.ErrInvalid
	}
	seen := map[string]bool{}
	for _, raw := range list {
		item, e := contracts.Object(raw, "key", "strength", "basis")
		if e != nil {
			return f, e
		}
		if !contracts.Is(item["key"], featureKeys...) || !contracts.Is(item["basis"], bases...) {
			return f, contracts.ErrInvalid
		}
		n, ok := contracts.Int(item["strength"])
		if !ok || n < 1 || n > 3 {
			return f, contracts.ErrInvalid
		}
		key := item["key"].(string)
		if seen[key] {
			return f, contracts.ErrInvalid
		}
		seen[key] = true
		f.Features = append(f.Features, Feature{key, int(n), item["basis"].(string)})
	}
	return f, nil
}
func MethodID(s string) bool {
	if len(s) < 2 || len(s) > 64 || s[0] == '-' || s[len(s)-1] == '-' || strings.Contains(s, "--") {
		return false
	}
	for _, r := range s {
		if !(r >= 'a' && r <= 'z' || r >= '0' && r <= '9' || r == '-') {
			return false
		}
	}
	return true
}

type Route struct {
	Selected []string
	Reason   string
}
type scored struct {
	m       Method
	score   int
	blocked bool
	shape   bool
	cost    int
}

func score(m Method, f RoutingFeatures) scored {
	strengths := map[string]int{}
	for _, v := range f.Features {
		strengths[v.Key] = v.Strength
	}
	s := scored{m: m, shape: Has(m.Participation.Shapes, f.AnswerShape), cost: len(strings.Fields(m.Procedure["en"]))}
	for key, w := range m.Routing.Positive {
		s.score += w * strengths[key]
	}
	for key, w := range m.Routing.Negative {
		s.score -= w * strengths[key]
	}
	if _, exists := m.Routing.Negative["mechanical"]; !exists {
		s.score -= 3 * strengths["mechanical"]
	}
	contra := append([]string{}, m.Routing.Contraindications...)
	if !Has(contra, "mechanical") {
		contra = append(contra, "mechanical")
	}
	for _, key := range contra {
		if strengths[key] > 0 {
			s.score -= 12
			s.blocked = true
		}
	}
	return s
}
func RouteFeatures(participation string, f RoutingFeatures, methods []Method) Route {
	none := Route{[]string{}, "no_eligible_method"}
	if participation == "mechanical" {
		return none
	}
	byID := map[string]Method{}
	for _, m := range methods {
		byID[m.ID] = m
	}
	if f.ExplicitMethod != nil {
		m, ok := byID[*f.ExplicitMethod]
		if !ok {
			return none
		}
		if score(m, f).blocked {
			return Route{[]string{}, "contraindicated_explicit_method"}
		}
		return Route{[]string{m.ID}, "explicit_method"}
	}
	ranked := []scored{}
	for _, m := range methods {
		s := score(m, f)
		if !s.blocked && s.score >= m.Routing.Minimum {
			ranked = append(ranked, s)
		}
	}
	if len(ranked) == 0 {
		fallbacks := map[string][]string{"direct_judgment": {"critical-thinking"}, "decision_memo": {"trade-off-analysis", "sensitivity-analysis"}, "diagnostic": {"root-cause-analysis"}, "critique": {"argument-mapping", "critical-thinking"}, "risk_assessment": {"premortem-analysis", "failure-mode-effects-analysis"}, "evidence_reconciliation": {"evidence-hierarchy", "triangulation"}, "structured_plan": {"logic-tree", "premortem-analysis"}, "completion_review": {"critical-thinking"}}
		ids := fallbacks[f.AnswerShape]
		if f.AnswerShape == "decision_memo" {
			uncertain := false
			for _, v := range f.Features {
				uncertain = uncertain || Has([]string{"deep_uncertainty", "unknown_probability", "sensitive_inputs", "reference_cases"}, v.Key)
			}
			if !uncertain {
				ids = ids[:1]
			}
		}
		selected := []string{}
		for i, id := range ids {
			m, ok := byID[id]
			if !ok || score(m, f).blocked {
				if i == 0 {
					return none
				}
				continue
			}
			selected = append(selected, id)
		}
		return Route{selected, "answer_shape_fallback"}
	}
	sort.Slice(ranked, func(i, j int) bool {
		a, b := ranked[i], ranked[j]
		if a.score != b.score {
			return a.score > b.score
		}
		if a.shape != b.shape {
			return a.shape
		}
		if a.cost != b.cost {
			return a.cost < b.cost
		}
		return a.m.ID < b.m.ID
	})
	primary := ranked[0]
	selected := []string{primary.m.ID}
	for _, c := range ranked[1:] {
		if c.score*5 < primary.score*4 || c.m.Family == primary.m.Family || Has(primary.m.Complements.Incompatible, c.m.ID) || Has(c.m.Complements.Incompatible, primary.m.ID) {
			continue
		}
		if !(Has(primary.m.Complements.Preferred, c.m.ID) || Has(c.m.Complements.Preferred, primary.m.ID)) {
			continue
		}
		if len(primary.m.OutputContract.Sections) > 0 && len(c.m.OutputContract.Sections) > 0 && strings.Join(primary.m.OutputContract.Sections, "\x00") == strings.Join(c.m.OutputContract.Sections, "\x00") {
			continue
		}
		selected = append(selected, c.m.ID)
		break
	}
	reason := "weighted_primary"
	if len(selected) > 1 {
		reason = "weighted_primary_with_complement"
	}
	return Route{selected, reason}
}
