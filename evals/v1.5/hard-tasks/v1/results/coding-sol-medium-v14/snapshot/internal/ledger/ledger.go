package ledger

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const maxValue int64 = 9000000000000000

var nameRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)
var intRE = regexp.MustCompile(`^(0|[1-9][0-9]*)$`)

type Ledger struct{ DB *sql.DB }
type problem struct{ Code string }

func (p problem) Error() string { return p.Code }
func fail(code string) error    { return problem{code} }
func write(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func errwrite(w http.ResponseWriter, e error) {
	p := problem{"invalid"}
	if !errors.As(e, &p) {
		write(w, 500, map[string]any{"error": map[string]string{"code": "internal"}})
		return
	}
	s := 400
	if p.Code == "not_found" {
		s = 404
	} else if p.Code != "invalid" {
		s = 409
	}
	write(w, s, map[string]any{"error": map[string]string{"code": p.Code}})
}
func id() string { b := make([]byte, 16); _, _ = rand.Read(b); return hex.EncodeToString(b) }

type conn interface {
	ExecContext(context.Context, string, ...any) (sql.Result, error)
	QueryRowContext(context.Context, string, ...any) *sql.Row
	QueryContext(context.Context, string, ...any) (*sql.Rows, error)
}

func (l *Ledger) Init(ctx context.Context) error {
	var err error
	for attempt := 0; attempt < 150; attempt++ {
		err = l.initOnce(ctx)
		if err == nil || !strings.Contains(strings.ToLower(err.Error()), "locked") && !strings.Contains(err.Error(), "SQLITE_BUSY") {
			return err
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(100 * time.Millisecond):
		}
	}
	return err
}

func (l *Ledger) initOnce(ctx context.Context) error {
	l.DB.SetMaxOpenConns(8)
	l.DB.SetMaxIdleConns(8)
	c, e := l.DB.Conn(ctx)
	if e != nil {
		return e
	}
	defer c.Close()
	if _, e = c.ExecContext(ctx, "PRAGMA busy_timeout=15000"); e != nil {
		return e
	}
	if _, e = c.ExecContext(ctx, "PRAGMA journal_mode=WAL"); e != nil {
		return e
	}
	if _, e = c.ExecContext(ctx, "BEGIN IMMEDIATE"); e != nil {
		return e
	}
	defer c.ExecContext(context.Background(), "ROLLBACK")
	var ver int
	if e = c.QueryRowContext(ctx, "PRAGMA user_version").Scan(&ver); e != nil {
		return e
	}
	if ver > 2 {
		return fmt.Errorf("unsupported database version %d", ver)
	}
	schema := []string{
		`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name))`,
		`CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL DEFAULT 0,kind TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS entries(tenant TEXT NOT NULL,seq INTEGER NOT NULL,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,seq))`,
		`CREATE TABLE IF NOT EXISTS idem(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body TEXT NOT NULL,status INTEGER NOT NULL,result BLOB NOT NULL,PRIMARY KEY(tenant,key))`,
		`CREATE INDEX IF NOT EXISTS entries_account ON entries(tenant,account,seq)`,
	}
	for _, s := range schema {
		if _, e = c.ExecContext(ctx, s); e != nil {
			return e
		}
	}
	if ver == 1 {
		if e = migrate(ctx, c); e != nil {
			return e
		}
	}
	if _, e = c.ExecContext(ctx, "PRAGMA user_version=2"); e != nil {
		return e
	}
	_, e = c.ExecContext(ctx, "COMMIT")
	return e
}
func migrate(ctx context.Context, c conn) error {
	rows, e := c.QueryContext(ctx, `SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name`)
	if e != nil {
		return e
	}
	type arow struct {
		t, n string
		b    int64
	}
	var aa []arow
	for rows.Next() {
		var a arow
		if e = rows.Scan(&a.t, &a.n, &a.b); e != nil {
			rows.Close()
			return e
		}
		aa = append(aa, a)
	}
	e = rows.Err()
	rows.Close()
	if e != nil {
		return e
	}
	mr, e := c.QueryContext(ctx, `SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id`)
	if e != nil {
		return e
	}
	type movement struct {
		id       int64
		t, f, to string
		u        int64
	}
	var mm []movement
	delta := map[string]int64{}
	counts := map[string]int64{}
	for mr.Next() {
		var m movement
		if e = mr.Scan(&m.id, &m.t, &m.f, &m.to, &m.u); e != nil {
			mr.Close()
			return e
		}
		mm = append(mm, m)
		delta[m.t+"\x00"+m.f] += m.u
		delta[m.t+"\x00"+m.to] -= m.u
		counts[m.t+"\x00"+m.f]++
		counts[m.t+"\x00"+m.to]++
	}
	e = mr.Err()
	mr.Close()
	if e != nil {
		return e
	}
	seq := map[string]int64{}
	for _, a := range aa {
		open := a.b + delta[a.t+"\x00"+a.n]
		if open < 0 || open > maxValue || a.b < 0 || a.b > maxValue {
			return fmt.Errorf("invalid legacy balance")
		}
		if _, e = c.ExecContext(ctx, `INSERT INTO accounts VALUES(?,?,?,?,?)`, a.t, a.n, a.b, 0, 1+counts[a.t+"\x00"+a.n]); e != nil {
			return e
		}
		seq[a.t]++
		if _, e = c.ExecContext(ctx, `INSERT INTO entries(tenant,seq,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?,?,?,?,?,?)`, a.t, seq[a.t], a.n, "opening", open, 0, id()); e != nil {
			return e
		}
	}
	for _, m := range mm {
		tid := id()
		if _, e = c.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind,legacy_id) VALUES(?,?,?,?,?,0,'ordinary',?)`, m.t, tid, m.f, m.to, m.u, m.id); e != nil {
			return e
		}
		seq[m.t]++
		if _, e = c.ExecContext(ctx, `INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)`, m.t, seq[m.t], m.f, "transfer", -m.u, 0, tid, m.id); e != nil {
			return e
		}
		seq[m.t]++
		if _, e = c.ExecContext(ctx, `INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)`, m.t, seq[m.t], m.to, "transfer", m.u, 0, tid, m.id); e != nil {
			return e
		}
	}
	return nil
}
func (l *Ledger) transaction(ctx context.Context, fn func(*sql.Conn) error) error {
	c, e := l.DB.Conn(ctx)
	if e != nil {
		return e
	}
	defer c.Close()
	if _, e = c.ExecContext(ctx, "PRAGMA busy_timeout=15000"); e != nil {
		return e
	}
	if _, e = c.ExecContext(ctx, "BEGIN IMMEDIATE"); e != nil {
		return e
	}
	defer c.ExecContext(context.Background(), "ROLLBACK")
	if e = fn(c); e != nil {
		return e
	}
	_, e = c.ExecContext(ctx, "COMMIT")
	return e
}
func parseBody(r *http.Request) (map[string]json.RawMessage, string, error) {
	data, e := io.ReadAll(io.LimitReader(r.Body, (1<<20)+1))
	if e != nil || len(data) > 1<<20 {
		return nil, "", fail("invalid")
	}
	d := json.NewDecoder(strings.NewReader(string(data)))
	d.DisallowUnknownFields()
	var m map[string]json.RawMessage
	if e := d.Decode(&m); e != nil || m == nil {
		return nil, "", fail("invalid")
	}
	var extra any
	if e := d.Decode(&extra); e != io.EOF {
		return nil, "", fail("invalid")
	}
	// Decode once more into ordinary maps so JSON object order and whitespace at
	// every nesting level have no effect on the idempotency fingerprint.
	var semantic any
	canonDecoder := json.NewDecoder(strings.NewReader(rawJSON(m)))
	canonDecoder.UseNumber()
	if e := canonDecoder.Decode(&semantic); e != nil {
		return nil, "", fail("invalid")
	}
	b, _ := json.Marshal(semantic)
	return m, string(b), nil
}

func rawJSON(m map[string]json.RawMessage) string {
	b, _ := json.Marshal(m)
	return string(b)
}
func fields(m map[string]json.RawMessage, required, optional []string) error {
	allowed := map[string]bool{}
	for _, k := range required {
		allowed[k] = true
		if _, ok := m[k]; !ok {
			return fail("invalid")
		}
	}
	for _, k := range optional {
		allowed[k] = true
	}
	for k := range m {
		if !allowed[k] {
			return fail("invalid")
		}
	}
	return nil
}
func str(m map[string]json.RawMessage, k string, pattern *regexp.Regexp) (string, error) {
	var v string
	if e := json.Unmarshal(m[k], &v); e != nil || !pattern.MatchString(v) {
		return "", fail("invalid")
	}
	return v, nil
}
func number(m map[string]json.RawMessage, k string, required bool, min, max int64) (int64, bool, error) {
	v, ok := m[k]
	if !ok {
		if required {
			return 0, false, fail("invalid")
		}
		return 0, false, nil
	}
	s := string(v)
	if !intRE.MatchString(s) {
		return 0, false, fail("invalid")
	}
	n, e := strconv.ParseInt(s, 10, 64)
	if e != nil || n < min || n > max {
		return 0, false, fail("invalid")
	}
	return n, true, nil
}
func suppliedVersion(m map[string]json.RawMessage, k string) (int64, bool, error) {
	v, ok := m[k]
	if !ok {
		return 0, false, nil
	}
	s := string(v)
	if !intRE.MatchString(s) || s == "0" {
		return 0, false, fail("invalid")
	}
	n, e := strconv.ParseInt(s, 10, 64)
	if e != nil {
		// A positive integer beyond SQLite's signed range is a valid but
		// necessarily mismatched optimistic version.
		return -1, true, nil
	}
	return n, true, nil
}
func signedQuery(v string) (int64, error) {
	if !intRE.MatchString(v) {
		return 0, fail("invalid")
	}
	n, e := strconv.ParseInt(v, 10, 64)
	if e != nil {
		return 0, fail("invalid")
	}
	return n, nil
}
func add(a, b int64) (int64, error) {
	if b > 0 && a > maxValue-b || b < 0 && a < -b {
		return 0, fail("invalid")
	}
	return a + b, nil
}

type Account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}

func account(ctx context.Context, c conn, t, n string) (Account, error) {
	var a Account
	e := c.QueryRowContext(ctx, `SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	if errors.Is(e, sql.ErrNoRows) {
		return a, fail("not_found")
	}
	if e != nil {
		return a, e
	}
	a.Available = a.Balance - a.Reserved
	return a, nil
}
func save(ctx context.Context, c conn, t string, a Account) error {
	a.Version++
	a.Available = a.Balance - a.Reserved
	_, e := c.ExecContext(ctx, `UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?`, a.Balance, a.Reserved, a.Version, t, a.Name)
	return e
}
func version(a Account, v int64, present bool) error {
	if present && a.Version != v {
		return fail("version_conflict")
	}
	return nil
}
func entry(ctx context.Context, c conn, t, n, kind, op string, bd, rd int64) error {
	var seq int64
	if e := c.QueryRowContext(ctx, `SELECT COALESCE(MAX(seq),0)+1 FROM entries WHERE tenant=?`, t).Scan(&seq); e != nil {
		return e
	}
	_, e := c.ExecContext(ctx, `INSERT INTO entries(tenant,seq,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?,?,?,?,?,?)`, t, seq, n, kind, bd, rd, op)
	return e
}

