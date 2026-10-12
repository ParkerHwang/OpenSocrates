package domain

import (
	"crypto/sha256"
	"encoding/hex"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"regexp"
	"sort"
	"strings"
	"time"
)

const ObservationTagCapacity = 384

var safeTag = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)

type ObservationMetadata struct {
	ActiveTaskTag     string
	ToolCategory      string
	ResultSizeBucket  string
	ResultStatus      string
	ToolUseKey        string
	OccurredAt        string
	WindowTag         string
	BatchTag          *string
	SubjectTag        string
	ClaimVersionTags  []string
	RecordingEligible bool
}
type ObservationDedupeState struct {
	Fingerprints []string
	BatchTags    []string
}
type TaskObservationContext struct {
	State             TaskState
	CurrentJudgmentID *string
}
type ObservationDecision struct {
	Action            string
	Reason            string
	Fingerprint       *string
	NextFingerprints  []string
	NextBatchTags     []string
	ToolCategory      string
	InterventionClass string
}

func ValidateObservationMetadata(m ObservationMetadata) error {
	for _, tag := range []string{m.ActiveTaskTag, m.ToolUseKey, m.WindowTag, m.SubjectTag} {
		if !safeTag.MatchString(tag) {
			return contracts.ErrInvalid
		}
	}
	if m.BatchTag != nil && !safeTag.MatchString(*m.BatchTag) {
		return contracts.ErrInvalid
	}
	if !Has([]string{"retrieval", "read", "search", "calculation", "write", "format", "execution", "navigation", "other"}, m.ToolCategory) || !Has([]string{"empty", "small", "medium", "large", "oversize"}, m.ResultSizeBucket) || !Has([]string{"succeeded", "failed", "empty", "unavailable"}, m.ResultStatus) || len(m.ClaimVersionTags) > 5 || !sort.StringsAreSorted(m.ClaimVersionTags) || !uniqueStrings(m.ClaimVersionTags) {
		return contracts.ErrInvalid
	}
	for _, tag := range m.ClaimVersionTags {
		if !safeTag.MatchString(tag) {
			return contracts.ErrInvalid
		}
	}
	if _, e := time.Parse(time.RFC3339Nano, m.OccurredAt); e != nil {
		return contracts.ErrInvalid
	}
	return nil
}
func ObservationFingerprint(m ObservationMetadata, class string) (string, error) {
	if e := ValidateObservationMetadata(m); e != nil {
		return "", e
	}
	if !Has([]string{"reframe", "conflict", "weak_evidence", "missing_alternative", "completion_gap"}, class) {
		return "", contracts.ErrInvalid
	}
	batch := "-"
	if m.BatchTag != nil {
		batch = *m.BatchTag
	}
	parts := []string{"opensocrates-observation/1", m.ActiveTaskTag, m.WindowTag, batch, m.SubjectTag, class, m.ToolCategory, m.ToolUseKey}
	parts = append(parts, m.ClaimVersionTags...)
	sum := sha256.Sum256([]byte(strings.Join(parts, "\x1f")))
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}
func AssessObservation(m ObservationMetadata, task *TaskObservationContext, dedupe ObservationDedupeState, activeTaskTag *string, class string) (ObservationDecision, error) {
	d := ObservationDecision{Action: "empty", ToolCategory: m.ToolCategory, InterventionClass: class, NextFingerprints: []string{}, NextBatchTags: []string{}}
	if e := ValidateObservationMetadata(m); e != nil {
		return d, e
	}
	if !Has([]string{"reframe", "conflict", "weak_evidence", "missing_alternative", "completion_gap"}, class) {
		return d, contracts.ErrInvalid
	}
	empty := func(reason string) (ObservationDecision, error) { d.Reason = reason; return d, nil }
	if len(dedupe.Fingerprints) > ObservationTagCapacity || len(dedupe.BatchTags) > ObservationTagCapacity {
		return empty("dedupe_capacity_exhausted")
	}
	for _, tags := range [][]string{dedupe.Fingerprints, dedupe.BatchTags} {
		if !uniqueStrings(tags) {
			return d, contracts.ErrInvalid
		}
		for _, tag := range tags {
			if !safeTag.MatchString(tag) {
				return d, contracts.ErrInvalid
			}
		}
	}
	if task == nil {
		return empty("no_active_task")
	}
	if !m.RecordingEligible {
		return empty("recording_off")
	}
	if activeTaskTag != nil {
		if !safeTag.MatchString(*activeTaskTag) {
			return d, contracts.ErrInvalid
		}
		if m.ActiveTaskTag != *activeTaskTag {
			return empty("task_tag_mismatch")
		}
	}
	if !Has([]string{"framing", "working", "rejudging", "cross_examining", "verifying"}, string(task.State)) {
		return empty("task_not_active")
	}
	if task.CurrentJudgmentID == nil {
		return empty("no_current_judgment")
	}
	if Has([]string{"write", "format", "navigation"}, m.ToolCategory) {
		return empty("mechanical_category")
	}
	if !Has([]string{"retrieval", "read", "search", "calculation"}, m.ToolCategory) && !(m.ToolCategory == "execution" && m.ResultStatus == "failed") {
		return empty("ineligible_category")
	}
	if m.ResultStatus == "empty" {
		return empty("empty_result")
	}
	if m.ResultStatus == "unavailable" {
		return empty("unavailable_result")
	}
	if m.ResultSizeBucket == "empty" && m.ResultStatus != "failed" {
		return empty("empty_result")
	}
	fingerprint, e := ObservationFingerprint(m, class)
	if e != nil {
		return d, e
	}
	d.Fingerprint = &fingerprint
	if Has(dedupe.Fingerprints, fingerprint) {
		return empty("duplicate")
	}
	if m.BatchTag != nil && Has(dedupe.BatchTags, *m.BatchTag) {
		return empty("batch_duplicate")
	}
	if len(dedupe.Fingerprints) >= ObservationTagCapacity || m.BatchTag != nil && len(dedupe.BatchTags) >= ObservationTagCapacity {
		return empty("dedupe_capacity_exhausted")
	}
	d.Action = "inject"
	d.Reason = "eligible"
	d.NextFingerprints = append(append([]string{}, dedupe.Fingerprints...), fingerprint)
	d.NextBatchTags = append([]string{}, dedupe.BatchTags...)
	if m.BatchTag != nil {
		d.NextBatchTags = append(d.NextBatchTags, *m.BatchTag)
	}
	return d, nil
}
