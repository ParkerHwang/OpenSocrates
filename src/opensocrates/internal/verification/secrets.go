package verification

import (
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode"
)

type SecretFinding struct {
	Kind string
	Path []string
	Code string
}

var forbiddenKeys = strings.Fields("prompt prompts transcript transcript_path messages conversation reasoning rationale_internal thought thoughts chain_of_thought raw raw_input raw_output tool_input tool_output tool_response stdout stderr command environment env cookie authorization password passwd secret token api_key private_key credentials")
var secretQueryKeys = strings.Fields("key api_key apikey access_token auth authorization credential password passwd secret token sig signature")
var patterns = []struct {
	code    string
	pattern *regexp.Regexp
}{
	{"pem_private_key", regexp.MustCompile(`-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----`)},
	{"authorization_header", regexp.MustCompile(`(?i)\b(authorization|cookie)\s*[:=]\s*(bearer|basic)\s+\S+`)},
	{"bearer_token", regexp.MustCompile(`(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}`)},
	{"known_token_prefix", regexp.MustCompile(`(?i)\b(sk|rk|pk|ghp|github_pat|glpat|xox[baprs]-|npm|pypi)[_-][A-Za-z0-9._~+/=-]{12,}`)},
	{"cloud_access_key", regexp.MustCompile(`\b(AKIA|ASIA)[A-Z0-9]{16}\b`)},
	{"database_credentials", regexp.MustCompile(`(?i)\b(postgres(ql)?|mysql|mariadb|mongodb(\+srv)?|redis)://[^\s/:@]+:[^\s/@]+@`)},
	{"secret_assignment", regexp.MustCompile(`(?i)\b(api[_ -]?key|access[_ -]?token|password|passwd|secret)\s*[:=]\s*[^\s]{12,}`)},
}
var base64Run = regexp.MustCompile(`[A-Za-z0-9+/=_-]{49,}`)
var secretWord = regexp.MustCompile(`(?i)(secret|token|key|credential)`)
var textURLs = regexp.MustCompile(`(?i)https?://[^\s<>]+`)

func normalKey(s string) string {
	return strings.ReplaceAll(strings.ReplaceAll(strings.TrimSpace(cases.Fold().String(norm.NFKC.String(s))), "-", "_"), " ", "_")
}
func contains(items []string, s string) bool {
	for _, v := range items {
		if v == s {
			return true
		}
	}
	return false
}
func SecretFindings(value any) []SecretFinding       { return scan(value, false) }
func ForbiddenKeyFindings(value any) []SecretFinding { return scan(value, true) }
func scan(value any, keysOnly bool) []SecretFinding {
	found := []SecretFinding{}
	var visit func(any, []string, int)
	visit = func(item any, path []string, depth int) {
		add := func(kind, code string) { found = append(found, SecretFinding{kind, append([]string{}, path...), code}) }
		if depth > 12 {
			add("depth_limit", "json_depth")
			return
		}
		switch x := item.(type) {
		case string:
			if keysOnly {
				return
			}
			if strings.ContainsRune(x, 0) {
				add("invalid_text", "nul")
			} else {
				for _, r := range x {
					if r < 32 && r != '\n' && r != '\t' {
						add("invalid_text", "control_character")
						break
					}
				}
			}
			for _, p := range patterns {
				if p.pattern.MatchString(x) {
					add("secret", p.code)
				}
			}
			if base64Run.MatchString(x) && secretWord.MatchString(x) {
				add("secret", "high_entropy_secret")
			}
			for _, candidate := range textURLs.FindAllString(x, -1) {
				candidate = strings.TrimRight(candidate, ".,;:)]}")
				u, e := url.Parse(candidate)
				if e != nil {
					add("unsafe_url", "invalid_url")
					break
				}
				if u.Hostname() == "" {
					add("unsafe_url", "unsupported_url")
					break
				}
				if u.User != nil {
					add("unsafe_url", "url_userinfo")
					break
				}
				for k := range u.Query() {
					if contains(secretQueryKeys, normalKey(k)) {
						add("unsafe_url", "credential_query")
					}
				}
			}
		case map[string]any:
			keys := make([]string, 0, len(x))
			for k := range x {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			for _, k := range keys {
				next := append(append([]string{}, path...), k)
				if keysOnly && contains(forbiddenKeys, normalKey(k)) {
					found = append(found, SecretFinding{"forbidden_key", next, "forbidden_key"})
				}
				visit(x[k], next, depth+1)
			}
		case []any:
			for i, c := range x {
				visit(c, append(append([]string{}, path...), strconv.Itoa(i)), depth+1)
			}
		case nil, bool, int, int64, float64, json.Number:
		default:
			add("unsupported_value", "unsupported_value")
		}
	}
	visit(value, []string{}, 0)
	return found
}
func SanitizePublicText(s string, max int) (string, error) {
	if len([]rune(s)) > max || strings.TrimSpace(s) == "" || !normText(s, true) {
		return "", contracts.ErrInvalid
	}
	for _, r := range s {
		if unicode.IsControl(r) && r != '\n' && r != '\t' {
			return "", contracts.ErrInvalid
		}
	}
	if len(SecretFindings(s)) > 0 {
		return "", contracts.ErrInvalid
	}
	return s, nil
}

// RejectPublic is the persistence admission boundary for public artifacts.
func RejectPublic(value any) error {
	if len(ForbiddenKeyFindings(value)) > 0 || len(SecretFindings(value)) > 0 {
		return contracts.ErrInvalid
	}
	return nil
}