type Transfer struct {
	ID       string `json:"id"`
	From     string `json:"from"`
	To       string `json:"to"`
	Amount   int64  `json:"amount"`
	Reversed bool   `json:"reversed"`
	LegacyID *int64 `json:"legacy_id,omitempty"`
}
type Hold struct {
	ID      string `json:"id"`
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	State   string `json:"state"`
}

func transfer(ctx context.Context, c conn, t, from, to string, amount, fv, tv int64, fh, th bool, kind string) (Transfer, Account, Account, error) {
	var z Transfer
	var a, b Account
	var e error
	a, e = account(ctx, c, t, from)
	if e != nil {
		return z, a, b, e
	}
	b, e = account(ctx, c, t, to)
	if e != nil {
		return z, a, b, e
	}
	if e = version(a, fv, fh); e != nil {
		return z, a, b, e
	}
	if e = version(b, tv, th); e != nil {
		return z, a, b, e
	}
	if a.Available < amount {
		return z, a, b, fail("insufficient")
	}
	nb, e := add(b.Balance, amount)
	if e != nil {
		return z, a, b, e
	}
	a.Balance -= amount
	b.Balance = nb
	a.Version++
	b.Version++
	a.Available = a.Balance - a.Reserved
	b.Available = b.Balance - b.Reserved
	z = Transfer{ID: id(), From: from, To: to, Amount: amount}
	if _, e = c.ExecContext(ctx, `UPDATE accounts SET balance=?,version=? WHERE tenant=? AND name=?`, a.Balance, a.Version, t, from); e != nil {
		return z, a, b, e
	}
	if _, e = c.ExecContext(ctx, `UPDATE accounts SET balance=?,version=? WHERE tenant=? AND name=?`, b.Balance, b.Version, t, to); e != nil {
		return z, a, b, e
	}
	if _, e = c.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind) VALUES(?,?,?,?,?,0,?)`, t, z.ID, from, to, amount, kind); e != nil {
		return z, a, b, e
	}
	if e = entry(ctx, c, t, from, kind, z.ID, -amount, 0); e != nil {
		return z, a, b, e
	}
	e = entry(ctx, c, t, to, kind, z.ID, amount, 0)
	return z, a, b, e
}
func getTransfer(ctx context.Context, c conn, t, id string) (Transfer, string, error) {
	var x Transfer
	var rev int
	var kind string
	var lid sql.NullInt64
	e := c.QueryRowContext(ctx, `SELECT id,source,target,amount,reversed,kind,legacy_id FROM transfers WHERE tenant=? AND id=?`, t, id).Scan(&x.ID, &x.From, &x.To, &x.Amount, &rev, &kind, &lid)
	if errors.Is(e, sql.ErrNoRows) {
		return x, "", fail("not_found")
	}
	if e != nil {
		return x, "", e
	}
	x.Reversed = rev != 0
	if lid.Valid {
		x.LegacyID = &lid.Int64
	}
	return x, kind, nil
}
func getHold(ctx context.Context, c conn, t, id string) (Hold, error) {
	var h Hold
	e := c.QueryRowContext(ctx, `SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?`, t, id).Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	if errors.Is(e, sql.ErrNoRows) {
		return h, fail("not_found")
	}
	return h, e
}

type transferReq struct {
	From, To       string
	Amount, FV, TV int64
	FH, TH         bool
}

func parseTransfer(m map[string]json.RawMessage) (transferReq, error) {
	var x transferReq
	var e error
	if e = fields(m, []string{"from", "to", "amount"}, []string{"from_version", "to_version"}); e != nil {
		return x, e
	}
	if x.From, e = str(m, "from", nameRE); e != nil {
		return x, e
	}
	if x.To, e = str(m, "to", nameRE); e != nil {
		return x, e
	}
	if x.From == x.To {
		return x, fail("invalid")
	}
	if x.Amount, _, e = number(m, "amount", true, 1, 1000000000); e != nil {
		return x, e
	}
	if x.FV, x.FH, e = suppliedVersion(m, "from_version"); e != nil {
		return x, e
	}
	x.TV, x.TH, e = suppliedVersion(m, "to_version")
	return x, e
}
func parseObject(raw json.RawMessage) (map[string]json.RawMessage, error) {
	var m map[string]json.RawMessage
	if e := json.Unmarshal(raw, &m); e != nil || m == nil {
		return nil, fail("invalid")
	}
	return m, nil
}
func route(path string) (string, string) {
	if path == "/accounts" || path == "/transfers" || path == "/batches" || path == "/holds" || path == "/entries" || path == "/summary" || path == "/health" {
		return path, ""
	}
	p := strings.Split(path, "/")
	if len(p) == 3 && p[0] == "" && p[1] == "accounts" && nameRE.MatchString(p[2]) {
		return "account", p[2]
	}
	if len(p) == 4 && p[0] == "" && p[1] == "holds" && (p[3] == "capture" || p[3] == "release") && p[2] != "" {
		return p[3], p[2]
	}
	if len(p) == 4 && p[0] == "" && p[1] == "transfers" && p[3] == "reverse" && p[2] != "" {
		return "reverse", p[2]
	}
	return "", ""
}
func (l *Ledger) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" && r.Method == http.MethodGet {
		var n int
		e := l.DB.QueryRowContext(r.Context(), "SELECT 1").Scan(&n)
		if e != nil {
			write(w, 503, map[string]any{"error": map[string]string{"code": "unavailable"}})
			return
		}
		write(w, 200, map[string]bool{"ok": true})
		return
	}
	rt, arg := route(r.URL.Path)
	readRoute := r.Method == http.MethodGet && (rt == "account" || rt == "/entries" || rt == "/summary")
	writeRoute := r.Method == http.MethodPost && (rt == "/accounts" || rt == "/transfers" || rt == "/batches" || rt == "/holds" || rt == "capture" || rt == "release" || rt == "reverse")
	if !readRoute && !writeRoute {
		errwrite(w, fail("not_found"))
		return
	}
	tenants := r.Header.Values("X-Tenant")
	if len(tenants) != 1 || !nameRE.MatchString(tenants[0]) {
		errwrite(w, fail("invalid"))
		return
	}
	tenant := tenants[0]
	if r.Method == http.MethodGet {
		switch rt {
		case "account":
			a, e := account(r.Context(), l.DB, tenant, arg)
			if e != nil {
				errwrite(w, e)
			} else {
				write(w, 200, map[string]any{"account": a})
			}
			return
		case "/entries":
			l.readEntries(w, r, tenant)
			return
		case "/summary":
			l.readSummary(w, r, tenant)
			return
		}
	}
	keys := r.Header.Values("Idempotency-Key")
	if len(keys) != 1 || !keyRE.MatchString(keys[0]) {
		errwrite(w, fail("invalid"))
		return
	}
	key := keys[0]
	m, canonical, e := parseBody(r)
	if e != nil {
		errwrite(w, e)
		return
	}
	var result []byte
	var returnedStatus int
	e = l.transaction(r.Context(), func(c *sql.Conn) error {
		var oldPath, oldBody string
		var oldStatus int
		var oldResult []byte
		q := c.QueryRowContext(r.Context(), `SELECT path,body,status,result FROM idem WHERE tenant=? AND key=?`, tenant, key).Scan(&oldPath, &oldBody, &oldStatus, &oldResult)
		if q == nil {
			if oldPath != r.URL.Path || oldBody != canonical {
				return fail("idempotency_conflict")
			}
			returnedStatus = oldStatus
			result = oldResult
			return nil
		}
		if !errors.Is(q, sql.ErrNoRows) {
			return q
		}
		body, status, e := l.prepare(rt, m)
		if e != nil {
			return e
		}
		obj, e := l.apply(r.Context(), c, tenant, rt, arg, body)
		if e != nil {
			return e
		}
		result, e = json.Marshal(obj)
		if e != nil {
			return e
		}
		returnedStatus = status
		_, e = c.ExecContext(r.Context(), `INSERT INTO idem VALUES(?,?,?,?,?,?)`, tenant, key, r.URL.Path, canonical, status, result)
		return e
	})
	if e != nil {
		errwrite(w, e)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(returnedStatus)
	_, _ = w.Write(result)
}
func (l *Ledger) prepare(rt string, m map[string]json.RawMessage) (any, int, error) {
	switch rt {
	case "/accounts":
		if e := fields(m, []string{"name", "opening"}, nil); e != nil {
			return nil, 0, e
		}
		n, e := str(m, "name", nameRE)
		if e != nil {
			return nil, 0, e
		}
		v, _, e := number(m, "opening", true, 0, 1000000000)
		return struct {
			N string
			V int64
		}{n, v}, 201, e
	case "/transfers":
		x, e := parseTransfer(m)
		return x, 201, e
	case "/batches":
		if e := fields(m, []string{"transfers"}, nil); e != nil {
			return nil, 0, e
		}
		var raw []json.RawMessage
		if e := json.Unmarshal(m["transfers"], &raw); e != nil || len(raw) < 1 || len(raw) > 20 {
			return nil, 0, fail("invalid")
		}
		xs := make([]transferReq, 0, len(raw))
		for _, v := range raw {
			obj, e := parseObject(v)
			if e != nil {
				return nil, 0, e
			}
			x, e := parseTransfer(obj)
			if e != nil {
				return nil, 0, e
			}
			xs = append(xs, x)
		}
		return xs, 201, nil
	case "/holds":
		if e := fields(m, []string{"account", "amount"}, []string{"version"}); e != nil {
			return nil, 0, e
		}
		n, e := str(m, "account", nameRE)
		if e != nil {
			return nil, 0, e
		}
		amount, _, e := number(m, "amount", true, 1, 1000000000)
		if e != nil {
			return nil, 0, e
		}
		v, p, e := suppliedVersion(m, "version")
		return struct {
			N         string
			Amount, V int64
			P         bool
		}{n, amount, v, p}, 201, e
	case "capture":
		if e := fields(m, []string{"to"}, []string{"from_version", "to_version"}); e != nil {
			return nil, 0, e
		}
		n, e := str(m, "to", nameRE)
		if e != nil {
			return nil, 0, e
		}
		fv, fp, e := suppliedVersion(m, "from_version")
		if e != nil {
			return nil, 0, e
		}
		tv, tp, e := suppliedVersion(m, "to_version")
		return struct {
			N      string
			FV, TV int64
			FP, TP bool
		}{n, fv, tv, fp, tp}, 200, e
	case "release":
		if e := fields(m, nil, []string{"version"}); e != nil {
			return nil, 0, e
		}
		v, p, e := suppliedVersion(m, "version")
		return struct {
			V int64
			P bool
		}{v, p}, 200, e
	case "reverse":
		if e := fields(m, nil, []string{"from_version", "to_version"}); e != nil {
			return nil, 0, e
		}
		fv, fp, e := suppliedVersion(m, "from_version")
		if e != nil {
			return nil, 0, e
		}
		tv, tp, e := suppliedVersion(m, "to_version")
		return struct {
			FV, TV int64
			FP, TP bool
		}{fv, tv, fp, tp}, 200, e
	}
	return nil, 0, fail("not_found")
}
func (l *Ledger) apply(ctx context.Context, c *sql.Conn, t, rt, arg string, body any) (any, error) {
	switch rt {
	case "/accounts":
		x := body.(struct {
			N string
			V int64
		})
		var exists int
		e := c.QueryRowContext(ctx, `SELECT 1 FROM accounts WHERE tenant=? AND name=?`, t, x.N).Scan(&exists)
		if e == nil {
			return nil, fail("exists")
		}
		if !errors.Is(e, sql.ErrNoRows) {
			return nil, e
		}
		a := Account{x.N, x.V, 0, x.V, 1}
		if _, e = c.ExecContext(ctx, `INSERT INTO accounts VALUES(?,?,?,?,?)`, t, x.N, x.V, 0, 1); e != nil {
			return nil, e
		}
		if e = entry(ctx, c, t, x.N, "opening", id(), x.V, 0); e != nil {
			return nil, e
		}
		return map[string]any{"account": a}, nil
	case "/transfers":
		x := body.(transferReq)
		tr, a, b, e := transfer(ctx, c, t, x.From, x.To, x.Amount, x.FV, x.TV, x.FH, x.TH, "transfer")
		if e != nil {
			return nil, e
		}
		return map[string]any{"transfer": tr, "accounts": []Account{a, b}}, nil
	case "/batches":
		xs := body.([]transferReq)
		out := make([]Transfer, 0, len(xs))
		seen := map[string]bool{}
		for _, x := range xs {
			tr, _, _, e := transfer(ctx, c, t, x.From, x.To, x.Amount, x.FV, x.TV, x.FH, x.TH, "transfer")
			if e != nil {
				return nil, e
			}
			out = append(out, tr)
			seen[x.From] = true
			seen[x.To] = true
		}
		names := make([]string, 0, len(seen))
		for n := range seen {
			names = append(names, n)
		}
		sort.Strings(names)
		aa := make([]Account, 0, len(names))
		for _, n := range names {
			a, e := account(ctx, c, t, n)
			if e != nil {
				return nil, e
			}
			aa = append(aa, a)
		}
		return map[string]any{"transfers": out, "accounts": aa}, nil
	case "/holds":
		x := body.(struct {
			N         string
			Amount, V int64
			P         bool
		})
		a, e := account(ctx, c, t, x.N)
		if e != nil {
			return nil, e
		}
		if e = version(a, x.V, x.P); e != nil {
			return nil, e
		}
		if a.Available < x.Amount {
			return nil, fail("insufficient")
		}
		a.Reserved += x.Amount
		if e = save(ctx, c, t, a); e != nil {
			return nil, e
		}
		h := Hold{id(), x.N, x.Amount, "active"}
		if _, e = c.ExecContext(ctx, `INSERT INTO holds VALUES(?,?,?,?,?)`, t, h.ID, h.Account, h.Amount, h.State); e != nil {
			return nil, e
		}
		if e = entry(ctx, c, t, x.N, "hold", h.ID, 0, x.Amount); e != nil {
			return nil, e
		}
		a.Version++
		a.Available = a.Balance - a.Reserved
		return map[string]any{"hold": h, "account": a}, nil
	case "release":
		x := body.(struct {
			V int64
			P bool
		})
		h, e := getHold(ctx, c, t, arg)
		if e != nil {
			return nil, e
		}
		if h.State != "active" {
			return nil, fail("terminal")
		}
		a, e := account(ctx, c, t, h.Account)
		if e != nil {
			return nil, e
		}
		if e = version(a, x.V, x.P); e != nil {
			return nil, e
		}
		a.Reserved -= h.Amount
		if e = save(ctx, c, t, a); e != nil {
			return nil, e
		}
		if _, e = c.ExecContext(ctx, `UPDATE holds SET state='released' WHERE tenant=? AND id=?`, t, h.ID); e != nil {
			return nil, e
		}
		if e = entry(ctx, c, t, a.Name, "release", h.ID, 0, -h.Amount); e != nil {
			return nil, e
		}
		h.State = "released"
		a.Version++
		a.Available = a.Balance - a.Reserved
		return map[string]any{"hold": h, "account": a}, nil
	case "capture":
		x := body.(struct {
			N      string
			FV, TV int64
			FP, TP bool
		})
		h, e := getHold(ctx, c, t, arg)
		if e != nil {
			return nil, e
		}
		if h.State != "active" {
			return nil, fail("terminal")
		}
		if h.Account == x.N {
			return nil, fail("invalid")
		}
		a, e := account(ctx, c, t, h.Account)
		if e != nil {
			return nil, e
		}
		b, e := account(ctx, c, t, x.N)
		if e != nil {
			return nil, e
		}
		if e = version(a, x.FV, x.FP); e != nil {
			return nil, e
		}
		if e = version(b, x.TV, x.TP); e != nil {
			return nil, e
		}
		nb, e := add(b.Balance, h.Amount)
		if e != nil {
			return nil, e
		}
		a.Reserved -= h.Amount
		a.Balance -= h.Amount
		b.Balance = nb
		if e = save(ctx, c, t, a); e != nil {
			return nil, e
		}
		if e = save(ctx, c, t, b); e != nil {
			return nil, e
		}
		tr := Transfer{ID: id(), From: a.Name, To: b.Name, Amount: h.Amount}
		if _, e = c.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind) VALUES(?,?,?,?,?,0,'capture')`, t, tr.ID, tr.From, tr.To, tr.Amount); e != nil {
			return nil, e
		}
		if _, e = c.ExecContext(ctx, `UPDATE holds SET state='captured' WHERE tenant=? AND id=?`, t, h.ID); e != nil {
			return nil, e
		}
		if e = entry(ctx, c, t, a.Name, "capture", tr.ID, -h.Amount, -h.Amount); e != nil {
			return nil, e
		}
		if e = entry(ctx, c, t, b.Name, "capture", tr.ID, h.Amount, 0); e != nil {
			return nil, e
		}
		h.State = "captured"
		a.Version++
		b.Version++
		a.Available = a.Balance - a.Reserved
		b.Available = b.Balance - b.Reserved
		return map[string]any{"hold": h, "transfer": tr, "accounts": []Account{a, b}}, nil
	case "reverse":
		x := body.(struct {
			FV, TV int64
			FP, TP bool
		})
		orig, kind, e := getTransfer(ctx, c, t, arg)
		if e != nil {
			return nil, e
		}
		if orig.Reversed || kind == "reversal" {
			return nil, fail("terminal")
		}
		a, e := account(ctx, c, t, orig.From)
		if e != nil {
			return nil, e
		}
		b, e := account(ctx, c, t, orig.To)
		if e != nil {
			return nil, e
		}
		if e = version(a, x.FV, x.FP); e != nil {
			return nil, e
		}
		if e = version(b, x.TV, x.TP); e != nil {
			return nil, e
		}
		if b.Available < orig.Amount {
			return nil, fail("insufficient")
		}
		na, e := add(a.Balance, orig.Amount)
		if e != nil {
			return nil, e
		}
		a.Balance = na
		b.Balance -= orig.Amount
		if e = save(ctx, c, t, a); e != nil {
			return nil, e
		}
		if e = save(ctx, c, t, b); e != nil {
			return nil, e
		}
		rev := Transfer{ID: id(), From: b.Name, To: a.Name, Amount: orig.Amount}
		if _, e = c.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind) VALUES(?,?,?,?,?,0,'reversal')`, t, rev.ID, rev.From, rev.To, rev.Amount); e != nil {
			return nil, e
		}
		if _, e = c.ExecContext(ctx, `UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?`, t, orig.ID); e != nil {
			return nil, e
		}
		if e = entry(ctx, c, t, b.Name, "reversal", rev.ID, -rev.Amount, 0); e != nil {
			return nil, e
		}
		if e = entry(ctx, c, t, a.Name, "reversal", rev.ID, rev.Amount, 0); e != nil {
			return nil, e
		}
		orig.Reversed = true
		a.Version++
		b.Version++
		a.Available = a.Balance - a.Reserved
		b.Available = b.Balance - b.Reserved
		return map[string]any{"transfer": orig, "reversal": rev, "accounts": []Account{a, b}}, nil
	}
	return nil, fail("not_found")
}

type Entry struct {
	Seq           int64  `json:"seq"`
	Account       string `json:"account"`
	Kind          string `json:"kind"`
	BalanceDelta  int64  `json:"balance_delta"`
	ReservedDelta int64  `json:"reserved_delta"`
	OperationID   string `json:"operation_id"`
	LegacyID      *int64 `json:"legacy_id,omitempty"`
}

func queryArgs(r *http.Request, allowed ...string) (map[string]string, error) {
	a := map[string]bool{}
	for _, k := range allowed {
		a[k] = true
	}
	out := map[string]string{}
	for k, vs := range r.URL.Query() {
		if !a[k] || len(vs) != 1 {
			return nil, fail("invalid")
		}
		out[k] = vs[0]
	}
	return out, nil
}
func snapshot(ctx context.Context, c conn, t string, q map[string]string) (int64, error) {
	var max int64
	if e := c.QueryRowContext(ctx, `SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?`, t).Scan(&max); e != nil {
		return 0, e
	}
	s, ok := q["snapshot"]
	if !ok {
		return max, nil
	}
	n, e := signedQuery(s)
	if e != nil || n > max {
		return 0, fail("invalid")
	}
	return n, nil
}
func (l *Ledger) readEntries(w http.ResponseWriter, r *http.Request, t string) {
	q, e := queryArgs(r, "after", "limit", "snapshot")
	if e != nil {
		errwrite(w, e)
		return
	}
	after := int64(0)
	if s, ok := q["after"]; ok {
		after, e = signedQuery(s)
		if e != nil {
			errwrite(w, e)
			return
		}
	}
	limit := int64(50)
	if s, ok := q["limit"]; ok {
		limit, e = signedQuery(s)
		if e != nil || limit < 1 || limit > 100 {
			errwrite(w, fail("invalid"))
			return
		}
	}
	tx, e := l.DB.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
	if e != nil {
		errwrite(w, e)
		return
	}
	defer tx.Rollback()
	snap, e := snapshot(r.Context(), tx, t, q)
	if e != nil || after > snap {
		errwrite(w, fail("invalid"))
		return
	}
	rows, e := tx.QueryContext(r.Context(), `SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, t, after, snap, limit)
	if e != nil {
		errwrite(w, e)
		return
	}
	out := make([]Entry, 0)
	next := after
	for rows.Next() {
		var en Entry
		var lid sql.NullInt64
		if e = rows.Scan(&en.Seq, &en.Account, &en.Kind, &en.BalanceDelta, &en.ReservedDelta, &en.OperationID, &lid); e != nil {
			break
		}
		if lid.Valid {
			en.LegacyID = &lid.Int64
		}
		out = append(out, en)
		next = en.Seq
	}
	if e == nil {
		e = rows.Err()
	}
	rows.Close()
	if e != nil {
		errwrite(w, e)
		return
	}
	var more bool
	e = tx.QueryRowContext(r.Context(), `SELECT EXISTS(SELECT 1 FROM entries WHERE tenant=? AND seq>? AND seq<=?)`, t, next, snap).Scan(&more)
	if e != nil {
		errwrite(w, e)
		return
	}
	if e = tx.Commit(); e != nil {
		errwrite(w, e)
		return
	}
	write(w, 200, map[string]any{"entries": out, "snapshot": snap, "next_after": next, "has_more": more})
}

