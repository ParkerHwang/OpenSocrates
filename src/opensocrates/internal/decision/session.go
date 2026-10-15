// Package decision owns a volatile, catalog-bounded content delivery session.
package decision

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"regexp"
	"strconv"
	"strings"
	"sync"
)

type Session struct {
	bundle    *content.Bundle
	mu        sync.Mutex
	context   string
	epoch     string
	lastKey   string
	lastRoute domain.Route
	delivered map[string]string
	available map[string]bool
}

func New(bundle *content.Bundle) *Session { s := &Session{bundle: bundle}; s.reset(); return s }
func Failure(reason string) map[string]any {
	return map[string]any{"status": "unavailable", "reason": reason, "applied": "unverified", "continue_ordinary_work": true, "constraints_remain_binding": true}
}
func (s *Session) reset() {
	s.context = ""
	s.epoch = ""
	s.lastKey = ""
	s.lastRoute = domain.Route{Selected: []string{}, Reason: "no_eligible_method"}
	s.delivered = map[string]string{}
	s.available = map[string]bool{}
}

var contextRE = regexp.MustCompile(`^[0-9a-f]{32}$`)
var decisionRE = regexp.MustCompile(`^[A-Za-z0-9]{1,64}$`)

// Repair responses contain closed schema paths and static guidance only. Never
// echo submitted values, unknown field names or validator error text.
var requestExpected = map[string]string{
	"request":                           "one JSON object with exactly the documented keys for its operation",
	"operation":                         "one of catalog, select, acknowledge, reset",
	"context":                           "32 lowercase hexadecimal characters [0-9a-f]",
	"epoch":                             "integer >= 0, never lower than the previous epoch for this context",
	"decision":                          "1-64 ASCII letters or digits, no hyphen, underscore or space",
	"revision":                          "integer >= 0",
	"locale":                            "one of en, ko, zh, ja, fr, de, it, es, pt, th",
	"participation":                     "one of judgment, mixed, mechanical",
	"routing.schema":                    "opensocrates.routing-features/1.0.0",
	"routing.answer_shape":              "a value from features.json answer_shapes",
	"routing.classification_confidence": "one of high, medium, low",
	"routing.explicit_method":           "null, or a catalog method ID the user requested",
	"routing.features":                  "a list of at most 16 entries with key, strength and basis",
	"key":                               "a value from features.json features, used once",
	"strength":                          "integer 1, 2 or 3",
	"basis":                             "a value from features.json basis",
}

// InvalidJSONRequest reports only a closed category. Decoder error strings and
// submitted bytes must never enter the public response.
func InvalidJSONRequest() map[string]any { return requestFault("request", "invalid_json") }

func requestFault(field, code string) map[string]any {
	result := Failure("invalid_decision_request")
	result["field"], result["error"], result["repair"] = field, code, "correct_field_once"
	expected := requestExpected[field]
	if expected == "" {
		expected = requestExpected[field[strings.LastIndex(field, ".")+1:]]
	}
	if expected != "" {
		result["expected"] = expected
	}
	return result
}

func closedRequestFields(m map[string]any, at string, keys ...string) map[string]any {
	for _, key := range keys {
		if _, exists := m[key]; !exists {
			field := key
			if at != "request" {
				field = at + "." + key
			}
			return requestFault(field, "missing_field")
		}
	}
	if len(m) != len(keys) {
		return requestFault(at, "unknown_field")
	}
	return nil
}

// The domain parser remains the authority for feature/basis membership. These
// bounded probes run only while diagnosing a rejected routing object, so the
// session does not maintain a second copy of either closed vocabulary.
func routingEntryAccepted(key, basis any) bool {
	_, err := domain.ParseRouting(map[string]any{
		"schema": "opensocrates.routing-features/1.0.0", "answer_shape": "direct_judgment",
		"classification_confidence": "high", "explicit_method": nil,
		"features": []any{map[string]any{"key": key, "strength": contracts.Number(1), "basis": basis}},
	})
	return err == nil
}

