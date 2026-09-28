package main

import (
	"auditledger/internal/platform"
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const maxBalance int64 = 9000000000000000

var nameRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type api struct{ db *sql.DB }
type problem struct{ code string }

func (p problem) Error() string { return p.code }
func bad(code string) error     { return problem{code} }
func status(err error) int {
	if p, ok := err.(problem); ok {
		switch p.code {
		case "invalid":
			return 400
		case "not_found":
			return 404
		default:
			return 409
		}
	}
	return 500
}
func reply(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
func fail(w http.ResponseWriter, err error) {
	if status(err) == 500 {
		log.Printf("internal error: %v", err)
	}
	code := "internal"
	if p, ok := err.(problem); ok {
		code = p.code
	}
	reply(w, status(err), map[string]any{"error": map[string]any{"code": code}})
}
func object(r *http.Request) (map[string]any, string, error) {
	d := json.NewDecoder(io.LimitReader(r.Body, 1048577))
	d.UseNumber()
	var v any
	if err := d.Decode(&v); err != nil {
		return nil, "", bad("invalid")
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, "", bad("invalid")
	}
	var tail any
	if err := d.Decode(&tail); err != io.EOF {
		return nil, "", bad("invalid")
	}
	b, _ := json.Marshal(m)
	return m, string(b), nil
}
func fields(m map[string]any, required, optional []string) error {
	allow := map[string]bool{}
	for _, s := range required {
		allow[s] = true
		if _, ok := m[s]; !ok {
			return bad("invalid")
		}
	}
	for _, s := range optional {
		allow[s] = true
	}
	for s := range m {
		if !allow[s] {
			return bad("invalid")
		}
	}
	return nil
}
func str(m map[string]any, k string, re *regexp.Regexp, required bool) (string, error) {
	v, ok := m[k]
	if !ok && !required {
		return "", nil
	}
	s, ok := v.(string)
	if !ok || !re.MatchString(s) {
		return "", bad("invalid")
	}
	return s, nil
}
func num(m map[string]any, k string, min, max int64, required bool) (int64, bool, error) {
	v, ok := m[k]
	if !ok {
		if required {
			return 0, false, bad("invalid")
		}
		return 0, false, nil
	}
	n, ok := v.(json.Number)
	if !ok {
		return 0, false, bad("invalid")
	}
	i, e := strconv.ParseInt(string(n), 10, 64)
	if e != nil || i < min || i > max {
		return 0, false, bad("invalid")
	}
	return i, true, nil
}
func id() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b[:])
}

type account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}

