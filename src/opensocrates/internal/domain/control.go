package domain

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
	"net/url"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"
)

const MaxControlBytes = 32 * 1024
const MaxTurnStateBytes = 64 * 1024
const MaxAcceptedControls = 16
const MaxObservationTags = 384
const TimestampFormat = "2006-01-02T15:04:05.000Z"

var ErrControl = errors.New("invalid_payload")
var ErrExpiredTurn = errors.New("expired_token")
var ErrCapacity = errors.New("capacity_exhausted")
var tokenPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{43}$`)
var tagPattern = regexp.MustCompile(`^sha256:[0-9a-f]{64}$`)
var messagePattern = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)
var localPattern = regexp.MustCompile(`^[JCEAKI][0-9]{6}$`)

type Control struct {
	MessageID   string
	TurnToken   string
	MessageType string
	Published   bool
	Payload     map[string]any
}
type AssignedIDs struct {
	TaskID         *string  `json:"task_id"`
	JudgmentID     *string  `json:"judgment_id"`
	ClaimIDs       []string `json:"claim_ids"`
	SourceIDs      []string `json:"source_ids"`
	CriterionIDs   []string `json:"criterion_ids"`
	AlternativeIDs []string `json:"alternative_ids"`
}
type ControlResult struct {
	Schema                string         `json:"schema"`
	MessageID             string         `json:"message_id"`
	Status                string         `json:"status"`
	ReasonCode            *string        `json:"reason_code"`
	ErrorCode             *string        `json:"error_code"`
	DurableMutation       bool           `json:"durable_mutation"`
	AssignedIDs           AssignedIDs    `json:"assigned_ids"`
	EffectiveRigor        *string        `json:"effective_rigor"`
	Route                 map[string]any `json:"route"`
	CapabilityLimitations []string       `json:"capability_limitations"`
	NextAction            string         `json:"next_action"`
}

func Pointer(s string) *string { return &s }
func EmptyAssignedIDs() AssignedIDs {
	return AssignedIDs{ClaimIDs: []string{}, SourceIDs: []string{}, CriterionIDs: []string{}, AlternativeIDs: []string{}}
}
func NewControlResult(id string) ControlResult {
	if !messagePattern.MatchString(id) {
		id = NewMessageID()
	}
	return ControlResult{Schema: "opensocrates.host-control-result/1.0.0", MessageID: id, Status: "rejected", AssignedIDs: EmptyAssignedIDs(), CapabilityLimitations: []string{}, NextAction: "continue"}
}
func NewMessageID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	n := uint64(time.Now().UnixMilli())
	for i := 5; i >= 0; i-- {
		b[i] = byte(n)
		n >>= 8
	}
	b[6] = b[6]&15 | 112
	b[8] = b[8]&63 | 128
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[:4], b[4:6], b[6:8], b[8:10], b[10:])
}
func NewTaskID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	n := uint64(time.Now().UnixMilli())
	for i := 5; i >= 0; i-- {
		b[i] = byte(n)
		n >>= 8
	}
	const alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
	out := make([]byte, 26)
	var carry uint32
	bits := uint(2)
	j := 0
	for _, x := range b {
		carry = (carry << 8) | uint32(x)
		bits += 8
		for bits >= 5 {
			bits -= 5
			out[j] = alphabet[(carry>>bits)&31]
			j++
		}
	}
	return string(out)
}
func Normalize(value any) (map[string]any, error) {
	b, e := contracts.CanonicalCompact(value)
	if e != nil {
		return nil, e
	}
	v, e := contracts.Decode(b)
	if e != nil {
		return nil, e
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, ErrControl
	}
	return m, nil
}
func ParseControl(raw []byte) (Control, error) {
	c := Control{}
	if len(raw) > MaxControlBytes {
		return c, errors.New("oversized")
	}
	v, e := contracts.Decode(raw)
	if e != nil {
		return c, errors.New("invalid_json")
	}
	// The released parser classifies valid JSON with a non-object root as
	// invalid_json; malformed object fields belong to invalid_payload.
	if _, ok := v.(map[string]any); !ok {
		return c, errors.New("invalid_json")
	}
	m, e := contracts.Object(v, "schema", "message_id", "turn_token", "message_type", "published", "payload")
	if e != nil {
		return c, ErrControl
	}
	if m["schema"] != "opensocrates.host-control/1.0.0" {
		return c, errors.New("unknown_schema")
	}
	token, ok := m["turn_token"].(string)
	if !ok || !tokenPattern.MatchString(token) {
		return c, errors.New("invalid_token")
	}
	kind, ok := m["message_type"].(string)
	if !ok || !Has(strings.Fields("begin_judgment intervention_feedback publish_framing publish_claim publish_conflict publish_alternative revise_judgment complete_cross_exam hold_judgment cancel_judgment"), kind) {
		return c, errors.New("unknown_message_type")
	}
	if e = contracts.Validate("host-control", v); e != nil {
		return c, ErrControl
	}
	if e = GuardControlTree(v, 0); e != nil {
		return c, e
	}
	c = Control{m["message_id"].(string), token, kind, m["published"].(bool), m["payload"].(map[string]any)}
	return c, ValidateControlPayload(c)
}

var prohibitedControl = strings.Fields("prompt prompts transcript transcript_path messages conversation reasoning rationale_internal thought thoughts chain_of_thought raw raw_input raw_output tool_input tool_output tool_response stdout stderr command environment env cookie authorization password passwd secret token api_key private_key credentials")

func GuardControlTree(v any, depth int) error {
	if depth > 12 {
		return ErrControl
	}
	switch x := v.(type) {
	case map[string]any:
		if len(x) > 128 {
			return ErrControl
		}
		for k, v := range x {
			key := cases.Fold().String(norm.NFKC.String(k))
			key = strings.ReplaceAll(strings.ReplaceAll(key, "-", "_"), " ", "_")
			if Has(prohibitedControl, key) {
				return ErrControl
			}
			if e := GuardControlTree(v, depth+1); e != nil {
				return e
			}
		}
	case []any:
		if len(x) > 256 {
			return ErrControl
		}
		for _, v := range x {
			if e := GuardControlTree(v, depth+1); e != nil {
				return e
			}
		}
	case string:
		if !canonicalText(x) {
			return ErrControl
		}
	}
	return nil
}
func canonicalText(s string) bool {
	if !utf8.ValidString(s) || !norm.NFC.IsNormalString(s) {
		return false
	}
	for _, r := range s {
		if r == 0 || r < 32 && r != '\n' && r != '\t' {
			return false
		}
	}
	return true
}
func controlText(v any, max int) bool {
	s, ok := v.(string)
	return ok && canonicalText(s) && strings.TrimSpace(s) != "" && utf8.RuneCountInString(s) <= max
}
func controlList(v any, max int) ([]any, bool) { a, ok := v.([]any); return a, ok && len(a) <= max }
func localID(v any, prefix string) bool {
	s, ok := v.(string)
	return ok && len(s) <= 32 && strings.HasPrefix(s, prefix) && localPattern.MatchString(s)
}
func controlIDs(v any, prefix string, max int) bool {
	a, ok := controlList(v, max)
	if !ok {
		return false
	}
	seen := map[string]bool{}
	for _, v := range a {
		if !localID(v, prefix) {
			return false
		}
		s := v.(string)
		if seen[s] {
			return false
		}
		seen[s] = true
	}
	return true
}
func controlReference(v any) bool {
	m, ok := v.(map[string]any)
	if !ok || len(m) != 1 {
		return false
	}
	if id, ok := m["existing_id"]; ok {
		return localID(id, "E")
	}
	n, ok := contracts.Int(m["new_index"])
	return ok && n >= 0 && n <= 4
}
func ValidateControlPayload(c Control) error {
	p := c.Payload
	keys := map[string][]string{
		"begin_judgment": {"participation", "rigor", "routing_features"}, "intervention_feedback": {"class", "outcome"}, "publish_framing": {"decision_question", "assumptions", "decisive_evidence", "completion_criteria"},
		"publish_claim": {"claim_ref", "expected_current_version", "text", "materiality", "evidence_state", "source_refs", "new_sources", "basis_claim_ids", "calculation", "conflict"}, "publish_conflict": {"conflict", "affected_claim_ids"}, "publish_alternative": {"name", "disposition", "reason", "material_claim_ids"},
		"revise_judgment": {"conclusion", "strength", "change_reason", "ground_claim_ids", "uncertainty_claim_ids", "alternative_ids", "flip_conditions"}, "complete_cross_exam": {"findings_summary", "affected_ids"}, "hold_judgment": {"missing_items", "reason_code"}, "cancel_judgment": {"reason"},
	}
	if _, e := contracts.Object(p, keys[c.MessageType]...); e != nil {
		return ErrControl
	}
	if c.MessageType != "begin_judgment" && c.MessageType != "intervention_feedback" && c.MessageType != "cancel_judgment" && !c.Published {
		return ErrControl
	}
	switch c.MessageType {
	case "begin_judgment":
		for _, name := range []string{"participation", "rigor", "routing_features"} {
			if e := contracts.Validate(strings.ReplaceAll(name, "_", "-")+"-decision", p[name]); e != nil {
				if name != "routing_features" {
					return ErrControl
				}
			}
		}
		if e := contracts.Validate("routing-features", p["routing_features"]); e != nil {
			return ErrControl
		}
		if _, e := ParseRouting(p["routing_features"]); e != nil {
			return ErrControl
		}
		if e := validateControlRigor(p["rigor"]); e != nil {
			return e
		}
		if e := validateBeginParticipation(p["participation"]); e != nil {
			return e
		}
	case "intervention_feedback":
		if !contracts.Is(p["class"], "reframe", "conflict", "weak_evidence", "missing_alternative", "completion_gap") || !contracts.Is(p["outcome"], "accepted", "dismissed") {
			return ErrControl
		}
	case "publish_framing":
		if !controlText(p["decision_question"], 500) {
			return ErrControl
		}
		a, ok := controlList(p["assumptions"], 3)
		if !ok {
			return ErrControl
		}
		for _, v := range a {
			m, e := contracts.Object(v, "text", "material")
			if e != nil || !controlText(m["text"], 500) {
				return ErrControl
			}
			if _, ok := m["material"].(bool); !ok {
				return ErrControl
			}
		}
		a, ok = controlList(p["decisive_evidence"], 3)
		if !ok {
			return ErrControl
		}
		for _, v := range a {
			if !controlText(v, 500) {
				return ErrControl
			}
		}
		a, ok = controlList(p["completion_criteria"], 8)
		if !ok || len(a) == 0 {
			return ErrControl
		}
		for _, v := range a {
			m, e := contracts.Object(v, "text", "required", "kind", "evidence_claim_ids")
			if e != nil || !controlText(m["text"], 400) || !controlIDs(m["evidence_claim_ids"], "C", 5) {
				return ErrControl
			}
			bound := map[string]any{"criterion_id": "K000001", "text": m["text"], "required": m["required"], "kind": m["kind"], "evidence_claim_ids": m["evidence_claim_ids"]}
			fr := map[string]any{"schema": "opensocrates.framing/1.0.0", "judgment_id": "J000001", "decision_question": p["decision_question"], "assumptions": p["assumptions"], "decisive_evidence": p["decisive_evidence"], "completion_criteria": []any{bound}}
			if e = contracts.Validate("framing", fr); e != nil {
				return ErrControl
			}
		}
	case "publish_claim":
		if !controlText(p["text"], 600) || !controlIDs(p["basis_claim_ids"], "C", 5) {
			return ErrControl
		}
		if (p["claim_ref"] == nil) != (p["expected_current_version"] == nil) {
			return ErrControl
		}
		if p["claim_ref"] != nil {
			n, ok := contracts.Integer(p["expected_current_version"])
			if !localID(p["claim_ref"], "C") || !ok || n.Sign() < 1 {
				return ErrControl
			}
		}
		refs, ok := controlList(p["source_refs"], 5)
		if !ok {
			return ErrControl
		}
		sources, ok := controlList(p["new_sources"], 5)
		if !ok {
			return ErrControl
		}
		for _, ref := range refs {
			if !controlReference(ref) {
				return ErrControl
			}
			m := ref.(map[string]any)
			if m["new_index"] != nil {
				n, _ := contracts.Int(m["new_index"])
				if n >= int64(len(sources)) {
					return ErrControl
				}
			}
		}
		for _, src := range sources {
			m, e := contracts.Object(src, "kind", "display_name", "uri", "safe_locator", "published_at", "checked_at", "content_hash")
			if e != nil || !controlText(m["display_name"], 200) {
				return ErrControl
			}
			bound := map[string]any{"schema": "opensocrates.source-reference/1.0.0", "source_id": "E000001"}
			for k, v := range m {
				bound[k] = v
			}
			if e = contracts.Validate("source-reference", bound); e != nil {
				return ErrControl
			}
		}
		if p["calculation"] != nil {
			calc, e := contracts.Object(p["calculation"], "schema", "expression", "operands", "result", "unit", "rounding")
			if e != nil {
				return ErrControl
			}
			ops, ok := controlList(calc["operands"], 16)
			if !ok || len(ops) == 0 {
				return ErrControl
			}
			seen := map[string]bool{}
			bound := map[string]any{}
			for k, v := range calc {
				bound[k] = v
			}
			arr := []any{}
			for _, raw := range ops {
				op, e := contracts.Object(raw, "name", "value", "unit", "source_ref")
				if e != nil || !controlText(op["name"], 128) || !controlText(op["value"], 128) || !controlText(op["unit"], 64) || seen[op["name"].(string)] {
					return ErrControl
				}
				seen[op["name"].(string)] = true
				if op["source_ref"] != nil && !controlReference(op["source_ref"]) {
					return ErrControl
				}
				arr = append(arr, map[string]any{"name": op["name"], "value": op["value"], "unit": op["unit"], "source_id": nil})
			}
			bound["operands"] = arr
			if e = contracts.Validate("calculation", bound); e != nil {
				return ErrControl
			}
		}
		if p["conflict"] != nil {
			if e := validateControlConflict(p["conflict"]); e != nil {
				return e
			}
		}
		claim := map[string]any{"schema": "opensocrates.claim-version/1.0.0", "claim_id": "C000001", "version": contracts.Number(1), "text": p["text"], "materiality": p["materiality"], "evidence_state": p["evidence_state"], "source_ids": []any{}, "basis_claim_ids": p["basis_claim_ids"], "calculation": nil, "conflict": p["conflict"], "active": true}
		if e := contracts.Validate("claim-version", claim); e != nil {
			return ErrControl
		}
	case "publish_conflict":
		if !controlIDs(p["affected_claim_ids"], "C", 5) {
			return ErrControl
		}
		return validateControlConflict(p["conflict"])
	case "publish_alternative":
		if !controlText(p["name"], 160) || !controlText(p["reason"], 400) || !controlIDs(p["material_claim_ids"], "C", 5) {
			return ErrControl
		}
		a := map[string]any{"schema": "opensocrates.alternative/1.0.0", "alternative_id": "A000001"}
		for k, v := range p {
			a[k] = v
		}
		if e := contracts.Validate("alternative", a); e != nil {
			return ErrControl
		}
	case "revise_judgment":
		if !controlText(p["conclusion"], 500) || !controlText(p["change_reason"], 500) || !controlIDs(p["ground_claim_ids"], "C", 5) || !controlIDs(p["uncertainty_claim_ids"], "C", 2) || !controlIDs(p["alternative_ids"], "A", 3) {
			return ErrControl
		}
		flips, ok := controlList(p["flip_conditions"], 2)
		if !ok {
			return ErrControl
		}
		for _, v := range flips {
			if _, e := contracts.Object(v, "schema", "condition", "affected_conclusion", "direction", "check"); e != nil {
				return ErrControl
			}
			if e := contracts.Validate("flip-condition", v); e != nil {
				return ErrControl
			}
		}
		if !contracts.Is(p["strength"], "held", "provisional", "supported", "strongly_supported") {
			return ErrControl
		}
	case "complete_cross_exam":
		if !controlText(p["findings_summary"], 1000) {
			return ErrControl
		}
		a, ok := controlList(p["affected_ids"], 12)
		if !ok {
			return ErrControl
		}
		for _, v := range a {
			if !controlText(v, 32) {
				return ErrControl
			}
		}
	case "hold_judgment":
		a, ok := controlList(p["missing_items"], 5)
		if !ok || len(a) == 0 {
			return ErrControl
		}
		for _, v := range a {
			if !controlText(v, 500) {
				return ErrControl
			}
		}
		if !contracts.Is(p["reason_code"], "evidence_missing", "evidence_conflict", "completion_criteria_unmet", "capability_missing", "verifier_unavailable", "verifier_failed", "method_unavailable", "record_unavailable", "runtime_error") {
			return ErrControl
		}
	case "cancel_judgment":
		if p["reason"] != "user_cancelled" {
			return ErrControl
		}
	default:
		return ErrControl
	}
	return nil
}
func validateControlConflict(v any) error {
	m, e := contracts.Object(v, "schema", "summary", "subject", "source_ids", "affected_claim_ids", "material", "resolution", "resolution_reason")
	if e != nil || !controlText(m["summary"], 600) || !controlText(m["subject"], 300) || !controlIDs(m["affected_claim_ids"], "C", 5) {
		return ErrControl
	}
	a, ok := controlList(m["source_ids"], 5)
	if !ok {
		return ErrControl
	}
	for _, v := range a {
		if !localID(v, "E") {
			return ErrControl
		}
	}
	if m["resolution_reason"] != nil && !controlText(m["resolution_reason"], 600) {
		return ErrControl
	}
	if e = contracts.Validate("conflict", v); e != nil {
		return ErrControl
	}
	return nil
}
func validateControlRigor(v any) error {
	m, ok := v.(map[string]any)
	if !ok {
		return ErrControl
	}
	levels := []string{"quiet", "together", "strict"}
	stored, ok := m["stored_rigor"].(string)
	if !ok {
		return ErrControl
	}
	base := stored
	if m["task_override"] != nil {
		base, ok = m["task_override"].(string)
		if !ok {
			return ErrControl
		}
	}
	floor, ok := m["risk_floor"].(string)
	if !ok || !Has(levels, stored) || !Has(levels, base) || !Has(levels, floor) {
		return ErrControl
	}
	ordinal := func(s string) int {
		for i, v := range levels {
			if s == v {
				return i
			}
		}
		return -1
	}
	effective := base
	if ordinal(floor) > ordinal(base) {
		effective = floor
	}
	if m["effective_rigor"] != effective || m["show_raise_notice"] != (ordinal(effective) > ordinal(base)) {
		return ErrControl
	}
	reasons := map[string][]string{"quiet": {"none"}, "together": {"ordinary_judgment", "externally_checkable_material_claims"}, "strict": {"material_consequence", "irreversible_commitment", "explicit_user_strict"}}
	if !contracts.Is(m["risk_reason"], reasons[floor]...) {
		return ErrControl
	}
	return nil
}
func LegalControlTransition(kind, state string) bool {
	if kind == "intervention_feedback" {
		return true
	}
	allowed := map[string][]string{"begin_judgment": {"new"}, "publish_framing": {"framing"}, "publish_claim": {"framing", "working", "rejudging"}, "publish_conflict": {"working", "rejudging"}, "publish_alternative": {"framing", "working", "rejudging"}, "revise_judgment": {"working", "rejudging"}, "complete_cross_exam": {"cross_examining"}, "hold_judgment": {"framing", "working", "rejudging", "cross_examining", "verifying", "degraded"}, "cancel_judgment": {"framing", "working", "rejudging", "cross_examining", "verifying", "degraded"}}
	return Has(allowed[kind], state)
}
func NextControlState(kind, state string) (string, error) {
	if !LegalControlTransition(kind, state) {
		return "", errors.New("invalid_state_transition")
	}
	next := map[string]string{"publish_framing": "working", "publish_conflict": "rejudging", "revise_judgment": "cross_examining", "complete_cross_exam": "verifying", "hold_judgment": "insufficient", "cancel_judgment": "cancelled"}
	if n, ok := next[kind]; ok {
		return n, nil
	}
	return state, nil
}
func TokenTag(raw string, key []byte) (string, error) {
	if !tokenPattern.MatchString(raw) || len(key) != 32 {
		return "", errors.New("invalid_token")
	}
	msg := append([]byte("turn-token\x00"), make([]byte, 4)...)
	binary.BigEndian.PutUint32(msg[len(msg)-4:], uint32(len(raw)))
	msg = append(msg, []byte(raw)...)
	return hmacTag(msg, key), nil
}
func PayloadTag(value map[string]any, key []byte) (string, error) {
	if len(key) != 32 {
		return "", ErrControl
	}
	b, e := contracts.CanonicalJSON(value)
	if e != nil {
		return "", e
	}
	return hmacTag(append([]byte("control-payload\x00"), b...), key), nil
}
func ObservationTag(stable, category string, key []byte) (string, error) {
	if stable == "" || category == "" || len(key) != 32 {
		return "", ErrControl
	}
	return hmacTag([]byte("observation\x00"+category+"\x00"+stable), key), nil
}
func hmacTag(b, key []byte) string {
	m := hmac.New(sha256.New, key)
	m.Write(b)
	return "sha256:" + hex.EncodeToString(m.Sum(nil))
}
func ExpiryFor(issued string) (string, error) {
	t, e := time.Parse(TimestampFormat, issued)
	if e != nil || t.UTC().Format(TimestampFormat) != issued {
		return "", ErrControl
	}
	return t.Add(6 * time.Hour).UTC().Format(TimestampFormat), nil
}
func ValidateTurnState(m map[string]any) error {
	if e := contracts.Validate("ephemeral-turn-state", m); e != nil {
		return ErrControl
	}
	issued, ok := m["issued_at"].(string)
	if !ok {
		return ErrControl
	}
	expires, ok := m["expires_at"].(string)
	if !ok {
		return ErrControl
	}
	a, e := time.Parse(TimestampFormat, issued)
	if e != nil || a.UTC().Format(TimestampFormat) != issued {
		return ErrControl
	}
	b, e := time.Parse(TimestampFormat, expires)
	if e != nil || b.UTC().Format(TimestampFormat) != expires || !b.After(a) || b.Sub(a) > 6*time.Hour {
		return ErrControl
	}
	accepted, ok := m["accepted_controls"].([]any)
	if !ok || len(accepted) > MaxAcceptedControls {
		return ErrCapacity
	}
	observations, ok := m["observation_tags"].([]any)
	if !ok || len(observations) > MaxObservationTags {
		return ErrCapacity
	}
	seen := map[string]bool{}
	for _, v := range observations {
		s, ok := v.(string)
		if !ok || !tagPattern.MatchString(s) || seen[s] {
			return ErrControl
		}
		seen[s] = true
	}
	seen = map[string]bool{}
	for _, v := range accepted {
		a, ok := v.(map[string]any)
		if !ok {
			return ErrControl
		}
		id, ok := a["message_id"].(string)
		tag, tagOK := a["payload_tag"].(string)
		if !ok || !tagOK || !tagPattern.MatchString(tag) || seen[id] {
			return ErrControl
		}
		seen[id] = true
		if e := validateCachedControlResult(a["result"]); e != nil {
			return e
		}
	}
	repair, ok := contracts.Int(m["repair_count"])
	if !ok || repair < 0 || repair > 1 {
		return ErrControl
	}
	return nil
}
func RequireActiveTurn(m map[string]any, now time.Time) error {
	if e := ValidateTurnState(m); e != nil {
		return e
	}
	expires, _ := time.Parse(TimestampFormat, m["expires_at"].(string))
	if !now.Before(expires) {
		return ErrExpiredTurn
	}
	return nil
}
func AcceptedControl(m map[string]any, id string) map[string]any {
	a, _ := m["accepted_controls"].([]any)
	for _, v := range a {
		entry, _ := v.(map[string]any)
		if entry["message_id"] == id {
			return entry
		}
	}
	return nil
}
func AppendAcceptedControl(m map[string]any, id, tag string, result ControlResult) error {
	if AcceptedControl(m, id) != nil {
		return ErrControl
	}
	a, _ := m["accepted_controls"].([]any)
	if len(a) >= MaxAcceptedControls {
		return ErrCapacity
	}
	r, e := Normalize(result)
	if e != nil {
		return e
	}
	m["accepted_controls"] = append(a, map[string]any{"message_id": id, "payload_tag": tag, "result": r})
	return ValidateTurnState(m)
}
func AppendObservationTag(m map[string]any, tag string) error {
	if !tagPattern.MatchString(tag) {
		return ErrControl
	}
	a, _ := m["observation_tags"].([]any)
	for _, v := range a {
		if v == tag {
			return nil
		}
	}
	if len(a) >= MaxObservationTags {
		return ErrCapacity
	}
	m["observation_tags"] = append(a, tag)
	return ValidateTurnState(m)
}

// ValidateRecord closes the generic schema's payload union before any public
// event reaches persistence; unknown fields cannot masquerade as public data.
func ValidateRecord(event map[string]any) error {
	if e := contracts.Validate("judgment-event", event); e != nil {
		return e
	}
	if e := GuardControlTree(event, 0); e != nil {
		return e
	}
	seq, ok := contracts.Int(event["sequence"])
	if !ok || seq < 1 || !contracts.Is(event["locale"], "en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th") {
		return ErrControl
	}
	t, ok := event["occurred_at"].(string)
	if !ok {
		return ErrControl
	}
	if _, e := ExpiryFor(t); e != nil {
		return e
	}
	p, ok := event["payload"].(map[string]any)
	if !ok {
		return ErrControl
	}
	kind, _ := event["event_type"].(string)
	keys := map[string][]string{
		"task_started": {"requested_rigor", "effective_rigor", "capability_gaps", "participation_reason", "host_session_key"}, "framing_published": {"framing"}, "claim_published": {"claim_version"}, "source_published": {"source_reference"}, "conflict_published": {"conflict", "affected_claim_ids"}, "alternative_published": {"alternative"}, "conclusion_published": {"judgment_version"}, "completion_checked": {"completion_result"}, "method_selected": {"primary_method", "secondary_method", "selection_source"}, "method_activated": {"method_id", "activation_source", "turn_tag"}, "judgment_started": {"judgment_id", "version"}, "observation_check_requested": {"tool_category", "dedupe_fingerprint"}, "intervention_published": {"class", "summary", "action", "fingerprint"}, "conflict_resolved": {"resolution", "public_reason"}, "cross_exam_completed": {"findings_summary", "affected_ids"}, "repair_requested": {"rule_ids", "repair_count"}, "verification_failed": {"rule_ids", "reason"}, "capability_degraded": {"capability_key", "limitation_key"}, "task_concluded": {"terminal_reason", "current_judgment_version"}, "task_insufficient": {"terminal_reason", "missing_items"}, "task_cancelled": {"reason"}, "recovered_from_torn_tail": {"source_record_safe_identifier", "complete_line_count"},
	}
	allowed, exists := keys[kind]
	if !exists {
		return ErrControl
	}
	if _, e := contracts.Object(p, allowed...); e != nil {
		return e
	}
	model := map[string][2]string{"framing_published": {"framing", "framing"}, "claim_published": {"claim_version", "claim-version"}, "source_published": {"source_reference", "source-reference"}, "conflict_published": {"conflict", "conflict"}, "alternative_published": {"alternative", "alternative"}, "completion_checked": {"completion_result", "completion-result"}}
	if spec, ok := model[kind]; ok {
		if e := contracts.Validate(spec[1], p[spec[0]]); e != nil {
			return e
		}
		if e := semanticRecordModel(spec[1], p[spec[0]]); e != nil {
			return e
		}
	}
	switch kind {
	case "conclusion_published":
		if e := validateJudgmentRecord(p["judgment_version"]); e != nil {
			return e
		}
	case "task_started":
		if !contracts.Is(p["requested_rigor"], "quiet", "together", "strict") || !contracts.Is(p["effective_rigor"], "quiet", "together", "strict") {
			return ErrControl
		}
		gaps, ok := controlList(p["capability_gaps"], 8)
		if !ok {
			return ErrControl
		}
		last := ""
		for _, v := range gaps {
			if !recordText(v, 128) || v.(string) <= last {
				return ErrControl
			}
			last = v.(string)
		}
		if s, ok := p["host_session_key"].(string); !ok || !tagPattern.MatchString(s) {
			return ErrControl
		}
	case "judgment_started":
		if !localID(p["judgment_id"], "J") {
			return ErrControl
		}
		n, ok := contracts.Int(p["version"])
		if !ok || n < 1 {
			return ErrControl
		}
	case "method_selected":
		if !recordText(p["selection_source"], 64) {
			return ErrControl
		}
		s, ok := p["primary_method"].(string)
		if !ok || !MethodID(s) {
			return ErrControl
		}
		if p["secondary_method"] != nil {
			other, ok := p["secondary_method"].(string)
			if !ok || !MethodID(other) || other == s {
				return ErrControl
			}
		}
	case "conflict_published":
		if !controlIDs(p["affected_claim_ids"], "C", 5) {
			return ErrControl
		}
	case "method_activated":
		id, ok := p["method_id"].(string)
		if !ok || !MethodID(id) || !contracts.Is(p["activation_source"], "automatic", "explicit") || !recordTag(p["turn_tag"]) {
			return ErrControl
		}
	case "observation_check_requested":
		if !contracts.Is(p["tool_category"], "retrieval", "read", "search", "calculation", "write", "format", "execution", "navigation", "other") || !recordTag(p["dedupe_fingerprint"]) {
			return ErrControl
		}
	case "intervention_published":
		if !contracts.Is(p["class"], InterventionClasses...) || !recordText(p["summary"], 500) || !recordText(p["action"], 128) || !recordTag(p["fingerprint"]) {
			return ErrControl
		}
	case "conflict_resolved":
		if !contracts.Is(p["resolution"], "unresolved", "source_precedence", "recency", "measurement_definition", "calculation_correction", "scope_split", "user_decision") || !recordText(p["public_reason"], 600) {
			return ErrControl
		}
	case "cross_exam_completed":
		if !recordText(p["findings_summary"], 1000) {
			return ErrControl
		}
		items, ok := controlList(p["affected_ids"], 12)
		if !ok {
			return ErrControl
		}
		for _, v := range items {
			if !recordText(v, 32) {
				return ErrControl
			}
		}
	case "repair_requested", "verification_failed":
		items, ok := controlList(p["rule_ids"], 16)
		if !ok {
			return ErrControl
		}
		last := ""
		for _, v := range items {
			if !recordText(v, 64) {
				return ErrControl
			}
			if kind == "repair_requested" && v.(string) <= last {
				return ErrControl
			}
			last = v.(string)
		}
		if kind == "repair_requested" {
			n, ok := contracts.Int(p["repair_count"])
			if len(items) == 0 || !ok || n != 1 {
				return ErrControl
			}
		} else if !recordText(p["reason"], 500) {
			return ErrControl
		}
	case "capability_degraded":
		if !recordText(p["capability_key"], 128) || !recordText(p["limitation_key"], 128) {
			return ErrControl
		}
	case "task_concluded":
		if !contracts.Is(p["terminal_reason"], terminalRecordReasons...) {
			return ErrControl
		}
		if p["current_judgment_version"] != nil {
			n, ok := contracts.Integer(p["current_judgment_version"])
			if !ok || n.Sign() < 1 {
				return ErrControl
			}
		}
	case "recovered_from_torn_tail":
		if !recordText(p["source_record_safe_identifier"], 128) || !contracts.Nonnegative(p["complete_line_count"]) {
			return ErrControl
		}
	case "task_cancelled":
		if p["reason"] != "user_cancelled" {
			return ErrControl
		}
	case "task_insufficient":
		if !contracts.Is(p["terminal_reason"], terminalRecordReasons...) {
			return ErrControl
		}
		a, ok := controlList(p["missing_items"], 5)
		if !ok || len(a) == 0 {
			return ErrControl
		}
		for _, v := range a {
			if !recordText(v, 500) {
				return ErrControl
			}
		}
	}
	return nil
}

func validateJudgmentRecord(v any) error {
	m, e := contracts.Object(v, "judgment_id", "version", "state", "conclusion", "strength", "supersedes_version", "change_reason", "ground_claim_ids", "uncertainty_claim_ids", "flip_conditions", "alternative_ids")
	if e != nil || !localID(m["judgment_id"], "J") || !contracts.Is(m["state"], "identified", "active", "revised", "cross_examined", "verified", "published", "held", "superseded", "abandoned", "verification_failed") || !contracts.Is(m["strength"], "held", "provisional", "supported", "strongly_supported") {
		return ErrControl
	}
	n, ok := contracts.Int(m["version"])
	if !ok || n < 1 {
		return ErrControl
	}
	if n == 1 && m["supersedes_version"] != nil {
		return ErrControl
	}
	if n > 1 {
		previous, ok := contracts.Int(m["supersedes_version"])
		if !ok || previous != n-1 || !recordSingleLine(m["change_reason"], 500) {
			return ErrControl
		}
	}
	if m["conclusion"] != nil && !recordSingleLine(m["conclusion"], 500) {
		return ErrControl
	}
	if m["change_reason"] != nil && !recordSingleLine(m["change_reason"], 500) {
		return ErrControl
	}
	if m["supersedes_version"] != nil {
		n, ok := contracts.Int(m["supersedes_version"])
		if !ok || n < 1 {
			return ErrControl
		}
	}
	if !controlIDs(m["ground_claim_ids"], "C", 5) || !controlIDs(m["uncertainty_claim_ids"], "C", 2) || !controlIDs(m["alternative_ids"], "A", 3) {
		return ErrControl
	}
	flips, ok := controlList(m["flip_conditions"], 2)
	if !ok {
		return ErrControl
	}
	for _, v := range flips {
		if e = contracts.Validate("flip-condition", v); e != nil {
			return ErrControl
		}
	}
	return nil
}

func validateBeginParticipation(v any) error {
	m, ok := v.(map[string]any)
	if !ok {
		return ErrControl
	}
	j, ok := controlList(m["judgment_targets"], 3)
	if !ok {
		return ErrControl
	}
	mechanical, ok := controlList(m["mechanical_targets"], 3)
	if !ok {
		return ErrControl
	}
	if m["participation"] == "mechanical" && len(j) > 0 {
		return ErrControl
	}
	for _, v := range append(append([]any{}, j...), mechanical...) {
		if !controlText(v, 120) || strings.ContainsAny(v.(string), "\n\t") {
			return ErrControl
		}
	}
	return nil
}

func recordSingleLine(v any, max int) bool {
	s, ok := v.(string)
	return ok && controlText(s, max) && !strings.ContainsAny(s, "\n\t")
}
func semanticRecordModel(name string, v any) error {
	m, ok := v.(map[string]any)
	if !ok {
		return ErrControl
	}
	switch name {
	case "claim-version":
		if !localID(m["claim_id"], "C") || !recordSingleLine(m["text"], 600) {
			return ErrControl
		}
		version, ok := contracts.Integer(m["version"])
		if !ok || version.Sign() < 1 {
			return ErrControl
		}
		sources, _ := m["source_ids"].([]any)
		basis, _ := m["basis_claim_ids"].([]any)
		if !controlIDs(m["source_ids"], "E", 128) || !controlIDs(m["basis_claim_ids"], "C", 128) {
			return ErrControl
		}
		switch m["evidence_state"] {
		case "verified":
			if len(sources) == 0 {
				return ErrControl
			}
		case "computed":
			if m["calculation"] == nil {
				return ErrControl
			}
		case "inferred":
			if len(basis) == 0 {
				return ErrControl
			}
		case "assumed":
			if len(sources) > 0 || len(basis) > 0 || m["calculation"] != nil {
				return ErrControl
			}
		case "conflicted":
			if m["conflict"] == nil || len(sources) < 2 && len(basis) == 0 && m["calculation"] == nil {
				return ErrControl
			}
		}
		if m["conflict"] != nil {
			return semanticRecordModel("conflict", m["conflict"])
		}
	case "source-reference":
		if !localID(m["source_id"], "E") || !recordSingleLine(m["display_name"], 200) {
			return ErrControl
		}
		if m["uri"] != nil {
			uri, ok := m["uri"].(string)
			if !ok || !validRecordURI(uri) {
				return ErrControl
			}
		}
		if m["safe_locator"] != nil {
			if !recordSingleLine(m["safe_locator"], 200) || strings.ContainsAny(m["safe_locator"].(string), "/\\") {
				return ErrControl
			}
		}
		checked, ok := m["checked_at"].(string)
		if !ok {
			return ErrControl
		}
		if _, e := ExpiryFor(checked); e != nil {
			return e
		}
		if m["published_at"] != nil {
			date, ok := m["published_at"].(string)
			if !ok {
				return ErrControl
			}
			t, e := time.Parse("2006-01-02", date)
			if e != nil || t.Format("2006-01-02") != date {
				return ErrControl
			}
		}
	case "conflict":
		if !recordSingleLine(m["summary"], 600) || !recordSingleLine(m["subject"], 300) {
			return ErrControl
		}
		sources, _ := m["source_ids"].([]any)
		claims, _ := m["affected_claim_ids"].([]any)
		if len(sources) < 2 && len(claims) == 0 {
			return ErrControl
		}
		if m["resolution"] == "unresolved" {
			if m["resolution_reason"] != nil {
				return ErrControl
			}
		} else if !recordSingleLine(m["resolution_reason"], 600) {
			return ErrControl
		}
		for _, v := range sources {
			if !localID(v, "E") {
				return ErrControl
			}
		}
		for _, v := range claims {
			if !localID(v, "C") {
				return ErrControl
			}
		}
	case "framing":
		if !localID(m["judgment_id"], "J") || !recordSingleLine(m["decision_question"], 500) {
			return ErrControl
		}
		assumptions, ok := controlList(m["assumptions"], 3)
		if !ok {
			return ErrControl
		}
		for _, v := range assumptions {
			a, _ := v.(map[string]any)
			if !recordSingleLine(a["text"], 500) {
				return ErrControl
			}
		}
		evidence, ok := controlList(m["decisive_evidence"], 3)
		if !ok {
			return ErrControl
		}
		for _, v := range evidence {
			if !controlText(v, 4096) {
				return ErrControl
			}
		}
		criteria, ok := controlList(m["completion_criteria"], 8)
		if !ok || len(criteria) == 0 {
			return ErrControl
		}
		seen := map[string]bool{}
		for _, v := range criteria {
			c, _ := v.(map[string]any)
			id, ok := c["criterion_id"].(string)
			if !ok || !localID(id, "K") || seen[id] || !recordSingleLine(c["text"], 400) {
				return ErrControl
			}
			seen[id] = true
		}
	case "alternative":
		if !localID(m["alternative_id"], "A") || !recordSingleLine(m["name"], 160) || !recordSingleLine(m["reason"], 400) || !controlIDs(m["material_claim_ids"], "C", 128) {
			return ErrControl
		}
	}
	return nil
}

func validRecordURI(raw string) bool {
	u, e := url.Parse(raw)
	if e != nil || u.User != nil || u.Host == "" {
		return false
	}
	scheme := strings.ToLower(u.Scheme)
	if scheme != "https" && scheme != "http" {
		return false
	}
	if scheme == "http" && !Has([]string{"localhost", "127.0.0.1", "::1"}, strings.ToLower(u.Hostname())) {
		return false
	}
	for key := range u.Query() {
		if Has([]string{"token", "key", "secret", "signature", "sig", "auth", "code", "session"}, strings.ToLower(key)) {
			return false
		}
	}
	return true
}

var terminalRecordReasons = strings.Fields("mechanical criteria_satisfied user_cancelled evidence_missing evidence_conflict completion_criteria_unmet capability_missing verifier_unavailable verifier_failed method_unavailable record_unavailable runtime_error")

func recordTag(v any) bool { s, ok := v.(string); return ok && tagPattern.MatchString(s) }

func recordText(v any, max int) bool {
	s, ok := v.(string)
	return ok && canonicalText(s) && utf8.RuneCountInString(s) <= max
}
func ValidateControlConflictModel(v any) error {
	if e := contracts.Validate("conflict", v); e != nil {
		return e
	}
	return semanticRecordModel("conflict", v)
}
func validateCachedControlResult(v any) error {
	r, ok := v.(map[string]any)
	if !ok || contracts.Validate("host-control-result", r) != nil {
		return ErrControl
	}
	ids := r["assigned_ids"].(map[string]any)
	if r["status"] == "rejected" {
		if r["error_code"] == nil || r["durable_mutation"] == true || ids["task_id"] != nil || ids["judgment_id"] != nil {
			return ErrControl
		}
		for _, key := range []string{"claim_ids", "source_ids", "criterion_ids", "alternative_ids"} {
			if len(ids[key].([]any)) > 0 {
				return ErrControl
			}
		}
	} else if r["error_code"] != nil {
		return ErrControl
	}
	seen := map[string]bool{}
	for _, v := range r["capability_limitations"].([]any) {
		s := v.(string)
		if seen[s] {
			return ErrControl
		}
		seen[s] = true
	}
	return nil
}