type SummaryAccount struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
}

func (l *Ledger) readSummary(w http.ResponseWriter, r *http.Request, t string) {
	q, e := queryArgs(r, "snapshot")
	if e != nil {
		errwrite(w, e)
		return
	}
	tx, e := l.DB.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
	if e != nil {
		errwrite(w, e)
		return
	}
	defer tx.Rollback()
	snap, e := snapshot(r.Context(), tx, t, q)
	if e != nil {
		errwrite(w, e)
		return
	}
	rows, e := tx.QueryContext(r.Context(), `SELECT account,SUM(balance_delta),SUM(reserved_delta) FROM entries WHERE tenant=? AND seq<=? GROUP BY account HAVING SUM(CASE WHEN kind='opening' THEN 1 ELSE 0 END)>0 ORDER BY account`, t, snap)
	if e != nil {
		errwrite(w, e)
		return
	}
	aa := make([]SummaryAccount, 0)
	total := SummaryAccount{}
	for rows.Next() {
		var a SummaryAccount
		if e = rows.Scan(&a.Name, &a.Balance, &a.Reserved); e != nil {
			break
		}
		a.Available = a.Balance - a.Reserved
		aa = append(aa, a)
		total.Balance += a.Balance
		total.Reserved += a.Reserved
	}
	if e == nil {
		e = rows.Err()
	}
	rows.Close()
	if e != nil {
		errwrite(w, e)
		return
	}
	total.Available = total.Balance - total.Reserved
	var count int64
	e = tx.QueryRowContext(r.Context(), `SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?`, t, snap).Scan(&count)
	if e != nil {
		errwrite(w, e)
		return
	}
	if e = tx.Commit(); e != nil {
		errwrite(w, e)
		return
	}
	write(w, 200, map[string]any{"snapshot": snap, "accounts": aa, "totals": map[string]int64{"balance": total.Balance, "reserved": total.Reserved, "available": total.Available}, "entry_count": count})
}

// ShutdownGracefully gives in-flight requests time to finish on process signals.
func ShutdownGracefully(s *http.Server) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = s.Shutdown(ctx)
}
