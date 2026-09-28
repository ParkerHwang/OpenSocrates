package queue

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
)

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

type Handler struct{ Store *Store }

func reply(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func problem(w http.ResponseWriter, status int, code string) {
	reply(w, status, map[string]any{"error": map[string]string{"code": code, "message": strings.ReplaceAll(code, "_", " ")}})
}
func storageError(w http.ResponseWriter, e error) {
	code := Code(e)
	switch code {
	case "not_found":
		problem(w, 404, code)
	case "lease_conflict", "idempotency_conflict":
		problem(w, 409, code)
	case "invalid_transition":
		problem(w, 409, code)
	case "capacity":
		problem(w, 429, code)
	case "validation":
		problem(w, 400, code)
	default:
		problem(w, 503, "storage_unavailable")
	}
}
func decode(w http.ResponseWriter, r *http.Request, v any) bool {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	d.UseNumber()
	if e := d.Decode(v); e != nil {
		problem(w, 400, "validation")
		return false
	}
	var x any
	if e := d.Decode(&x); !errors.Is(e, io.EOF) {
		problem(w, 400, "validation")
		return false
	}
	return true
}
func object(raw json.RawMessage) (json.RawMessage, bool) {
	var v any
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	if len(raw) > 16*1024 || d.Decode(&v) != nil {
		return nil, false
	}
	if _, ok := v.(map[string]any); !ok {
		return nil, false
	}
	b, e := json.Marshal(v)
	return b, e == nil && len(b) <= 16*1024
}

type inputJSON struct {
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	MaxAttempts json.RawMessage `json:"max_attempts"`
	Priority    json.RawMessage `json:"priority"`
	RunAtMS     json.RawMessage `json:"run_at_ms"`
	RetryBaseMS json.RawMessage `json:"retry_base_ms"`
}

func optionalInt(raw json.RawMessage, def, lo, hi int64) (int64, bool) {
	if len(raw) == 0 {
		return def, true
	}
	if bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
		return 0, false
	}
	var n int64
	if json.Unmarshal(raw, &n) != nil || n < lo || n > hi {
		return 0, false
	}
	return n, true
}

