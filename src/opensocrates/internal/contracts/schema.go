package contracts

import (
	"embed"
	"encoding/json"
	"fmt"
	"golang.org/x/text/unicode/norm"
	"math/big"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"
)

//go:embed assets/*.json
var schemaAssets embed.FS

// Validate applies the frozen language-neutral schema and its semantic checks.
func Validate(name string, value any) error {
	raw, e := schemaAssets.ReadFile("assets/" + name + ".schema.json")
	if e != nil {
		return e
	}
	v, e := Decode(raw)
	if e != nil {
		return e
	}
	schema, ok := v.(map[string]any)
	if !ok {
		return ErrInvalid
	}
	if e = ValidateSchema(schema, value); e != nil {
		return e
	}
	return semantic(name, value)
}
func equal(a, b any) bool {
	x, e := CanonicalCompact(a)
	if e != nil {
		return false
	}
	y, e := CanonicalCompact(b)
	return e == nil && string(x) == string(y)
}
func ValidateSchema(schema map[string]any, value any) error {
	return validateSchema(schema, value, schema, 0)
}
func validateSchema(s map[string]any, v any, root map[string]any, depth int) error {
	if depth > 64 {
		return ErrInvalid
	}
	if ref, ok := s["$ref"].(string); ok {
		if !strings.HasPrefix(ref, "#/") {
			return ErrInvalid
		}
		var target any = root
		for _, part := range strings.Split(ref[2:], "/") {
			m, ok := target.(map[string]any)
			if !ok {
				return ErrInvalid
			}
			target = m[strings.ReplaceAll(strings.ReplaceAll(part, "~1", "/"), "~0", "~")]
		}
		m, ok := target.(map[string]any)
		if !ok {
			return ErrInvalid
		}
		return validateSchema(m, v, root, depth+1)
	}
	if constant, ok := s["const"]; ok && !equal(constant, v) {
		return ErrInvalid
	}
	if enum, ok := s["enum"].([]any); ok {
		found := false
		for _, item := range enum {
			found = found || equal(item, v)
		}
		if !found {
			return ErrInvalid
		}
	}
	for _, kind := range []string{"anyOf", "oneOf", "allOf"} {
		if branches, ok := s[kind].([]any); ok {
			matches := 0
			for _, branch := range branches {
				m, ok := branch.(map[string]any)
				if ok && validateSchema(m, v, root, depth+1) == nil {
					matches++
				}
			}
			if kind == "anyOf" && matches == 0 || kind == "oneOf" && matches != 1 || kind == "allOf" && matches != len(branches) {
				return ErrInvalid
			}
		}
	}
	if raw, ok := s["not"].(map[string]any); ok && validateSchema(raw, v, root, depth+1) == nil {
		return ErrInvalid
	}
	if types, ok := s["type"]; ok {
		allowed := []any{types}
		if a, ok := types.([]any); ok {
			allowed = a
		}
		match := false
		for _, t := range allowed {
			switch t {
			case "null":
				match = match || v == nil
			case "boolean":
				_, ok := v.(bool)
				match = match || ok
			case "string":
				_, ok := v.(string)
				match = match || ok
			case "object":
				_, ok := v.(map[string]any)
				match = match || ok
			case "array":
				_, ok := v.([]any)
				match = match || ok
			case "integer":
				_, ok := Integer(v)
				match = match || ok
			case "number":
				_, ok := v.(json.Number)
				match = match || ok
			}
		}
		if !match {
			return ErrInvalid
		}
	}
	if m, ok := v.(map[string]any); ok {
		properties, _ := s["properties"].(map[string]any)
		required, _ := s["required"].([]any)
		for _, k := range required {
			key, ok := k.(string)
			if !ok {
				return ErrInvalid
			}
			if _, ok := m[key]; !ok {
				return ErrInvalid
			}
		}
		for key, item := range m {
			raw, exists := properties[key]
			if exists {
				child, ok := raw.(map[string]any)
				if !ok || validateSchema(child, item, root, depth+1) != nil {
					return ErrInvalid
				}
				continue
			}
			switch add := s["additionalProperties"].(type) {
			case bool:
				if !add {
					return ErrInvalid
				}
			case map[string]any:
				if validateSchema(add, item, root, depth+1) != nil {
					return ErrInvalid
				}
			}
		}
		if n, ok := Int(s["maxProperties"]); ok && len(m) > int(n) {
			return ErrInvalid
		}
	}
	if a, ok := v.([]any); ok {
		if n, ok := Int(s["minItems"]); ok && len(a) < int(n) {
			return ErrInvalid
		}
		if n, ok := Int(s["maxItems"]); ok && len(a) > int(n) {
			return ErrInvalid
		}
		if child, ok := s["items"].(map[string]any); ok {
			for _, item := range a {
				if validateSchema(child, item, root, depth+1) != nil {
					return ErrInvalid
				}
			}
		}
		if s["uniqueItems"] == true {
			for i, item := range a {
				for _, other := range a[:i] {
					if equal(item, other) {
						return ErrInvalid
					}
				}
			}
		}
	}
	if text, ok := v.(string); ok {
		n := utf8.RuneCountInString(text)
		if min, ok := Int(s["minLength"]); ok && int64(n) < min {
			return ErrInvalid
		}
		if max, ok := Int(s["maxLength"]); ok && int64(n) > max {
			return ErrInvalid
		}
		if pattern, ok := s["pattern"].(string); ok {
			pattern = strings.ReplaceAll(pattern, `\d`, `[0-9]`)
			r, e := regexp.Compile(pattern)
			if e != nil {
				return fmt.Errorf("schema pattern: %w", e)
			}
			if !r.MatchString(text) {
				return ErrInvalid
			}
		}
	}
	if number, ok := v.(json.Number); ok {
		x, ok := new(big.Rat).SetString(string(number))
		if !ok {
			return ErrInvalid
		}
		for _, bound := range []string{"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"} {
			if raw, ok := s[bound].(json.Number); ok {
				y, ok := new(big.Rat).SetString(string(raw))
				if !ok {
					return ErrInvalid
				}
				cmp := x.Cmp(y)
				if bound == "minimum" && cmp < 0 || bound == "maximum" && cmp > 0 || bound == "exclusiveMinimum" && cmp <= 0 || bound == "exclusiveMaximum" && cmp >= 0 {
					return ErrInvalid
				}
			}
		}
	}
	return nil
}
func semantic(name string, v any) error {
	m, ok := v.(map[string]any)
	if !ok {
		return nil
	}
	switch name {
	case "user-settings":
		revision, ok := Integer(m["revision"])
		if !ok || revision.Sign() < 1 || !Is(m["locale_preference"], "en", "ko", "zh", "ja") && m["locale_preference"] != nil {
			return ErrInvalid
		}
		days, ok := Int(m["record_retention_days"])
		if !ok || days < 7 || days > 3650 {
			return ErrInvalid
		}
		size, ok := Int(m["record_size_limit_bytes"])
		if !ok || size < 10*1024*1024 || size > 10*1024*1024*1024 {
			return ErrInvalid
		}
		if m["recording_mode"] == "local_public_artifacts" && m["onboarding_version_seen"] == nil {
			return ErrInvalid
		}
		prefs, _ := m["intervention_preferences"].(map[string]any)
		for key, raw := range prefs {
			if !norm.NFC.IsNormalString(key) {
				return ErrInvalid
			}
			pref, ok := raw.(map[string]any)
			if !ok {
				return ErrInvalid
			}
			next, ok := Integer(pref["next_sequence"])
			if !ok || next.Sign() < 1 {
				return ErrInvalid
			}
			feedback, _ := pref["recent_feedback"].([]any)
			if len(feedback) > 20 {
				return ErrInvalid
			}
			last := new(big.Int)
			for _, f := range feedback {
				entry, _ := f.(map[string]any)
				n, ok := Integer(entry["sequence"])
				if !ok || n.Cmp(last) <= 0 || n.Cmp(next) >= 0 {
					return ErrInvalid
				}
				last = n
				day, _ := entry["day"].(string)
				if _, e := time.Parse("2006-01-02", day); e != nil {
					return ErrInvalid
				}
			}
			if until, ok := pref["reduced_until"].(string); ok {
				if _, e := time.Parse("2006-01-02", until); e != nil {
					return ErrInvalid
				}
			}
		}
	}
	return nil
}
