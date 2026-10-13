// Package decision owns a volatile, catalog-bounded content delivery session.
package decision

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"regexp"
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

func (s *Session) Handle(value any) map[string]any {
	if !s.mu.TryLock() {
		return Failure("recursive_request")
	}
	defer s.mu.Unlock()
	m, ok := value.(map[string]any)
	if !ok {
		return Failure("invalid_decision_request")
	}
	switch m["operation"] {
	case "reset":
		if _, e := contracts.Object(value, "operation"); e != nil {
			return Failure("invalid_decision_request")
		}
		s.reset()
		return map[string]any{"status": "reset", "context_eviction": false}
	case "catalog":
		if _, e := contracts.Object(value, "operation", "locale"); e != nil || !contracts.Is(m["locale"], "en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th") {
			return Failure("invalid_decision_request")
		}
		locale := m["locale"].(string)
		methods := []any{}
		for _, method := range s.bundle.Methods {
			methods = append(methods, map[string]any{"id": method.ID, "use_for": method.PlainAction[locale], "routing": method.Routing})
		}
		return map[string]any{"status": "catalog", "content_revision": s.bundle.Revision, "methods": methods, "evidence": "metadata_only"}
	case "acknowledge":
		if _, e := contracts.Object(value, "operation", "context", "epoch", "digests"); e != nil {
			return Failure("invalid_decision_request")
		}
		epoch, ok := contracts.Integer(m["epoch"])
		if !ok || m["context"] != s.context || epoch.String() != s.epoch {
			return Failure("invalid_decision_request")
		}
		digests, ok := m["digests"].([]any)
		if !ok || len(digests) > len(s.bundle.Methods) {
			return Failure("invalid_decision_request")
		}
		allowed := map[string]bool{}
		for _, v := range s.delivered {
			allowed[v] = true
		}
		for _, d := range digests {
			digest, ok := d.(string)
			if !ok || !allowed[digest] {
				return Failure("invalid_decision_request")
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
	return Failure("invalid_decision_request")
}
func (s *Session) selectMethods(m map[string]any) map[string]any {
	if _, e := contracts.Object(m, "operation", "context", "epoch", "decision", "revision", "locale", "participation", "routing"); e != nil {
		return Failure("invalid_decision_request")
	}
	context, ok := m["context"].(string)
	epoch, integer := contracts.Integer(m["epoch"])
	id, text := m["decision"].(string)
	if !ok || !contextRE.MatchString(context) || !integer || epoch.Sign() < 0 || !text || !decisionRE.MatchString(id) || !contracts.Nonnegative(m["revision"]) || !contracts.Is(m["locale"], "en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th") || !contracts.Is(m["participation"], "mechanical", "judgment", "mixed") {
		return Failure("invalid_decision_request")
	}
	features, e := domain.ParseRouting(m["routing"])
	if e != nil {
		return Failure("invalid_decision_request")
	}
	if features.ExplicitMethod != nil && !s.bundle.Known(*features.ExplicitMethod) {
		return Failure("unknown_method")
	}
	if s.context == context && s.epoch != "" {
		old, _ := contracts.Integer(contracts.Number(0))
		old.SetString(s.epoch, 10)
		if epoch.Cmp(old) < 0 {
			return Failure("invalid_decision_request")
		}
	}
	// Commit a new context only after every request field has been validated.
	// The prior runtime cleared availability before checking routing and participation.
	if s.context != context || s.epoch != epoch.String() {
		s.reset()
		s.context = context
		s.epoch = epoch.String()
	}
	raw, e := contracts.CanonicalCompact(m)
	if e != nil {
		return Failure("invalid_decision_request")
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
