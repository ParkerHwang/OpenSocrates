package devtools

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

type CheckReport struct {
	Schema      string          `json:"schema"`
	Status      string          `json:"status"`
	GeneratedAt string          `json:"generated_at"`
	Checks      map[string]any  `json:"checks"`
	Errors      []string        `json:"error_codes"`
	Privacy     map[string]bool `json:"privacy"`
}
type checkOptions struct {
	root, event, report, packagePath, mode string
	paths                                  pathFlags
}
type pathFlags []string

func (p *pathFlags) String() string     { return strings.Join(*p, ",") }
func (p *pathFlags) Set(v string) error { *p = append(*p, v); return nil }

// RunChecks is the single native entry for source, package and governance gates.
// Unavailable evidence fails closed with exit 2; no gate claims live delivery.
func RunChecks(args []string, out, errout io.Writer) int {
	name := "all"
	if len(args) > 0 && !strings.HasPrefix(args[0], "-") {
		name = args[0]
		args = args[1:]
	}
	name = strings.TrimSuffix(name, "-check")
	if name == "security-scan" {
		name = "security"
	}
	o := checkOptions{}
	f := flag.NewFlagSet("check", flag.ContinueOnError)
	f.SetOutput(errout)
	f.StringVar(&o.root, "root", ".", "repository root")
	f.StringVar(&o.event, "event", "", "GitHub event JSON")
	f.StringVar(&o.report, "report", "", "evidence JSON")
	f.StringVar(&o.packagePath, "package", "", "package directory")
	f.StringVar(&o.mode, "mode", "committed", "adjudication evidence scope")
	f.Var(&o.paths, "path", "documentation file/directory (repeatable)")
	f.Bool("packages", false, "validate built native packages")
	if e := f.Parse(args); e != nil {
		return 2
	}
	if len(f.Args()) != 0 {
		fmt.Fprintln(errout, "check: unexpected arguments")
		return 2
	}
	root, e := filepath.Abs(o.root)
	if e != nil {
		return 2
	}
	o.root = root
	report := CheckReport{Schema: "opensocrates.go-check-evidence/1.0.0", Status: "pass", GeneratedAt: time.Now().UTC().Format(time.RFC3339), Checks: map[string]any{}, Errors: []string{}, Privacy: map[string]bool{"source_content_recorded": false, "absolute_paths_recorded": false, "environment_recorded": false}}
	names := []string{name}
	if name == "all" {
		names = []string{"generated", "content", "adjudication", "docs", "governance", "package", "security", "boundaries"}
	}
	unavailable := false
	for _, n := range names {
		var codes []string
		var detail any
		var e error
		switch n {
		case "generated", "generated-contract":
			codes, e = checkGenerated(o)
		case "content":
			codes, e = checkContent(o.root)
		case "adjudication":
			codes, e = checkAdjudication(o.root, o.mode)
		case "docs", "links":
			codes, detail, e = checkLinks(o.root, o.paths)
		case "governance":
			codes, e = checkGovernance(o.root, o.event)
		case "package", "package-docs", "windows", "macos-hosts", "content-hosts", "claude-host":
			codes, e = checkPackages(o.root, o.packagePath)
		case "security", "security-scan":
			codes, detail, e = checkSecurity(o.root)
		case "boundaries", "import-boundaries":
			codes, e = checkBoundaries(o.root)
		default:
			fmt.Fprintln(errout, "check: unknown gate", n)
			return 2
		}
		if e != nil {
			codes = append(codes, "evidence_unavailable")
			unavailable = true
		}
		sort.Strings(codes)
		report.Checks[n] = map[string]any{"status": statusOf(codes), "error_codes": codes, "detail": detail}
		for _, c := range codes {
			report.Errors = append(report.Errors, n+":"+c)
		}
	}
	if len(report.Errors) > 0 {
		report.Status = "fail"
	}
	if unavailable {
		report.Status = "unavailable"
	}
	sort.Strings(report.Errors)
	b, e := json.MarshalIndent(report, "", "  ")
	if e != nil {
		return 2
	}
	b = append(b, '\n')
	if o.report != "" {
		p := o.report
		if !filepath.IsAbs(p) {
			p = filepath.Join(o.root, p)
		}
		if e := os.MkdirAll(filepath.Dir(p), 0700); e != nil {
			return 2
		}
		if e := os.WriteFile(p, b, 0600); e != nil {
			return 2
		}
	}
	fmt.Fprintf(out, "%s-check: %s\n", name, strings.ToUpper(report.Status))
	for _, c := range report.Errors {
		fmt.Fprintln(errout, c)
	}
	if unavailable {
		return 2
	}
	if len(report.Errors) > 0 {
		return 1
	}
	return 0
}
func statusOf(codes []string) string {
	if len(codes) > 0 {
		return "fail"
	}
	return "pass"
}
func checkJSON(path string) (any, error) {
	b, e := os.ReadFile(path)
	if e != nil {
		return nil, e
	}
	return contracts.Decode(b)
}
func checkObject(path string) (map[string]any, error) {
	v, e := checkJSON(path)
	if e != nil {
		return nil, e
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, errors.New("object required")
	}
	return m, nil
}
func safeCheckPath(root, relative string) (string, error) {
	if relative == "" || strings.Contains(relative, "\\") || filepath.IsAbs(relative) {
		return "", errors.New("unsafe relative path")
	}
	p := filepath.Join(root, filepath.FromSlash(relative))
	rel, e := filepath.Rel(root, p)
	if e != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", errors.New("path escapes root")
	}
	return p, nil
}
func copyCheckTree(from, to string) error {
	return filepath.WalkDir(from, func(p string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		r, e := filepath.Rel(from, p)
		if e != nil {
			return e
		}
		dest := filepath.Join(to, r)
		if d.Type()&os.ModeSymlink != 0 {
			return errors.New("symlink source")
		}
		if d.IsDir() {
			return os.MkdirAll(dest, 0700)
		}
		b, e := os.ReadFile(p)
		if e != nil {
			return e
		}
		info, e := d.Info()
		if e != nil {
			return e
		}
		return os.WriteFile(dest, b, info.Mode().Perm())
	})
}
func compareCheckTree(a, b string) ([]string, error) {
	codes := []string{}
	names := map[string]bool{}
	for _, base := range []string{a, b} {
		e := filepath.WalkDir(base, func(p string, d os.DirEntry, e error) error {
			if e != nil {
				return e
			}
			if !d.IsDir() {
				r, e := filepath.Rel(base, p)
				if e != nil {
					return e
				}
				names[r] = true
			}
			return nil
		})
		if e != nil {
			return nil, e
		}
	}
	for r := range names {
		x, ex := os.ReadFile(filepath.Join(a, r))
		y, ey := os.ReadFile(filepath.Join(b, r))
		if ex != nil || ey != nil || !bytes.Equal(x, y) {
			codes = append(codes, "generated_mismatch:"+filepath.ToSlash(r))
		}
	}
	sort.Strings(codes)
	return codes, nil
}
func checkGenerated(o checkOptions) ([]string, error) {
	tmp, e := os.MkdirTemp("", "opensocrates-generated-check-")
	if e != nil {
		return nil, e
	}
	defer os.RemoveAll(tmp)
	for _, r := range []string{"content", "schemas/source", "config/update"} {
		if e = copyCheckTree(filepath.Join(o.root, r), filepath.Join(tmp, r)); e != nil {
			return nil, e
		}
	}
	bundle, e := checkObject(filepath.Join(o.root, "content/compiled-content.bundle.json"))
	if e != nil {
		return nil, e
	}
	version, _ := bundle["product_version"].(string)
	if e = GenerateContent(tmp, version); e != nil {
		return []string{"content_generation_failed"}, e
	}
	if e = GenerateSchemas(tmp); e != nil {
		return []string{"schema_generation_failed"}, e
	}
	if e = GenerateTrustConfig(tmp); e != nil {
		return []string{"trust_generation_failed"}, e
	}
	trustCodes := []string{}
	for _, name := range []string{"root.json", "identities.json"} {
		rel := filepath.Join("src/opensocrates/internal/update/trustconfig", name)
		x, ex := os.ReadFile(filepath.Join(o.root, rel))
		y, ey := os.ReadFile(filepath.Join(tmp, rel))
		if ex != nil || ey != nil || !bytes.Equal(x, y) {
			trustCodes = append(trustCodes, "generated_mismatch:"+filepath.ToSlash(rel))
		}
	}
	codes, e := compareCheckTree(filepath.Join(o.root, "schemas/v1"), filepath.Join(tmp, "schemas/v1"))
	if e != nil {
		return codes, e
	}
	codes = append(codes, trustCodes...)
	entries, e := os.ReadDir(filepath.Join(tmp, "content"))
	if e != nil {
		return codes, e
	}
	for _, d := range entries {
		if strings.HasPrefix(d.Name(), "compiled-") && strings.HasSuffix(d.Name(), ".json") {
			x, ex := os.ReadFile(filepath.Join(o.root, "content", d.Name()))
			y, ey := os.ReadFile(filepath.Join(tmp, "content", d.Name()))
			if ex != nil || ey != nil || !bytes.Equal(x, y) {
				codes = append(codes, "generated_mismatch:content/"+d.Name())
			}
		}
	}
	return codes, nil
}
