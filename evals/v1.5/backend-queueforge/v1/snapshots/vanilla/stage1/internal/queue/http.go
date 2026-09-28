package queue

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"
)

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)

type Server struct {
	Store     *Store
	ClockFile string
}

func (s *Server) now() (int64, error) {
	if s.ClockFile == "" {
		return time.Now().UnixMilli(), nil
	}
	b, e := os.ReadFile(s.ClockFile)
	if e != nil {
		return 0, e
	}
	return strconv.ParseInt(strings.TrimSpace(string(b)), 10, 64)
}
func respond(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func failHTTP(w http.ResponseWriter, status int, code, msg string) {
	respond(w, status, map[string]any{"error": map[string]string{"code": code, "message": msg}})
}
func mapError(w http.ResponseWriter, e error) {
	switch {
	case errors.Is(e, ErrNotFound):
		failHTTP(w, 404, "not_found", "job not found")
	case errors.Is(e, ErrLease):
		failHTTP(w, 409, "lease_conflict", "lease is no longer current")
	case errors.Is(e, ErrIdem):
		failHTTP(w, 409, "idempotency_conflict", "idempotency key has different input")
	case errors.Is(e, ErrTransition):
		failHTTP(w, 409, "invalid_transition", "invalid job transition")
	default:
		failHTTP(w, 503, "storage_unavailable", "storage temporarily unavailable")
	}
}
func decode(r *http.Request, v any) error {
	r.Body = http.MaxBytesReader(nil, r.Body, 1<<20)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	d.UseNumber()
	if e := d.Decode(v); e != nil {
		return e
	}
	var extra any
	if e := d.Decode(&extra); e != io.EOF {
		if e == nil {
			return errors.New("extra JSON")
		}
		return e
	}
	return nil
}
func object(raw json.RawMessage) (json.RawMessage, error) {
	if len(raw) == 0 {
		return nil, errors.New("object required")
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	var v any
	if e := d.Decode(&v); e != nil {
		return nil, e
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, errors.New("object required")
	}
	return json.Marshal(m)
}
func validateInput(i *Input) error {
	if !ident.MatchString(i.Queue) {
		return errors.New("invalid queue")
	}
	if len(i.Payload) > 16<<10 {
		return errors.New("payload too large")
	}
	p, e := object(i.Payload)
	if e != nil {
		return e
	}
	if len(p) > 16<<10 {
		return errors.New("payload too large")
	}
	i.Payload = p
	if i.MaxAttempts == 0 {
		i.MaxAttempts = 3
	}
	if i.MaxAttempts < 1 || i.MaxAttempts > 10 {
		return errors.New("invalid max_attempts")
	}
	return nil
}
func validKey(k string) bool {
	if len(k) == 0 || len(k) > 128 {
		return false
	}
	for _, b := range []byte(k) {
		if b < 32 || b > 126 {
			return false
		}
	}
	return true
}
func validation(w http.ResponseWriter) { failHTTP(w, 400, "validation", "invalid request") }
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" && r.URL.Path == "/health" {
		respond(w, 200, map[string]any{"ok": true, "schema_version": 1})
		return
	}
	tenant := r.Header.Get("X-Tenant-ID")
	if !ident.MatchString(tenant) {
		validation(w)
		return
	}
	now, e := s.now()
	if e != nil {
		mapError(w, e)
		return
	}
	path := strings.Trim(r.URL.Path, "/")
	parts := strings.Split(path, "/")
	if r.Method == "POST" && path == "v1/jobs" {
		s.submit(w, r, tenant, now, false)
		return
	}
	if r.Method == "POST" && path == "v1/jobs/batch" {
		s.submit(w, r, tenant, now, true)
		return
	}
	if r.Method == "GET" && path == "v1/stats" {
		if len(r.URL.Query()) > 1 || len(r.URL.Query()["queue"]) > 1 {
			validation(w)
			return
		}
		for k := range r.URL.Query() {
			if k != "queue" {
				validation(w)
				return
			}
		}
		q := r.URL.Query().Get("queue")
		if q != "" && !ident.MatchString(q) {
			validation(w)
			return
		}
		v, e := s.Store.Stats(r.Context(), tenant, q)
		if e != nil {
			mapError(w, e)
			return
		}
		respond(w, 200, v)
		return
	}
	if len(parts) == 3 && parts[0] == "v1" && parts[1] == "jobs" && r.Method == "GET" {
		j, e := s.Store.Get(r.Context(), tenant, parts[2])
		if e != nil {
			mapError(w, e)
			return
		}
		respond(w, 200, map[string]any{"job": j})
		return
	}
	if len(parts) == 4 && parts[0] == "v1" && parts[1] == "queues" && parts[3] == "claim" && r.Method == "POST" {
		if !ident.MatchString(parts[2]) {
			validation(w)
			return
		}
		s.claim(w, r, tenant, parts[2], now)
		return
	}
	if len(parts) == 4 && parts[0] == "v1" && parts[1] == "jobs" && r.Method == "POST" {
		switch parts[3] {
		case "heartbeat":
			s.heartbeat(w, r, tenant, parts[2], now)
			return
		case "complete":
			s.complete(w, r, tenant, parts[2], now)
			return
		case "fail":
			s.fail(w, r, tenant, parts[2], now)
			return
		}
	}
	failHTTP(w, 404, "not_found", "endpoint not found")
}

