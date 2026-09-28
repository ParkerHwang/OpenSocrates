package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math/rand"
	"net"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strings"
	"sync"
	"time"
)

type Ref struct {
	ID     string `json:"id"`
	Tenant string `json:"tenant"`
}
type Sample struct {
	FinishOffsetMS    float64 `json:"finish_offset_ms"`
	Tenant            string  `json:"tenant"`
	Phase             string  `json:"phase"`
	Op                string  `json:"op"`
	Status            int     `json:"status"`
	SendMS            float64 `json:"send_ms"`
	ScheduledMS       float64 `json:"scheduled_ms"`
	LagMS             float64 `json:"lag_ms"`
	Error             string  `json:"error,omitempty"`
	Success           bool    `json:"success"`
	Idle              bool    `json:"idle"`
	ID                string  `json:"id,omitempty"`
	Duplicate         bool    `json:"duplicate"`
	ScheduledOffsetMS float64 `json:"scheduled_offset_ms"`
	SendOffsetMS      float64 `json:"send_offset_ms"`
}
type Job struct {
	ID          string         `json:"id"`
	Tenant      string         `json:"tenant"`
	Queue       string         `json:"queue"`
	State       string         `json:"state"`
	Attempts    int            `json:"attempts"`
	Payload     map[string]any `json:"payload"`
	MaxAttempts int            `json:"max_attempts"`
	CreatedSeq  int64          `json:"created_seq"`
	Result      map[string]any `json:"result"`
}
type Reply struct {
	Job   *Job   `json:"job"`
	Token string `json:"lease_token"`
}

var client *http.Client
var requestContext = context.Background()

