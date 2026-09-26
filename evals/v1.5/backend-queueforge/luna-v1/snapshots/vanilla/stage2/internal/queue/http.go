package queue

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
)

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

type API struct{ S *Store }

func (a API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" && r.Method == "GET" {
		write(w, 200, map[string]any{"ok": true, "schema_version": 2})
		return
	}
	tenant := r.Header.Get("X-Tenant-ID")
	if !ident.MatchString(tenant) {
		fail(w, 400, "validation", "valid X-Tenant-ID is required")
		return
	}
	ctx := r.Context()
	p := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	var out any
	status := 200
	var e error
	switch {
	case r.Method == "POST" && r.URL.Path == "/v1/jobs":
		var x Input
		if !decode(w, r, &x) {
			return
		}
		x, e = validateInput(x)
		if e != nil {
			fail(w, 400, "validation", e.Error())
			return
		}
		out, status, e = a.submit(ctx, tenant, "jobs", r.Header.Get("Idempotency-Key"), []Input{x})
	case r.Method == "POST" && r.URL.Path == "/v1/jobs/batch":
		var x struct {
			Jobs []Input `json:"jobs"`
		}
		if !decode(w, r, &x) {
			return
		}
		if len(x.Jobs) < 1 || len(x.Jobs) > 100 {
			fail(w, 400, "validation", "jobs must contain 1 to 100 entries")
			return
		}
		for i := range x.Jobs {
			x.Jobs[i], e = validateInput(x.Jobs[i])
			if e != nil {
				fail(w, 400, "validation", e.Error())
				return
			}
		}
		out, status, e = a.submit(ctx, tenant, "batch", r.Header.Get("Idempotency-Key"), x.Jobs)
	case r.Method == "GET" && len(p) == 3 && p[0] == "v1" && p[1] == "jobs":
		var j Job
		j, e = a.S.Get(ctx, tenant, p[2])
		out = map[string]any{"job": j}
	case r.Method == "GET" && r.URL.Path == "/v1/jobs":
		q := r.URL.Query().Get("queue")
		if q != "" && !ident.MatchString(q) {
			fail(w, 400, "validation", "invalid queue")
			return
		}
		lim := 50
		if x := r.URL.Query().Get("limit"); x != "" {
			n, er := strconv.Atoi(x)
			if er != nil || n < 1 || n > 100 {
				fail(w, 400, "validation", "invalid limit")
				return
			}
			lim = n
		}
		var items []Job
		var next string
		items, next, e = a.S.List(ctx, tenant, q, lim, r.URL.Query().Get("cursor"))
		out = map[string]any{"items": items, "next_cursor": nil}
		if next != "" {
			out = map[string]any{"items": items, "next_cursor": next}
		}
	case r.Method == "POST" && len(p) == 4 && p[0] == "v1" && p[1] == "queues" && p[3] == "claim":
		if !ident.MatchString(p[2]) {
			fail(w, 400, "validation", "invalid queue")
			return
		}
		var x struct {
			Worker string `json:"worker_id"`
			Lease  int    `json:"lease_ms"`
		}
		if !decode(w, r, &x) {
			return
		}
		if !ident.MatchString(x.Worker) || x.Lease < 10 || x.Lease > 300000 {
			fail(w, 400, "validation", "invalid claim parameters")
			return
		}
		var j *Job
		var tok string
		j, tok, e = a.S.Claim(ctx, tenant, p[2], x.Worker, x.Lease)
		if j == nil && e == nil {
			out = map[string]any{"job": nil, "lease_token": nil, "lease_until_ms": nil}
		} else if j != nil {
			out = map[string]any{"job": j, "lease_token": tok, "lease_until_ms": j.LeaseUntil}
		}
	case r.Method == "POST" && len(p) == 4 && p[0] == "v1" && p[1] == "jobs":
		var token string
		var value json.RawMessage
		var ms int
		op := p[3]
		if op == "cancel" {
			var x map[string]json.RawMessage
			if !decode(w, r, &x) {
				return
			}
			if x == nil || len(x) != 0 {
				fail(w, 400, "validation", "cancel body must be empty object")
				return
			}
			var j Job
			j, e = a.S.Cancel(ctx, tenant, p[2])
			out = map[string]any{"job": j}
			break
		}
		switch op {
		case "heartbeat":
			var x struct {
				Token string `json:"lease_token"`
				Lease int    `json:"lease_ms"`
			}
			if !decode(w, r, &x) {
				return
			}
			token = x.Token
			ms = x.Lease
			if ms < 10 || ms > 300000 {
				fail(w, 400, "validation", "invalid lease_ms")
				return
			}
		case "complete":
			var x struct {
				Token  string          `json:"lease_token"`
				Result json.RawMessage `json:"result"`
			}
			if !decode(w, r, &x) {
				return
			}
			token = x.Token
			value = x.Result
			if !isObject(value) {
				fail(w, 400, "validation", "result must be an object")
				return
			}
		case "fail":
			var x struct {
				Token   string `json:"lease_token"`
				Message string `json:"error"`
			}
			if !decode(w, r, &x) {
				return
			}
			token = x.Token
			if len(x.Message) < 1 || len(x.Message) > 256 {
				fail(w, 400, "validation", "error must contain 1 to 256 characters")
				return
			}
			value, _ = json.Marshal(x.Message)
		default:
			fail(w, 404, "not_found", "not found")
			return
		}
		if token == "" {
			fail(w, 400, "validation", "lease_token required")
			return
		}
		var j Job
		j, e = a.S.Mutate(ctx, tenant, p[2], token, op, ms, value)
		out = map[string]any{"job": j}
	case r.Method == "GET" && r.URL.Path == "/v1/stats":
		q := r.URL.Query().Get("queue")
		if q != "" && !ident.MatchString(q) {
			fail(w, 400, "validation", "invalid queue")
			return
		}
		out, e = a.S.Stats(ctx, tenant, q)
	default:
		fail(w, 404, "not_found", "not found")
		return
	}
	if e != nil {
		switch {
		case errors.Is(e, ErrMissing):
			fail(w, 404, "not_found", "job not found")
		case errors.Is(e, ErrLease):
			fail(w, 409, "lease_conflict", "lease is no longer current")
		case errors.Is(e, ErrIdempotency):
			fail(w, 409, "idempotency_conflict", "idempotency key was used with different input")
		case errors.Is(e, ErrTransition):
			fail(w, 409, "invalid_transition", "invalid lifecycle transition")
		case errors.Is(e, ErrCapacity):
			fail(w, 429, "capacity", "tenant pending capacity reached")
		case errors.Is(e, ErrValidation):
			fail(w, 400, "validation", "invalid Idempotency-Key")
		default:
			fail(w, 503, "unavailable", "storage temporarily unavailable")
		}
		return
	}
	write(w, status, out)
}
func (a API) submit(ctx context.Context, t, ep, key string, in []Input) (any, int, error) {
	if len(key) < 1 || len(key) > 128 {
		return nil, 0, ErrValidation
	}
	for _, c := range key {
		if c < 33 || c > 126 {
			return nil, 0, ErrValidation
		}
	}
	jobs, replay, e := a.S.Submit(ctx, t, ep, key, in)
	if e != nil {
		return nil, 0, e
	}
	if ep == "jobs" {
		return map[string]any{"job": jobs[0], "replayed": replay}, map[bool]int{true: 200, false: 201}[replay], nil
	}
	return map[string]any{"jobs": jobs, "replayed": replay}, map[bool]int{true: 200, false: 201}[replay], nil
}

