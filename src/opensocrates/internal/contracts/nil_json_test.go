package contracts

import "testing"

// Nil collections are explicit null; a deliberately initialized collection
// retains its empty wire form, including when nested in a typed response.
func TestCanonicalNilCollections(t *testing.T) {
	for _, tc := range []struct {
		name  string
		value any
		want  string
	}{
		{"nil object", map[string]any(nil), "null"},
		{"empty object", map[string]any{}, "{}"},
		{"nil array", []any(nil), "null"},
		{"empty array", []any{}, "[]"},
		{"nested nil", struct {
			Route  map[string]any `json:"route"`
			Values []any          `json:"values"`
		}{}, `{"route":null,"values":null}`},
		{"nested empty", struct {
			Route  map[string]any `json:"route"`
			Values []any          `json:"values"`
		}{map[string]any{}, []any{}}, `{"route":{},"values":[]}`},
	} {
		t.Run(tc.name, func(t *testing.T) {
			raw, e := CanonicalCompact(tc.value)
			if e != nil || string(raw) != tc.want {
				t.Fatalf("canonical=%s error=%v want=%s", raw, e, tc.want)
			}
		})
	}
}
