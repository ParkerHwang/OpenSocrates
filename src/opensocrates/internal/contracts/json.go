// Package contracts owns the language-neutral wire boundary. JSON numbers stay
// lexical until their contract is known: IDs and revisions never pass a float64.
package contracts

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"math/big"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

var ErrInvalid = errors.New("invalid_contract")

// Decode rejects duplicate fields, invalid Unicode and non-JSON numbers.
func Decode(raw []byte) (any, error) {
	if !utf8.Valid(raw) || !validEscapes(raw) {
		return nil, ErrInvalid
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	value, err := decode(d, 0)
	if err != nil {
		return nil, ErrInvalid
	}
	if _, err = d.Token(); err != io.EOF {
		return nil, ErrInvalid
	}
	return value, nil
}
func decode(d *json.Decoder, depth int) (any, error) {
	if depth > 64 {
		return nil, ErrInvalid
	}
	token, err := d.Token()
	if err != nil {
		return nil, err
	}
	delim, ok := token.(json.Delim)
	if !ok {
		return token, nil
	}
	switch delim {
	case '{':
		obj := map[string]any{}
		for d.More() {
			k, err := d.Token()
			if err != nil {
				return nil, err
			}
			key, ok := k.(string)
			if !ok {
				return nil, ErrInvalid
			}
			if _, exists := obj[key]; exists {
				return nil, ErrInvalid
			}
			v, err := decode(d, depth+1)
			if err != nil {
				return nil, err
			}
			obj[key] = v
		}
		end, err := d.Token()
		if err != nil || end != json.Delim('}') {
			return nil, ErrInvalid
		}
		return obj, nil
	case '[':
		arr := []any{}
		for d.More() {
			v, err := decode(d, depth+1)
			if err != nil {
				return nil, err
			}
			arr = append(arr, v)
		}
		end, err := d.Token()
		if err != nil || end != json.Delim(']') {
			return nil, ErrInvalid
		}
		return arr, nil
	}
	return nil, ErrInvalid
}

// encoding/json replaces unpaired UTF-16 surrogates. Admit only actual scalar
// values, so a malformed escape cannot silently change canonical identity.
func validEscapes(raw []byte) bool {
	inString := false
	for i := 0; i < len(raw); i++ {
		if raw[i] == '"' {
			inString = !inString
			continue
		}
		if !inString || raw[i] != '\\' {
			continue
		}
		i++
		if i >= len(raw) {
			return false
		}
		if raw[i] != 'u' {
			continue
		}
		if i+4 >= len(raw) {
			return false
		}
		n, e := strconv.ParseUint(string(raw[i+1:i+5]), 16, 16)
		if e != nil {
			return false
		}
		i += 4
		if n >= 0xdc00 && n <= 0xdfff {
			return false
		}
		if n >= 0xd800 && n <= 0xdbff {
			if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
				return false
			}
			m, e := strconv.ParseUint(string(raw[i+3:i+7]), 16, 16)
			if e != nil || m < 0xdc00 || m > 0xdfff {
				return false
			}
			i += 6
		}
	}
	return true
}
func Object(v any, keys ...string) (map[string]any, error) {
	m, ok := v.(map[string]any)
	if !ok || len(m) != len(keys) {
		return nil, ErrInvalid
	}
	for _, key := range keys {
		if _, ok := m[key]; !ok {
			return nil, ErrInvalid
		}
	}
	return m, nil
}
func String(v any) (string, bool) { s, ok := v.(string); return s, ok }
func Integer(v any) (*big.Int, bool) {
	n, ok := v.(json.Number)
	if !ok || strings.ContainsAny(string(n), ".eE") {
		return nil, false
	}
	i, ok := new(big.Int).SetString(string(n), 10)
	return i, ok
}
func Int(v any) (int64, bool) {
	i, ok := Integer(v)
	if !ok || !i.IsInt64() {
		return 0, false
	}
	return i.Int64(), true
}
func Nonnegative(v any) bool { i, ok := Integer(v); return ok && i.Sign() >= 0 }
func Is(v any, allowed ...string) bool {
	s, ok := v.(string)
	if !ok {
		return false
	}
	for _, a := range allowed {
		if a == s {
			return true
		}
	}
	return false
}
func Number(n int64) json.Number { return json.Number(strconv.FormatInt(n, 10)) }

