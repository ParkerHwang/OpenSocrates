package devtools

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
)

func manifestStrings(v any) []string {
	xs, _ := v.([]any)
	result := []string{}
	for _, x := range xs {
		if s, ok := x.(string); ok {
			result = append(result, s)
		}
	}
	return result
}
func checkPackages(root, selected string) ([]string, error) {
	paths := []string{}
	if selected != "" {
		if !filepath.IsAbs(selected) {
			selected = filepath.Join(root, selected)
		}
		paths = append(paths, selected)
	} else {
		for _, base := range []string{"build/generated/plugins", "build/generated/content-hosts", "dist"} {
			p := filepath.Join(root, base)
			if _, e := os.Stat(p); e != nil {
				continue
			}
			e := filepath.WalkDir(p, func(p string, d os.DirEntry, e error) error {
				if e != nil {
					return e
				}
				if !d.IsDir() && d.Name() == "release-manifest.json" {
					packageRoot := filepath.Dir(p)
					if m, er := checkObject(p); er == nil && m["host"] == "claude-chat" && filepath.Base(packageRoot) == "opensocrates" {
						packageRoot = filepath.Dir(packageRoot)
					}
					paths = append(paths, packageRoot)
				}
				return nil
			})
			if e != nil {
				return nil, e
			}
		}
	}
	if len(paths) == 0 {
		return []string{"generated_packages_missing"}, fmt.Errorf("packages unavailable")
	}
	codes := []string{}
	for _, p := range paths {
		found, e := checkPackageTree(p)
		codes = append(codes, found...)
		if e != nil {
			return codes, e
		}
	}
	return codes, nil
}
func checkPackageTree(p string) ([]string, error) {
	manifestRelative := "release-manifest.json"
	if _, e := os.Stat(filepath.Join(p, manifestRelative)); e != nil {
		manifestRelative = "opensocrates/release-manifest.json"
	}
	m, e := checkObject(filepath.Join(p, manifestRelative))
	if e != nil {
		return nil, e
	}
	host, _ := m["host"].(string)
	switch host {
	case "codex", "claude", "claude-chat", "antigravity":
	default:
		return []string{"package_host_invalid"}, nil
	}
	codes := []string{}
	version, _ := m["product_version"].(string)
	if !regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+$`).MatchString(version) {
		codes = append(codes, "package_version_invalid")
	}
	targets := manifestStrings(m["release_targets"])
	if host == "codex" || host == "claude" {
		validTarget := false
		if len(targets) == 1 {
			_, _, _, targetError := nativeBuildTarget(targets[0])
			validTarget = targetError == nil
		}
		if !validTarget || host == "claude" && targets[0] != "darwin-arm64" {
			codes = append(codes, "native_target_invalid")
		}
	}
	inventory, ok := m["files"].([]any)
	if !ok || len(inventory) == 0 {
		return append(codes, "package_inventory_missing"), nil
	}
	owned := map[string]bool{manifestRelative: true}
	for _, v := range inventory {
		entry, ok := v.(map[string]any)
		if !ok {
			codes = append(codes, "package_entry_invalid")
			continue
		}
		relative, _ := entry["path"].(string)
		if owned[relative] {
			codes = append(codes, "package_inventory_duplicate")
			continue
		}
		owned[relative] = true
		path, e := safeCheckPath(p, relative)
		if e != nil {
			codes = append(codes, "package_path_invalid")
			continue
		}
		info, e := os.Lstat(path)
		if e != nil {
			codes = append(codes, "package_file_missing:"+relative)
			continue
		}
		if !info.Mode().IsRegular() {
			codes = append(codes, "package_file_not_regular:"+relative)
			continue
		}
		b, e := os.ReadFile(path)
		if e != nil {
			return codes, e
		}
		expected, _ := entry["sha256"].(string)
		sum := sha256.Sum256(b)
		if strings.TrimPrefix(expected, "sha256:") != hex.EncodeToString(sum[:]) {
			codes = append(codes, "package_hash_mismatch:"+relative)
		}
		if permission, ok := schemaNumber(entry["mode"]); ok && runtime.GOOS != "windows" {
			if !permission.IsInt() || uint32(permission.Num().Int64()) != uint32(info.Mode().Perm()) {
				codes = append(codes, "package_mode_mismatch:"+relative)
			}
		}
		if size, ok := schemaNumber(entry["size"]); ok {
			if !size.IsInt() || size.Num().Int64() != info.Size() {
				codes = append(codes, "package_size_mismatch:"+relative)
			}
		}
		ext := strings.ToLower(filepath.Ext(relative))
		if ext == ".py" || ext == ".mjs" || ext == ".js" || ext == ".ps1" || ext == ".sh" {
			codes = append(codes, "non_go_package_executable:"+relative)
		}
		if (host == "claude-chat" || host == "antigravity") && (strings.HasPrefix(relative, "bin/") || strings.HasPrefix(relative, "runtime/") || strings.HasSuffix(relative, ".exe")) {
			codes = append(codes, "content_package_executable:"+relative)
		}
		if len(targets) == 1 && strings.HasPrefix(relative, "runtime/") {
			_, _, suffix, targetError := nativeBuildTarget(targets[0])
			if targetError != nil || relative != "runtime/"+targets[0]+"/opensocrates"+suffix || verifyGoBinary(path, targets[0]) != nil {
				codes = append(codes, "native_package_binary_target_invalid:"+relative)
			}
		}
	}
	e = filepath.WalkDir(p, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.Type()&os.ModeSymlink != 0 {
			codes = append(codes, "package_symlink_forbidden")
			return nil
		}
		if !d.IsDir() {
			r, e := filepath.Rel(p, path)
			if e != nil {
				return e
			}
			if !owned[filepath.ToSlash(r)] {
				codes = append(codes, "package_unlisted_file:"+filepath.ToSlash(r))
			}
		}
		return nil
	})
	if e != nil {
		return codes, e
	}
	readmeRelative := "README.md"
	if host == "claude-chat" || host == "antigravity" {
		readmeRelative = filepath.Join(str(m["skill_root"]), "README.md")
	}
	readme, e := os.ReadFile(filepath.Join(p, readmeRelative))
	if e != nil {
		return append(codes, "package_readme_missing"), nil
	}
	text := foldCheckText(string(readme))
	if host == "codex" || host == "claude" {
		codes = append(codes, packageClaimErrors(string(readme))...)
	}
	if host == "codex" {
		for _, phrase := range []string{"one-time interactive hook approval", "non-interactive `codex exec` silently skips untrusted hooks", "no live Codex hook-delivery receipt", "teacher questions"} {
			if !strings.Contains(text, foldCheckText(phrase)) {
				codes = append(codes, "codex_readme_boundary_missing")
			}
		}
	}
	for _, phrase := range []string{"validated on all platforms", "live delivery is validated", "signed and notarized", "hooks, project instructions, and session persistence disabled"} {
		if strings.Contains(text, phrase) {
			codes = append(codes, "readme_overclaim")
		}
	}
	if host == "codex" || host == "claude" {
		expectedShell := "posix"
		if len(targets) == 1 && windowsNativeTarget(targets[0]) {
			expectedShell = "powershell"
		}
		if m["shell_requirement"] != expectedShell {
			codes = append(codes, "native_hook_shell_requirement_invalid")
		}
		hooks, e := checkObject(filepath.Join(p, "hooks/hooks.json"))
		if e != nil {
			return append(codes, "native_hooks_missing"), nil
		}
		events, _ := hooks["hooks"].(map[string]any)
		for event, raw := range events {
			for _, handler := range arr(raw) {
				for _, rawCmd := range arr(obj(handler)["hooks"]) {
					c := obj(rawCmd)
					cmd := str(c["command"])
					target := ""
					if len(targets) == 1 {
						target = targets[0]
					}
					if !configuredHookMatches(cmd, host, target, event) {
						codes = append(codes, "native_hook_command_invalid")
					}
					if host == "codex" && event == "UserPromptSubmit" {
						if _, exists := c["timeout"]; exists {
							codes = append(codes, "codex_user_prompt_timeout_present")
						}
					}
					if host == "codex" && event == "SessionStart" && !schemaEqual(c["timeout"], jsonTwo) {
						codes = append(codes, "codex_session_timeout_invalid")
					}
				}
			}
		}
	}
	fixed, e := content.Load()
	if e != nil {
		return codes, e
	}
	canonical, ok := m["canonical_methods"].([]any)
	if !ok || len(canonical) != 48*len(releasedLocales) {
		codes = append(codes, "canonical_method_count_invalid")
	}
	methodLocales := map[string]bool{}
	for _, raw := range canonical {
		entry := obj(raw)
		id := str(entry["method_id"])
		locale := str(entry["locale"])
		key := id + ":" + locale
		if id == "" || !releasedLocale(locale) || methodLocales[key] {
			codes = append(codes, "canonical_method_identity_invalid")
		}
		methodLocales[key] = true
		relative := str(entry["path"])
		path, e := safeCheckPath(p, relative)
		if e != nil {
			codes = append(codes, "canonical_method_path_invalid")
			continue
		}
		b, e := os.ReadFile(path)
		if e != nil {
			codes = append(codes, "canonical_method_missing")
			continue
		}
		if str(entry["sha256"]) != digest(b) {
			codes = append(codes, "canonical_method_digest_invalid")
		}
		expected, e := fixed.Assemble([]string{id}, locale)
		if e != nil || string(b) != expected {
			codes = append(codes, "canonical_method_content_mismatch")
		}
	}
	if m["source_tree_hash"] != "sha256:e1e11f7a772cb2a3f6c8dc0e3b22b0787cdc903de69842de957577a177cee7be" || m["normalized_semantic_hash"] != "sha256:b5fc82f5ce8725bd23b7d270014f90853e39474e7b00ae4f20553a484524c659" {
		codes = append(codes, "package_released_content_identity_changed")
	}
	return codes, nil
}

var jsonTwo = json.Number("2")

func packageClaimErrors(text string) []string {
	patterns := map[string]string{
		"clean_machine_overclaim":     `(?i)\b(?:proves?|validates?|verifies?)\b.{0,24}\bclean[- ]machine(?:\s+installation)?\b`,
		"automatic_hook_overclaim":    `(?i)\bautomatic\b.{0,48}\bhook\s+delivery\b.{0,32}\b(?:is|was|has\s+been)?\s*(?:validated|verified|passed|working)\b`,
		"public_release_overclaim":    `(?i)\b(?:candidate|package|plugin|archive|release)\b.{0,40}\b(?:is|was|has\s+been)\s+(?:validated|verified|approved|ready)\b.{0,24}\b(?:as|for)\s+(?:a\s+)?public\s+release\b`,
		"signing_overclaim":           `(?i)\b(?:code\s+)?signing\b.{0,24}\b(?:is|was|has\s+been)?\s*(?:validated|verified|passed|complete)\b`,
		"universal_support_overclaim": `(?i)\b(?:fully|completely|universally)\s+(?:validated|supported|compatible)\b.{0,96}\b(?:all|every)\s+(?:codex\s+)?(?:surface|platform|environment)s?\b`,
		"platform_overclaim":          `(?i)\b(?:validated|supported|compatible)\b.{0,48}\b(?:across|on|for)\s+(?:all|every)\s+(?:codex\s+)?(?:surface|platform|environment)s?\b`,
		"endorsement_overclaim":       `(?i)\b(?:signed|notarized|approved|certified|endorsed)\s+by\s+(?:anthropic|openai|apple|claude)\b`,
		"managed_safety_overclaim":    `(?i)\b(?:(?:guaranteed|fully|completely|perfectly)\s+)?(?:safe|secure|isolated)\s+(?:on|in|for)\s+(?:all\s+)?(?:managed|enterprise|organization-managed)\s+(?:machines?|environments?|systems?)\b`,
	}
	found := map[string]bool{}
	negated := regexp.MustCompile(`(?i)(?:\bnot\b|\bnever\b|\bno\b|\bwithout\b|\bdoes\s+not\b|\bcannot\b)(?:\W+\w+){0,6}\W*$`)
	clauses := regexp.MustCompile(`(?i)[,;:]|\b(?:but|however|although|yet)\b`)
	for _, line := range strings.Split(text, "\n") {
		line = strings.Join(strings.Fields(line), " ")
		for code, pattern := range patterns {
			for _, match := range regexp.MustCompile(pattern).FindAllStringIndex(line, -1) {
				prefix := line[max(0, match[0]-96):match[0]]
				parts := clauses.Split(prefix, -1)
				claim := line[match[0]:match[1]]
				inlineNegated := regexp.MustCompile(`(?i)\b(?:not|never|no|without|cannot)\b`).MatchString(claim)
				if !negated.MatchString(parts[len(parts)-1]) && !inlineNegated {
					found[code] = true
				}
			}
		}
	}
	codes := []string{}
	for code := range found {
		codes = append(codes, "native_readme_"+code)
	}
	return codes
}
