package verification

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"golang.org/x/text/unicode/norm"
	"net/netip"
	"net/url"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

func normText(s string, newline bool) bool {
	if !utf8.ValidString(s) || !norm.NFC.IsNormalString(s) {
		return false
	}
	for _, r := range s {
		if newline && r == '\n' {
			continue
		}
		if r <= 31 || r >= 127 && r <= 159 {
			return false
		}
	}
	return true
}
func ValidateScalarText(s string, max int, newline bool) error {
	if !normText(s, newline) || utf8.RuneCountInString(s) > max || strings.TrimSpace(s) == "" {
		return contracts.ErrInvalid
	}
	return nil
}
func EscapeInline(s string, semicolons bool) (string, error) {
	if e := ValidateScalarText(s, 1<<20, false); e != nil {
		return "", e
	}
	var b strings.Builder
	for _, r := range s {
		if strings.ContainsRune("\\`*_[]<>#", r) || semicolons && r == ';' {
			b.WriteRune('\\')
		}
		b.WriteRune(r)
	}
	return b.String(), nil
}
func UnescapeInline(s string) (string, error) {
	var b strings.Builder
	runes := []rune(s)
	for i := 0; i < len(runes); i++ {
		r := runes[i]
		if r == '\\' {
			i++
			if i >= len(runes) || !strings.ContainsRune("\\`*_[]<>;#", runes[i]) {
				return "", contracts.ErrInvalid
			}
			r = runes[i]
		}
		b.WriteRune(r)
	}
	result := b.String()
	return result, ValidateScalarText(result, 1<<20, false)
}
func InlineCode(s string) (string, error) {
	if e := ValidateScalarText(s, 1<<20, false); e != nil {
		return "", e
	}
	longest, current := 0, 0
	for _, r := range s {
		if r == '`' {
			current++
			if current > longest {
				longest = current
			}
		} else {
			current = 0
		}
	}
	fence := strings.Repeat("`", longest+1)
	if strings.TrimSpace(s) != s {
		return fence + " " + s + " " + fence, nil
	}
	return fence + s + fence, nil
}
func ParseInlineCode(s string) (string, error) {
	n := len(s) - len(strings.TrimLeft(s, "`"))
	if n < 1 || len(s) <= 2*n || !strings.HasSuffix(s, strings.Repeat("`", n)) {
		return "", contracts.ErrInvalid
	}
	body := s[n : len(s)-n]
	if len(body) >= 2 && strings.HasPrefix(body, " ") && strings.HasSuffix(body, " ") {
		body = body[1 : len(body)-1]
	}
	return body, ValidateScalarText(body, 1<<20, false)
}
func ValidatePublicURL(s string) error {
	if e := ValidateScalarText(s, 2048, false); e != nil {
		return e
	}
	for _, r := range s {
		if unicode.IsSpace(r) || strings.ContainsRune("\\<>", r) {
			return contracts.ErrInvalid
		}
	}
	u, e := url.Parse(s)
	if e != nil || u.Host == "" || u.Hostname() == "" || u.User != nil || (u.Scheme != "https" && u.Scheme != "http") {
		return contracts.ErrInvalid
	}
	host := strings.ToLower(u.Hostname())
	loopback := host == "localhost" || host == "127.0.0.1" || host == "::1"
	if u.Scheme == "http" && !loopback || u.Scheme == "https" && host == "localhost" {
		return contracts.ErrInvalid
	}
	if port := u.Port(); port != "" {
		n, e := strconv.Atoi(port)
		if e != nil || n < 0 || n > 65535 {
			return contracts.ErrInvalid
		}
	}
	if ip, e := netip.ParseAddr(host); e == nil {
		unsafe := ip.IsPrivate() || ip.IsLinkLocalUnicast() || ip.IsLoopback() || ip.IsUnspecified() || ip.IsMulticast()
		if unsafe && !(u.Scheme == "http" && ip.IsLoopback()) {
			return contracts.ErrInvalid
		}
	}
	keys := append(append([]string{}, secretQueryKeys...), "code", "session")
	for k := range u.Query() {
		if contains(keys, normalKey(k)) {
			return contracts.ErrInvalid
		}
	}
	return nil
}
func RenderLink(name, uri string) (string, error) {
	if e := ValidateScalarText(name, 200, false); e != nil {
		return "", e
	}
	if contains([]string{"click here", "here", "link"}, strings.ToLower(strings.TrimSpace(name))) {
		return "", contracts.ErrInvalid
	}
	if e := ValidatePublicURL(uri); e != nil {
		return "", e
	}
	escaped, e := EscapeInline(name, false)
	if e != nil {
		return "", e
	}
	if strings.ContainsAny(uri, ")\\") {
		uri = "<" + uri + ">"
	}
	return "[" + escaped + "](" + uri + ")", nil
}
func ParseLink(s string) (string, string, error) {
	end := strings.Index(s, "](")
	if !strings.HasPrefix(s, "[") || end <= 1 || !strings.HasSuffix(s, ")") {
		return "", "", contracts.ErrInvalid
	}
	name, e := UnescapeInline(s[1:end])
	if e != nil {
		return "", "", e
	}
	uri := s[end+2 : len(s)-1]
	if strings.HasPrefix(uri, "<") && strings.HasSuffix(uri, ">") {
		uri = uri[1 : len(uri)-1]
	}
	return name, uri, ValidatePublicURL(uri)
}
func ValidateCardMarkdown(s string) (string, error) {
	s = strings.ReplaceAll(s, "\r\n", "\n")
	if !normText(s, true) || utf8.RuneCountInString(s) > 2200 {
		return "", contracts.ErrInvalid
	}
	lines := 0
	for _, l := range strings.Split(s, "\n") {
		if strings.TrimSpace(l) != "" {
			lines++
		}
	}
	if lines > 14 {
		return "", contracts.ErrInvalid
	}
	return s, nil
}
