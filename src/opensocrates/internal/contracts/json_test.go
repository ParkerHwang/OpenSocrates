package contracts

import (
	"encoding/json"
	"math"
	"testing"
)

func TestStrictJSONBoundary(t *testing.T) {
	for _, raw := range []string{`{"a":1,"a":2}`, `{"a":{"b":1,"b":2}}`, `{"a":NaN}`, `{"a":Infinity}`, `{"a":"\ud800"}`, `{"a":"\udfff"}`, `{} {}`, "{\"a\":\"\xff\"}"} {
		if _, e := Decode([]byte(raw)); e == nil {
			t.Fatalf("accepted malformed JSON %q", raw)
		}
	}
	for _, raw := range []string{`{"a":"\ud83d\ude42"}`, `{"a":"한글🙂"}`, `[null,{},[],"",false,9007199254740993]`} {
		if _, e := Decode([]byte(raw)); e != nil {
			t.Fatalf("rejected valid JSON %q: %v", raw, e)
		}
	}
}
func TestCanonicalGoldenNumbers(t *testing.T) {
	cases := []struct {
		in       any
		expected string
	}{{json.Number("9007199254740993"), "9007199254740993"}, {json.Number("1e6"), "1000000.0"}, {json.Number("1e15"), "1000000000000000.0"}, {json.Number("1e16"), "1e+16"}, {json.Number("1e-4"), "0.0001"}, {json.Number("1e-5"), "1e-05"}, {json.Number("-0.0"), "-0.0"}, {json.Number("-0"), "0"}, {float64(1000000), "1000000.0"}, {math.Copysign(0, -1), "-0.0"}, {json.Number("1.2345678901234567"), "1.2345678901234567"}}
	for _, c := range cases {
		got, e := CanonicalCompact(c.in)
		if e != nil || string(got) != c.expected {
			t.Errorf("%v: got %s (%v), want %s", c.in, got, e, c.expected)
		}
	}
	for _, value := range []any{math.Inf(1), math.NaN(), json.Number("1e9999")} {
		if _, e := CanonicalCompact(value); e == nil {
			t.Errorf("accepted %v", value)
		}
	}
}
func TestCanonicalGoldenUnicodeAndPresence(t *testing.T) {
	v, e := Decode([]byte(`{"z":null,"ko":"한글🙂<>&\u2028","empty":[],"map":{},"quote":"\"\\\t"}`))
	if e != nil {
		t.Fatal(e)
	}
	got, e := CanonicalJSON(v)
	want := "{\"empty\":[],\"ko\":\"한글🙂<>&\u2028\",\"map\":{},\"quote\":\"\\\"\\\\\\t\",\"z\":null}\n"
	if e != nil || string(got) != want {
		t.Fatalf("got %q (%v), want %q", got, e, want)
	}
}
func TestIntegerNeverCoerces(t *testing.T) {
	for _, raw := range []string{"true", "1.0", "1e0", "null", "\"1\""} {
		v, e := Decode([]byte(raw))
		if e != nil {
			t.Fatal(e)
		}
		if _, ok := Integer(v); ok {
			t.Fatalf("accepted integer %s", raw)
		}
	}
	v, _ := Decode([]byte("123456789012345678901234567890"))
	i, ok := Integer(v)
	if !ok || i.String() != "123456789012345678901234567890" {
		t.Fatal("precision lost")
	}
}
func TestTypedNestedFloatStaysFloat(t *testing.T) {
	type wire struct {
		Float    float64 `json:"float"`
		Integer  int     `json:"integer"`
		Nullable *string `json:"nullable"`
	}
	for _, value := range []any{wire{1000000, 1000000, nil}, map[string]any{"float": float64(1000000), "integer": 1000000, "nullable": nil}, map[string]float64{"float": 1000000}} {
		raw, e := CanonicalCompact(value)
		if e != nil {
			t.Fatal(e)
		}
		if string(raw) != `{"float":1000000.0,"integer":1000000,"nullable":null}` && string(raw) != `{"float":1000000.0}` {
			t.Fatalf("float kind lost: %s", raw)
		}
	}
}
