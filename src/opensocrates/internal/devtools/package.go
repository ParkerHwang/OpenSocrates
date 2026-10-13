package devtools

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
)

var tokenPattern = regexp.MustCompile(`\{\{([A-Z][A-Z0-9_]*)\}\}`)

func windowsNativeTarget(target string) bool {
	return target == "windows-x64" || target == "windows-arm64"
}

// nativeBuildTarget is the closed first-party release matrix. Windows x64 is
// named explicitly for backward compatibility; native ARM64 is a separate asset.
func nativeBuildTarget(target string) (goos, arch, suffix string, err error) {
	switch target {
	case "darwin-arm64":
		return "darwin", "arm64", "", nil
	case "windows-x64":
		return "windows", "amd64", ".exe", nil
	case "windows-arm64":
		return "windows", "arm64", ".exe", nil
	default:
		return "", "", "", fmt.Errorf("unsupported native target")
	}
}

func specializeNativeCommands(text, host, target string) string {
	binary := "runtime/" + target + "/opensocrates"
	if windowsNativeTarget(target) {
		binary += ".exe"
	}
	root := "$PLUGIN_ROOT"
	if host == "claude" {
		root = "$CLAUDE_PLUGIN_ROOT"
	}
	if windowsNativeTarget(target) {
		root = "$env:PLUGIN_ROOT"
	}
	for _, prefix := range []string{"${PLUGIN_ROOT}", "${CLAUDE_PLUGIN_ROOT}"} {
		text = strings.ReplaceAll(text, prefix+"/bin/launch.sh", "\""+root+"/"+binary+"\"")
	}
	text = strings.ReplaceAll(text, "bin/launch.sh", "\"./"+binary+"\"")
	text = strings.ReplaceAll(text, "python -m opensocrates decision", "\"./"+binary+"\" decision")
	for _, wrapperHost := range []string{"codex", "claude", "<host>"} {
		text = strings.ReplaceAll(text, "\" decision "+wrapperHost, "\" decision")
		text = strings.ReplaceAll(text, "\" locale "+wrapperHost, "\" locale")
	}
	text = strings.ReplaceAll(text, "source CLI is", "native CLI is")
	text = strings.ReplaceAll(text, "The source\nCLI is", "The native\nCLI is")
	text = strings.ReplaceAll(text, "소스 CLI는", "네이티브 CLI는")
	if windowsNativeTarget(target) {
		text = strings.ReplaceAll(text, "`\"./"+binary+"\" ", "`& \"./"+binary+"\" ")
		text = strings.ReplaceAll(text, "`\""+root+"/"+binary+"\" ", "`& \""+root+"/"+binary+"\" ")
	}
	return text
}
func packageSourceInventory(root, host string) ([]any, error) {
	paths := map[string]bool{}
	bases := []string{"plugin-src/" + host, "plugin-src/shared"}
	if host == "antigravity" {
		bases = append(bases, "plugin-src/claude-chat")
	}
	for _, base := range bases {
		if e := filepath.WalkDir(filepath.Join(root, base), func(p string, d os.DirEntry, e error) error {
			if e != nil {
				return e
			}
			if !d.IsDir() {
				r, _ := filepath.Rel(root, p)
				paths[filepath.ToSlash(r)] = true
			}
			return nil
		}); e != nil {
			return nil, e
		}
	}
	for _, name := range []string{"generation.go", "content.go", "content_validation.go", "content_locales.go", "content_yaml.go", "schema.go", "package.go", "package_reference.go"} {
		paths["src/opensocrates/internal/devtools/"+name] = true
	}
	keys := []string{}
	for path := range paths {
		keys = append(keys, path)
	}
	sort.Strings(keys)
	sources := []any{}
	for _, path := range keys {
		b, e := regularRead(root, path)
		if e != nil {
			return nil, e
		}
		sources = append(sources, map[string]any{"path": path, "sha256": digest(b)})
	}
	return sources, nil
}
func render(text string, values map[string]string) (string, error) {
	var failure error
	r := tokenPattern.ReplaceAllStringFunc(text, func(token string) string {
		k := token[2 : len(token)-2]
		v, ok := values[k]
		if !ok {
			failure = fmt.Errorf("unknown template token %s", k)
			return token
		}
		return v
	})
	return markdown(r), failure
}
func safeRelative(path string) bool {
	return path != "" && !filepath.IsAbs(path) && !strings.ContainsAny(path, "\\:\x00") && filepath.ToSlash(filepath.Clean(path)) == path && path != "." && path != ".." && !strings.HasPrefix(path, "../")
}
func regularRead(root, path string) ([]byte, error) {
	if !safeRelative(path) {
		return nil, fmt.Errorf("unsafe package path")
	}
	full := filepath.Join(root, filepath.FromSlash(path))
	rel := path
	for {
		info, e := os.Lstat(filepath.Join(root, filepath.FromSlash(rel)))
		if e != nil {
			return nil, e
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return nil, fmt.Errorf("linked package input")
		}
		parent := filepath.ToSlash(filepath.Dir(rel))
		if parent == "." {
			break
		}
		rel = parent
	}
	info, e := os.Lstat(full)
	if e != nil {
		return nil, e
	}
	if !info.Mode().IsRegular() {
		return nil, fmt.Errorf("nonregular package input")
	}
	return os.ReadFile(full)
}
func readTemplate(root, relative string, values map[string]string) ([]byte, error) {
	b, e := regularRead(root, relative)
	if e != nil {
		return nil, e
	}
	r, e := render(string(b), values)
	return []byte(r), e
}
func copyPackageTree(root, source, output string, files map[string][]byte) error {
	return filepath.WalkDir(filepath.Join(root, filepath.FromSlash(source)), func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("linked package source")
		}
		if d.IsDir() {
			return nil
		}
		rel, _ := filepath.Rel(filepath.Join(root, filepath.FromSlash(source)), p)
		b, e := regularRead(root, filepath.ToSlash(filepath.Join(source, rel)))
		if e != nil {
			return e
		}
		files[filepath.ToSlash(filepath.Join(output, rel))] = b
		return nil
	})
}
func responseText(policy map[string]any, locale string) string {
	entry := obj(obj(policy["locales"])[locale])
	heading := "Guided presentation policy"
	boundary := "Guided only: no automatic rewrite, verified compliance, length cap or required-content removal."
	if locale == "ko" {
		heading = "작성 단계의 표현 안내"
		boundary = "작성 안내만 제공합니다. 자동 재작성·검증된 준수·길이 상한·필수 내용 삭제를 뜻하지 않습니다."
	}
	if locale == "zh" {
		heading = "写作表达指导"
		boundary = "仅提供指导：不自动改写，不表示已验证合规，不设长度上限，也不删除必需内容。"
	} else if locale == "ja" {
		heading = "表現の作成ガイド"
		boundary = "作成の指針のみです。自動書き換え、遵守の検証、長さの上限、必須内容の削除を意味しません。"
	}
	identity := digest([]byte(jsonToken(policy)))
	lines := []string{"### " + heading, fmt.Sprintf("Profile: %s; revision %s; %s", str(entry["profile_id"]), jsonToken(policy["revision"]), identity), boundary, str(entry["protected_rule"])}
	for _, r := range arr(entry["rules"]) {
		lines = append(lines, str(r))
	}
	for _, raw := range orderedKeys(obj(entry["shapes"])) {
		key := str(raw)
		lines = append(lines, "- "+key+": "+str(obj(entry["shapes"])[key]))
	}
	return strings.Join(lines, "\n\n")
}
func commonValues(bundle, policy map[string]any, host, target string) (map[string]string, error) {
	semantic, e := SemanticHash(bundle)
	if e != nil {
		return nil, e
	}
	if bundle["normalized_semantic_hash"] != semantic {
		return nil, fmt.Errorf("semantic identity mismatch")
	}
	values := map[string]string{"HOST": host, "PRODUCT_VERSION": str(bundle["product_version"]), "CONTENT_REVISION": jsonToken(bundle["content_revision"]), "SOURCE_TREE_HASH": str(bundle["source_tree_hash"]), "SEMANTIC_HASH": semantic, "SEMANTIC_PROJECTION_HASH": semantic, "METHOD_COUNT": "48", "TEMPLATE_REVISION": "1", "PACKAGE_RELEASE_TARGET": target, "PACKAGE_LAUNCHER_PATH": "runtime/" + target + "/opensocrates", "PACKAGE_RELEASE_BOUNDARY": "Native Go runtime; installation and execution require no Python, Node.js, npm or Go toolchain."}
	for _, key := range []string{"method_ids", "methods", "locale_messages", "prompt_fragments", "policy_versions"} {
		values[strings.ToUpper(key)+"_JSON"] = jsonToken(bundle[key])
	}
	for k, v := range obj(bundle["prompt_fragments"]) {
		for _, locale := range releasedLocales {
			text := str(obj(v)[locale])
			values["FRAGMENT_"+strings.ToUpper(k)+"_"+strings.ToUpper(locale)] = text
			if k == "controller" || k == "capability_notice" {
				values[strings.ToUpper(k)+"_"+strings.ToUpper(locale)] = text
				values[strings.ToUpper(k)+"_"+strings.ToUpper(locale)+"_JSON"] = jsonToken(text)
			}
		}
	}
	for _, locale := range releasedLocales {
		values["RESPONSE_POLICY_"+strings.ToUpper(locale)] = responseText(policy, locale)
		values["LOCALE_MESSAGES_"+strings.ToUpper(locale)+"_JSON"] = jsonToken(obj(bundle["locale_messages"])[locale])
	}
	values["RESPONSE_POLICY_JSON"] = jsonToken(policy)
	values["RESPONSE_POLICY_SHA_JSON"] = jsonToken(digest([]byte(jsonToken(policy))))
	values["METHOD_REFERENCE_INDEX"] = methodIndex(arr(bundle["methods"]))
	if windowsNativeTarget(target) {
		values["PACKAGE_LAUNCHER_PATH"] += ".exe"
	}
	return values, nil
}
func methodIndex(methods []any) string {
	sections := []string{}
	for _, raw := range methods {
		m := obj(raw)
		id := str(m["id"])
		sections = append(sections, fmt.Sprintf("## `%s` — %s\n\n- Korean name: %s\n- 中文名称: %s\n- 日本語名: %s\n- Family: `%s`\n- Use for: %s\n- 한국어: %s\n- 简体中文: %s\n- 日本語: %s\n- Routing metadata: `%s`\n- Procedure: [methods/%s.md](methods/%s.md)\n", id, str(obj(m["display_name"])["en"]), str(obj(m["display_name"])["ko"]), str(obj(m["display_name"])["zh"]), str(obj(m["display_name"])["ja"]), str(m["family"]), str(obj(m["plain_action"])["en"]), str(obj(m["plain_action"])["ko"]), str(obj(m["plain_action"])["zh"]), str(obj(m["plain_action"])["ja"]), jsonToken(m["routing"]), id, id))
	}
	return strings.TrimRight(strings.Join(sections, "\n"), "\n")
}
func methodValues(method map[string]any, common map[string]string) map[string]string {
	v := map[string]string{}
	for k, x := range common {
		v[k] = x
	}
	v["METHOD_ID"] = str(method["id"])
	v["METHOD_FAMILY"] = str(method["family"])
	for key, token := range map[string]string{"display_name": "DISPLAY_NAME", "plain_action": "PLAIN_ACTION", "procedure": "PROCEDURE", "complement_fragment": "COMPLEMENT"} {
		for _, locale := range releasedLocales {
			v["METHOD_"+token+"_"+strings.ToUpper(locale)] = str(obj(method[key])[locale])
		}
	}
	for _, key := range []string{"participation", "routing", "output_contract", "complements"} {
		v["METHOD_"+strings.ToUpper(key)+"_JSON"] = jsonToken(method[key])
	}
	return v
}