func routingRequestFault(value any) map[string]any {
	m, ok := value.(map[string]any)
	if !ok {
		return requestFault("routing", "invalid_type")
	}
	// Python #130 sorts missing routing/entry keys; select envelope keys use
	// their documented order instead.
	if fault := closedRequestFields(m, "routing", "answer_shape", "classification_confidence", "explicit_method", "features", "schema"); fault != nil {
		return fault
	}
	if !contracts.Is(m["schema"], "opensocrates.routing-features/1.0.0") {
		return requestFault("routing.schema", "invalid_value")
	}
	if !contracts.Is(m["answer_shape"], domain.Shapes...) {
		return requestFault("routing.answer_shape", "invalid_value")
	}
	if !contracts.Is(m["classification_confidence"], "high", "medium", "low") {
		return requestFault("routing.classification_confidence", "invalid_value")
	}
	explicit, text := m["explicit_method"].(string)
	if m["explicit_method"] != nil && !text {
		return requestFault("routing.explicit_method", "invalid_type")
	}
	list, ok := m["features"].([]any)
	if !ok {
		return requestFault("routing.features", "invalid_type")
	}
	if len(list) > 16 {
		return requestFault("routing.features", "too_many_features")
	}
	seen := map[string]bool{}
	var listFault map[string]any
	for i, raw := range list {
		at := "routing.features[" + strconv.Itoa(i) + "]"
		item, ok := raw.(map[string]any)
		if !ok {
			return requestFault(at, "invalid_type")
		}
		if fault := closedRequestFields(item, at, "basis", "key", "strength"); fault != nil {
			return fault
		}
		if !routingEntryAccepted(item["key"], "task_shape") {
			if listFault == nil {
				listFault = requestFault(at+".key", "unknown_feature")
			}
			continue
		}
		if !routingEntryAccepted(item["key"], item["basis"]) {
			return requestFault(at+".basis", "invalid_value")
		}
		strength, integer := contracts.Integer(item["strength"])
		if !integer {
			return requestFault(at+".strength", "invalid_type")
		}
		if !strength.IsInt64() || strength.Int64() < 1 || strength.Int64() > 3 {
			return requestFault(at+".strength", "invalid_value")
		}
		key := item["key"].(string)
		if seen[key] {
			if listFault == nil {
				listFault = requestFault(at+".key", "duplicate_feature")
			}
			continue
		}
		seen[key] = true
	}
	if text && !domain.MethodID(explicit) {
		return requestFault("routing.explicit_method", "invalid_format")
	}
	if listFault != nil {
		return listFault
	}
	return requestFault("routing", "invalid_value")
}

