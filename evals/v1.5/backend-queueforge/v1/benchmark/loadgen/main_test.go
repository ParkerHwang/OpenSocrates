package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestRequestErrorControls(t *testing.T) {
	client = &http.Client{Timeout: 20 * time.Millisecond, Transport: &http.Transport{Proxy: nil}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	cases := []struct {
		name, body string
		status     int
		delay      time.Duration
		want       string
	}{{"malformed", "{", 200, 0, "parse:"}, {"missing", "{}", 200, 0, "missing job"}, {"timeout", "{}", 200, 60 * time.Millisecond, "timeout"}, {"server_error", `{"error":{"code":"busy"}}`, 503, 0, ""}}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				time.Sleep(c.delay)
				w.WriteHeader(c.status)
				w.Write([]byte(c.body))
			}))
			defer srv.Close()
			_, status, err := request(srv.URL, "test", "GET", "/", nil)
			if c.name == "timeout" {
				if status != 0 || (!strings.Contains(err, "timeout") && !strings.Contains(err, "deadline")) {
					t.Fatalf("timeout control %d %s", status, err)
				}
				return
			}
			if status != c.status || !strings.Contains(err, c.want) {
				t.Fatalf("control %d %s", status, err)
			}
		})
	}
}
func TestPercentileEmptyAndKnown(t *testing.T) {
	if pct(nil, .99) != nil {
		t.Fatal("empty must be null")
	}
	if pct([]float64{9, 1, 5}, .5) != float64(5) {
		t.Fatal("known median")
	}
}
