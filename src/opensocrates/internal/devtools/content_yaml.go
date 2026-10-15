package devtools

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go.yaml.in/yaml/v3"
	"io"
	"math"
	"math/big"
	"strconv"
	"strings"
	"unicode/utf8"
)

// Build-only YAML parsing is separate from runtime JSON. Nodes preserve the
// source insertion order and arbitrary precision integer tokens, and reject
// duplicate fields, aliases, tags outside JSON-compatible values and multi-docs.
func decodeAuthoringYAML(raw []byte) (any, error) {
	if !utf8.Valid(raw) {
		return nil, fmt.Errorf("invalid YAML Unicode")
	}
	d := yaml.NewDecoder(bytes.NewReader(raw))
	var node yaml.Node
	if e := d.Decode(&node); e != nil {
		return nil, e
	}
	var extra yaml.Node
	if e := d.Decode(&extra); e != io.EOF {
		return nil, fmt.Errorf("multiple YAML documents")
	}
	return yamlValue(&node, 0)
}
func yamlValue(n *yaml.Node, depth int) (any, error) {
	if depth > 64 {
		return nil, fmt.Errorf("YAML nesting limit")
	}
	switch n.Kind {
	case yaml.DocumentNode:
		if len(n.Content) != 1 {
			return nil, fmt.Errorf("invalid YAML document")
		}
		return yamlValue(n.Content[0], depth+1)
	case yaml.MappingNode:
		if n.Tag != "!!map" {
			return nil, fmt.Errorf("unsupported YAML tag")
		}
		r := map[string]any{}
		for i := 0; i < len(n.Content); i += 2 {
			k := n.Content[i]
			if k.Kind != yaml.ScalarNode || k.Tag != "!!str" {
				return nil, fmt.Errorf("YAML object keys must be strings")
			}
			if _, exists := r[k.Value]; exists {
				return nil, fmt.Errorf("duplicate YAML field")
			}
			v, e := yamlValue(n.Content[i+1], depth+1)
			if e != nil {
				return nil, e
			}
			r[k.Value] = v
		}
		return r, nil
	case yaml.SequenceNode:
		if n.Tag != "!!seq" {
			return nil, fmt.Errorf("unsupported YAML tag")
		}
		r := []any{}
		for _, c := range n.Content {
			v, e := yamlValue(c, depth+1)
			if e != nil {
				return nil, e
			}
			r = append(r, v)
		}
		return r, nil
	case yaml.ScalarNode:
		switch n.Tag {
		case "!!str":
			return n.Value, nil
		case "!!null":
			return nil, nil
		case "!!bool":
			return strconv.ParseBool(strings.ToLower(n.Value))
		case "!!int":
			text := strings.ReplaceAll(n.Value, "_", "")
			base := 10
			if strings.HasPrefix(text, "0x") || strings.HasPrefix(text, "0o") || strings.HasPrefix(text, "0b") {
				base = 0
			}
			v, ok := new(big.Int).SetString(text, base)
			if !ok {
				return nil, fmt.Errorf("invalid YAML integer")
			}
			return json.Number(v.String()), nil
		case "!!float":
			v, e := strconv.ParseFloat(strings.ReplaceAll(n.Value, "_", ""), 64)
			if e != nil || math.IsNaN(v) || math.IsInf(v, 0) {
				return nil, fmt.Errorf("invalid YAML finite number")
			}
			text := strconv.FormatFloat(v, 'g', -1, 64)
			if !strings.ContainsAny(text, ".eE") {
				text += ".0"
			}
			return json.Number(text), nil
		}
		return nil, fmt.Errorf("unsupported YAML scalar tag")
	}
	return nil, fmt.Errorf("unsupported YAML node")
}