// CanonicalJSON matches the released sorted, compact, UTF-8 wire encoding and
// appends its one LF. CanonicalCompact is used inside content and hashes.
func CanonicalJSON(value any) ([]byte, error) {
	b, e := CanonicalCompact(value)
	if e != nil {
		return nil, e
	}
	return append(b, '\n'), nil
}
func CanonicalCompact(value any) ([]byte, error) {
	var b bytes.Buffer
	if err := canonical(&b, value); err != nil {
		return nil, err
	}
	return b.Bytes(), nil
}
func canonical(b *bytes.Buffer, v any) error {
	switch x := v.(type) {
	case nil:
		b.WriteString("null")
	case bool:
		if x {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case string:
		if !utf8.ValidString(x) {
			return ErrInvalid
		}
		b.WriteByte('"')
		for _, r := range x {
			switch r {
			case '"':
				b.WriteString("\\\"")
			case '\\':
				b.WriteString("\\\\")
			case '\b':
				b.WriteString("\\b")
			case '\f':
				b.WriteString("\\f")
			case '\n':
				b.WriteString("\\n")
			case '\r':
				b.WriteString("\\r")
			case '\t':
				b.WriteString("\\t")
			default:
				if r < 32 {
					fmt.Fprintf(b, "\\u%04x", r)
				} else {
					b.WriteRune(r)
				}
			}
		}
		b.WriteByte('"')
	case json.Number:
		if !strings.ContainsAny(string(x), ".eE") {
			i, ok := new(big.Int).SetString(string(x), 10)
			if !ok {
				return ErrInvalid
			}
			b.WriteString(i.String())
			return nil
		}
		f, err := strconv.ParseFloat(string(x), 64)
		if err != nil {
			return ErrInvalid
		}
		return canonicalFloat(b, f)
	case float64:
		return canonicalFloat(b, x)
	case float32:
		return canonicalFloat(b, float64(x))
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		b.WriteByte('{')
		for i, k := range keys {
			if i > 0 {
				b.WriteByte(',')
			}
			if e := canonical(b, k); e != nil {
				return e
			}
			b.WriteByte(':')
			if e := canonical(b, x[k]); e != nil {
				return e
			}
		}
		b.WriteByte('}')
	case []any:
		b.WriteByte('[')
		for i, a := range x {
			if i > 0 {
				b.WriteByte(',')
			}
			if e := canonical(b, a); e != nil {
				return e
			}
		}
		b.WriteByte(']')
	default:
		rv := reflect.ValueOf(v)
		switch rv.Kind() {
		case reflect.Pointer:
			if rv.IsNil() {
				return canonical(b, nil)
			}
			return canonical(b, rv.Elem().Interface())
		case reflect.Float32, reflect.Float64:
			return canonicalFloat(b, rv.Float())
		case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
			b.WriteString(strconv.FormatInt(rv.Int(), 10))
			return nil
		case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
			b.WriteString(strconv.FormatUint(rv.Uint(), 10))
			return nil
		case reflect.String:
			return canonical(b, rv.String())
		case reflect.Bool:
			return canonical(b, rv.Bool())
		case reflect.Slice, reflect.Array:
			a := make([]any, rv.Len())
			for i := range a {
				a[i] = rv.Index(i).Interface()
			}
			return canonical(b, a)
		case reflect.Map:
			if rv.IsNil() {
				return canonical(b, nil)
			}
			if rv.Type().Key().Kind() != reflect.String {
				return ErrInvalid
			}
			m := map[string]any{}
			for _, key := range rv.MapKeys() {
				m[key.String()] = rv.MapIndex(key).Interface()
			}
			return canonical(b, m)
		case reflect.Struct:
			if marshaler, ok := v.(json.Marshaler); ok {
				raw, e := marshaler.MarshalJSON()
				if e != nil {
					return e
				}
				normalized, e := Decode(raw)
				if e != nil {
					return e
				}
				return canonical(b, normalized)
			}
			m := map[string]any{}
			t := rv.Type()
			for i := 0; i < rv.NumField(); i++ {
				f := t.Field(i)
				if f.PkgPath != "" {
					continue
				}
				tag := strings.Split(f.Tag.Get("json"), ",")
				if tag[0] == "-" {
					continue
				}
				name := tag[0]
				if name == "" {
					name = f.Name
				}
				value := rv.Field(i)
				omit := false
				for _, option := range tag[1:] {
					if option == "omitempty" && isEmpty(value) {
						omit = true
					}
				}
				if omit {
					continue
				}
				m[name] = value.Interface()
			}
			return canonical(b, m)
		}
		return ErrInvalid
	}
	return nil
}
func isEmpty(v reflect.Value) bool {
	switch v.Kind() {
	case reflect.Array, reflect.Map, reflect.Slice, reflect.String:
		return v.Len() == 0
	case reflect.Bool, reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64, reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64, reflect.Float32, reflect.Float64, reflect.Interface, reflect.Pointer:
		return v.IsZero()
	}
	return false
}

// Python's JSON serializer uses its shortest binary64 representation, with
// fixed notation at decimal exponents -4..15 and a .0 for integral floats.
// Go's 'g' switches at exponent 6, so use an explicit exponent decision.
func canonicalFloat(b *bytes.Buffer, f float64) error {
	if math.IsNaN(f) || math.IsInf(f, 0) {
		return ErrInvalid
	}
	scientific := strconv.FormatFloat(f, 'e', -1, 64)
	parts := strings.Split(scientific, "e")
	exponent, e := strconv.Atoi(parts[1])
	if e != nil {
		return ErrInvalid
	}
	if exponent >= -4 && exponent < 16 {
		s := strconv.FormatFloat(f, 'f', -1, 64)
		if !strings.Contains(s, ".") {
			s += ".0"
		}
		b.WriteString(s)
	} else {
		b.WriteString(scientific)
	}
	return nil
}