func getAccount(c *sql.Conn, t, n string) (account, error) {
	var a account
	err := c.QueryRowContext(context.Background(), `SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	if errors.Is(err, sql.ErrNoRows) {
		return a, bad("not_found")
	}
	if err != nil {
		return a, err
	}
	a.Available = a.Balance - a.Reserved
	return a, nil
}

type transfer struct {
	ID       string `json:"id"`
	From     string `json:"from"`
	To       string `json:"to"`
	Amount   int64  `json:"amount"`
	Reversed bool   `json:"reversed"`
	LegacyID *int64 `json:"legacy_id,omitempty"`
}

func getTransfer(c *sql.Conn, t, id string) (transfer, string, error) {
	var x transfer
	var reversed int
	var legacy sql.NullInt64
	var kind string
	err := c.QueryRowContext(context.Background(), `SELECT id,source,target,amount,reversed,kind,legacy_id FROM transfers WHERE tenant=? AND id=?`, t, id).Scan(&x.ID, &x.From, &x.To, &x.Amount, &reversed, &kind, &legacy)
	if errors.Is(err, sql.ErrNoRows) {
		return x, "", bad("not_found")
	}
	if err != nil {
		return x, "", err
	}
	x.Reversed = reversed != 0
	if legacy.Valid {
		x.LegacyID = &legacy.Int64
	}
	return x, kind, nil
}

type hold struct {
	ID      string `json:"id"`
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	State   string `json:"state"`
}

func getHold(c *sql.Conn, t, id string) (hold, error) {
	var x hold
	err := c.QueryRowContext(context.Background(), `SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?`, t, id).Scan(&x.ID, &x.Account, &x.Amount, &x.State)
	if errors.Is(err, sql.ErrNoRows) {
		return x, bad("not_found")
	}
	return x, err
}
func checkVersion(a account, v int64, yes bool) error {
	if yes && a.Version != v {
		return bad("version_conflict")
	}
	return nil
}
func save(c *sql.Conn, t string, a account) error {
	_, e := c.ExecContext(context.Background(), `UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?`, a.Balance, a.Reserved, a.Version, t, a.Name)
	return e
}
func (s *api) write(w http.ResponseWriter, r *http.Request, t, path, body string, fn func(*sql.Conn) (int, any, error)) {
	key := r.Header.Get("Idempotency-Key")
	if !keyRE.MatchString(key) {
		fail(w, bad("invalid"))
		return
	}
	ctx := r.Context()
	c, e := s.db.Conn(ctx)
	if e != nil {
		fail(w, e)
		return
	}
	defer c.Close()
	if _, e = c.ExecContext(ctx, "BEGIN IMMEDIATE"); e != nil {
		fail(w, e)
		return
	}
	committed := false
	defer func() {
		if !committed {
			c.ExecContext(context.Background(), "ROLLBACK")
		}
	}()
	var oldPath, oldBody string
	var oldStatus int
	var oldResult []byte
	e = c.QueryRowContext(ctx, `SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?`, t, key).Scan(&oldPath, &oldBody, &oldStatus, &oldResult)
	if e == nil {
		if oldPath != path || oldBody != body {
			fail(w, bad("idempotency_conflict"))
			return
		}
		if _, e = c.ExecContext(ctx, "COMMIT"); e != nil {
			fail(w, e)
			return
		}
		committed = true
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(oldStatus)
		_, _ = w.Write(oldResult)
		return
	}
	if !errors.Is(e, sql.ErrNoRows) {
		fail(w, e)
		return
	}
	code, result, e := fn(c)
	if e != nil {
		fail(w, e)
		return
	}
	raw, e := json.Marshal(result)
	if e != nil {
		fail(w, e)
		return
	}
	if _, e = c.ExecContext(ctx, `INSERT INTO idempotency VALUES(?,?,?,?,?,?)`, t, key, path, body, code, raw); e != nil {
		fail(w, e)
		return
	}
	if _, e = c.ExecContext(ctx, "COMMIT"); e != nil {
		fail(w, e)
		return
	}
	committed = true
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_, _ = w.Write(raw)
}

type transferReq struct {
	from, to     string
	amount       int64
	fv, tv       int64
	hasFV, hasTV bool
}

func parseTransfer(m map[string]any) (transferReq, error) {
	var q transferReq
	var e error
	if e = fields(m, []string{"from", "to", "amount"}, []string{"from_version", "to_version"}); e != nil {
		return q, e
	}
	if q.from, e = str(m, "from", nameRE, true); e != nil {
		return q, e
	}
	if q.to, e = str(m, "to", nameRE, true); e != nil {
		return q, e
	}
	if q.from == q.to {
		return q, bad("invalid")
	}
	if q.amount, _, e = num(m, "amount", 1, 1000000000, true); e != nil {
		return q, e
	}
	if q.fv, q.hasFV, e = num(m, "from_version", 1, 9223372036854775807, false); e != nil {
		return q, e
	}
	q.tv, q.hasTV, e = num(m, "to_version", 1, 9223372036854775807, false)
	return q, e
}
func postTransfer(c *sql.Conn, t string, q transferReq, kind string) (transfer, account, account, error) {
	var x transfer
	from, e := getAccount(c, t, q.from)
	if e != nil {
		return x, from, account{}, e
	}
	to, e := getAccount(c, t, q.to)
	if e != nil {
		return x, from, to, e
	}
	if e = checkVersion(from, q.fv, q.hasFV); e != nil {
		return x, from, to, e
	}
	if e = checkVersion(to, q.tv, q.hasTV); e != nil {
		return x, from, to, e
	}
	if from.Available < q.amount {
		return x, from, to, bad("insufficient")
	}
	if to.Balance > maxBalance-q.amount {
		return x, from, to, bad("insufficient")
	}
	from.Balance -= q.amount
	from.Available -= q.amount
	from.Version++
	to.Balance += q.amount
	to.Available += q.amount
	to.Version++
	x = transfer{ID: id(), From: q.from, To: q.to, Amount: q.amount}
	if e = save(c, t, from); e != nil {
		return x, from, to, e
	}
	if e = save(c, t, to); e != nil {
		return x, from, to, e
	}
	_, e = c.ExecContext(context.Background(), `INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind) VALUES(?,?,?,?,?,0,?)`, t, x.ID, x.From, x.To, x.Amount, kind)
	if e != nil {
		return x, from, to, e
	}
	if e = platform.AddEntry(c, t, q.from, kind, -q.amount, 0, x.ID, nil); e != nil {
		return x, from, to, e
	}
	e = platform.AddEntry(c, t, q.to, kind, q.amount, 0, x.ID, nil)
	return x, from, to, e
}
func (s *api) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	if path == "/health" && r.Method == "GET" {
		reply(w, 200, map[string]any{"ok": true})
		return
	}
	t := r.Header.Get("X-Tenant")
	if !nameRE.MatchString(t) {
		fail(w, bad("invalid"))
		return
	}
	if r.Method == "GET" {
		s.read(w, r, t)
		return
	}
	if r.Method != "POST" {
		fail(w, bad("not_found"))
		return
	}
	parts := strings.Split(strings.Trim(path, "/"), "/")
	route := ""
	item := ""
	switch {
	case path == "/accounts":
		route = "account"
	case path == "/transfers":
		route = "transfer"
	case path == "/batches":
		route = "batch"
	case path == "/holds":
		route = "hold"
	case len(parts) == 3 && parts[0] == "holds" && parts[2] == "capture":
		route = "capture"
		item = parts[1]
	case len(parts) == 3 && parts[0] == "holds" && parts[2] == "release":
		route = "release"
		item = parts[1]
	case len(parts) == 3 && parts[0] == "transfers" && parts[2] == "reverse":
		route = "reverse"
		item = parts[1]
	}
	if route == "" || strings.Contains(item, "%") || item == "" && (route == "capture" || route == "release" || route == "reverse") {
		fail(w, bad("not_found"))
		return
	}
	m, body, e := object(r)
	if e != nil {
		fail(w, e)
		return
	}
	// Validate the entire request before consulting replay state. State-dependent checks happen inside the transaction.
	var name, to string
	var opening, amount, v, fv, tv int64
	var hv, hfv, htv bool
	var batch []transferReq
	switch route {
	case "account":
		e = fields(m, []string{"name", "opening"}, nil)
		if e == nil {
			name, e = str(m, "name", nameRE, true)
		}
		if e == nil {
			opening, _, e = num(m, "opening", 0, 1000000000, true)
		}
	case "transfer":
		var q transferReq
		q, e = parseTransfer(m)
		if e == nil {
			batch = []transferReq{q}
		}
	case "batch":
		e = fields(m, []string{"transfers"}, nil)
		if e == nil {
			var a []any
			var ok bool
			a, ok = m["transfers"].([]any)
			if !ok || len(a) < 1 || len(a) > 20 {
				e = bad("invalid")
			} else {
				for _, v := range a {
					mm, ok := v.(map[string]any)
					if !ok {
						e = bad("invalid")
						break
					}
					var q transferReq
					q, e = parseTransfer(mm)
					if e != nil {
						break
					}
					batch = append(batch, q)
				}
			}
		}
	case "hold":
		e = fields(m, []string{"account", "amount"}, []string{"version"})
		if e == nil {
			name, e = str(m, "account", nameRE, true)
		}
		if e == nil {
			amount, _, e = num(m, "amount", 1, 1000000000, true)
		}
		if e == nil {
			v, hv, e = num(m, "version", 1, 9223372036854775807, false)
		}
	case "capture":
		e = fields(m, []string{"to"}, []string{"from_version", "to_version"})
		if e == nil {
			to, e = str(m, "to", nameRE, true)
		}
		if e == nil {
			fv, hfv, e = num(m, "from_version", 1, 9223372036854775807, false)
		}
		if e == nil {
			tv, htv, e = num(m, "to_version", 1, 9223372036854775807, false)
		}
	case "release":
		e = fields(m, nil, []string{"version"})
		if e == nil {
			v, hv, e = num(m, "version", 1, 9223372036854775807, false)
		}
	case "reverse":
		e = fields(m, nil, []string{"from_version", "to_version"})
		if e == nil {
			fv, hfv, e = num(m, "from_version", 1, 9223372036854775807, false)
		}
		if e == nil {
			tv, htv, e = num(m, "to_version", 1, 9223372036854775807, false)
		}
	}
	if e != nil {
		fail(w, e)
		return
	}
	s.write(w, r, t, path, body, func(c *sql.Conn) (int, any, error) {
		switch route {
		case "account":
			_, e := getAccount(c, t, name)
			if e == nil {
				return 0, nil, bad("exists")
			}
			if e != nil && status(e) != 404 {
				return 0, nil, e
			}
			a := account{Name: name, Balance: opening, Available: opening, Version: 1}
			_, e = c.ExecContext(context.Background(), `INSERT INTO accounts VALUES(?,?,?,0,1)`, t, name, opening)
			if e != nil {
				return 0, nil, e
			}
			e = platform.AddEntry(c, t, name, "opening", opening, 0, id(), nil)
			return 201, map[string]any{"account": a}, e
		case "transfer", "batch":
			xs := []transfer{}
			touched := map[string]bool{}
			for _, q := range batch {
				x, _, _, e := postTransfer(c, t, q, "transfer")
				if e != nil {
					return 0, nil, e
				}
				xs = append(xs, x)
				touched[q.from] = true
				touched[q.to] = true
			}
			names := []string{}
			for n := range touched {
				names = append(names, n)
			}
			sort.Strings(names)
			as := []account{}
			for _, n := range names {
				a, e := getAccount(c, t, n)
				if e != nil {
					return 0, nil, e
				}
				as = append(as, a)
			}
			if route == "transfer" {
				q := batch[0]
				a, _ := getAccount(c, t, q.from)
				b, _ := getAccount(c, t, q.to)
				return 201, map[string]any{"transfer": xs[0], "accounts": []account{a, b}}, nil
			}
			return 201, map[string]any{"transfers": xs, "accounts": as}, nil
		case "hold":
			a, e := getAccount(c, t, name)
			if e != nil {
				return 0, nil, e
			}
			if e = checkVersion(a, v, hv); e != nil {
				return 0, nil, e
			}
			if a.Available < amount {
				return 0, nil, bad("insufficient")
			}
			a.Reserved += amount
			a.Available -= amount
			a.Version++
			h := hold{ID: id(), Account: name, Amount: amount, State: "active"}
			if e = save(c, t, a); e != nil {
				return 0, nil, e
			}
			_, e = c.ExecContext(context.Background(), `INSERT INTO holds VALUES(?,?,?,?,?)`, t, h.ID, name, amount, h.State)
			if e != nil {
				return 0, nil, e
			}
			e = platform.AddEntry(c, t, name, "hold", 0, amount, h.ID, nil)
			return 201, map[string]any{"hold": h, "account": a}, e
		case "capture":
			h, e := getHold(c, t, item)
			if e != nil {
				return 0, nil, e
			}
			if h.State != "active" {
				return 0, nil, bad("terminal")
			}
			if h.Account == to {
				return 0, nil, bad("invalid")
			}
			a, e := getAccount(c, t, h.Account)
			if e != nil {
				return 0, nil, e
			}
			b, e := getAccount(c, t, to)
			if e != nil {
				return 0, nil, e
			}
			if e = checkVersion(a, fv, hfv); e != nil {
				return 0, nil, e
			}
			if e = checkVersion(b, tv, htv); e != nil {
				return 0, nil, e
			}
			if b.Balance > maxBalance-h.Amount {
				return 0, nil, bad("insufficient")
			}
			a.Balance -= h.Amount
			a.Reserved -= h.Amount
			a.Version++
			a.Available = a.Balance - a.Reserved
			b.Balance += h.Amount
			b.Available += h.Amount
			b.Version++
			h.State = "captured"
			x := transfer{ID: id(), From: h.Account, To: to, Amount: h.Amount}
			if e = save(c, t, a); e != nil {
				return 0, nil, e
			}
			if e = save(c, t, b); e != nil {
				return 0, nil, e
			}
			if _, e = c.ExecContext(context.Background(), `UPDATE holds SET state='captured' WHERE tenant=? AND id=?`, t, item); e != nil {
				return 0, nil, e
			}
			if _, e = c.ExecContext(context.Background(), `INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind) VALUES(?,?,?,?,?,0,'capture')`, t, x.ID, x.From, x.To, x.Amount); e != nil {
				return 0, nil, e
			}
			if e = platform.AddEntry(c, t, a.Name, "capture", -h.Amount, -h.Amount, x.ID, nil); e != nil {
				return 0, nil, e
			}
			e = platform.AddEntry(c, t, b.Name, "capture", h.Amount, 0, x.ID, nil)
			return 200, map[string]any{"hold": h, "transfer": x, "accounts": []account{a, b}}, e
		case "release":
			h, e := getHold(c, t, item)
			if e != nil {
				return 0, nil, e
			}
			if h.State != "active" {
				return 0, nil, bad("terminal")
			}
			a, e := getAccount(c, t, h.Account)
			if e != nil {
				return 0, nil, e
			}
			if e = checkVersion(a, v, hv); e != nil {
				return 0, nil, e
			}
			a.Reserved -= h.Amount
			a.Available += h.Amount
			a.Version++
			h.State = "released"
			if e = save(c, t, a); e != nil {
				return 0, nil, e
			}
			if _, e = c.ExecContext(context.Background(), `UPDATE holds SET state='released' WHERE tenant=? AND id=?`, t, item); e != nil {
				return 0, nil, e
			}
			e = platform.AddEntry(c, t, a.Name, "release", 0, -h.Amount, h.ID, nil)
			return 200, map[string]any{"hold": h, "account": a}, e
		case "reverse":
			orig, kind, e := getTransfer(c, t, item)
			if e != nil {
				return 0, nil, e
			}
			if kind == "reversal" || orig.Reversed {
				return 0, nil, bad("terminal")
			}
			a, e := getAccount(c, t, orig.From)
			if e != nil {
				return 0, nil, e
			}
			b, e := getAccount(c, t, orig.To)
			if e != nil {
				return 0, nil, e
			}
			if e = checkVersion(a, fv, hfv); e != nil {
				return 0, nil, e
			}
			if e = checkVersion(b, tv, htv); e != nil {
				return 0, nil, e
			}
			if b.Available < orig.Amount {
				return 0, nil, bad("insufficient")
			}
			if a.Balance > maxBalance-orig.Amount {
				return 0, nil, bad("insufficient")
			}
			a.Balance += orig.Amount
			a.Available += orig.Amount
			a.Version++
			b.Balance -= orig.Amount
			b.Available -= orig.Amount
			b.Version++
			rev := transfer{ID: id(), From: orig.To, To: orig.From, Amount: orig.Amount}
			orig.Reversed = true
			if e = save(c, t, a); e != nil {
				return 0, nil, e
			}
			if e = save(c, t, b); e != nil {
				return 0, nil, e
			}
			if _, e = c.ExecContext(context.Background(), `UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?`, t, item); e != nil {
				return 0, nil, e
			}
			if _, e = c.ExecContext(context.Background(), `INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind) VALUES(?,?,?,?,?,0,'reversal')`, t, rev.ID, rev.From, rev.To, rev.Amount); e != nil {
				return 0, nil, e
			}
			if e = platform.AddEntry(c, t, b.Name, "reversal", -orig.Amount, 0, rev.ID, nil); e != nil {
				return 0, nil, e
			}
			e = platform.AddEntry(c, t, a.Name, "reversal", orig.Amount, 0, rev.ID, nil)
			return 200, map[string]any{"transfer": orig, "reversal": rev, "accounts": []account{a, b}}, e
		}
		return 0, nil, bad("not_found")
	})
}
func main() {
	dbPath := flag.String("db", "ledger.db", "SQLite database path")
	listen := flag.String("listen", "127.0.0.1:8080", "HTTP listen address")
	flag.Parse()
	db, e := platform.Open(*dbPath)
	if e != nil {
		log.Fatal(e)
	}
	defer db.Close()
	srv := &http.Server{Addr: *listen, Handler: &api{db: db}, ReadHeaderTimeout: 10 * time.Second}
	errs := make(chan error, 1)
	go func() { errs <- srv.ListenAndServe() }()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	select {
	case <-sig:
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(ctx)
	case e = <-errs:
		if e != nil && e != http.ErrServerClosed {
			log.Fatal(e)
		}
	}
}

type entry struct {
	Seq           int64  `json:"seq"`
	Account       string `json:"account"`
	Kind          string `json:"kind"`
	BalanceDelta  int64  `json:"balance_delta"`
	ReservedDelta int64  `json:"reserved_delta"`
	OperationID   string `json:"operation_id"`
	LegacyID      *int64 `json:"legacy_id,omitempty"`
}
type summaryAccount struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
}
type totals struct {
	Balance   int64 `json:"balance"`
	Reserved  int64 `json:"reserved"`
	Available int64 `json:"available"`
}

func queryInt(q map[string][]string, k string, def, min, max int64) (int64, error) {
	vs, ok := q[k]
	if !ok {
		return def, nil
	}
	if len(vs) != 1 || vs[0] == "" {
		return 0, bad("invalid")
	}
	n, e := strconv.ParseInt(vs[0], 10, 64)
	if e != nil || n < min || n > max {
		return 0, bad("invalid")
	}
	return n, nil
}
func (s *api) read(w http.ResponseWriter, r *http.Request, t string) {
	path := r.URL.Path
	q, queryErr := url.ParseQuery(r.URL.RawQuery)
	if queryErr != nil {
		fail(w, bad("invalid"))
		return
	}
	if strings.HasPrefix(path, "/accounts/") && strings.Count(path, "/") == 2 {
		if len(q) > 0 {
			fail(w, bad("invalid"))
			return
		}
		n := strings.TrimPrefix(path, "/accounts/")
		if !nameRE.MatchString(n) {
			fail(w, bad("not_found"))
			return
		}
		c, e := s.db.Conn(r.Context())
		if e != nil {
			fail(w, e)
			return
		}
		defer c.Close()
		a, e := getAccount(c, t, n)
		if e != nil {
			fail(w, e)
			return
		}
		reply(w, 200, map[string]any{"account": a})
		return
	}
	if path != "/entries" && path != "/summary" {
		fail(w, bad("not_found"))
		return
	}
	for k := range q {
		if k != "snapshot" && !(path == "/entries" && (k == "after" || k == "limit")) {
			fail(w, bad("invalid"))
			return
		}
	}
	c, e := s.db.Conn(r.Context())
	if e != nil {
		fail(w, e)
		return
	}
	defer c.Close()
	ctx := r.Context()
	if _, e = c.ExecContext(ctx, "BEGIN"); e != nil {
		fail(w, e)
		return
	}
	defer c.ExecContext(context.Background(), "ROLLBACK")
	var current int64
	e = c.QueryRowContext(ctx, `SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?`, t).Scan(&current)
	if e != nil {
		fail(w, e)
		return
	}
	snap, e := queryInt(q, "snapshot", current, 0, current)
	if e != nil {
		fail(w, e)
		return
	}
	if path == "/entries" {
		after, e := queryInt(q, "after", 0, 0, snap)
		if e != nil {
			fail(w, e)
			return
		}
		limit, e := queryInt(q, "limit", 50, 1, 100)
		if e != nil {
			fail(w, e)
			return
		}
		rows, e := c.QueryContext(ctx, `SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, t, after, snap, limit+1)
		if e != nil {
			fail(w, e)
			return
		}
		out := []entry{}
		for rows.Next() {
			var x entry
			var legacy sql.NullInt64
			if e = rows.Scan(&x.Seq, &x.Account, &x.Kind, &x.BalanceDelta, &x.ReservedDelta, &x.OperationID, &legacy); e != nil {
				break
			}
			if legacy.Valid {
				x.LegacyID = &legacy.Int64
			}
			out = append(out, x)
		}
		if e == nil {
			e = rows.Err()
		}
		rows.Close()
		if e != nil {
			fail(w, e)
			return
		}
		more := int64(len(out)) > limit
		if more {
			out = out[:limit]
		}
		next := after
		if len(out) > 0 {
			next = out[len(out)-1].Seq
		}
		reply(w, 200, map[string]any{"entries": out, "snapshot": snap, "next_after": next, "has_more": more})
		return
	}
	rows, e := c.QueryContext(ctx, `SELECT account,SUM(balance_delta),SUM(reserved_delta),COUNT(*) FROM entries WHERE tenant=? AND seq<=? GROUP BY account ORDER BY account`, t, snap)
	if e != nil {
		fail(w, e)
		return
	}
	as := []summaryAccount{}
	sum := totals{}
	count := int64(0)
	for rows.Next() {
		var a summaryAccount
		var accountCount int64
		if e = rows.Scan(&a.Name, &a.Balance, &a.Reserved, &accountCount); e != nil {
			break
		}
		a.Available = a.Balance - a.Reserved
		as = append(as, a)
		sum.Balance += a.Balance
		sum.Reserved += a.Reserved
		sum.Available += a.Available
		count += accountCount
	}
	if e == nil {
		e = rows.Err()
	}
	rows.Close()
	if e != nil {
		fail(w, e)
		return
	}
	reply(w, 200, map[string]any{"snapshot": snap, "accounts": as, "totals": sum, "entry_count": count})
}