func resolve(in inputJSON) (Input, bool) {
	p, ok := object(in.Payload)
	if !ok || !ident.MatchString(in.Queue) {
		return Input{}, false
	}
	max, ok := optionalInt(in.MaxAttempts, 3, 1, 10)
	if !ok {
		return Input{}, false
	}
	priority, ok := optionalInt(in.Priority, 0, -10, 10)
	if !ok {
		return Input{}, false
	}
	runAt, ok := optionalInt(in.RunAtMS, 0, 0, 1<<63-1)
	if !ok {
		return Input{}, false
	}
	retry, ok := optionalInt(in.RetryBaseMS, 1000, 0, 60000)
	if !ok {
		return Input{}, false
	}
	return Input{Queue: in.Queue, Payload: p, MaxAttempts: int(max), Priority: int(priority), RunAtMS: runAt, RetryBaseMS: retry}, true
}
func key(r *http.Request) string {
	k := r.Header.Get("Idempotency-Key")
	if len(k) == 0 || len(k) > 128 {
		return ""
	}
	for _, b := range []byte(k) {
		if b < 32 || b > 126 {
			return ""
		}
	}
	return k
}
func leaseToken(t string) bool { return len(t) > 0 && len(t) <= 256 }
func (h Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" && r.URL.Path == "/health" {
		reply(w, 200, map[string]any{"ok": true, "schema_version": 2})
		return
	}
	tenant := r.Header.Get("X-Tenant-ID")
	if !ident.MatchString(tenant) {
		problem(w, 400, "validation")
		return
	}
	p := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	ctx := r.Context()
	if r.Method == "GET" && r.URL.Path == "/v1/jobs" {
		query := r.URL.Query()
		for k, v := range query {
			if (k != "queue" && k != "limit" && k != "cursor") || len(v) != 1 {
				problem(w, 400, "validation")
				return
			}
		}
		queue := query.Get("queue")
		if _, ok := query["queue"]; ok && !ident.MatchString(queue) {
			problem(w, 400, "validation")
			return
		}
		limit := 50
		if _, ok := query["limit"]; ok {
			n, e := strconv.Atoi(query.Get("limit"))
			if e != nil || n < 1 || n > 100 {
				problem(w, 400, "validation")
				return
			}
			limit = n
		}
		cursor := query.Get("cursor")
		if _, ok := query["cursor"]; ok && cursor == "" {
			problem(w, 400, "validation")
			return
		}
		items, next, e := h.Store.List(ctx, tenant, queue, limit, cursor)
		if e != nil {
			storageError(w, e)
			return
		}
		reply(w, 200, map[string]any{"items": items, "next_cursor": next})
		return
	}
	if r.Method == "POST" && r.URL.Path == "/v1/jobs" {
		k := key(r)
		if k == "" {
			problem(w, 400, "validation")
			return
		}
		var raw inputJSON
		if !decode(w, r, &raw) {
			return
		}
		in, ok := resolve(raw)
		if !ok {
			problem(w, 400, "validation")
			return
		}
		b, _ := json.Marshal(in)
		jobs, replayed, e := h.Store.Submit(ctx, tenant, "/v1/jobs", k, string(b), []Input{in})
		if e != nil {
			storageError(w, e)
			return
		}
		status := 201
		if replayed {
			status = 200
		}
		reply(w, status, map[string]any{"job": jobs[0], "replayed": replayed})
		return
	}
	if r.Method == "POST" && r.URL.Path == "/v1/jobs/batch" {
		k := key(r)
		if k == "" {
			problem(w, 400, "validation")
			return
		}
		var body struct {
			Jobs []inputJSON `json:"jobs"`
		}
		if !decode(w, r, &body) {
			return
		}
		if len(body.Jobs) < 1 || len(body.Jobs) > 100 {
			problem(w, 400, "validation")
			return
		}
		inputs := make([]Input, 0, len(body.Jobs))
		for _, v := range body.Jobs {
			in, ok := resolve(v)
			if !ok {
				problem(w, 400, "validation")
				return
			}
			inputs = append(inputs, in)
		}
		b, _ := json.Marshal(inputs)
		jobs, replayed, e := h.Store.Submit(ctx, tenant, "/v1/jobs/batch", k, string(b), inputs)
		if e != nil {
			storageError(w, e)
			return
		}
		status := 201
		if replayed {
			status = 200
		}
		reply(w, status, map[string]any{"jobs": jobs, "replayed": replayed})
		return
	}
	if r.Method == "GET" && r.URL.Path == "/v1/stats" {
		queue := ""
		if len(r.URL.Query()) > 1 || len(r.URL.Query()["queue"]) > 1 || (len(r.URL.Query()) == 1 && !r.URL.Query().Has("queue")) {
			problem(w, 400, "validation")
			return
		}
		if q, ok := r.URL.Query()["queue"]; ok {
			queue = q[0]
			if !ident.MatchString(queue) {
				problem(w, 400, "validation")
				return
			}
		}
		m, e := h.Store.Stats(ctx, tenant, queue)
		if e != nil {
			storageError(w, e)
			return
		}
		reply(w, 200, m)
		return
	}
	if len(p) == 4 && p[0] == "v1" && p[1] == "queues" && p[3] == "claim" && r.Method == "POST" {
		if !ident.MatchString(p[2]) {
			problem(w, 400, "validation")
			return
		}
		var v struct {
			WorkerID string `json:"worker_id"`
			LeaseMS  int64  `json:"lease_ms"`
		}
		if !decode(w, r, &v) {
			return
		}
		if !ident.MatchString(v.WorkerID) || v.LeaseMS < 10 || v.LeaseMS > 300000 {
			problem(w, 400, "validation")
			return
		}
		j, t, e := h.Store.Claim(ctx, tenant, p[2], v.LeaseMS)
		if e != nil {
			storageError(w, e)
			return
		}
		var deadline *int64
		if j != nil {
			deadline = j.LeaseUntilMS
		}
		reply(w, 200, map[string]any{"job": j, "lease_token": t, "lease_until_ms": deadline})
		return
	}
	if len(p) >= 3 && p[0] == "v1" && p[1] == "jobs" && p[2] != "" {
		id := p[2]
		if len(p) == 3 && r.Method == "GET" {
			j, e := h.Store.Get(ctx, tenant, id)
			if e != nil {
				storageError(w, e)
				return
			}
			reply(w, 200, map[string]any{"job": j})
			return
		}
		if len(p) == 4 && r.Method == "POST" {
			switch p[3] {
			case "cancel":
				var v json.RawMessage
				if !decode(w, r, &v) {
					return
				}
				if !bytes.Equal(bytes.TrimSpace(v), []byte("{}")) {
					problem(w, 400, "validation")
					return
				}
				j, e := h.Store.Cancel(ctx, tenant, id)
				if e != nil {
					storageError(w, e)
					return
				}
				reply(w, 200, map[string]any{"job": j})
				return
			case "heartbeat":
				var v struct {
					LeaseToken string `json:"lease_token"`
					LeaseMS    int64  `json:"lease_ms"`
				}
				if !decode(w, r, &v) {
					return
				}
				if !leaseToken(v.LeaseToken) || v.LeaseMS < 10 || v.LeaseMS > 300000 {
					problem(w, 400, "validation")
					return
				}
				j, e := h.Store.LeaseAction(ctx, tenant, id, "heartbeat", v.LeaseToken, v.LeaseMS, "")
				if e != nil {
					storageError(w, e)
					return
				}
				reply(w, 200, map[string]any{"job": j})
				return
			case "complete":
				var v struct {
					LeaseToken string          `json:"lease_token"`
					Result     json.RawMessage `json:"result"`
				}
				if !decode(w, r, &v) {
					return
				}
				result, ok := object(v.Result)
				if !leaseToken(v.LeaseToken) || !ok {
					problem(w, 400, "validation")
					return
				}
				j, e := h.Store.LeaseAction(ctx, tenant, id, "complete", v.LeaseToken, 0, string(result))
				if e != nil {
					storageError(w, e)
					return
				}
				reply(w, 200, map[string]any{"job": j})
				return
			case "fail":
				var v struct {
					LeaseToken string `json:"lease_token"`
					Error      string `json:"error"`
				}
				if !decode(w, r, &v) {
					return
				}
				if !leaseToken(v.LeaseToken) || len(v.Error) < 1 || len(v.Error) > 256 {
					problem(w, 400, "validation")
					return
				}
				j, e := h.Store.LeaseAction(ctx, tenant, id, "fail", v.LeaseToken, 0, v.Error)
				if e != nil {
					storageError(w, e)
					return
				}
				reply(w, 200, map[string]any{"job": j})
				return
			}
		}
	}
	problem(w, 404, "not_found")
}
