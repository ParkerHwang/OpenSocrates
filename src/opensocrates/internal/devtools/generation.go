// Package devtools contains first-party Go generation and release tooling.
package devtools

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"os"
	"path/filepath"
	"strings"
)

// Canonical preserves arbitrary precision JSON numbers, Unicode and empty/null
// distinctions. The wire format is sorted compact JSON followed by one LF.
func Canonical(value any) ([]byte, error) {
	return contracts.CanonicalJSON(value)
}

func ReadObject(path string) (map[string]any, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	value, err := contracts.Decode(data)
	extension := strings.ToLower(filepath.Ext(path))
	if err != nil && (extension == ".yaml" || extension == ".yml") && !strings.HasPrefix(strings.TrimSpace(string(data)), "{") {
		value, err = decodeAuthoringYAML(data)
	}
	if err != nil {
		return nil, fmt.Errorf("%s: invalid canonical source: %w", path, err)
	}
	result, _ := value.(map[string]any)
	if result == nil {
		return nil, fmt.Errorf("%s: expected object", path)
	}
	return result, nil
}
func digest(data []byte) string {
	h := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(h[:])
}
func markdown(text string) string {
	return strings.TrimRight(strings.ReplaceAll(strings.ReplaceAll(text, "\r\n", "\n"), "\r", "\n"), "\n") + "\n"
}
func writeData(path string, data []byte, mode os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	if err := os.WriteFile(path, data, mode); err != nil {
		return err
	}
	return os.Chmod(path, mode)
}
func writeJSON(path string, value any) error {
	data, err := Canonical(value)
	if err != nil {
		return err
	}
	return writeData(path, data, 0644)
}
func obj(value any) map[string]any { v, _ := value.(map[string]any); return v }
func arr(value any) []any          { v, _ := value.([]any); return v }
func str(value any) string         { v, _ := value.(string); return v }
func jsonToken(v any) string       { b, _ := Canonical(v); return strings.TrimSuffix(string(b), "\n") }
func clone(v map[string]any) map[string]any {
	r := map[string]any{}
	for k, x := range v {
		r[k] = x
	}
	return r
}
func schema(name string) string { return "opensocrates." + name + "/1.0.0" }
