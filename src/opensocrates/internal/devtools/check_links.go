package devtools

import (
	"errors"
	"fmt"
	"golang.org/x/text/unicode/norm"
	"html"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode"
)

var linkExpressions = []*regexp.Regexp{regexp.MustCompile(`\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))`), regexp.MustCompile(`(?m)^\s{0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))`), regexp.MustCompile(`(?i)\bhref\s*=\s*["']([^"']+)["']`)}

func headingSlug(v string) string {
	v = regexp.MustCompile(`<[^>]+>`).ReplaceAllString(v, "")
	v = html.UnescapeString(strings.TrimSpace(strings.ToLower(v)))
	v = strings.NewReplacer("`", "", "*", "", "_", "", "~", "").Replace(v)
	v = norm.NFKD.String(v)
	var b strings.Builder
	space := false
	for _, r := range v {
		if unicode.Is(unicode.Mn, r) {
			continue
		}
		if unicode.IsSpace(r) || r == '-' {
			if b.Len() > 0 {
				space = true
			}
			continue
		}
		if unicode.IsLetter(r) || unicode.IsNumber(r) || r == '_' {
			if space {
				b.WriteByte('-')
				space = false
			}
			b.WriteRune(r)
		}
	}
	return strings.Trim(b.String(), "-")
}
func linkAnchors(path string) map[string]bool {
	b, e := os.ReadFile(path)
	if e != nil {
		return nil
	}
	anchors := map[string]bool{}
	counts := map[string]int{}
	re := regexp.MustCompile(`^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$`)
	for _, line := range strings.Split(string(b), "\n") {
		m := re.FindStringSubmatch(line)
		if len(m) < 2 {
			continue
		}
		slug := headingSlug(m[1])
		if slug == "" {
			continue
		}
		suffix := counts[slug]
		counts[slug]++
		if suffix > 0 {
			slug = fmt.Sprintf("%s-%d", slug, suffix)
		}
		anchors[slug] = true
	}
	for _, m := range regexp.MustCompile(`(?i)<(?:a|[a-z][a-z0-9]*)\b[^>]*\bid=["']([^"']+)["']`).FindAllStringSubmatch(string(b), -1) {
		id, _ := url.PathUnescape(m[1])
		anchors[strings.ToLower(id)] = true
	}
	return anchors
}
func checkLinks(root string, selected []string) ([]string, any, error) {
	absolute, e := filepath.Abs(root)
	if e != nil {
		return nil, nil, e
	}
	root, e = filepath.EvalSymlinks(absolute)
	if e != nil {
		return nil, nil, e
	}
	if len(selected) == 0 {
		selected = []string{"README.md", "README.ko.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", ".github/pull_request_template.md", ".github/release-notes", "docs/v1.6.0"}
	}
	files := map[string]bool{}
	for _, r := range selected {
		p, e := safeCheckPath(root, r)
		if e != nil {
			return nil, nil, e
		}
		e = filepath.WalkDir(p, func(p string, d os.DirEntry, e error) error {
			if e != nil {
				return e
			}
			ext := strings.ToLower(filepath.Ext(p))
			if !d.IsDir() && (ext == ".md" || ext == ".markdown" || ext == ".html" || ext == ".htm") {
				actual, e := filepath.EvalSymlinks(p)
				if e != nil {
					return e
				}
				if !linkPathWithinRoot(root, actual) {
					return errors.New("document_escapes_repository")
				}
				files[actual] = true
			}
			return nil
		})
		if e != nil {
			return nil, nil, e
		}
	}
	codes := []string{}
	checked, external := 0, 0
	for p := range files {
		b, e := os.ReadFile(p)
		if e != nil {
			return codes, nil, e
		}
		rel, _ := filepath.Rel(root, p)
		for _, re := range linkExpressions {
			for _, indices := range re.FindAllSubmatchIndex(b, -1) {
				start := indices[0]
				if start > 0 && b[start-1] == '!' {
					continue
				}
				target := ""
				for j := 2; j < len(indices); j += 2 {
					if indices[j] >= 0 {
						target = string(b[indices[j]:indices[j+1]])
						break
					}
				}
				target = html.UnescapeString(target)
				checked++
				u, e := url.Parse(target)
				line := strings.Count(string(b[:start]), "\n") + 1
				code := ""
				if e != nil {
					code = "link_invalid"
				} else if u.Scheme == "http" || u.Scheme == "https" || u.Scheme == "ftp" || u.Scheme == "mailto" || u.Scheme == "tel" || strings.HasPrefix(target, "//") {
					external++
					continue
				} else if u.Scheme != "" {
					code = "unsupported_link_scheme"
				} else {
					candidate := p
					if u.Path != "" {
						if strings.HasPrefix(u.Path, "/") {
							candidate = filepath.Join(root, filepath.FromSlash(strings.TrimPrefix(u.Path, "/")))
						} else {
							candidate = filepath.Join(filepath.Dir(p), filepath.FromSlash(u.Path))
						}
					}
					actual, e := filepath.EvalSymlinks(candidate)
					if !linkPathWithinRoot(root, candidate) {
						code = "link_escapes_repository"
					} else if e != nil {
						code = "target_missing"
					} else {
						if !linkPathWithinRoot(root, actual) {
							code = "link_escapes_repository"
						} else if u.Fragment != "" {
							ext := strings.ToLower(filepath.Ext(actual))
							if (ext == ".md" || ext == ".markdown" || ext == ".html" || ext == ".htm") && !linkAnchors(actual)[strings.ToLower(u.Fragment)] {
								code = "anchor_missing"
							}
						}
					}
				}
				if code != "" {
					codes = append(codes, fmt.Sprintf("%s:%d:%s", filepath.ToSlash(rel), line, code))
				}
			}
		}
	}
	sort.Strings(codes)
	return codes, map[string]any{"documents": len(files), "checked_links": checked, "external_links_not_fetched": external}, nil
}

func linkPathWithinRoot(root, path string) bool {
	relative, e := filepath.Rel(root, path)
	return e == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator))
}
