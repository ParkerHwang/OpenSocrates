package persistence

import (
	"bytes"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
)

var OutcomeLabels = []string{"executable_missing", "request_rejected", "spawn_failed", "timeout", "nonzero_exit", "invalid_output", "selector_closed", "no_intervention", "selected"}

func EmptyOutcomes() map[string]int64 {
	m := map[string]int64{}
	for _, label := range OutcomeLabels {
		m[label] = 0
	}
	return m
}
func ReadOutcomes(root string) (map[string]int64, error) {
	data, e := platform.ReadFile(filepath.Join(root, "diagnostics", "selector-outcomes.json"), 4096)
	if errors.Is(e, os.ErrNotExist) {
		return EmptyOutcomes(), nil
	}
	if e != nil {
		return nil, e
	}
	v, e := contracts.Decode(data)
	if e != nil {
		return nil, e
	}
	m, e := contracts.Object(v, "schema", "counts")
	if e != nil || m["schema"] != "opensocrates.selector-outcome-aggregate/1.0.0" {
		return nil, contracts.ErrInvalid
	}
	canon, e := contracts.CanonicalJSON(m)
	if e != nil || !bytes.Equal(canon, data) {
		return nil, contracts.ErrInvalid
	}
	raw, ok := m["counts"].(map[string]any)
	if !ok {
		return nil, contracts.ErrInvalid
	}
	counts := EmptyOutcomes()
	for label, value := range raw {
		if _, ok := counts[label]; !ok {
			return nil, contracts.ErrInvalid
		}
		n, ok := contracts.Int(value)
		if !ok || n < 0 || n > 2147483647 {
			return nil, contracts.ErrInvalid
		}
		counts[label] = n
	}
	return counts, nil
}
func IncrementOutcomes(root string, delta map[string]int64) (map[string]int64, error) {
	nonzero := false
	for label, value := range delta {
		known := false
		for _, key := range OutcomeLabels {
			known = known || label == key
		}
		if !known || value < 0 || value > 2147483647 {
			return nil, contracts.ErrInvalid
		}
		nonzero = nonzero || value != 0
	}
	if !nonzero {
		return ReadOutcomes(root)
	}
	if e := Ensure(root); e != nil {
		return nil, e
	}
	lock, e := platform.Lock(filepath.Join(root, "diagnostics", "selector-outcomes.lock"))
	if e != nil {
		return nil, e
	}
	defer lock.Close()
	counts, e := ReadOutcomes(root)
	if e != nil {
		return nil, e
	}
	for label, value := range delta {
		counts[label] += value
		if counts[label] > 2147483647 {
			counts[label] = 2147483647
		}
	}
	raw, e := contracts.CanonicalJSON(map[string]any{"schema": "opensocrates.selector-outcome-aggregate/1.0.0", "counts": counts})
	if e != nil {
		return nil, e
	}
	if e = platform.AtomicWrite(filepath.Join(root, "diagnostics", "selector-outcomes.json"), raw, 0600); e != nil {
		return nil, e
	}
	return counts, nil
}
