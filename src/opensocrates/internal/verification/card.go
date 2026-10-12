package verification

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
	"regexp"
	"strings"
	"unicode"
)

type Violation struct {
	RuleID        string  `json:"rule_id"`
	Severity      string  `json:"severity"`
	MessageKey    string  `json:"message_key"`
	Field         *string `json:"field"`
	RepairHintKey *string `json:"repair_hint_key"`
}

func violation(id, message, field string) Violation {
	var f *string
	if field != "" {
		f = &field
	}
	return Violation{id, "error", message, f, nil}
}

var internalTerms = []string{"run", "gate", "routing", "router", "reasoning_gate", "lens_mode", "evidence_mode", "phase", "state machine", "hook", "adapter", "event journal", "task/claim/evidence ids", "task_id", "judgment_id", "claim_id", "evidence_id", "source_id", "schema version", "schema_version", "repair counter", "repair_counter", "capability tier", "capability_tier", "implementation filename"}

func ContainsInternalVocabulary(s string) bool {
	s = cases.Fold().String(norm.NFKC.String(s))
	for _, term := range internalTerms {
		if strings.Contains(term, "_") {
			if strings.Contains(s, term) || strings.Contains(s, strings.ReplaceAll(term, "_", "-")) {
				return true
			}
			continue
		}
		from := 0
		for from < len(s) {
			i := strings.Index(s[from:], term)
			if i < 0 {
				break
			}
			i += from
			end := i + len(term)
			before := []rune(s[:i])
			after := []rune(s[end:])
			word := func(r rune) bool { return unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_' }
			if (len(before) == 0 || !word(before[len(before)-1])) && (len(after) == 0 || !word(after[0])) {
				return true
			}
			from = end
		}
	}
	return false
}

var calcSummary = regexp.MustCompile(`^\s*[A-Za-z0-9_().%+*/\-\s]+\s*=\s*[+-]?[0-9]+(\.[0-9]+)?\s+\S+\s*$`)
var privateDisplay = regexp.MustCompile(`(^[/\\~])|(^[A-Za-z]:[/\\])|(^|[/\\])\.\.([/\\]|$)`)

func CardViolations(card domain.ConclusionCard, markdown *string) []Violation {
	result := []Violation{}
	add := func(id, message, field string) {
		if len(result) < 32 {
			result = append(result, violation(id, message, field))
		}
	}
	public := map[string]any{}
	check := func(s, field string, max int) {
		public[field] = s
		if e := ValidateScalarText(s, max, false); e != nil {
			add("OSV-CARD-001", "card.text_invalid", field)
			return
		}
		for _, u := range textURLs.FindAllString(s, -1) {
			if e := ValidatePublicURL(strings.TrimRight(u, ".,;:)]}")); e != nil {
				add("OSV-SOURCE-003", "source.unsafe_url", field)
			}
		}
		if ContainsInternalVocabulary(s) {
			add("OSV-VOCAB-001", "vocabulary.internal_term", field)
		}
	}
	if card.Locale != "en" && card.Locale != "ko" {
		add("OSV-LOCALE-001", "locale.unsupported", "locale")
	}
	if len(card.Grounds) < 1 || len(card.Grounds) > 5 {
		add("OSV-CARD-005", "card.ground_count", "grounds")
	}
	if len(card.Uncertainties) > 2 {
		add("OSV-CARD-006", "card.uncertainty_count", "uncertainties")
	}
	if len(card.FlipConditions) < 1 || len(card.FlipConditions) > 2 {
		add("OSV-CARD-007", "card.flip_count", "flip_conditions")
	}
	if card.JudgmentVersion < 1 {
		add("OSV-CARD-008", "card.version_invalid", "judgment_version")
	}
	check(card.Conclusion, "conclusion", 240)
	sentences := 0
	runes := []rune(card.Conclusion)
	for i, r := range runes {
		if strings.ContainsRune(".!?。！？", r) && (i == len(runes)-1 || unicode.IsSpace(runes[i+1])) {
			sentences++
		}
	}
	if sentences > 1 {
		add("OSV-CARD-002", "card.one_sentence_required", "conclusion")
	}
	weak, strong := false, true
	for i, g := range card.Grounds {
		field := fmt.Sprintf("grounds[%d]", i)
		check(g.Text, field+".text", 240)
		if !contains([]string{"verified", "computed", "inferred", "assumed", "unverified", "conflicted"}, string(g.State)) {
			add("OSV-EVIDENCE-001", "evidence.unknown_state", field+".state")
			continue
		}
		if g.ClaimID == "" {
			add("OSV-EVIDENCE-002", "evidence.claim_id_required", field+".claim_id")
		}
		for j, source := range g.SourceRefs {
			sf := fmt.Sprintf("%s.source_refs[%d]", field, j)
			check(source.DisplayName, sf+".display_name", 200)
			if contains([]string{"click here", "here", "link"}, strings.ToLower(strings.TrimSpace(source.DisplayName))) {
				add("OSV-SOURCE-002", "source.generic_label", sf+".display_name")
			}
			if privateDisplay.MatchString(source.DisplayName) {
				add("OSV-SOURCE-005", "source.private_display", sf+".display_name")
			}
			if source.URI != nil {
				public[sf+".uri"] = *source.URI
				if e := ValidatePublicURL(*source.URI); e != nil {
					add("OSV-SOURCE-001", "source.unsafe_url", sf+".uri")
				}
				if ContainsInternalVocabulary(*source.URI) {
					add("OSV-VOCAB-001", "vocabulary.internal_term", sf+".uri")
				}
			}
		}
		if g.CalculationSummary != nil {
			check(*g.CalculationSummary, field+".calculation_summary", 400)
		}
		switch g.State {
		case domain.Verified:
			if len(g.SourceRefs) == 0 {
				add("OSV-EVIDENCE-003", "evidence.verified_source_required", field)
			}
		case domain.Computed:
			if g.CalculationSummary == nil || !calcSummary.MatchString(*g.CalculationSummary) {
				add("OSV-CALC-001", "calculation.reproducible_required", field+".calculation_summary")
			}
			if g.CalculationSummary != nil {
				for _, term := range []string{"eval", "exec", "import", "shell"} {
					if strings.Contains(strings.ToLower(*g.CalculationSummary), term) {
						add("OSV-CALC-002", "calculation.unsafe_expression", field+".calculation_summary")
						break
					}
				}
			}
		case domain.Inferred:
			if g.CalculationSummary != nil {
				add("OSV-EVIDENCE-004", "evidence.inferred_no_calculation", field)
			}
		case domain.Assumed:
			if len(g.SourceRefs) > 0 || g.CalculationSummary != nil {
				add("OSV-EVIDENCE-005", "evidence.assumed_no_support", field)
			}
		case domain.Conflicted:
			hasLanguage := false
			for _, marker := range []string{" vs ", " versus ", " but ", " while ", "although", "conflict", "disagree", "충돌", ";"} {
				hasLanguage = hasLanguage || strings.Contains(" "+strings.ToLower(g.Text)+" ", marker)
			}
			if len(g.SourceRefs) < 2 && g.CalculationSummary == nil && !hasLanguage {
				add("OSV-CONFLICT-001", "conflict.public_summary_required", field)
			}
			if card.Strength == domain.Supported || card.Strength == domain.StronglySupported {
				add("OSV-CONFLICT-002", "conflict.must_lower_strength", field)
			}
		}
		weak = weak || g.State == domain.Assumed || g.State == domain.Unverified || g.State == domain.Conflicted
		strong = strong && (g.State == domain.Verified || g.State == domain.Computed)
	}
	for i, u := range card.Uncertainties {
		check(u, fmt.Sprintf("uncertainties[%d]", i), 220)
	}
	for i, f := range card.FlipConditions {
		field := fmt.Sprintf("flip_conditions[%d]", i)
		check(f.Condition, field+".condition", 220)
		check(f.Check, field+".check", 220)
		if f.AffectedConclusion != nil {
			check(*f.AffectedConclusion, field+".affected_conclusion", 220)
		}
		if contains([]string{"if circumstances change", "if new information emerges", "if the analysis is wrong", "if new information appears", "if things change", "if more data arrives"}, strings.ToLower(strings.TrimSpace(f.Condition))) {
			add("OSV-CARD-003", "card.observable_flip_required", field+".condition")
		}
		if !contains([]string{"strengthen", "weaken", "reverse", "hold"}, f.Direction) {
			add("OSV-CARD-004", "card.unknown_flip_direction", field+".direction")
		}
	}
	check(card.AlternativesSummary, "alternatives_summary", 300)
	if card.Strength == domain.StronglySupported && !strong {
		add("OSV-EVIDENCE-006", "evidence.strong_strength_requires_support", "strength")
	}
	if card.Strength == domain.Provisional && !weak {
		add("OSV-EVIDENCE-007", "evidence.provisional_basis_required", "strength")
	}
	if card.Strength == domain.Supported && weak {
		add("OSV-EVIDENCE-009", "evidence.uncertain_strength_requires_downgrade", "strength")
	}
	if !contains([]string{"held", "provisional", "supported", "strongly_supported"}, string(card.Strength)) {
		add("OSV-EVIDENCE-008", "evidence.unknown_strength", "strength")
	}
	if len(SecretFindings(public)) > 0 {
		add("OSV-PRIVACY-001", "privacy.secret_or_unsafe_text", "")
	}
	if markdown != nil {
		if _, e := ValidateCardMarkdown(*markdown); e != nil {
			add("OSV-CARD-010", "card.collapsed_limits", "")
		} else if strings.TrimSpace(*markdown) == "" {
			add("OSV-CARD-009", "card.empty", "")
		}
	}
	return result
}

var CardLocaleKeys = []string{"card.heading.conclusion", "card.heading.why", "card.heading.still_uncertain", "card.heading.this_flips_if", "card.heading.alternatives_considered", "card.state.verified", "card.state.computed", "card.state.inferred", "card.state.assumed", "card.state.unverified", "card.state.conflicted", "card.uncertainty.none", "card.source.user_provided", "card.strength.held", "card.strength.provisional", "card.strength.supported", "card.strength.strongly_supported", "card.flip.direction.strengthen", "card.flip.direction.weaken", "card.flip.direction.reverse", "card.flip.direction.hold", "card.flip.check", "card.flip.affected_conclusion"}

func RenderCard(card domain.ConclusionCard, messages map[string]string, headingLevel int) (string, error) {
	if headingLevel < 1 || headingLevel > 5 || len(CardViolations(card, nil)) > 0 {
		return "", contracts.ErrInvalid
	}
	for _, k := range CardLocaleKeys {
		if e := ValidateScalarText(messages[k], 4000, false); e != nil {
			return "", e
		}
	}
	esc := func(s string, semi bool) string { v, _ := EscapeInline(s, semi); return v }
	h := strings.Repeat("#", headingLevel)
	sub := h + "#"
	lines := []string{h + " " + messages["card.heading.conclusion"], esc(card.Conclusion, false) + " — **" + esc(messages["card.strength."+string(card.Strength)], false) + "**", sub + " " + messages["card.heading.why"]}
	for _, g := range card.Grounds {
		support := []string{}
		if g.CalculationSummary != nil {
			code, e := InlineCode(*g.CalculationSummary)
			if e != nil {
				return "", e
			}
			support = append(support, code)
		}
		for _, s := range g.SourceRefs {
			if s.URI != nil {
				link, e := RenderLink(s.DisplayName, *s.URI)
				if e != nil {
					return "", e
				}
				support = append(support, link)
			} else {
				support = append(support, messages["card.source.user_provided"]+": "+esc(s.DisplayName, true))
			}
		}
		suffix := ""
		if len(support) > 0 {
			suffix = " (" + strings.Join(support, "; ") + ")"
		}
		lines = append(lines, "- "+esc(g.Text, false)+" — **"+esc(messages["card.state."+string(g.State)], false)+"**"+suffix)
	}
	lines = append(lines, sub+" "+messages["card.heading.still_uncertain"])
	if len(card.Uncertainties) == 0 {
		lines = append(lines, "- "+esc(messages["card.uncertainty.none"], false))
	} else {
		for _, u := range card.Uncertainties {
			lines = append(lines, "- "+esc(u, false))
		}
	}
	lines = append(lines, sub+" "+messages["card.heading.this_flips_if"])
	for _, f := range card.FlipConditions {
		support := []string{messages["card.flip.check"] + ": " + esc(f.Check, true)}
		if f.AffectedConclusion != nil {
			support = append(support, messages["card.flip.affected_conclusion"]+": "+esc(*f.AffectedConclusion, true))
		}
		lines = append(lines, "- "+esc(f.Condition, false)+" — **"+esc(messages["card.flip.direction."+f.Direction], false)+"** ("+strings.Join(support, "; ")+")")
	}
	lines = append(lines, sub+" "+messages["card.heading.alternatives_considered"], esc(card.AlternativesSummary, false))
	rendered, e := ValidateCardMarkdown(strings.Join(lines, "\n"))
	if e != nil {
		return "", e
	}
	if len(CardViolations(card, &rendered)) > 0 {
		return "", contracts.ErrInvalid
	}
	return rendered, nil
}
