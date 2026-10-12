package devtools

import (
	"bytes"
	"encoding/json"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

func validateSourceSchema(root, name string, v any) error {
	s, e := ReadObject(filepath.Join(root, "schemas/source/contracts", name))
	if e != nil {
		return e
	}
	return contracts.ValidateSchema(s, v)
}

var procedureHeadings = []string{"Purpose", "Use when", "Do not use when", "Inputs to establish", "Procedure", "Public output contract", "Evidence and uncertainty rules", "Stop conditions", "Complement handoff"}

func validateProcedure(text string) error {
	headings := []string{}
	for _, line := range strings.Split(text, "\n") {
		if strings.HasPrefix(line, "## ") {
			headings = append(headings, strings.TrimSpace(line[3:]))
		}
	}
	if strings.Join(headings, "\x00") != strings.Join(procedureHeadings, "\x00") {
		return fmt.Errorf("expected exact nine procedure headings")
	}
	words := len(strings.Fields(text))
	if words < 350 || words > 900 {
		return fmt.Errorf("expected 350-900 words")
	}
	start := strings.Index(text, "## Procedure\n")
	end := strings.Index(text, "## Public output contract\n")
	if start < 0 || end < start {
		return fmt.Errorf("missing numbered procedure")
	}
	steps := regexp.MustCompile(`(?m)^\s*\d+[.)]\s+`).FindAllString(text[start:end], -1)
	if len(steps) < 5 || len(steps) > 9 {
		return fmt.Errorf("expected 5-9 steps")
	}
	return nil
}
func validateCases(id string, v map[string]any) error {
	if len(v) != 2 || v["schema"] != schema("method-cases") {
		return fmt.Errorf("invalid case document")
	}
	seen := map[string]bool{}
	counts := map[string]int{}
	for _, raw := range arr(v["cases"]) {
		c := obj(raw)
		cid := str(c["id"])
		kind := str(c["kind"])
		if len(c) != 7 || !strings.HasPrefix(cid, id+"-"+kind+"-") || seen[cid] {
			return fmt.Errorf("invalid case %s", cid)
		}
		seen[cid] = true
		counts[kind]++
		if str(c["prompt"]) == "" || str(c["rationale"]) == "" {
			return fmt.Errorf("empty case")
		}
		allowed := map[string]string{"positive": "route", "negative": "route no_route hold", "mechanical": "no_route refuse", "explicit": "explicit_primary refuse", "insufficiency": "hold refuse"}
		if !strings.Contains(" "+allowed[kind]+" ", " "+str(c["expected_behavior"])+" ") {
			return fmt.Errorf("case behavior/kind mismatch")
		}
		if kind == "negative" && c["expected_behavior"] == "route" && c["expected_route"] == id {
			return fmt.Errorf("negative case routes to itself")
		}
	}
	for k, n := range map[string]int{"positive": 3, "negative": 2, "mechanical": 1, "explicit": 1, "insufficiency": 1} {
		if counts[k] < n {
			return fmt.Errorf("missing case kind %s", k)
		}
	}
	return nil
}

// sourceFieldKeys records source object insertion order, which is part of the
// frozen compact selector projection even though canonical object keys sort.
func sourceFieldKeys(path, field string) ([]any, error) {
	b, e := os.ReadFile(path)
	if e != nil {
		return nil, e
	}
	d := json.NewDecoder(bytes.NewReader(b))
	result := []any{}
	for {
		tok, e := d.Token()
		if e != nil {
			return nil, e
		}
		if tok == field {
			next, e := d.Token()
			if e != nil {
				return nil, e
			}
			if next != json.Delim('{') {
				return nil, fmt.Errorf("feature map required")
			}
			for d.More() {
				key, e := d.Token()
				if e != nil {
					return nil, e
				}
				result = append(result, key)
				var value any
				if e = d.Decode(&value); e != nil {
					return nil, e
				}
			}
			return result, nil
		}
	}
}
