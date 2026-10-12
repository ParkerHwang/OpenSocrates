package update

import (
	"bytes"
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/theupdateframework/go-tuf/v2/metadata"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

func bytesReader(b []byte) *bytes.Reader { return bytes.NewReader(b) }

// Transport requires HTTPS and explicit hosts. Redirects are checked again;
// github.com release redirects may go only to the named GitHub asset service.
type Transport struct {
	Context      context.Context
	AllowedHosts []string
	Client       *http.Client
	OnDownloaded func(string, []byte)
}

func (t *Transport) permitted(raw string) bool {
	u, e := url.Parse(raw)
	if e != nil || u.Scheme != "https" || u.User != nil || u.Fragment != "" || u.Port() != "" && u.Port() != "443" {
		return false
	}
	for _, h := range t.AllowedHosts {
		if strings.EqualFold(u.Hostname(), h) {
			return true
		}
	}
	return false
}
func (t *Transport) DownloadFile(raw string, max int64, _ time.Duration) ([]byte, error) {
	if !t.permitted(raw) || max <= 0 || max > MaxArchiveSize {
		return nil, closed(diagnostics.Verification, "transport")
	}
	ctx := t.Context
	if ctx == nil {
		ctx = context.Background()
	}
	ctx, cancel := context.WithTimeout(ctx, 45*time.Second)
	defer cancel()
	client := http.Client{Timeout: 45 * time.Second}
	if t.Client != nil {
		client = *t.Client
	}
	client.CheckRedirect = func(req *http.Request, via []*http.Request) error {
		if len(via) > 3 || !t.permitted(req.URL.String()) {
			return closed(diagnostics.Verification, "transport")
		}
		return nil
	}
	req, e := http.NewRequestWithContext(ctx, http.MethodGet, raw, nil)
	if e != nil {
		return nil, closed(diagnostics.Network, "transport")
	}
	req.Header.Set("User-Agent", "OpenSocrates-native-update/1.6")
	res, e := client.Do(req)
	if e != nil {
		return nil, closed(diagnostics.Network, "transport")
	}
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK {
		return nil, &metadata.ErrDownloadHTTP{StatusCode: res.StatusCode}
	}
	if res.ContentLength > max {
		return nil, closed(diagnostics.Verification, "transport")
	}
	b, e := io.ReadAll(io.LimitReader(res.Body, max+1))
	if e != nil {
		return nil, closed(diagnostics.Network, "transport")
	}
	if int64(len(b)) > max {
		return nil, closed(diagnostics.Verification, "transport")
	}
	if t.OnDownloaded != nil {
		t.OnDownloaded(raw, b)
	}
	return b, nil
}