var ErrValidation = errors.New("validation")

func validateInput(x Input) (Input, error) {
	if !ident.MatchString(x.Queue) {
		return x, errors.New("invalid queue")
	}
	if !isObject(x.Payload) || len(x.Payload) > 16<<10 {
		return x, errors.New("payload must be an object of at most 16 KiB")
	}
	if x.Max == 0 {
		x.Max = 3
	}
	if x.Max < 1 || x.Max > 10 {
		return x, errors.New("max_attempts must be 1 to 10")
	}
	if x.Priority < -10 || x.Priority > 10 {
		return x, errors.New("priority must be -10 to 10")
	}
	if x.RunAt < 0 {
		return x, errors.New("run_at_ms must be nonnegative")
	}
	if !x.RetrySet {
		x.RetryBase = 1000
	}
	if x.RetryBase < 0 || x.RetryBase > 60000 {
		return x, errors.New("retry_base_ms must be 0 to 60000")
	}
	return x, nil
}
func isObject(b []byte) bool {
	var x map[string]json.RawMessage
	if len(b) == 0 || json.Unmarshal(b, &x) != nil || x == nil {
		return false
	}
	return true
}
func decode(w http.ResponseWriter, r *http.Request, v any) bool {
	b, e := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20))
	if e != nil {
		fail(w, 400, "validation", "invalid or oversized JSON body")
		return false
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.DisallowUnknownFields()
	if d.Decode(v) != nil {
		fail(w, 400, "validation", "malformed or unknown request fields")
		return false
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		fail(w, 400, "validation", "malformed JSON body")
		return false
	}
	return true
}
func write(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
func fail(w http.ResponseWriter, status int, code, msg string) {
	write(w, status, map[string]any{"error": map[string]string{"code": code, "message": msg}})
}

var _ = strconv.IntSize
