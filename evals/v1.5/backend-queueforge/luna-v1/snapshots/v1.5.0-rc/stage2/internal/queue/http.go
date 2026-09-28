package queue

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
)

type API struct{ S *Service }

var tenantRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

type apiErr struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func write(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func fail(w http.ResponseWriter, status int, code, msg string) {
	write(w, status, map[string]any{"error": apiErr{code, msg}})
}
func decode(w http.ResponseWriter, r *http.Request, v any) bool {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if d.Decode(v) != nil {
		return false
	}
	var extra any
	return d.Decode(&extra) == io.EOF
}
func (a *API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" && r.Method == "GET" {
		write(w, 200, map[string]any{"ok": true, "schema_version": 2})
		return
	}
	t := r.Header.Get("X-Tenant-ID")
	if !tenantRE.MatchString(t) {
		fail(w, 400, "validation", "valid X-Tenant-ID required")
		return
	}
	ctx := r.Context()
	path := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	if r.URL.Path == "/v1/jobs" && r.Method == "POST" {
		a.submit(w, r, ctx, t, "single")
		return
	}
	if r.URL.Path == "/v1/jobs/batch" && r.Method == "POST" {
		a.submit(w, r, ctx, t, "batch")
		return
	}
	if r.URL.Path == "/v1/jobs" && r.Method == "GET" {
		q := r.URL.Query().Get("queue")
		if q != "" && !ident.MatchString(q) {
			fail(w, 400, "validation", "invalid queue")
			return
		}
		limit := 50
		if raw := r.URL.Query().Get("limit"); raw != "" {
			n, e := strconv.Atoi(raw)
			if e != nil || n < 1 || n > 100 {
				fail(w, 400, "validation", "invalid limit")
				return
			}
			limit = n
		}
		items, next, e := a.S.List(ctx, t, q, limit, r.URL.Query().Get("cursor"))
		if errors.Is(e, ErrCursor) {
			fail(w, 400, "validation", "invalid cursor")
			return
		}
		if e != nil {
			storageErr(w)
			return
		}
		var nc any
		if next != "" {
			nc = next
		}
		write(w, 200, map[string]any{"items": items, "next_cursor": nc})
		return
	}
	if len(path) == 4 && path[0] == "v1" && path[1] == "queues" && path[3] == "claim" && r.Method == "POST" {
		a.claim(w, r, ctx, t, path[2])
		return
	}
	if len(path) >= 3 && path[0] == "v1" && path[1] == "jobs" {
		id := path[2]
		if len(path) == 3 && r.Method == "GET" {
			j, e := a.S.Get(ctx, t, id)
			if e != nil {
				fail(w, 404, "not_found", "job not found")
			} else {
				write(w, 200, map[string]any{"job": j})
			}
			return
		}
		if len(path) == 4 && path[3] == "cancel" && r.Method == "POST" {
			var b map[string]any
			if !decode(w, r, &b) || len(b) != 0 {
				fail(w, 400, "validation", "empty object required")
				return
			}
			j, e := a.S.Cancel(ctx, t, id)
			if errors.Is(e, sql.ErrNoRows) {
				fail(w, 404, "not_found", "job not found")
			} else if errors.Is(e, ErrTransition) {
				fail(w, 409, "invalid_transition", "job cannot be cancelled")
			} else if e != nil {
				storageErr(w)
			} else {
				write(w, 200, map[string]any{"job": j})
			}
			return
		}
		if len(path) == 4 && r.Method == "POST" {
			a.mutate(w, r, ctx, t, id, path[3])
			return
		}
	}
	if r.URL.Path == "/v1/stats" && r.Method == "GET" {
		q := r.URL.Query().Get("queue")
		if q != "" && !ident.MatchString(q) {
			fail(w, 400, "validation", "invalid queue")
			return
		}
		m, e := a.S.Stats(ctx, t, q)
		if e != nil {
			storageErr(w)
			return
		}
		write(w, 200, m)
		return
	}
	fail(w, 404, "not_found", "endpoint not found")
}
func (a *API) submit(w http.ResponseWriter, r *http.Request, ctx context.Context, t, kind string) {
	key := r.Header.Get("Idempotency-Key")
	if len(key) < 1 || len(key) > 128 {
		fail(w, 400, "validation", "valid Idempotency-Key required")
		return
	}
	for _, c := range key {
		if c < 32 || c > 126 {
			fail(w, 400, "validation", "valid Idempotency-Key required")
			return
		}
	}
	var ins []Input
	if kind == "single" {
		var in Input
		if !decode(w, r, &in) {
			fail(w, 400, "validation", "invalid JSON request")
			return
		}
		ins = []Input{in}
	} else {
		var b struct {
			Jobs []Input `json:"jobs"`
		}
		if !decode(w, r, &b) {
			fail(w, 400, "validation", "invalid JSON request")
			return
		}
		ins = b.Jobs
	}
	jobs, replay, e := a.S.Submit(ctx, t, kind, key, ins)
	if e != nil {
		if errors.Is(e, ErrIdempotency) {
			fail(w, 409, "idempotency_conflict", "idempotency key has different input")
		} else if errors.Is(e, ErrCapacity) {
			fail(w, 429, "capacity", "tenant pending capacity reached")
		} else if strings.Contains(e.Error(), "invalid") || strings.Contains(e.Error(), "batch size") {
			fail(w, 400, "validation", "invalid job input")
		} else {
			storageErr(w)
		}
		return
	}
	status := 201
	if replay {
		status = 200
	}
	if kind == "single" {
		write(w, status, map[string]any{"job": jobs[0], "replayed": replay})
	} else {
		write(w, status, map[string]any{"jobs": jobs, "replayed": replay})
	}
}
func (a *API) claim(w http.ResponseWriter, r *http.Request, ctx context.Context, t, q string) {
	var b struct {
		Worker string `json:"worker_id"`
		Lease  int    `json:"lease_ms"`
	}
	if !decode(w, r, &b) || !ident.MatchString(b.Worker) || b.Lease < 10 || b.Lease > 300000 || !ident.MatchString(q) {
		fail(w, 400, "validation", "invalid claim request")
		return
	}
	j, tok, until, e := a.S.Claim(ctx, t, q, b.Worker, b.Lease)
	if e != nil {
		storageErr(w)
		return
	}
	write(w, 200, map[string]any{"job": j, "lease_token": nullable(tok), "lease_until_ms": until})
}
func nullable(s string) any {
	if s == "" {
		return nil
	}
	return s
}
func (a *API) mutate(w http.ResponseWriter, r *http.Request, ctx context.Context, t, id, op string) {
	switch op {
	case "heartbeat":
		var b struct {
			Token string `json:"lease_token"`
			Lease int    `json:"lease_ms"`
		}
		if !decode(w, r, &b) || b.Token == "" || b.Lease < 10 || b.Lease > 300000 {
			fail(w, 400, "validation", "invalid heartbeat request")
			return
		}
		j, e := a.S.Heartbeat(ctx, t, id, b.Token, b.Lease)
		a.jobResult(w, j, e)
	case "complete":
		var b struct {
			Token  string          `json:"lease_token"`
			Result json.RawMessage `json:"result"`
		}
		if !decode(w, r, &b) || b.Token == "" || !validObject(b.Result) {
			fail(w, 400, "validation", "invalid completion request")
			return
		}
		var v any
		_ = json.Unmarshal(b.Result, &v)
		b.Result, _ = json.Marshal(v)
		j, e := a.S.Complete(ctx, t, id, b.Token, b.Result)
		a.jobResult(w, j, e)
	case "fail":
		var b struct {
			Token string `json:"lease_token"`
			Error string `json:"error"`
		}
		if !decode(w, r, &b) || b.Token == "" || len([]rune(b.Error)) < 1 || len([]rune(b.Error)) > 256 {
			fail(w, 400, "validation", "invalid failure request")
			return
		}
		j, e := a.S.Fail(ctx, t, id, b.Token, b.Error)
		a.jobResult(w, j, e)
	default:
		fail(w, 404, "not_found", "endpoint not found")
	}
}
func (a *API) jobResult(w http.ResponseWriter, j Job, e error) {
	if errors.Is(e, ErrLease) {
		fail(w, 409, "lease_conflict", "lease is stale or conflicting")
		return
	}
	if errors.Is(e, sql.ErrNoRows) {
		fail(w, 404, "not_found", "job not found")
		return
	}
	if e != nil {
		storageErr(w)
		return
	}
	write(w, 200, map[string]any{"job": j})
}
func storageErr(w http.ResponseWriter) { fail(w, 503, "unavailable", "temporary storage failure") }

var _ = strconv.Itoa
