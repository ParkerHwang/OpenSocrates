package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

func selfcheck() {
	var mu sync.Mutex
	completed := false
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/slow") {
			time.Sleep(200 * time.Millisecond)
		} else {
			time.Sleep(5 * time.Millisecond)
		}
		if strings.HasSuffix(r.URL.Path, "/bad") {
			w.Write([]byte("{"))
			return
		}
		mu.Lock()
		defer mu.Unlock()
		job := map[string]any{"id": "test", "tenant": "t0", "queue": "mail", "state": "ready", "attempts": 1, "max_attempts": 3, "created_seq": 1, "created_at_ms": 1, "available_at_ms": 1, "lease_until_ms": nil, "last_error": nil, "result": nil, "payload": map[string]any{"blob": strings.Repeat("x", 245)}}
		if strings.HasSuffix(r.URL.Path, "/slow") {
			job["id"] = "slow"
		}
		switch {
		case strings.HasSuffix(r.URL.Path, "/claim"):
			if completed {
				json.NewEncoder(w).Encode(map[string]any{"job": nil, "lease_token": nil, "lease_until_ms": nil})
				return
			}
			job["state"] = "leased"
			json.NewEncoder(w).Encode(map[string]any{"job": job, "lease_token": "token"})
		case strings.HasSuffix(r.URL.Path, "/complete"):
			completed = true
			job["state"] = "completed"
			job["result"] = map[string]any{"ok": true}
			json.NewEncoder(w).Encode(map[string]any{"job": job})
		default:
			json.NewEncoder(w).Encode(map[string]any{"job": job})
		}
	}))
	defer srv.Close()
	dir, e := os.MkdirTemp("", "qf-generator-selfcheck-")
	if e != nil {
		panic(e)
	}
	defer os.RemoveAll(dir)
	refs := filepath.Join(dir, "refs.json")
	os.WriteFile(refs, []byte(`[{"id":"test","tenant":"t0"}]`), 0600)
	exe, _ := os.Executable()
	for _, mode := range []string{"read", "closed_long", "lifecycle", "arrival", "slow", "malformed"} {
		out := filepath.Join(dir, mode+".json")
		if mode == "slow" {
			os.WriteFile(refs, []byte(`[{"id":"slow","tenant":"t0"}]`), 0600)
		}
		if mode == "malformed" {
			os.WriteFile(refs, []byte(`[{"id":"bad","tenant":"t0"}]`), 0600)
		}
		args := []string{"--url", srv.URL, "--refs", refs, "--output", out, "--warmup", "30ms", "--duration", "100ms", "--concurrency", "1"}
		if mode == "closed_long" {
			args = []string{"--url", srv.URL, "--refs", refs, "--output", out, "--warmup", "3s", "--duration", "8s", "--concurrency", "1", "--workload", "read"}
		} else if mode == "arrival" || mode == "slow" {
			args = append(args, "--rate", "100")
		} else {
			work := mode
			if mode == "malformed" {
				work = "read"
			}
			args = append(args, "--workload", work)
		}
		cmd := exec.Command(exe, args...)
		if v, e := cmd.CombinedOutput(); e != nil {
			panic(fmt.Sprintf("selfcheck %s: %s %v", mode, v, e))
		}
		v, _ := os.ReadFile(out)
		var result map[string]any
		json.Unmarshal(v, &result)
		ph := result["phases"].(map[string]any)
		m := ph["measure"].(map[string]any)
		if mode == "closed_long" && (result["wall_seconds"].(float64) < 11 || m["window_successful_http"].(float64) == 0 || result["drain_budget_exceeded"].(bool)) {
			panic("closed-loop duration must include warmup plus measurement before drain")
		}
		if mode == "malformed" {
			if m["errors"].(float64) == 0 || m["successful_http"].(float64) != 0 {
				panic("error predicate failed")
			}
			continue
		}
		if m["send_latency_ms"].(map[string]any)["p50"].(float64) < 4 {
			panic("timing predicate failed")
		}
		if m["errors"].(float64) != 0 || m["attempts"].(float64) == 0 {
			panic("mock counters failed")
		}
		if (mode == "arrival" || mode == "slow") && m["scheduled_count"].(float64) != 10 {
			panic("arrival count failed")
		}
		if mode == "slow" {
			if m["completed_requests"].(float64) != 10 || m["window_completed_requests"].(float64) != 0 || m["drain_completed_requests"].(float64) != 10 || m["successful_rps"].(float64) != 0 {
				panic("cutoff/drain throughput predicate failed")
			}
		}
		if mode == "lifecycle" && result["acknowledged_unique"].(float64) != 1 {
			panic("lifecycle conservation failed")
		}
	}
	fmt.Println("selfcheck passed: controlled 5ms dispatch, exact arrival count, drain, lifecycle conservation/idle predicates")
}
