package devtools

import (
	"crypto/sha256"
	"debug/buildinfo"
	"encoding/hex"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

func checkBoundaries(root string) ([]string, error) {
	codes := []string{}
	base := filepath.Join(root, "src/opensocrates")
	e := filepath.WalkDir(base, func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() || !strings.HasSuffix(p, ".go") || strings.HasSuffix(p, "_test.go") {
			return nil
		}
		r, _ := filepath.Rel(base, p)
		r = filepath.ToSlash(r)
		f, e := parser.ParseFile(token.NewFileSet(), p, nil, 0)
		if e != nil {
			codes = append(codes, "source_parse_invalid:"+r)
			return nil
		}
		domain := strings.HasPrefix(r, "internal/domain/")
		for _, i := range f.Imports {
			name, e := strconv.Unquote(i.Path.Value)
			if e != nil {
				codes = append(codes, "source_import_invalid:"+r)
				continue
			}
			if domain && (name == "os" || name == "os/exec" || strings.HasPrefix(name, "net") || strings.Contains(name, "/internal/lifecycle") || strings.Contains(name, "/internal/hosts") || strings.Contains(name, "/internal/persistence") || strings.Contains(name, "/internal/compat") || strings.Contains(name, "/internal/management") || strings.Contains(name, "/internal/runtimecli")) {
				codes = append(codes, "domain_boundary_violation:"+r)
			}
			if name == "os/exec" && !(strings.HasPrefix(r, "internal/platform/") || strings.HasPrefix(r, "internal/compat/") || strings.HasPrefix(r, "internal/update/") || strings.HasPrefix(r, "internal/devtools/") || strings.HasPrefix(r, "internal/management/") || strings.HasPrefix(r, "internal/hosts/") || strings.HasPrefix(r, "internal/runtimecli/")) {
				codes = append(codes, "process_boundary_violation:"+r)
			}
		}
		return nil
	})
	return codes, e
}
func checkSecurity(root string) ([]string, any, error) {
	codes, e := checkBoundaries(root)
	if e != nil {
		return codes, nil, e
	}
	files, imports := 0, 0
	for _, rel := range []string{"src/opensocrates", "tools", "installer", "packaging/launchers"} {
		base := filepath.Join(root, rel)
		if _, e := os.Stat(base); e != nil {
			continue
		}
		e = filepath.WalkDir(base, func(p string, d os.DirEntry, e error) error {
			if e != nil {
				return e
			}
			if d.IsDir() {
				if d.Name() == "__pycache__" {
					return filepath.SkipDir
				}
				return nil
			}
			r, _ := filepath.Rel(root, p)
			r = filepath.ToSlash(r)
			ext := strings.ToLower(filepath.Ext(p))
			if ext == ".py" || ext == ".js" || ext == ".mjs" || ext == ".sh" || ext == ".ps1" {
				codes = append(codes, "active_first_party_non_go:"+r)
				return nil
			}
			if ext != ".go" || strings.HasSuffix(p, "_test.go") {
				return nil
			}
			files++
			f, e := parser.ParseFile(token.NewFileSet(), p, nil, 0)
			if e != nil {
				return e
			}
			imports += len(f.Imports)
			if strings.Contains(r, "/devtools/") {
				return nil
			}
			aliases := map[string]string{}
			for _, i := range f.Imports {
				n, _ := strconv.Unquote(i.Path.Value)
				alias := filepath.Base(n)
				if i.Name != nil {
					alias = i.Name.Name
				}
				aliases[alias] = n
				if n == "plugin" || (n == "unsafe" && !strings.Contains(r, "/platform/")) {
					codes = append(codes, "unsafe_runtime_dependency:"+r)
				}
			}
			ast.Inspect(f, func(n ast.Node) bool {
				call, ok := n.(*ast.CallExpr)
				if !ok {
					return true
				}
				sel, ok := call.Fun.(*ast.SelectorExpr)
				if !ok {
					return true
				}
				id, ok := sel.X.(*ast.Ident)
				if !ok {
					return true
				}
				pkg := aliases[id.Name]
				method := sel.Sel.Name
				if pkg == "os/exec" && (method == "Command" || method == "CommandContext") {
					for _, arg := range call.Args {
						literal, ok := arg.(*ast.BasicLit)
						if !ok || literal.Kind != token.STRING {
							continue
						}
						value, _ := strconv.Unquote(literal.Value)
						if value == "python" || value == "python3" || value == "node" || value == "npm" || value == "bash" || value == "sh" || value == "powershell" || value == "pwsh" {
							codes = append(codes, "first_party_interpreter_process:"+r)
						}
					}
				}
				if (pkg == "log" || pkg == "log/slog") && (method == "Print" || method == "Printf" || method == "Println" || method == "Info" || method == "Debug" || method == "Error" || method == "Warn") {
					for _, arg := range call.Args {
						if id, ok := arg.(*ast.Ident); ok {
							lower := strings.ToLower(id.Name)
							for _, private := range []string{"prompt", "transcript", "credential", "token", "auth", "envelope", "payload"} {
								if strings.Contains(lower, private) {
									codes = append(codes, "sensitive_diagnostic_argument:"+r)
								}
							}
						}
					}
				}
				return true
			})
			return nil
		})
		if e != nil {
			return codes, nil, e
		}
	}
	// Go module checks use the pinned, checksummed closure rather than ambient
	// tools. Replacement/local paths and unpinned versions never pass a release.
	mod, e := os.ReadFile(filepath.Join(root, "go.mod"))
	if e != nil {
		return codes, nil, e
	}
	if !regexp.MustCompile(`(?m)^module github\.com/ParkerHwang/OpenSocrates\s*$`).Match(mod) {
		codes = append(codes, "module_identity_invalid")
	}
	if !regexp.MustCompile(`(?m)^go [0-9]+\.[0-9]+\.[0-9]+\s*$`).Match(mod) {
		codes = append(codes, "toolchain_patch_not_pinned")
	}
	if regexp.MustCompile(`(?m)^\s*(replace|exclude)\b`).Match(mod) {
		codes = append(codes, "module_dependency_override_forbidden")
	}
	deps := map[string]string{}
	inRequire := false
	for _, line := range strings.Split(string(mod), "\n") {
		line = strings.TrimSpace(line)
		if line == "require (" {
			inRequire = true
			continue
		}
		if line == ")" {
			inRequire = false
			continue
		}
		if strings.HasPrefix(line, "require ") {
			line = strings.TrimPrefix(line, "require ")
		} else if !inRequire {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) >= 2 {
			if !regexp.MustCompile(`^v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$`).MatchString(fields[1]) {
				codes = append(codes, "dependency_version_unpinned")
			}
			deps[fields[0]] = fields[1]
		}
	}
	if len(deps) > 0 {
		sum, e := os.ReadFile(filepath.Join(root, "go.sum"))
		if e != nil {
			return append(codes, "dependency_lock_missing"), nil, e
		}
		for name, version := range deps {
			if !strings.Contains(string(sum), name+" "+version+" h1:") || !strings.Contains(string(sum), name+" "+version+"/go.mod h1:") {
				codes = append(codes, "dependency_checksum_missing:"+name)
			}
		}
	}
	sbom, e := checkObject(filepath.Join(root, "build/evidence/sbom.json"))
	if e != nil {
		return append(codes, "sbom_evidence_unavailable"), nil, e
	}
	if sbom["bomFormat"] != "CycloneDX" || sbom["specVersion"] != "1.5" {
		codes = append(codes, "sbom_format_invalid")
	}
	components, ok := sbom["components"].([]any)
	if !ok || len(components) == 0 {
		codes = append(codes, "sbom_component_inventory_empty")
	}
	versions := map[string]string{}
	artifacts := map[string]string{}
	for _, raw := range components {
		c := obj(raw)
		name := str(c["name"])
		switch c["type"] {
		case "library":
			if _, exists := versions[name]; exists {
				codes = append(codes, "sbom_dependency_duplicate")
			}
			versions[name] = str(c["version"])
		case "file":
			if _, exists := artifacts[name]; exists {
				codes = append(codes, "sbom_file_duplicate")
			}
			hash := ""
			for _, h := range arr(c["hashes"]) {
				m := obj(h)
				if m["alg"] == "SHA-256" {
					hash = str(m["content"])
				}
			}
			artifacts[name] = hash
		default:
			codes = append(codes, "sbom_component_type_invalid")
		}
	}
	for name, version := range versions {
		if deps[name] != version {
			codes = append(codes, "sbom_unpinned_dependency:"+name)
		}
	}
	target := ""
	for _, property := range arr(obj(sbom["metadata"])["properties"]) {
		m := obj(property)
		if m["name"] == "opensocrates.target" {
			target = str(m["value"])
		}
	}
	if target != "darwin-arm64" && target != "windows-x64" {
		codes = append(codes, "sbom_target_invalid")
	}
	bundleRoot := filepath.Join(root, "dist/native", target)
	manifest, e := checkObject(filepath.Join(bundleRoot, "bundle-manifest.json"))
	if e != nil {
		return append(codes, "sbom_native_bundle_unavailable"), nil, e
	}
	expectedFiles := map[string]bool{}
	runtimeDependencies := map[string]string{}
	for _, raw := range arr(manifest["files"]) {
		entry := obj(raw)
		name := str(entry["path"])
		expectedFiles[name] = true
		p, e := safeCheckPath(bundleRoot, name)
		if e != nil {
			codes = append(codes, "sbom_file_path_invalid")
			continue
		}
		b, e := os.ReadFile(p)
		if e != nil {
			codes = append(codes, "sbom_file_missing")
			continue
		}
		if strings.HasPrefix(name, "bin/") {
			info, e := buildinfo.ReadFile(p)
			if e != nil {
				codes = append(codes, "native_binary_buildinfo_missing")
			} else {
				for _, module := range info.Deps {
					if module.Replace != nil {
						codes = append(codes, "native_binary_dependency_replaced")
					}
					runtimeDependencies[module.Path] = module.Version
				}
				settings := map[string]string{}
				for _, setting := range info.Settings {
					settings[setting.Key] = setting.Value
				}
				wantOS, wantArch := "darwin", "arm64"
				if target == "windows-x64" {
					wantOS, wantArch = "windows", "amd64"
				}
				if settings["GOOS"] != wantOS || settings["GOARCH"] != wantArch || settings["CGO_ENABLED"] != "0" {
					codes = append(codes, "native_binary_target_invalid")
				}
			}
		}
		h := sha256.Sum256(b)
		actual := hex.EncodeToString(h[:])
		if artifacts[name] != actual || strings.TrimPrefix(str(entry["sha256"]), "sha256:") != actual {
			codes = append(codes, "sbom_file_hash_mismatch:"+name)
		}
	}
	if len(artifacts) != len(expectedFiles) {
		codes = append(codes, "sbom_file_inventory_mismatch")
	}
	for name := range artifacts {
		if !expectedFiles[name] {
			codes = append(codes, "sbom_unlisted_file:"+name)
		}
	}
	for name, version := range runtimeDependencies {
		if versions[name] != version {
			codes = append(codes, "sbom_runtime_dependency_missing_or_mismatched:"+name)
		}
	}
	for name := range versions {
		if _, exists := runtimeDependencies[name]; !exists {
			codes = append(codes, "sbom_undeployed_dependency:"+name)
		}
	}

	return codes, map[string]any{"go_source_files_checked": files, "imports_checked": imports, "runtime_module_dependencies": len(deps), "sbom_file_count": len(artifacts), "live_evidence_claimed": false}, nil
}
