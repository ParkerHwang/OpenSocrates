package verification

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"regexp"
	"strings"
	"time"
)

var modelProvidedID = regexp.MustCompile(`(^|[^A-Za-z0-9])([JCEAKI][0-9]{6}|[0-9A-HJKMNP-TV-Z]{26})($|[^A-Za-z0-9])`)
var trustedLocalID = regexp.MustCompile(`^[JCEAKI][0-9]{6}$`)
var trustedTaskID = regexp.MustCompile(`^[0-7][0-9A-HJKMNP-TV-Z]{25}$`)

type TrustedCardContext struct {
	TaskID          string
	JudgmentID      string
	ClaimIDs        []string
	JudgmentVersion int
	RenderedAt      string
}

func splitSupport(s string) ([]string, error) {
	parts := []string{}
	start, code, brackets, parens := 0, 0, 0, 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == '\\' {
			i++
			continue
		}
		if c == '`' {
			fence := 1
			for i+fence < len(s) && s[i+fence] == '`' {
				fence++
			}
			if code == 0 {
				code = fence
			} else if code == fence {
				code = 0
			}
			i += fence - 1
			continue
		}
		if code > 0 {
			continue
		}
		switch c {
		case '[':
			brackets++
		case ']':
			if brackets > 0 {
				brackets--
			}
		case '(':
			if brackets == 0 {
				parens++
			}
		case ')':
			if parens > 0 {
				parens--
			}
		case ';':
			if brackets == 0 && parens == 0 {
				part := strings.TrimSpace(s[start:i])
				if part == "" {
					return nil, contracts.ErrInvalid
				}
				parts = append(parts, part)
				start = i + 1
			}
		}
	}
	if code > 0 || brackets > 0 || parens > 0 {
		return nil, contracts.ErrInvalid
	}
	part := strings.TrimSpace(s[start:])
	if part == "" {
		return nil, contracts.ErrInvalid
	}
	return append(parts, part), nil
}
func splitLabel(line string, bullet bool) (string, string, string, error) {
	prefix := ""
	if bullet {
		prefix = "- "
		if !strings.HasPrefix(line, prefix) {
			return "", "", "", contracts.ErrInvalid
		}
	}
	marker := strings.LastIndex(line, " — **")
	if marker <= len(prefix) {
		return "", "", "", contracts.ErrInvalid
	}
	start := marker + len(" — **")
	end := strings.Index(line[start:], "**")
	if end <= 0 {
		return "", "", "", contracts.ErrInvalid
	}
	label := line[start : start+end]
	return line[len(prefix):marker], label, line[start+end+2:], nil
}
func reverseLabel(messages map[string]string, prefix string, values []string) (map[string]string, error) {
	labels := map[string]string{}
	for _, v := range values {
		label := messages[prefix+v]
		escaped, e := EscapeInline(label, false)
		if e != nil {
			return nil, e
		}
		if _, ok := labels[escaped]; ok {
			return nil, contracts.ErrInvalid
		}
		labels[escaped] = v
	}
	return labels, nil
}
func ParseCard(markdown, locale string, messages map[string]string, context TrustedCardContext) (domain.ConclusionCard, error) {
	card := domain.ConclusionCard{Schema: "opensocrates.conclusion-card/1.0.0", Locale: locale, TaskID: context.TaskID, JudgmentID: context.JudgmentID, JudgmentVersion: context.JudgmentVersion, RenderedAt: context.RenderedAt, Grounds: []domain.ConclusionGround{}, Uncertainties: []string{}, FlipConditions: []domain.FlipCondition{}}
	invalid := func() (domain.ConclusionCard, error) { return card, contracts.ErrInvalid }
	normalized, e := ValidateCardMarkdown(markdown)
	if e != nil {
		return card, e
	}
	if modelProvidedID.MatchString(normalized) {
		return invalid()
	}
	if context.TaskID == "" {
		context.TaskID = domain.NewTaskID()
		card.TaskID = context.TaskID
	}
	if context.JudgmentID == "" {
		context.JudgmentID = "J000001"
		card.JudgmentID = context.JudgmentID
	}
	if context.JudgmentVersion == 0 {
		context.JudgmentVersion = 1
		card.JudgmentVersion = 1
	}
	if context.RenderedAt == "" {
		context.RenderedAt = time.Now().UTC().Format(domain.TimestampFormat)
		card.RenderedAt = context.RenderedAt
	}
	if locale != "en" && locale != "ko" || !trustedTaskID.MatchString(context.TaskID) || !strings.HasPrefix(context.JudgmentID, "J") || !trustedLocalID.MatchString(context.JudgmentID) || context.JudgmentVersion < 1 {
		return invalid()
	}
	if _, e := time.Parse(time.RFC3339Nano, context.RenderedAt); e != nil {
		return invalid()
	}
	for _, k := range CardLocaleKeys {
		if e := ValidateScalarText(messages[k], 4000, false); e != nil {
			return card, e
		}
	}
	lines := []string{}
	for _, line := range strings.Split(normalized, "\n") {
		if strings.TrimSpace(line) != "" {
			if line != strings.TrimSpace(line) {
				return invalid()
			}
			lines = append(lines, line)
		}
	}
	if len(lines) < 3 {
		return invalid()
	}
	depth := len(lines[0]) - len(strings.TrimLeft(lines[0], "#"))
	if depth < 1 || depth > 5 || lines[0] != strings.Repeat("#", depth)+" "+messages["card.heading.conclusion"] {
		return invalid()
	}
	sub := strings.Repeat("#", depth+1) + " "
	text, label, support, e := splitLabel(lines[1], false)
	if e != nil || support != "" {
		return invalid()
	}
	strengths, e := reverseLabel(messages, "card.strength.", []string{"held", "provisional", "supported", "strongly_supported"})
	if e != nil {
		return card, e
	}
	strength, ok := strengths[label]
	if !ok {
		return invalid()
	}
	card.Strength = domain.JudgmentStrength(strength)
	card.Conclusion, e = UnescapeInline(text)
	if e != nil {
		return card, e
	}
	sections := [][]string{}
	index := 2
	for _, key := range []string{"card.heading.why", "card.heading.still_uncertain", "card.heading.this_flips_if", "card.heading.alternatives_considered"} {
		if index >= len(lines) || lines[index] != sub+messages[key] {
			return invalid()
		}
		index++
		section := []string{}
		for index < len(lines) && !strings.HasPrefix(lines[index], "#") {
			section = append(section, lines[index])
			index++
		}
		sections = append(sections, section)
	}
	if index != len(lines) || len(sections[0]) < 1 || len(sections[0]) > 5 || context.ClaimIDs != nil && len(context.ClaimIDs) != len(sections[0]) || len(sections[1]) > 2 || len(sections[2]) < 1 || len(sections[2]) > 2 || len(sections[3]) != 1 || strings.HasPrefix(sections[3][0], "- ") {
		return invalid()
	}
	if context.ClaimIDs == nil {
		for i := range sections[0] {
			context.ClaimIDs = append(context.ClaimIDs, fmt.Sprintf("C%06d", i+1))
		}
	}
	seenClaims := map[string]bool{}
	for _, id := range context.ClaimIDs {
		if !strings.HasPrefix(id, "C") || !trustedLocalID.MatchString(id) || seenClaims[id] {
			return invalid()
		}
		seenClaims[id] = true
	}
	states, e := reverseLabel(messages, "card.state.", []string{"verified", "computed", "inferred", "assumed", "unverified", "conflicted"})
	if e != nil {
		return card, e
	}
	for i, line := range sections[0] {
		text, label, support, e := splitLabel(line, true)
		if e != nil {
			return card, e
		}
		state, ok := states[label]
		if !ok {
			return invalid()
		}
		g := domain.ConclusionGround{ClaimID: context.ClaimIDs[i], State: domain.EvidenceState(state), SourceRefs: []domain.CardSourceReference{}}
		g.Text, e = UnescapeInline(text)
		if e != nil {
			return card, e
		}
		if support != "" {
			if !strings.HasPrefix(support, " (") || !strings.HasSuffix(support, ")") {
				return invalid()
			}
			parts, e := splitSupport(support[2 : len(support)-1])
			if e != nil {
				return card, e
			}
			for _, part := range parts {
				switch {
				case strings.HasPrefix(part, "`"):
					if g.CalculationSummary != nil {
						return invalid()
					}
					value, e := ParseInlineCode(part)
					if e != nil {
						return card, e
					}
					g.CalculationSummary = &value
				case strings.HasPrefix(part, "["):
					name, uri, e := ParseLink(part)
					if e != nil {
						return card, e
					}
					g.SourceRefs = append(g.SourceRefs, domain.CardSourceReference{name, &uri})
				case strings.HasPrefix(part, messages["card.source.user_provided"]+": "):
					name, e := UnescapeInline(strings.TrimPrefix(part, messages["card.source.user_provided"]+": "))
					if e != nil {
						return card, e
					}
					g.SourceRefs = append(g.SourceRefs, domain.CardSourceReference{name, nil})
				default:
					return invalid()
				}
			}
		}
		card.Grounds = append(card.Grounds, g)
	}
	none, _ := EscapeInline(messages["card.uncertainty.none"], false)
	for _, line := range sections[1] {
		if line == "- "+none {
			if len(sections[1]) != 1 {
				return invalid()
			}
			continue
		}
		if !strings.HasPrefix(line, "- ") {
			return invalid()
		}
		value, e := UnescapeInline(line[2:])
		if e != nil {
			return card, e
		}
		card.Uncertainties = append(card.Uncertainties, value)
	}
	directions, e := reverseLabel(messages, "card.flip.direction.", []string{"strengthen", "weaken", "reverse", "hold"})
	if e != nil {
		return card, e
	}
	for _, line := range sections[2] {
		text, label, support, e := splitLabel(line, true)
		if e != nil {
			return card, e
		}
		direction, ok := directions[label]
		if !ok || !strings.HasPrefix(support, " (") || !strings.HasSuffix(support, ")") {
			return invalid()
		}
		f := domain.FlipCondition{Schema: "opensocrates.flip-condition/1.0.0", Direction: direction}
		f.Condition, e = UnescapeInline(text)
		if e != nil {
			return card, e
		}
		parts, e := splitSupport(support[2 : len(support)-1])
		if e != nil {
			return card, e
		}
		check := false
		for _, part := range parts {
			prefix := messages["card.flip.check"] + ": "
			affected := messages["card.flip.affected_conclusion"] + ": "
			switch {
			case strings.HasPrefix(part, prefix):
				if check {
					return invalid()
				}
				f.Check, e = UnescapeInline(part[len(prefix):])
				if e != nil {
					return card, e
				}
				check = true
			case strings.HasPrefix(part, affected):
				if f.AffectedConclusion != nil {
					return invalid()
				}
				value, e := UnescapeInline(part[len(affected):])
				if e != nil {
					return card, e
				}
				f.AffectedConclusion = &value
			default:
				return invalid()
			}
		}
		if !check {
			return invalid()
		}
		card.FlipConditions = append(card.FlipConditions, f)
	}
	card.AlternativesSummary, e = UnescapeInline(sections[3][0])
	if e != nil {
		return card, e
	}
	if len(CardViolations(card, &normalized)) > 0 {
		return invalid()
	}
	canonical, e := RenderCard(card, messages, depth)
	if e != nil {
		return card, e
	}
	if canonical != strings.Join(lines, "\n") {
		return invalid()
	}
	return card, nil
}
