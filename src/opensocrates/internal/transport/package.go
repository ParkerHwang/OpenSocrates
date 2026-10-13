// Package transport verifies bounded native release archives and exact inventories.
package transport

import (
	"archive/zip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

const BundleSchema = "opensocrates.native-bundle/1.0.0"

type File struct {
	Path             string `json:"path"`
	SHA256           string `json:"sha256"`
	Mode             uint32 `json:"mode,omitempty"`
	Size             int64  `json:"size,omitempty"`
	hasMode, hasSize bool
}
type CanonicalMethod struct {
	Locale   string `json:"locale"`
	MethodID string `json:"method_id"`
	Path     string `json:"path"`
	SHA256   string `json:"sha256"`
}

func (row *CanonicalMethod) UnmarshalJSON(b []byte) error {
	value, e := contracts.Decode(b)
	if e != nil {
		return invalid("methods")
	}
	if _, e := contracts.Object(value, "locale", "method_id", "path", "sha256"); e != nil {
		return invalid("methods")
	}
	type plain CanonicalMethod
	var decoded plain
	if json.Unmarshal(b, &decoded) != nil {
		return invalid("methods")
	}
	*row = CanonicalMethod(decoded)
	return nil
}

type Manifest struct {
	Schema                 string            `json:"schema"`
	Host                   string            `json:"host"`
	ProductVersion         string            `json:"product_version"`
	ContentRevision        string            `json:"content_revision"`
	SourceTreeHash         string            `json:"source_tree_hash"`
	NormalizedSemanticHash string            `json:"normalized_semantic_hash"`
	Target                 string            `json:"target"`
	Files                  []File            `json:"files"`
	RuntimeTargets         []string          `json:"runtime_targets"`
	ReleaseTargets         []string          `json:"release_targets"`
	Launchers              []string          `json:"launchers"`
	MethodCount            int               `json:"method_count"`
	MethodIDs              []string          `json:"method_ids"`
	SkillRoot              string            `json:"skill_root"`
	PublicSkills           []string          `json:"public_skills"`
	CanonicalMethods       []CanonicalMethod `json:"canonical_methods"`
	SourceIdentity         map[string]string `json:"source_identity"`
}
type Package struct {
	Root           string
	BundleRoot     string
	Manifest       Manifest
	BundleManifest *Manifest
	ManifestPath   string
	Hashes         map[string]string
	cleanup        string
}

func (p *Package) Close() error {
	if p.cleanup != "" {
		return platform.RemoveTree(p.cleanup)
	}
	return nil
}
func invalid(stage string) error { return diagnostics.New(diagnostics.Verification, stage) }

var digestRE = regexp.MustCompile(`^(?:sha256:)?[a-f0-9]{64}$`)
var reservedNameRE = regexp.MustCompile(`^(COM|LPT)[1-9]$`)
var methodRE = regexp.MustCompile(`^[a-z0-9]+(?:-[a-z0-9]+)*$`)
var versionRE = regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+$`)

func Digest(s string) (string, error) {
	if !digestRE.MatchString(s) {
		return "", invalid("digest")
	}
	return strings.TrimPrefix(s, "sha256:"), nil
}
func SafeRelative(p string) bool {
	if p == "" || strings.ContainsAny(p, "\\\x00:\"<>|?*") || strings.HasPrefix(p, "/") || strings.HasSuffix(p, "/") {
		return false
	}
	for _, s := range strings.Split(p, "/") {
		if s == "" || s == "." || s == ".." || strings.TrimRight(s, " .") != s {
			return false
		}
		base := strings.ToUpper(strings.SplitN(s, ".", 2)[0])
		if base == "CON" || base == "PRN" || base == "AUX" || base == "NUL" || reservedNameRE.MatchString(base) {
			return false
		}
	}
	return true
}
func readManifest(root, path string) (Manifest, error) {
	b, e := platform.ReadOwnedFile(filepath.Join(root, filepath.FromSlash(path)), 8<<20)
	if e != nil {
		return Manifest{}, e
	}
	var m Manifest
	if _, e := contracts.Decode(b); e != nil {
		return m, invalid("manifest")
	}
	if json.Unmarshal(b, &m) != nil || len(m.Files) == 0 || len(m.Files) > lifecycle.MaxFiles || !versionRE.MatchString(m.ProductVersion) {
		return m, invalid("manifest")
	}
	return m, nil
}
func verifyInventory(root, path string, m Manifest) (map[string]string, error) {
	snapshot, e := lifecycle.Inspect(root)
	if e != nil {
		return nil, e
	}
	actual := map[string]string{}
	for _, row := range snapshot.Entries {
		if !row.Directory {
			actual[row.Path] = row.SHA256
		}
	}
	expected := map[string]string{}
	folded := map[string]bool{}
	for _, row := range m.Files {
		if !SafeRelative(row.Path) || row.Path == path || folded[strings.ToLower(row.Path)] {
			return nil, invalid("inventory")
		}
		hash, e := Digest(row.SHA256)
		if e != nil {
			return nil, e
		}
		expected[row.Path] = hash
		folded[strings.ToLower(row.Path)] = true
		if row.hasMode && runtime.GOOS != "windows" {
			for _, entry := range snapshot.Entries {
				if entry.Path == row.Path && entry.Mode != row.Mode {
					return nil, invalid("mode")
				}
			}
		}
		if row.hasSize {
			for _, entry := range snapshot.Entries {
				if entry.Path == row.Path && entry.Size != row.Size {
					return nil, invalid("size")
				}
			}
		}
	}
	if actual[path] == "" {
		return nil, invalid("manifest")
	}
	rest := map[string]string{}
	for p, h := range actual {
		if p != path {
			rest[p] = h
		}
	}
	if _, ok := rest["checksums.sha256"]; ok && expected["checksums.sha256"] == "" {
		b, e := platform.ReadOwnedFile(filepath.Join(root, "checksums.sha256"), 8<<20)
		if e != nil {
			return nil, e
		}
		checks := map[string]string{}
		for _, line := range strings.Split(strings.TrimSpace(string(b)), "\n") {
			parts := strings.SplitN(strings.TrimSuffix(line, "\r"), "  ", 2)
			if len(parts) != 2 || !SafeRelative(parts[1]) || checks[parts[1]] != "" {
				return nil, invalid("checksums")
			}
			h, e := Digest(parts[0])
			if e != nil {
				return nil, e
			}
			checks[parts[1]] = h
		}
		full := map[string]string{}
		for p, h := range actual {
			if p != "checksums.sha256" {
				full[p] = h
			}
		}
		if !equalHashes(full, checks) {
			return nil, invalid("checksums")
		}
		delete(rest, "checksums.sha256")
	}
	if !equalHashes(rest, expected) {
		return nil, invalid("inventory")
	}
	return actual, nil
}
func equalHashes(a, b map[string]string) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if b[k] != v {
			return false
		}
	}
	return true
}
func Verify(root, host, version, target string) (Package, error) {
	path := "release-manifest.json"
	if host == "claude-chat" {
		path = "opensocrates/release-manifest.json"
	}
	m, e := readManifest(root, path)
	if e != nil {
		return Package{}, e
	}
	if m.Host != host || (version != "" && m.ProductVersion != version) {
		return Package{}, invalid("identity")
	}
	hashes, e := verifyInventory(root, path, m)
	if e != nil {
		return Package{}, e
	}
	if m.MethodCount != 48 || len(m.MethodIDs) != 48 {
		return Package{}, invalid("methods")
	}
	seen := map[string]bool{}
	for _, id := range m.MethodIDs {
		if !methodRE.MatchString(id) || seen[id] {
			return Package{}, invalid("methods")
		}
		seen[id] = true
	}
	for _, hash := range []string{m.SourceTreeHash, m.NormalizedSemanticHash} {
		if _, e := Digest(hash); e != nil {
			return Package{}, e
		}
	}
	switch host {
	case "codex", "claude":
		if m.Schema != "opensocrates.plugin-release-manifest/1.0.0" {
			return Package{}, invalid("manifest")
		}
		if target != "" && (len(m.RuntimeTargets) != 1 || m.RuntimeTargets[0] != target || len(m.ReleaseTargets) != 1 || m.ReleaseTargets[0] != target) {
			return Package{}, diagnostics.New(diagnostics.Unsupported, "target")
		}
		if host == "claude" && (len(m.RuntimeTargets) != 1 || m.RuntimeTargets[0] != "darwin-arm64") {
			return Package{}, diagnostics.New(diagnostics.Unsupported, "target")
		}
		pluginPath := ".codex-plugin/plugin.json"
		if host == "claude" {
			pluginPath = ".claude-plugin/plugin.json"
		}
		b, e := platform.ReadOwnedFile(filepath.Join(root, pluginPath), 8<<20)
		if e != nil {
			return Package{}, e
		}
		var plugin struct {
			Name    string `json:"name"`
			Version string `json:"version"`
		}
		if json.Unmarshal(b, &plugin) != nil || plugin.Name != "opensocrates" || plugin.Version != m.ProductVersion {
			return Package{}, invalid("plugin")
		}
		if !completeMethods("skills/opensocrates", methodLocales(m.ProductVersion), seen, hashes) {
			return Package{}, invalid("methods")
		}
	case "antigravity", "claude-chat":
		if m.Schema != "opensocrates.content-host-manifest/1.0.0" || m.RuntimeTargets == nil || m.Launchers == nil || len(m.RuntimeTargets) != 0 || len(m.Launchers) != 0 || len(m.PublicSkills) != 1 || m.PublicSkills[0] != "opensocrates" {
			return Package{}, invalid("content-manifest")
		}
		skill := ".agents/skills/opensocrates"
		if host == "claude-chat" {
			skill = "opensocrates"
		}
		if m.SkillRoot != skill || m.SourceIdentity["canonical"] != m.SourceTreeHash {
			return Package{}, invalid("content-identity")
		}
		if _, e := Digest(m.SourceIdentity["templates"]); e != nil {
			return Package{}, e
		}
		locales := methodLocales(m.ProductVersion)
		if hashes[skill+"/SKILL.md"] == "" || len(m.CanonicalMethods) != len(locales)*m.MethodCount || !completeMethods(skill, locales, seen, hashes) {
			return Package{}, invalid("methods")
		}
		canonicalSeen := map[string]bool{}
		for _, row := range m.CanonicalMethods {
			p := skill + "/references/decision/methods/" + row.Locale + "/" + row.MethodID + ".md"
			h, e := Digest(row.SHA256)
			key := row.Locale + ":" + row.MethodID
			if e != nil || !seen[row.MethodID] || !contains(locales, row.Locale) || canonicalSeen[key] || row.Path != p || hashes[p] != h {
				return Package{}, invalid("methods")
			}
			canonicalSeen[key] = true
		}
		for p := range hashes {
			if host == "claude-chat" {
				if !strings.HasPrefix(p, "opensocrates/") {
					return Package{}, invalid("layout")
				}
			} else if p != path && p != ".agents/rules/opensocrates.md" && !strings.HasPrefix(p, skill+"/") {
				return Package{}, invalid("layout")
			}
			ext := strings.ToLower(filepath.Ext(p))
			switch ext {
			case ".exe", ".dll", ".com", ".cmd", ".bat", ".ps1", ".sh", ".mjs", ".js", ".py", ".pyc":
				return Package{}, invalid("executable-content")
			}
			for _, part := range strings.Split(p, "/") {
				if part == "runtime" || part == "bin" || part == "hooks" || part == ".claude-plugin" {
					return Package{}, invalid("executable-content")
				}
			}
		}
		contentSnapshot, e := lifecycle.Inspect(root)
		if e != nil {
			return Package{}, e
		}
		for _, row := range contentSnapshot.Entries {
			if !row.Directory && row.Mode&0111 != 0 {
				return Package{}, invalid("executable-content")
			}
		}
		if host == "antigravity" {
			b, e := platform.ReadOwnedFile(filepath.Join(root, ".agents/rules/opensocrates.md"), 4096)
			if e != nil || !strings.HasPrefix(string(b), "---\ntrigger: always_on\n") {
				return Package{}, invalid("rule")
			}
		}
	default:
		return Package{}, diagnostics.New(diagnostics.Unsupported, "host")
	}
	return Package{Root: root, Manifest: m, ManifestPath: path, Hashes: hashes}, nil
}

// Preserve the locale inventory from each released package generation:
// before v1.5.1 two languages, v1.5.1 four, v1.5.2 and newer ten.
func methodLocales(version string) []string {
	if versionAtLeast(version, "1.5.2") {
		return []string{"en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"}
	}
	if versionAtLeast(version, "1.5.1") {
		return []string{"en", "ko", "zh", "ja"}
	}
	return []string{"en", "ko"}
}

// Manifest versions have already passed versionRE. Decimal comparison avoids
// losing precision or overflowing on a valid numeric version component.
func versionAtLeast(version, baseline string) bool {
	parts, minimum := strings.Split(version, "."), strings.Split(baseline, ".")
	for i, part := range parts {
		part = strings.TrimLeft(part, "0")
		if part == "" {
			part = "0"
		}
		if len(part) != len(minimum[i]) {
			return len(part) > len(minimum[i])
		}
		if part != minimum[i] {
			return part > minimum[i]
		}
	}
	return true
}

// Inventory integrity alone cannot establish locale/method completeness: an
// internally consistent manifest could omit a language or substitute a method.
func completeMethods(skill string, locales []string, methods map[string]bool, hashes map[string]string) bool {
	prefix := skill + "/references/decision/methods/"
	expected := map[string]bool{}
	for _, locale := range locales {
		for id := range methods {
			path := prefix + locale + "/" + id + ".md"
			if hashes[path] == "" {
				return false
			}
			expected[path] = true
		}
	}
	for path := range hashes {
		if strings.HasPrefix(path, prefix) && !expected[path] {
			return false
		}
	}
	return true
}

func contains(a []string, s string) bool {
	for _, v := range a {
		if v == s {
			return true
		}
	}
	return false
}
func Prepare(source, host, version, target string) (Package, error) {
	if !filepath.IsAbs(source) {
		return Package{}, invalid("package")
	}
	if e := platform.GuardOwned(source); e != nil {
		return Package{}, e
	}
	info, e := os.Lstat(source)
	if e != nil {
		return Package{}, invalid("package")
	}
	root := source
	cleanup := ""
	if !info.IsDir() {
		parent, e := platform.MkdirTemp("", "opensocrates-package-")
		if e != nil {
			return Package{}, diagnostics.New(diagnostics.Permission, "stage")
		}
		cleanup = parent
		root = filepath.Join(parent, "payload")
		limits := platform.ArchiveLimits{MaxEntries: lifecycle.MaxFiles, MaxFileBytes: lifecycle.MaxFileBytes, MaxTotalBytes: lifecycle.MaxTotalBytes}
		if e := platform.ExtractArchive(source, root, limits); e != nil {
			platform.RemoveTree(parent)
			return Package{}, e
		}
	}
	fail := func(e error) (Package, error) {
		if cleanup != "" {
			platform.RemoveTree(cleanup)
		}
		return Package{}, e
	}
	// Accept the native release bundle, and exact legacy per-host archive nesting.
	bundlePath := "bundle-manifest.json"
	if _, e := os.Lstat(filepath.Join(root, bundlePath)); e == nil {
		m, e := readManifest(root, bundlePath)
		if e != nil {
			return fail(e)
		}
		if m.Schema != BundleSchema || m.Target != target || (version != "" && m.ProductVersion != version) {
			return fail(invalid("bundle"))
		}
		if _, e := verifyInventory(root, bundlePath, m); e != nil {
			return fail(e)
		}
		p, e := Verify(filepath.Join(root, "packages", host), host, m.ProductVersion, target)
		if e != nil {
			return fail(e)
		}
		p.BundleRoot = root
		p.BundleManifest = &m
		p.cleanup = cleanup
		return p, nil
	}
	p, e := Verify(root, host, version, target)
	if e != nil && host == "codex" {
		p, e = Verify(filepath.Join(root, "build/generated/plugins/codex"), host, version, target)
	}
	if e != nil {
		return fail(e)
	}
	p.cleanup = cleanup
	return p, nil
}

// Export writes a deterministic content-only account ZIP, without account upload.
func Export(p Package, target string) error {
	if p.Manifest.Host != "claude-chat" || !filepath.IsAbs(target) {
		return diagnostics.New(diagnostics.Unsupported, "export")
	}
	if e := platform.GuardOwned(target); e != nil {
		return e
	}
	if _, e := os.Lstat(target); e == nil {
		return invalid("export-collision")
	}
	keys := make([]string, 0, len(p.Hashes))
	for k := range p.Hashes {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	parent := filepath.Dir(target)
	if e := platform.Mkdir(parent); e != nil {
		return e
	}
	tmp, e := platform.CreateTemp(parent, ".opensocrates-export-")
	if e != nil {
		return diagnostics.New(diagnostics.Permission, "export")
	}
	name := tmp.Name()
	defer platform.Remove(name)
	z := zip.NewWriter(tmp)
	for _, path := range keys {
		b, e := platform.ReadOwnedFile(filepath.Join(p.Root, filepath.FromSlash(path)), lifecycle.MaxFileBytes)
		if e != nil {
			z.Close()
			tmp.Close()
			return e
		}
		h := sha256.Sum256(b)
		if hex.EncodeToString(h[:]) != p.Hashes[path] {
			z.Close()
			tmp.Close()
			return invalid("export")
		}
		header := &zip.FileHeader{Name: path, Method: zip.Deflate}
		header.SetMode(0644)
		w, e := z.CreateHeader(header)
		if e != nil {
			z.Close()
			tmp.Close()
			return invalid("export")
		}
		if _, e = w.Write(b); e != nil {
			z.Close()
			tmp.Close()
			return invalid("export")
		}
	}
	if e := z.Close(); e != nil {
		tmp.Close()
		return invalid("export")
	}
	if e := tmp.Sync(); e != nil {
		tmp.Close()
		return invalid("export")
	}
	if e := tmp.Close(); e != nil {
		return invalid("export")
	}
	return platform.Rename(name, target)
}

// VerifyBundle validates the whole immutable bundle before any pinned manager
// executable is used, including other profiles in its exact signed inventory.
func VerifyBundle(root, version, target string) (Manifest, error) {
	m, e := readManifest(root, "bundle-manifest.json")
	if e != nil {
		return m, e
	}
	if m.Schema != BundleSchema || m.Target != target || (version != "" && m.ProductVersion != version) {
		return m, invalid("bundle")
	}
	_, e = verifyInventory(root, "bundle-manifest.json", m)
	return m, e
}

// The released authored content_revision is an integer, while authenticated
// release identifiers may also be strings. Retain its exact integer precision
// for comparisons without changing the canonical package's JSON representation.
func (m *Manifest) UnmarshalJSON(b []byte) error {
	type plain Manifest
	var wire struct {
		*plain
		Revision json.RawMessage `json:"content_revision"`
	}
	wire.plain = (*plain)(m)
	if e := json.Unmarshal(b, &wire); e != nil {
		return e
	}
	if len(wire.Revision) == 0 || string(wire.Revision) == "null" {
		return invalid("content-revision")
	}
	value, e := contracts.Decode(wire.Revision)
	if e != nil {
		return invalid("content-revision")
	}
	if s, ok := value.(string); ok {
		if s == "" {
			return invalid("content-revision")
		}
		m.ContentRevision = s
		return nil
	}
	n, ok := contracts.Integer(value)
	if !ok || n.Sign() < 0 {
		return invalid("content-revision")
	}
	m.ContentRevision = n.String()
	return nil
}

func (f *File) UnmarshalJSON(b []byte) error {
	type plain File
	var wire plain
	if e := json.Unmarshal(b, &wire); e != nil {
		return e
	}
	var fields map[string]json.RawMessage
	if json.Unmarshal(b, &fields) != nil {
		return invalid("inventory")
	}
	*f = File(wire)
	if raw, ok := fields["mode"]; ok {
		value, e := contracts.Decode(raw)
		if e != nil {
			return invalid("mode")
		}
		mode, ok := contracts.Int(value)
		if !ok || mode < 0 || mode > 0777 || uint32(mode)&0022 != 0 {
			return invalid("mode")
		}
		f.hasMode = true
	}
	if raw, ok := fields["size"]; ok {
		value, e := contracts.Decode(raw)
		if e != nil {
			return invalid("size")
		}
		size, ok := contracts.Int(value)
		if !ok || size < 0 || size > lifecycle.MaxFileBytes {
			return invalid("size")
		}
		f.hasSize = true
	}
	return nil
}
