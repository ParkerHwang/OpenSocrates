package devtools

import (
	"debug/buildinfo"
	"fmt"
	"path/filepath"
	"strings"
)

// WriteSBOM records exact distributed files and compiler/module identities from
// native binaries, including dependency replacements. It does not infer runtime
// vulnerability absence from an inventory or omit helper/updater dependencies.
func WriteSBOM(packagePath, output string) error {
	manifest, e := VerifyPackage(packagePath, "bundle-manifest.json")
	if e != nil {
		return e
	}
	components := []any{}
	seen := map[string]bool{}
	for _, raw := range arr(manifest["files"]) {
		entry := obj(raw)
		path := str(entry["path"])
		components = append(components, map[string]any{"type": "file", "name": path, "hashes": []any{map[string]any{"alg": "SHA-256", "content": strings.TrimPrefix(str(entry["sha256"]), "sha256:")}}})
		if strings.HasPrefix(path, "bin/") {
			info, e := buildinfo.ReadFile(filepath.Join(packagePath, filepath.FromSlash(path)))
			if e != nil {
				return fmt.Errorf("missing Go build info")
			}
			for _, module := range info.Deps {
				if module.Replace != nil {
					module = module.Replace
				}
				key := module.Path + "@" + module.Version
				if seen[key] {
					continue
				}
				seen[key] = true
				c := map[string]any{"type": "library", "name": module.Path, "version": module.Version, "purl": "pkg:golang/" + module.Path + "@" + module.Version}
				if module.Sum != "" {
					c["properties"] = []any{map[string]any{"name": "go.module.sum", "value": module.Sum}}
				}
				components = append(components, c)
			}
		}
	}
	return writeJSON(output, map[string]any{"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1, "metadata": map[string]any{"component": map[string]any{"type": "application", "name": "OpenSocrates", "version": manifest["product_version"]}, "properties": []any{map[string]any{"name": "opensocrates.source.commit", "value": manifest["source_git_commit"]}, map[string]any{"name": "opensocrates.target", "value": manifest["target"]}}}, "components": components})
}
