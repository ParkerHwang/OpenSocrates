package devtools

// This validator implements the closed JSON Schema vocabulary used by committed
// contracts. It preserves JSON numbers as decimal rationals rather than floats.
import (
	"encoding/json"
	"fmt"
	"math/big"
	"reflect"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"
)

func schemaNumber(v any) (*big.Rat, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return nil, false
	}
	r, ok := new(big.Rat).SetString(string(n))
	return r, ok
}
func schemaType(v any, t string) bool {
	switch t {
	case "null":
		return v == nil
	case "object":
		_, ok := v.(map[string]any)
		return ok
	case "array":
		_, ok := v.([]any)
		return ok
	case "string":
		_, ok := v.(string)
		return ok
	case "boolean":
		_, ok := v.(bool)
		return ok
	case "number":
		_, ok := schemaNumber(v)
		return ok
	case "integer":
		r, ok := schemaNumber(v)
		return ok && r.IsInt()
	}
	return false
}
func schemaEqual(a, b any) bool {
	ar, aok := schemaNumber(a)
	br, bok := schemaNumber(b)
	if aok && bok {
		return ar.Cmp(br) == 0
	}
	switch x := a.(type) {
	case map[string]any:
		y, ok := b.(map[string]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, v := range x {
			other, ok := y[k]
			if !ok || !schemaEqual(v, other) {
				return false
			}
		}
		return true
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i, v := range x {
			if !schemaEqual(v, y[i]) {
				return false
			}
		}
		return true
	}
	return reflect.DeepEqual(a, b)
}
func schemaLimit(v any) int {
	n, ok := v.(json.Number)
	if !ok {
		return -1
	}
	i, e := n.Int64()
	if e != nil {
		return -1
	}
	return int(i)
}

// ValidateSchema returns bounded field diagnostics, never input values.
func ValidateSchema(value any, schema map[string]any) []string {
	return validateSchema(value, schema, schema, "$", 0)
}
func validateSchema(v any, s, root map[string]any, path string, depth int) []string {
	if depth > 128 {
		return []string{path + ": schema_depth_exceeded"}
	}
	errs := []string{}
	add := func(code string) { errs = append(errs, path+": "+code) }
	if ref, ok := s["$ref"].(string); ok {
		if !strings.HasPrefix(ref, "#/") {
			return []string{path + ": unsupported_schema_reference"}
		}
		var target any = root
		for _, part := range strings.Split(ref[2:], "/") {
			m, ok := target.(map[string]any)
			if !ok {
				return []string{path + ": invalid_schema_reference"}
			}
			target = m[strings.ReplaceAll(strings.ReplaceAll(part, "~1", "/"), "~0", "~")]
		}
		m, ok := target.(map[string]any)
		if !ok {
			return []string{path + ": invalid_schema_reference"}
		}
		errs = append(errs, validateSchema(v, m, root, path, depth+1)...)
	}
	if t, ok := s["type"]; ok {
		matched := false
		switch ts := t.(type) {
		case string:
			matched = schemaType(v, ts)
		case []any:
			for _, x := range ts {
				if z, ok := x.(string); ok && schemaType(v, z) {
					matched = true
				}
			}
		}
		if !matched {
			add("type_invalid")
			return errs
		}
	}
	if c, ok := s["const"]; ok && !schemaEqual(v, c) {
		add("const_invalid")
	}
	if options, ok := s["enum"].([]any); ok {
		found := false
		for _, o := range options {
			found = found || schemaEqual(v, o)
		}
		if !found {
			add("enum_invalid")
		}
	}
	for _, key := range []string{"allOf", "anyOf", "oneOf"} {
		if options, ok := s[key].([]any); ok {
			matches := 0
			for _, o := range options {
				m, ok := o.(map[string]any)
				if ok && len(validateSchema(v, m, root, path, depth+1)) == 0 {
					matches++
				}
			}
			if (key == "allOf" && matches != len(options)) || (key == "anyOf" && matches == 0) || (key == "oneOf" && matches != 1) {
				add(key + "_invalid")
			}
		}
	}
	if m, ok := s["not"].(map[string]any); ok && len(validateSchema(v, m, root, path, depth+1)) == 0 {
		add("not_invalid")
	}
	if cond, ok := s["if"].(map[string]any); ok {
		key := "else"
		if len(validateSchema(v, cond, root, path, depth+1)) == 0 {
			key = "then"
		}
		if m, ok := s[key].(map[string]any); ok {
			errs = append(errs, validateSchema(v, m, root, path, depth+1)...)
		}
	}
	switch x := v.(type) {
	case map[string]any:
		props, _ := s["properties"].(map[string]any)
		if required, ok := s["required"].([]any); ok {
			for _, k := range required {
				key, ok := k.(string)
				if !ok {
					add("required_schema_invalid")
					continue
				}
				if _, exists := x[key]; !exists {
					errs = append(errs, path+"."+key+": required_missing")
				}
			}
		}
		for k, child := range x {
			if nameSchema, ok := s["propertyNames"].(map[string]any); ok {
				errs = append(errs, validateSchema(k, nameSchema, root, path+".<key>", depth+1)...)
			}
			if spec, exists := props[k]; exists {
				if m, ok := spec.(map[string]any); ok {
					errs = append(errs, validateSchema(child, m, root, path+"."+k, depth+1)...)
				}
				continue
			}
			switch a := s["additionalProperties"].(type) {
			case bool:
				if !a {
					errs = append(errs, path+"."+k+": additional_property")
				}
			case map[string]any:
				errs = append(errs, validateSchema(child, a, root, path+"."+k, depth+1)...)
			}
		}
		if n := schemaLimit(s["minProperties"]); n >= 0 && len(x) < n {
			add("minProperties_invalid")
		}
		if n := schemaLimit(s["maxProperties"]); n >= 0 && len(x) > n {
			add("maxProperties_invalid")
		}
	case []any:
		if n := schemaLimit(s["minItems"]); n >= 0 && len(x) < n {
			add("minItems_invalid")
		}
		if n := schemaLimit(s["maxItems"]); n >= 0 && len(x) > n {
			add("maxItems_invalid")
		}
		prefix, _ := s["prefixItems"].([]any)
		for i, child := range x {
			spec := s["items"]
			if i < len(prefix) {
				spec = prefix[i]
			}
			if m, ok := spec.(map[string]any); ok {
				errs = append(errs, validateSchema(child, m, root, fmt.Sprintf("%s[%d]", path, i), depth+1)...)
			} else if b, ok := spec.(bool); ok && !b {
				add("items_forbidden")
			}
		}
		if unique, _ := s["uniqueItems"].(bool); unique {
			for i := range x {
				for j := 0; j < i; j++ {
					if schemaEqual(x[i], x[j]) {
						add("uniqueItems_invalid")
					}
				}
			}
		}
	case string:
		if format, ok := s["format"].(string); ok {
			if format != "date-time" {
				add("unsupported_format")
			} else if _, e := time.Parse(time.RFC3339Nano, strings.ReplaceAll(strings.ReplaceAll(x, "t", "T"), "z", "Z")); e != nil {
				add("date_time_invalid")
			}
		}
		n := utf8.RuneCountInString(x)
		if limit := schemaLimit(s["minLength"]); limit >= 0 && n < limit {
			add("minLength_invalid")
		}
		if limit := schemaLimit(s["maxLength"]); limit >= 0 && n > limit {
			add("maxLength_invalid")
		}
		if pattern, ok := s["pattern"].(string); ok {
			r, e := regexp.Compile(pattern)
			if e != nil || !r.MatchString(x) {
				add("pattern_invalid")
			}
		}
	default:
		if n, ok := schemaNumber(v); ok {
			for _, key := range []string{"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"} {
				if limit, exists := schemaNumber(s[key]); exists {
					cmp := n.Cmp(limit)
					if (key == "minimum" && cmp < 0) || (key == "maximum" && cmp > 0) || (key == "exclusiveMinimum" && cmp <= 0) || (key == "exclusiveMaximum" && cmp >= 0) {
						add(key + "_invalid")
					}
				}
			}
			if divisor, ok := schemaNumber(s["multipleOf"]); ok {
				if divisor.Sign() <= 0 || !new(big.Rat).Quo(n, divisor).IsInt() {
					add("multipleOf_invalid")
				}
			}
		}
	}
	return errs
}

// CheckSchema rejects unsupported assertion keywords instead of silently skipping
// them. Descriptive annotations are permitted; remote references are forbidden.
func CheckSchema(s map[string]any) []string {
	known := map[string]bool{}
	for _, k := range strings.Fields("$schema $id $ref $defs definitions title description default examples deprecated readOnly writeOnly type const enum required properties additionalProperties items prefixItems minItems maxItems minProperties maxProperties propertyNames uniqueItems minLength maxLength pattern format minimum maximum exclusiveMinimum exclusiveMaximum multipleOf allOf anyOf oneOf not if then else") {
		known[k] = true
	}
	codes := []string{}
	var visit func(map[string]any, string)
	visit = func(m map[string]any, path string) {
		for k, v := range m {
			if !known[k] {
				codes = append(codes, path+": unsupported_keyword:"+k)
			}
			switch k {
			case "properties", "$defs", "definitions":
				if children, ok := v.(map[string]any); ok {
					for name, c := range children {
						if z, ok := c.(map[string]any); ok {
							visit(z, path+"."+k+"."+name)
						}
					}
				}
			case "items", "additionalProperties", "propertyNames", "not", "if", "then", "else":
				if z, ok := v.(map[string]any); ok {
					visit(z, path+"."+k)
				}
			case "allOf", "anyOf", "oneOf", "prefixItems":
				if children, ok := v.([]any); ok {
					for i, c := range children {
						if z, ok := c.(map[string]any); ok {
							visit(z, fmt.Sprintf("%s.%s[%d]", path, k, i))
						}
					}
				}
			}
		}
	}
	visit(s, "$")
	return codes
}
