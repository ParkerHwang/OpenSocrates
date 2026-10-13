package compat

import (
	"context"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
)

type ReasoningSelector interface {
	Select(context.Context, Request) (*Candidate, error)
}
type Application struct {
	Selector  ReasoningSelector
	Bundle    *content.Bundle
	Artifacts *ArtifactStore
	OnOutcome func(string)
}
type Decision struct {
	Intervene    bool     `json:"intervene"`
	IDs          []string `json:"selected_reasoning_systems"`
	Instructions string   `json:"instructions"`
}

func (Decision) String() string { return "SelectorDecision(<redacted>)" }

// Select fails open and injects only a reference to content-owned assembly.
// Neither prompt nor model-authored instructions are persisted or returned.
func (a Application) Select(ctx context.Context, r Request, session, turn string) *Decision {
	record := func(label string) {
		if a.OnOutcome != nil {
			a.OnOutcome(label)
		}
	}
	if a.Selector == nil || a.Bundle == nil || a.Artifacts == nil {
		record("request_rejected")
		return nil
	}
	locale := domain.ResolveLocale(r.TrustedExplicitLocale, r.StoredPreference, r.Prompt, false)
	if locale == "" {
		record("request_rejected")
		return nil
	}
	candidate, err := a.Selector.Select(ctx, r)
	if err != nil {
		label := "spawn_failed"
		var outcome *OutcomeError
		var category *diagnostics.Error
		if errors.As(err, &outcome) {
			label = outcome.Outcome
		} else if errors.As(err, &category) {
			switch category.Code {
			case diagnostics.Verification:
				label = "invalid_output"
			case diagnostics.ProtocolIncompatible, diagnostics.Unsupported, diagnostics.Permission:
				label = "request_rejected"
			}
		}
		record(label)
		return nil
	}
	if ValidateCandidate(candidate, a.Bundle.IDs) != nil {
		record("invalid_output")
		return nil
	}
	if !candidate.Intervene {
		record("no_intervention")
		return nil
	}
	artifact, err := a.Artifacts.Create(session, turn, candidate.SelectedReasoningSystems, locale, a.Bundle)
	if err != nil {
		record("invalid_output")
		return nil
	}
	reference, err := artifact.ReferenceMessage()
	if err != nil {
		record("invalid_output")
		return nil
	}
	record("selected")
	return &Decision{Intervene: true, IDs: append([]string{}, candidate.SelectedReasoningSystems...), Instructions: reference}
}