func (s *Session) Handle(value any) map[string]any {
	if !s.mu.TryLock() {
		return Failure("recursive_request")
	}
	defer s.mu.Unlock()
	m, ok := value.(map[string]any)
	if !ok {
		return requestFault("request", "invalid_type")
	}
	switch m["operation"] {
	case "reset":
		if _, e := contracts.Object(value, "operation"); e != nil {
			return requestFault("request", "unknown_field")
		}
		s.reset()
		return map[string]any{"status": "reset", "context_eviction": false}
	case "catalog":
		if fault := closedRequestFields(m, "request", "operation", "locale"); fault != nil {
			return fault
		}
		if !contracts.Is(m["locale"], "en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th") {
			return requestFault("locale", "invalid_value")
		}
		locale := m["locale"].(string)
		methods := []any{}
		for _, method := range s.bundle.Methods {
			methods = append(methods, map[string]any{"id": method.ID, "use_for": method.PlainAction[locale], "routing": method.Routing})
		}
		return map[string]any{"status": "catalog", "content_revision": s.bundle.Revision, "methods": methods, "evidence": "metadata_only"}
	case "acknowledge":
		if fault := closedRequestFields(m, "request", "operation", "context", "epoch", "digests"); fault != nil {
			return fault
		}
		epoch, ok := contracts.Integer(m["epoch"])
		if !ok {
			return requestFault("epoch", "invalid_type")
		}
		if s.epoch == "" || m["context"] != s.context {
			return requestFault("context", "invalid_value")
		}
		if epoch.String() != s.epoch {
			return requestFault("epoch", "invalid_value")
		}
		digests, ok := m["digests"].([]any)
		if !ok || len(digests) > len(s.bundle.Methods) {
			return requestFault("digests", "invalid_type")
		}
		allowed := map[string]bool{}
		for _, v := range s.delivered {
			allowed[v] = true
		}
		for _, d := range digests {
			digest, ok := d.(string)
			if !ok || !allowed[digest] {
				return requestFault("digests", "invalid_value")
			}
		}
		for identity, digest := range s.delivered {
			for _, d := range digests {
				if d == digest {
					s.available[identity+":"+digest] = true
				}
			}
		}
		return map[string]any{"status": "acknowledged", "available": "agent_reported", "read": "agent_reported", "applied": "unverified"}
	case "select":
		return s.selectMethods(m)
	}
	if _, exists := m["operation"]; !exists {
		return requestFault("operation", "missing_field")
	}
	return requestFault("operation", "unknown_operation")
}
func (s *Session) selectMethods(m map[string]any) map[string]any {
	if fault := closedRequestFields(m, "request", "operation", "context", "epoch", "decision", "revision", "locale", "participation", "routing"); fault != nil {
		return fault
	}
	context, ok := m["context"].(string)
	if !ok {
		return requestFault("context", "invalid_type")
	}
	if !contextRE.MatchString(context) {
		return requestFault("context", "invalid_format")
	}
	epoch, integer := contracts.Integer(m["epoch"])
	if !integer {
		return requestFault("epoch", "invalid_type")
	}
	if epoch.Sign() < 0 {
		return requestFault("epoch", "invalid_value")
	}
	if s.context == context && s.epoch != "" {
		old, _ := contracts.Integer(contracts.Number(0))
		old.SetString(s.epoch, 10)
		if epoch.Cmp(old) < 0 {
			return requestFault("epoch", "stale_epoch")
		}
	}
	id, text := m["decision"].(string)
	if !text {
		return requestFault("decision", "invalid_type")
	}
	if !decisionRE.MatchString(id) {
		return requestFault("decision", "invalid_format")
	}
	revision, integer := contracts.Integer(m["revision"])
	if !integer {
		return requestFault("revision", "invalid_type")
	}
	if revision.Sign() < 0 {
		return requestFault("revision", "invalid_value")
	}
	if !contracts.Is(m["locale"], "en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th") {
		return requestFault("locale", "invalid_value")
	}
	if !contracts.Is(m["participation"], "mechanical", "judgment", "mixed") {
		return requestFault("participation", "invalid_value")
	}
	features, e := domain.ParseRouting(m["routing"])
	if e != nil {
		return routingRequestFault(m["routing"])
	}
	if features.ExplicitMethod != nil && !s.bundle.Known(*features.ExplicitMethod) {
		return Failure("unknown_method")
	}
	raw, e := contracts.CanonicalCompact(m)
	if e != nil {
		return Failure("decision_unavailable")
	}
	// Commit a new context only after every request field has been validated.
	// The prior runtime cleared availability before checking routing and participation.
	if s.context != context || s.epoch != epoch.String() {
		s.reset()
		s.context = context
		s.epoch = epoch.String()
	}
	key := content.Hash(raw)
	reused := key == s.lastKey
	route := s.lastRoute
	if !reused {
		route = domain.RouteFeatures(m["participation"].(string), features, s.bundle.Methods)
	}
	locale := m["locale"].(string)
	methods := []any{}
	for _, id := range route.Selected {
		instructions, e := s.bundle.Assemble([]string{id}, locale)
		if e != nil {
			return Failure("canonical_content_unavailable")
		}
		digest := content.Hash([]byte(instructions))
		identity := id + ":" + locale + ":" + contracts.Number(int64(s.bundle.Revision)).String()
		old := s.delivered[identity]
		if old != "" && old != digest {
			delete(s.available, identity+":"+old)
		}
		retained := s.available[identity+":"+digest]
		s.delivered[identity] = digest
		delivery, read := "emitted", "unverified"
		var body any = instructions
		if retained {
			delivery, read = "reused_agent_reported_available", "agent_reported"
			body = nil
		}
		methods = append(methods, map[string]any{"id": id, "locale": locale, "content_revision": s.bundle.Revision, "sha256": digest, "delivery": delivery, "read": read, "instructions": body})
	}
	s.lastKey, s.lastRoute = key, route
	status := "selected"
	var footer any = "Powered by OpenSocrates"
	if len(route.Selected) == 0 {
		status = "no_intervention"
		footer = nil
	}
	var presentation any
	if m["participation"] != "mechanical" {
		presentation = s.bundle.Guidance(locale, features.AnswerShape)
	}
	return map[string]any{"status": status, "selected": route.Selected, "reason": route.Reason, "content_revision": s.bundle.Revision, "methods": methods, "selection_reused": reused, "selector_model_calls": 0, "presentation": presentation, "scope": map[string]any{"context": context, "epoch": m["epoch"]}, "applied": "unverified", "audit_if_applied": footer, "context_eviction": false}
}
