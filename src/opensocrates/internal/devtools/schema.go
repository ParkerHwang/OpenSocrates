package devtools

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
)

// GenerateSchemas emits the language-neutral frozen v1 contracts. It verifies
// canonical source serialization; output does not depend on language reflection.
func GenerateSchemas(root string) error {
	paths, err := filepath.Glob(filepath.Join(root, "schemas/source/contracts/*.json"))
	if err != nil {
		return err
	}
	if len(paths) == 0 {
		return fmt.Errorf("missing canonical schema contracts")
	}
	manifest, err := ReadObject(filepath.Join(root, "schemas/source/schema-manifest.yaml"))
	if err != nil {
		return err
	}
	if manifest["schema_manifest_version"] != "1.0.0" {
		return fmt.Errorf("invalid schema manifest version")
	}
	entries := map[string]map[string]any{}
	for _, raw := range arr(manifest["schemas"]) {
		entry := obj(raw)
		file := str(entry["file"])
		if len(entry) != 4 || !safeRelative(file) || str(entry["source_contract"]) != "contracts/"+file || entry["compatibility"] != "additive" || entries[file] != nil {
			return fmt.Errorf("invalid language neutral schema manifest")
		}
		entries[file] = entry
	}
	if len(entries) != len(paths) {
		return fmt.Errorf("schema source inventory differs from manifest")
	}
	for _, path := range paths {
		value, err := ReadObject(path)
		if err != nil {
			return err
		}
		entry := entries[filepath.Base(path)]
		if entry == nil || value["$id"] != entry["schema"] {
			return fmt.Errorf("schema identity differs from manifest")
		}
		data, err := Canonical(value)
		if err != nil {
			return err
		}
		source, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if !bytes.Equal(data, source) {
			return fmt.Errorf("noncanonical schema source %s", filepath.Base(path))
		}
		for _, dest := range []string{"schemas/v1", "src/opensocrates/internal/contracts/assets"} {
			if err = writeData(filepath.Join(root, dest, filepath.Base(path)), data, 0644); err != nil {
				return err
			}
		}
	}
	return nil
}