func nativeHooks(host, target string) map[string]any {
	prefix := "$PLUGIN_ROOT"
	events := []string{"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd"}
	normalized := map[string]string{"SessionStart": "session_started", "UserPromptSubmit": "user_prompt_submitted", "PreToolUse": "tool_succeeded", "PostToolUse": "tool_succeeded", "PreCompact": "pre_compaction", "Stop": "completion_candidate", "SessionEnd": "session_ended"}
	matchers := map[string]string{"SessionStart": "startup|resume|clear|compact", "PreToolUse": "Bash|apply_patch|mcp__.*", "PostToolUse": "Bash|apply_patch|mcp__.*", "PreCompact": "manual|auto", "SessionEnd": "other"}
	if host == "claude" {
		prefix = "$CLAUDE_PLUGIN_ROOT"
		events = []string{"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}
		matchers = map[string]string{"SessionStart": "startup|resume|clear|compact|fork"}
	}
	binary := prefix + "/runtime/" + target + "/opensocrates"
	invoker := ""
	if windowsNativeTarget(target) {
		binary = `$env:PLUGIN_ROOT\runtime\` + target + `\opensocrates.exe`
		invoker = "& "
	}
	hooks := map[string]any{}
	for _, event := range events {
		command := map[string]any{"type": "command", "command": invoker + "\"" + binary + "\" hook " + host + " " + normalized[event]}
		if event != "UserPromptSubmit" {
			timeout := 2
			if event == "Stop" || event == "SessionEnd" {
				timeout = 3
			}
			command["timeout"] = timeout
		}
		if host == "claude" {
			timeout := 3
			if event == "Stop" || event == "SessionEnd" {
				timeout = 1
			}
			command["timeout"] = timeout
		}
		entry := map[string]any{"hooks": []any{command}}
		if matcher := matchers[event]; matcher != "" {
			entry["matcher"] = matcher
		}
		hooks[event] = []any{entry}
	}
	return map[string]any{"hooks": hooks}
}

func GeneratePlugin(root, host, target, runtimeRoot, output string) (map[string]any, error) {
	if _, _, _, err := nativeBuildTarget(target); err != nil {
		return nil, err
	}
	if host != "codex" && host != "claude" && host != "antigravity" && host != "claude-chat" {
		return nil, fmt.Errorf("unsupported profile")
	}
	if host == "claude" && target != "darwin-arm64" {
		return nil, fmt.Errorf("native Claude Windows unavailable")
	}
	bundle, e := ReadObject(filepath.Join(root, "content/compiled-content.bundle.json"))
	if e != nil {
		return nil, e
	}
	policy, e := ReadObject(filepath.Join(root, "content/compiled-response-policy.json"))
	if e != nil {
		return nil, e
	}
	projections, e := ReadObject(filepath.Join(root, "content/compiled-reasoning-content.bundle.json"))
	if e != nil {
		return nil, e
	}
	values, e := commonValues(bundle, policy, host, target)
	if e != nil {
		return nil, e
	}
	files := map[string][]byte{}
	modes := map[string]os.FileMode{}
	manifestPath := "release-manifest.json"
	skill := "skills/opensocrates"
	contentOnly := host == "claude-chat" || host == "antigravity"
	if contentOnly {
		skill = "opensocrates"
		if host == "antigravity" {
			skill = ".agents/skills/opensocrates"
		} else {
			manifestPath = "opensocrates/release-manifest.json"
		}
		for dest, source := range map[string]string{"SKILL.md": "plugin-src/claude-chat/SKILL.md.tmpl", "README.md": "plugin-src/" + host + "/README.md.tmpl", "THIRD_PARTY_NOTICES.md": "plugin-src/claude-chat/THIRD_PARTY_NOTICES.md.tmpl"} {
			b, e := readTemplate(root, source, values)
			if e != nil {
				return nil, e
			}
			files[skill+"/"+dest] = b
		}
		for dest, source := range map[string]string{"LICENSE": "LICENSE", "references/decision/features.json": "plugin-src/shared/decision/features.json"} {
			b, e := regularRead(root, source)
			if e != nil {
				return nil, e
			}
			files[skill+"/"+dest] = b
		}
		for _, locale := range releasedLocales {
			for dest, source := range map[string]string{"reader": "plugin-src/shared/reader/guide.", "decision": "plugin-src/claude-chat/guide."} {
				b, e := regularRead(root, source+locale+".md")
				if e != nil {
					return nil, e
				}
				files[skill+"/references/"+dest+"/guide."+locale+".md"] = b
			}
		}
		if host == "antigravity" {
			b, e := readTemplate(root, "plugin-src/antigravity/rule.md.tmpl", values)
			if e != nil {
				return nil, e
			}
			if len(b) > 4096 || !strings.HasPrefix(string(b), "---\ntrigger: always_on\n") {
				return nil, fmt.Errorf("invalid Antigravity rule")
			}
			files[".agents/rules/opensocrates.md"] = b
		}
	} else {
		metadata, e := ReadObject(filepath.Join(root, "plugin-src", host, "generator.json"))
		if e != nil {
			return nil, e
		}
		values["HOOKS_JSON"] = jsonToken(nativeHooks(host, target))
		// Preserve the existing shared activation guidance without changing sources.
		for _, locale := range releasedLocales {
			guard, e := regularRead(root, "plugin-src/shared/rigor/activation."+locale+".md")
			if e != nil {
				return nil, e
			}
			key := "FRAGMENT_STRICT_SECOND_PASS_" + strings.ToUpper(locale)
			values[key] = strings.TrimSpace(string(guard)) + "\n\n" + values[key]
		}
		for _, pair := range [][2]string{{str(metadata["manifest_template"]), str(metadata["manifest_output"])}, {str(metadata["hooks_template"]), str(metadata["hooks_output"])}} {
			b, e := readTemplate(root, "plugin-src/"+host+"/"+pair[0], values)
			if e != nil {
				return nil, e
			}
			files[pair[1]] = b
		}
		for _, group := range []string{"shared_templates", "command_templates"} {
			for _, raw := range arr(metadata[group]) {
				item := obj(raw)
				b, e := readTemplate(root, "plugin-src/"+host+"/"+str(item["template"]), values)
				if e != nil {
					return nil, e
				}
				files[str(item["output"])] = b
			}
		}
		for _, raw := range arr(bundle["methods"]) {
			method := obj(raw)
			b, e := readTemplate(root, "plugin-src/"+host+"/"+str(metadata["method_template"]), methodValues(method, values))
			if e != nil {
				return nil, e
			}
			files[strings.ReplaceAll(str(metadata["method_output"]), "{method_id}", str(method["id"]))] = b
		}
		for _, raw := range arr(metadata["copy_files"]) {
			item := obj(raw)
			source := str(item["source"])
			dest := str(item["output"])
			if strings.HasPrefix(source, "packaging/launchers/") {
				continue
			}
			info, e := os.Lstat(filepath.Join(root, source))
			if e != nil {
				return nil, e
			}
			if info.IsDir() {
				if e = copyPackageTree(root, source, dest, files); e != nil {
					return nil, e
				}
			} else {
				b, e := regularRead(root, source)
				if e != nil {
					return nil, e
				}
				files[dest] = b
			}
		}
		for _, name := range []string{"compiled-content.bundle.json", "compiled-reasoning-content.bundle.json", "compiled-response-policy.json"} {
			b, e := regularRead(root, "content/"+name)
			if e != nil {
				return nil, e
			}
			files["content/"+name] = b
		}
		if runtimeRoot != "" {
			binary := "opensocrates"
			if windowsNativeTarget(target) {
				binary += ".exe"
			}
			b, e := regularRead(runtimeRoot, target+"/"+binary)
			if e != nil {
				return nil, e
			}
			path := "runtime/" + target + "/" + binary
			files[path] = b
			modes[path] = 0755
		}
		// Existing templates embed literal launcher paths; generated references point
		// straight at the native binary. No first-party shell/JS wrapper is shipped.
		for path, b := range files {
			if strings.HasSuffix(path, ".md") {
				files[path] = []byte(specializeNativeCommands(string(b), host, target))
			}
		}
	}
	canonical := []any{}
	for _, locale := range releasedLocales {
		catalogEntries := []any{}
		for _, raw := range arr(bundle["methods"]) {
			method := obj(raw)
			id := str(method["id"])
			instruction, e := assembleReference(projections, id, locale)
			if e != nil {
				return nil, e
			}
			relative := "methods/" + locale + "/" + id + ".md"
			path := skill + "/references/decision/" + relative
			files[path] = []byte(instruction)
			hash := digest([]byte(instruction))
			catalogEntries = append(catalogEntries, map[string]any{"id": id, "use_for": obj(method["plain_action"])[locale], "routing": method["routing"], "sha256": hash, "path": relative})
			canonical = append(canonical, map[string]any{"method_id": id, "locale": locale, "path": path, "sha256": hash})
		}
		data, e := Canonical(map[string]any{"content_revision": bundle["content_revision"], "locale": locale, "methods": catalogEntries, "evidence": "metadata_only"})
		if e != nil {
			return nil, e
		}
		files[skill+"/references/decision/catalog."+locale+".json"] = data
	}
	manifest := map[string]any{"schema": schema("plugin-release-manifest"), "host": host, "product_version": bundle["product_version"], "content_revision": bundle["content_revision"], "source_tree_hash": bundle["source_tree_hash"], "normalized_semantic_hash": bundle["normalized_semantic_hash"], "semantic_projection_hash": bundle["normalized_semantic_hash"], "semantic_projection_fields": semanticFields, "template_revision": "1", "method_count": 48, "method_ids": bundle["method_ids"], "release_targets": []string{target}, "launchers": []string{}, "runtime_targets": []string{}, "canonical_methods": canonical, "capability_evidence": map[string]any{"status": "unknown", "reason": "package generation is not live host delivery or application"}}
	if contentOnly {
		manifest["release_targets"] = []string{}
		manifest["schema"] = schema("content-host-manifest")
		manifest["skill_root"] = skill
		manifest["public_skills"] = []string{"opensocrates"}
		manifest["delivery"] = "account-skill"
		if host == "antigravity" {
			manifest["delivery"] = "modular-workspace"
		}
		manifest["source_identity"] = map[string]any{"canonical": bundle["source_tree_hash"], "templates": digest([]byte(jsonToken(values)))}
	} else {
		manifest["launcher_host"] = host
		manifest["shell_requirement"] = "posix"
		if windowsNativeTarget(target) {
			manifest["shell_requirement"] = "powershell"
		}
		if runtimeRoot != "" {
			manifest["runtime_targets"] = []string{target}
			manifest["launchers"] = []string{values["PACKAGE_LAUNCHER_PATH"]}
		}
	}
	sources, e := packageSourceInventory(root, host)
	if e != nil {
		return nil, e
	}
	manifest["template_sources"] = sources
	manifest["source_identity"] = map[string]any{"canonical": bundle["source_tree_hash"], "templates": digest([]byte(jsonToken(sources)))}
	manifest["files"] = fileInventory(files, modes)
	data, e := Canonical(manifest)
	if e != nil {
		return nil, e
	}
	files[manifestPath] = data
	if output == "" {
		kind := "plugins"
		if contentOnly {
			kind = "content-hosts"
		}
		output = filepath.Join(root, "build/generated", kind, host)
	} else if !filepath.IsAbs(output) {
		output = filepath.Join(root, output)
	}
	if e = commitPackage(root, output, manifestPath, files, modes); e != nil {
		return nil, e
	}
	return manifest, nil
}

func fileInventory(files map[string][]byte, modes map[string]os.FileMode) []any {
	keys := []string{}
	for p := range files {
		keys = append(keys, p)
	}
	sort.Strings(keys)
	r := []any{}
	for _, p := range keys {
		mode := modes[p]
		if mode == 0 {
			mode = 0644
		}
		r = append(r, map[string]any{"path": p, "sha256": digest(files[p]), "size": len(files[p]), "mode": uint32(mode)})
	}
	return r
}
func commitPackage(root, output, manifest string, files map[string][]byte, modes map[string]os.FileMode) error {
	output, e := filepath.Abs(output)
	if e != nil {
		return e
	}
	root, _ = filepath.Abs(root)
	if output == root || output == string(filepath.Separator) {
		return fmt.Errorf("unsafe build destination")
	}
	for _, name := range []string{"src", "content", "schemas", "plugin-src", ".git", "tools", "docs"} {
		base := filepath.Join(root, name)
		if output == base || strings.HasPrefix(output, base+string(filepath.Separator)) {
			return fmt.Errorf("output overlaps source")
		}
	}
	if _, e = os.Lstat(output); e == nil {
		if _, e = VerifyPackage(output, manifest); e != nil {
			return fmt.Errorf("preserving unowned or modified output: %w", e)
		}
	} else if !os.IsNotExist(e) {
		return e
	}
	if e = os.MkdirAll(filepath.Dir(output), 0755); e != nil {
		return e
	}
	stage, e := os.MkdirTemp(filepath.Dir(output), ".native-stage-")
	if e != nil {
		return e
	}
	defer os.RemoveAll(stage)
	for path, b := range files {
		if !safeRelative(path) {
			return fmt.Errorf("unsafe inventory path")
		}
		mode := modes[path]
		if mode == 0 {
			mode = 0644
		}
		if e = writeData(filepath.Join(stage, filepath.FromSlash(path)), b, mode); e != nil {
			return e
		}
	}
	if _, e = VerifyPackage(stage, manifest); e != nil {
		return e
	}
	backup := stage + "-previous"
	if _, e = os.Stat(output); e == nil {
		if e = os.Rename(output, backup); e != nil {
			return e
		}
	}
	if e = os.Rename(stage, output); e != nil {
		if _, s := os.Stat(backup); s == nil {
			_ = os.Rename(backup, output)
		}
		return e
	}
	return os.RemoveAll(backup)
}

func VerifyPackage(root, manifestRelative string) (map[string]any, error) {
	rootInfo, rootError := os.Lstat(root)
	if rootError != nil || !rootInfo.IsDir() || rootInfo.Mode()&os.ModeSymlink != 0 {
		return nil, fmt.Errorf("package root must be regular directory")
	}
	b, e := regularRead(root, manifestRelative)
	if e != nil {
		return nil, e
	}
	v, e := ReadObject(filepath.Join(root, manifestRelative))
	if e != nil {
		return nil, e
	}
	canonical, e := Canonical(v)
	if e != nil || string(b) != string(canonical) {
		return nil, fmt.Errorf("noncanonical manifest")
	}
	seen := map[string]bool{manifestRelative: true}
	inventory := arr(v["files"])
	if len(inventory) == 0 {
		return nil, fmt.Errorf("missing inventory")
	}
	contentOnly := v["schema"] == schema("content-host-manifest")
	for _, raw := range inventory {
		entry := obj(raw)
		path := str(entry["path"])
		if !safeRelative(path) || seen[path] {
			return nil, fmt.Errorf("unsafe inventory member")
		}
		seen[path] = true
		data, e := regularRead(root, path)
		if e != nil || digest(data) != entry["sha256"] {
			return nil, fmt.Errorf("modified inventory member %s", path)
		}
		info, e := os.Stat(filepath.Join(root, filepath.FromSlash(path)))
		if e != nil {
			return nil, e
		}
		if contentOnly && info.Mode().Perm()&0111 != 0 {
			return nil, fmt.Errorf("executable content member")
		}
		if mode, ok := entry["mode"]; ok && runtime.GOOS != "windows" && jsonToken(mode) != fmt.Sprint(uint32(info.Mode().Perm())) {
			return nil, fmt.Errorf("modified inventory mode")
		}
		if size, ok := entry["size"]; ok && jsonToken(size) != fmt.Sprint(len(data)) {
			return nil, fmt.Errorf("inventory size mismatch")
		}
	}
	actual := 0
	e = filepath.WalkDir(root, func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("linked output")
		}
		if d.IsDir() {
			return nil
		}
		info, e := d.Info()
		if e != nil || !info.Mode().IsRegular() {
			return fmt.Errorf("nonregular output")
		}
		rel, _ := filepath.Rel(root, p)
		if !seen[filepath.ToSlash(rel)] {
			return fmt.Errorf("unexpected member")
		}
		actual++
		return nil
	})
	if e != nil {
		return nil, e
	}
	if actual != len(seen) {
		return nil, fmt.Errorf("incomplete inventory")
	}
	return v, nil
}