func request(base, tenant, method, path string, body any) (Reply, int, string) {
	var r Reply
	var b io.Reader
	if body != nil {
		v, _ := json.Marshal(body)
		b = bytes.NewReader(v)
	}
	q, e := http.NewRequestWithContext(requestContext, method, base+path, b)
	if e != nil {
		return r, 0, e.Error()
	}
	q.Header.Set("X-Tenant-ID", tenant)
	q.Header.Set("Content-Type", "application/json")
	s, e := client.Do(q)
	if e != nil {
		return r, 0, e.Error()
	}
	defer s.Body.Close()
	v, e := io.ReadAll(io.LimitReader(s.Body, 1<<20))
	if e != nil {
		return r, s.StatusCode, e.Error()
	}
	if e = json.Unmarshal(v, &r); e != nil {
		return r, s.StatusCode, "parse: " + e.Error()
	}
	if s.StatusCode == 200 {
		var fields map[string]json.RawMessage
		if json.Unmarshal(v, &fields) != nil || fields["job"] == nil {
			return r, s.StatusCode, "missing job field"
		}
		if r.Job == nil && strings.HasSuffix(path, "/claim") {
			if string(fields["lease_token"]) != "null" || string(fields["lease_until_ms"]) != "null" {
				return r, s.StatusCode, "invalid idle claim fields"
			}
		}
		if r.Job != nil {
			var jobFields map[string]json.RawMessage
			json.Unmarshal(fields["job"], &jobFields)
			for _, name := range []string{"id", "tenant", "queue", "payload", "state", "attempts", "max_attempts", "created_seq", "created_at_ms", "available_at_ms", "lease_until_ms", "last_error", "result"} {
				if jobFields[name] == nil {
					return r, s.StatusCode, "missing job field: " + name
				}
			}
			if jobFields["lease_token"] != nil {
				return r, s.StatusCode, "forbidden job lease token"
			}
			if r.Job.MaxAttempts != 3 || r.Job.CreatedSeq < 1 {
				return r, s.StatusCode, "invalid immutable fields"
			}
		}
	}
	return r, s.StatusCode, ""
}
func pct(a []float64, p float64) any {
	if len(a) == 0 {
		return nil
	}
	sort.Float64s(a)
	return a[int(float64(len(a)-1)*p)]
}
func main() {
	base := flag.String("url", "", "loopback base URL")
	refsPath := flag.String("refs", "", "seed refs JSON")
	out := flag.String("output", "", "new JSON result path")
	work := flag.String("workload", "read", "read or lifecycle")
	conc := flag.Int("concurrency", 1, "closed-loop workers")
	rate := flag.Int("rate", 0, "fixed arrival reads/s; zero closed-loop")
	warm := flag.Duration("warmup", 3*time.Second, "warmup")
	dur := flag.Duration("duration", 10*time.Second, "measure")
	self := flag.Bool("selfcheck", false, "selfcheck")
	flag.Parse()
	if *self {
		selfcheck()
		return
	}
	u, e := url.Parse(*base)
	if e != nil || u.Scheme != "http" || u.Hostname() != "127.0.0.1" {
		panic("only http://127.0.0.1 allowed")
	}
	if (*work != "read" && *work != "lifecycle") || *conc < 1 || *conc > 64 || (*rate != 0 && (*work != "read" || (*rate != 100 && *rate != 500 && *rate != 1000))) {
		panic("unsupported fixed workload")
	}
	var cancel context.CancelFunc
	requestContext, cancel = context.WithCancel(context.Background())
	defer cancel()
	client = &http.Client{Timeout: 2 * time.Second, Transport: &http.Transport{Proxy: nil, DialContext: (&net.Dialer{Timeout: 2 * time.Second}).DialContext, MaxIdleConns: 256, MaxIdleConnsPerHost: 256}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	v, e := os.ReadFile(*refsPath)
	if e != nil {
		panic(e)
	}
	var refs []Ref
	if json.Unmarshal(v, &refs) != nil || len(refs) == 0 {
		panic("invalid refs")
	}
	known := map[string]bool{}
	for _, ref := range refs {
		known[ref.Tenant+"\x00"+ref.ID] = true
	}
	var mu sync.Mutex
	var samples []Sample
	seen := map[string]bool{}
	acks := map[string]bool{}
	drops := map[string]int{"warmup": 0, "measure": 0}
	start := time.Now()
	end := start.Add(*warm + *dur)
	var wg sync.WaitGroup
	var failures int
	stopped := false
	execute := func(ref Ref, scheduled time.Time) {
		defer wg.Done()
		phase := "measure"
		if scheduled.Before(start.Add(*warm)) {
			phase = "warmup"
		}
		op := "get"
		path := "/v1/jobs/" + url.PathEscape(ref.ID)
		method := "GET"
		var body any
		if *work == "lifecycle" {
			op = "claim"
			path = "/v1/queues/mail/claim"
			method = "POST"
			body = map[string]any{"worker_id": "bench-worker", "lease_ms": 300000}
		}
		send := time.Now()
		r, status, err := request(*base, ref.Tenant, method, path, body)
		finish := time.Now()
		s := Sample{FinishOffsetMS: float64(finish.Sub(start).Microseconds()) / 1000, Tenant: ref.Tenant, Phase: phase, Op: op, Status: status, SendMS: float64(time.Since(send).Microseconds()) / 1000, ScheduledMS: float64(time.Since(scheduled).Microseconds()) / 1000, LagMS: float64(send.Sub(scheduled).Microseconds()) / 1000, Error: err, ScheduledOffsetMS: float64(scheduled.Sub(start).Microseconds()) / 1000, SendOffsetMS: float64(send.Sub(start).Microseconds()) / 1000}
		valid := status == 200 && err == ""
		if valid && r.Job == nil && op == "claim" {
			s.Idle = true
		} else if valid {
			valid = r.Job != nil && r.Job.ID != "" && r.Job.Tenant == ref.Tenant && r.Job.Queue == "mail" && r.Job.Payload != nil && r.Job.Payload["blob"] == strings.Repeat("x", 245)
			if op == "get" {
				valid = valid && r.Job.ID == ref.ID && r.Job.State == "ready"
			}
			if op == "claim" {
				valid = valid && r.Token != "" && r.Job.State == "leased" && r.Job.Attempts == 1 && known[ref.Tenant+"\x00"+r.Job.ID]
			}
		}
		s.Success = valid
		if !valid && s.Error == "" {
			s.Error = "invalid_status_or_body"
		}
		if r.Job != nil {
			s.ID = r.Job.ID
		}
		mu.Lock()
		if op == "claim" && valid && !s.Idle {
			if seen[ref.Tenant+"\x00"+s.ID] {
				s.Duplicate = true
				s.Success = false
			}
			seen[ref.Tenant+"\x00"+s.ID] = true
		}
		samples = append(samples, s)
		if status == 0 {
			failures++
		} else {
			failures = 0
		}
		if failures >= 20 {
			stopped = true
		}
		mu.Unlock()
		if op != "claim" || !s.Success || s.Idle {
			return
		}
		send = time.Now()
		r, status, err = request(*base, ref.Tenant, "POST", "/v1/jobs/"+url.PathEscape(s.ID)+"/complete", map[string]any{"lease_token": r.Token, "result": map[string]any{"ok": true}})
		finish = time.Now()
		c := Sample{FinishOffsetMS: float64(finish.Sub(start).Microseconds()) / 1000, Tenant: ref.Tenant, Phase: phase, Op: "complete", ID: s.ID, Status: status, Error: err, ScheduledOffsetMS: float64(send.Sub(start).Microseconds()) / 1000, SendOffsetMS: float64(send.Sub(start).Microseconds()) / 1000, SendMS: float64(time.Since(send).Microseconds()) / 1000, ScheduledMS: float64(time.Since(send).Microseconds()) / 1000}
		c.Success = status == 200 && err == "" && r.Job != nil && r.Job.ID == s.ID && r.Job.Tenant == ref.Tenant && r.Job.State == "completed" && r.Job.Result["ok"] == true
		if !c.Success && c.Error == "" {
			c.Error = "invalid_status_or_body"
		}
		mu.Lock()
		if c.Success {
			if acks[ref.Tenant+"\x00"+c.ID] {
				c.Duplicate = true
				c.Success = false
			}
			acks[ref.Tenant+"\x00"+c.ID] = true
		}
		samples = append(samples, c)
		mu.Unlock()
	}
	if *rate == 0 {
		for i := 0; i < *conc; i++ {
			wg.Add(1)
			go func(i int) {
				defer wg.Done()
				rng := rand.New(rand.NewSource(int64(20260926 + i)))
				for time.Now().Before(end) {
					mu.Lock()
					stop := stopped
					mu.Unlock()
					if stop {
						return
					}
					ref := refs[rng.Intn(len(refs))]
					wg.Add(1)
					execute(ref, time.Now())
				}
			}(i)
		}
	} else {
		sem := make(chan struct{}, 256)
		rng := rand.New(rand.NewSource(20260926))
		for n := 0; ; n++ {
			scheduled := start.Add(time.Duration(int64(n) * int64(time.Second) / int64(*rate)))
			if !scheduled.Before(end) {
				break
			}
			if d := time.Until(scheduled); d > 0 {
				time.Sleep(d)
			}
			mu.Lock()
			stop := stopped
			mu.Unlock()
			if stop {
				break
			}
			phase := "measure"
			if scheduled.Before(start.Add(*warm)) {
				phase = "warmup"
			}
			select {
			case sem <- struct{}{}:
				ref := refs[rng.Intn(len(refs))]
				wg.Add(1)
				go func() { defer func() { <-sem }(); execute(ref, scheduled) }()
			default:
				drops[phase]++
			}
		}
	}
	done := make(chan struct{})
	go func() { wg.Wait(); close(done) }()
	drainExceeded := false
	select {
	case <-done:
	case <-time.After(time.Until(end.Add(3 * time.Second))):
		drainExceeded = true
		cancel()
		<-done
	}
	phases := map[string]any{}
	for _, phase := range []string{"warmup", "measure"} {
		var send, sched, lag []float64
		schedulerMisses := 0
		statuses := map[string]int{}
		windowCompleted, windowSuccess, windowJobs, windowAttempts, drainCompleted, drainSuccess, drainJobs := 0, 0, 0, 0, 0, 0, 0
		attempts, completed, success, idle, errors, timeouts, jobs, dups := 0, 0, 0, 0, 0, 0, 0, 0
		for _, s := range samples {
			if s.Phase != phase {
				continue
			}
			attempts++
			lower, upper := float64(warm.Microseconds())/1000, float64((*warm+*dur).Microseconds())/1000
			if phase == "warmup" {
				lower = 0
				upper = float64(warm.Microseconds()) / 1000
			}
			if s.SendOffsetMS >= lower && s.SendOffsetMS < upper {
				windowAttempts++
			}
			if s.FinishOffsetMS >= lower && s.FinishOffsetMS < upper {
				if s.Status > 0 {
					windowCompleted++
				}
				if s.Success {
					windowSuccess++
				}
				if s.Op == "complete" && s.Success {
					windowJobs++
				}
			} else if s.FinishOffsetMS >= upper {
				if s.Status > 0 {
					drainCompleted++
				}
				if s.Success {
					drainSuccess++
				}
				if s.Op == "complete" && s.Success {
					drainJobs++
				}
			}
			statuses[fmt.Sprint(s.Status)]++
			if *rate > 0 && s.LagMS > 1000/float64(*rate) {
				schedulerMisses++
			}
			if s.Status > 0 {
				completed++
			}
			send = append(send, s.SendMS)
			sched = append(sched, s.ScheduledMS)
			lag = append(lag, s.LagMS)
			if s.Success {
				success++
			}
			if s.Idle {
				idle++
			}
			if s.Error != "" {
				errors++
			}
			if strings.Contains(s.Error, "timeout") || strings.Contains(s.Error, "deadline") {
				timeouts++
			}
			if s.Op == "complete" && s.Success {
				jobs++
			}
			if s.Duplicate {
				dups++
			}
		}
		seconds := dur.Seconds()
		if phase == "warmup" {
			seconds = warm.Seconds()
		}
		var scheduledCount any
		if *rate > 0 {
			scheduledCount = attempts + drops[phase]
		}
		phases[phase] = map[string]any{"cohort_attempts": attempts, "cohort_completed_requests": completed, "cohort_successful_http": success, "cohort_completed_jobs": jobs, "attempts": attempts, "sample_count": len(send), "scheduler_misses": schedulerMisses, "scheduler_miss_definition": "dispatch lag greater than one arrival interval", "status_counts": statuses, "completed_requests": completed, "successful_http": success, "window_attempts": windowAttempts, "window_completed_requests": windowCompleted, "window_successful_http": windowSuccess, "window_completed_jobs": windowJobs, "drain_completed_requests": drainCompleted, "drain_successful_http": drainSuccess, "drain_completed_jobs": drainJobs, "attempted_rps": float64(windowAttempts) / seconds, "completed_rps": float64(windowCompleted) / seconds, "successful_rps": float64(windowSuccess) / seconds, "completed_jobs": jobs, "completed_jobs_per_second": float64(windowJobs) / seconds, "errors": errors, "timeouts": timeouts, "idle_claims": idle, "duplicates": dups, "drops": drops[phase], "scheduled_count": scheduledCount, "send_latency_ms": map[string]any{"p50": pct(send, .5), "p95": pct(send, .95), "p99": pct(send, .99)}, "scheduled_latency_ms": map[string]any{"p50": pct(sched, .5), "p95": pct(sched, .95), "p99": pct(sched, .99)}, "scheduler_lag_ms": map[string]any{"p50": pct(lag, .5), "p95": pct(lag, .95), "p99": pct(lag, .99)}}
	}
	result := map[string]any{"throughput_semantics": "RPS counts only matching start-cohort responses finished inside the corresponding window; cohort counts and latencies retain drain and timeouts; warmup crossing never enters measure throughput", "phases": phases, "samples": samples, "claimed_unique": len(seen), "acknowledged_unique": len(acks), "lost_acknowledgements": len(seen) - len(acks), "stopped_transport_failures": stopped, "timeout_latencies_censored": true, "generator_capacity_flag": drops["measure"] > 0, "drain_budget_exceeded": drainExceeded, "wall_seconds": time.Since(start).Seconds()}
	f, e := os.OpenFile(*out, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if e != nil {
		panic(e)
	}
	defer f.Close()
	json.NewEncoder(f).Encode(result)
	fmt.Println("load complete")
}