type inputWire struct {
	Queue       string          `json:"queue"`
	Payload     json.RawMessage `json:"payload"`
	MaxAttempts *int            `json:"max_attempts"`
}

func normalize(in inputWire) (Input, error) {
	i := Input{Queue: in.Queue, Payload: in.Payload, MaxAttempts: 3}
	if in.MaxAttempts != nil {
		i.MaxAttempts = *in.MaxAttempts
		if i.MaxAttempts == 0 {
			return i, errors.New("zero attempts")
		}
	}
	return i, validateInput(&i)
}
func (s *Server) submit(w http.ResponseWriter, r *http.Request, tenant string, now int64, batch bool) {
	key := r.Header.Get("Idempotency-Key")
	if !validKey(key) {
		validation(w)
		return
	}
	var inputs []Input
	endpoint := "jobs"
	if batch {
		endpoint = "jobs/batch"
		var body struct {
			Jobs []inputWire `json:"jobs"`
		}
		if e := decode(r, &body); e != nil || len(body.Jobs) < 1 || len(body.Jobs) > 100 {
			validation(w)
			return
		}
		for _, wire := range body.Jobs {
			i, e := normalize(wire)
			if e != nil {
				validation(w)
				return
			}
			inputs = append(inputs, i)
		}
	} else {
		var wire inputWire
		if e := decode(r, &wire); e != nil {
			validation(w)
			return
		}
		i, e := normalize(wire)
		if e != nil {
			validation(w)
			return
		}
		inputs = []Input{i}
	}
	command, _ := json.Marshal(inputs)
	jobs, replayed, e := s.Store.Submit(r.Context(), tenant, endpoint, key, string(command), inputs, now)
	if e != nil {
		mapError(w, e)
		return
	}
	status := 201
	if replayed {
		status = 200
	}
	if batch {
		respond(w, status, map[string]any{"jobs": jobs, "replayed": replayed})
	} else {
		respond(w, status, map[string]any{"job": jobs[0], "replayed": replayed})
	}
}
func leaseMS(v int64) bool { return v >= 10 && v <= 300000 }
func (s *Server) claim(w http.ResponseWriter, r *http.Request, tenant, queue string, now int64) {
	var body struct {
		WorkerID string `json:"worker_id"`
		LeaseMS  int64  `json:"lease_ms"`
	}
	if e := decode(r, &body); e != nil || !ident.MatchString(body.WorkerID) || !leaseMS(body.LeaseMS) {
		validation(w)
		return
	}
	j, t, e := s.Store.Claim(r.Context(), tenant, queue, now, body.LeaseMS)
	if e != nil {
		mapError(w, e)
		return
	}
	var until *int64
	if j != nil {
		until = j.LeaseUntilMS
	}
	respond(w, 200, map[string]any{"job": j, "lease_token": t, "lease_until_ms": until})
}
func (s *Server) heartbeat(w http.ResponseWriter, r *http.Request, tenant, id string, now int64) {
	var body struct {
		LeaseToken string `json:"lease_token"`
		LeaseMS    int64  `json:"lease_ms"`
	}
	if e := decode(r, &body); e != nil || body.LeaseToken == "" || !leaseMS(body.LeaseMS) {
		validation(w)
		return
	}
	j, e := s.Store.Heartbeat(r.Context(), tenant, id, body.LeaseToken, now, body.LeaseMS)
	if e != nil {
		mapError(w, e)
		return
	}
	respond(w, 200, map[string]any{"job": j})
}
func (s *Server) complete(w http.ResponseWriter, r *http.Request, tenant, id string, now int64) {
	var body struct {
		LeaseToken string          `json:"lease_token"`
		Result     json.RawMessage `json:"result"`
	}
	if e := decode(r, &body); e != nil || body.LeaseToken == "" {
		validation(w)
		return
	}
	v, e := object(body.Result)
	if e != nil {
		validation(w)
		return
	}
	j, e := s.Store.Complete(r.Context(), tenant, id, body.LeaseToken, v, now)
	if e != nil {
		mapError(w, e)
		return
	}
	respond(w, 200, map[string]any{"job": j})
}
func (s *Server) fail(w http.ResponseWriter, r *http.Request, tenant, id string, now int64) {
	var body struct {
		LeaseToken string `json:"lease_token"`
		Error      string `json:"error"`
	}
	if e := decode(r, &body); e != nil || body.LeaseToken == "" || len(body.Error) < 1 || len(body.Error) > 256 {
		validation(w)
		return
	}
	j, e := s.Store.Fail(r.Context(), tenant, id, body.LeaseToken, body.Error, now)
	if e != nil {
		mapError(w, e)
		return
	}
	respond(w, 200, map[string]any{"job": j})
}
