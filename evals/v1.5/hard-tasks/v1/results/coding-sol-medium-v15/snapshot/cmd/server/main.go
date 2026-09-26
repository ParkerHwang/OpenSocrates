package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"

	"auditledger/internal/platform"
)

const maxBalance int64 = 9000000000000000

var nameRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type apiError struct {
	status int
	code   string
}

func (e apiError) Error() string        { return e.code }
func bad(code string, status int) error { return apiError{status, code} }

var invalid = bad("invalid", 400)

type account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}
type transfer struct {
	ID       string `json:"id"`
	From     string `json:"from"`
	To       string `json:"to"`
	Amount   int64  `json:"amount"`
	Reversed bool   `json:"reversed"`
	LegacyID *int64 `json:"legacy_id,omitempty"`
}
type hold struct {
	ID      string `json:"id"`
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	State   string `json:"state"`
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
type store struct{ db *sql.DB }
type sqler interface {
	ExecContext(context.Context, string, ...any) (sql.Result, error)
	QueryContext(context.Context, string, ...any) (*sql.Rows, error)
	QueryRowContext(context.Context, string, ...any) *sql.Row
}

func id() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}
func checked(v int64) bool { return v >= 0 && v <= maxBalance }
func fail(w http.ResponseWriter, e error) {
	a := apiError{500, "internal"}
	var b apiError
	if errors.As(e, &b) {
		a = b
	} else {
		log.Printf("request error: %v", e)
	}
	write(w, a.status, map[string]any{"error": map[string]string{"code": a.code}})
}
func write(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func parseBody(r *http.Request, allowed ...string) (map[string]json.RawMessage, string, error) {
	raw, e := io.ReadAll(io.LimitReader(r.Body, (1<<20)+1))
	if e != nil || len(raw) == 0 || len(raw) > 1<<20 {
		return nil, "", invalid
	}
	var m map[string]json.RawMessage
	if e = json.Unmarshal(raw, &m); e != nil || m == nil {
		return nil, "", invalid
	}
	set := map[string]bool{}
	for _, k := range allowed {
		set[k] = true
	}
	for k := range m {
		if !set[k] {
			return nil, "", invalid
		}
	}
	var x any
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	if e = dec.Decode(&x); e != nil {
		return nil, "", invalid
	}
	canon, _ := json.Marshal(x)
	return m, string(canon), nil
}
func str(m map[string]json.RawMessage, k string) (string, error) {
	v, ok := m[k]
	if !ok {
		return "", invalid
	}
	var s string
	if e := json.Unmarshal(v, &s); e != nil || s == "" {
		return "", invalid
	}
	return s, nil
}
func named(m map[string]json.RawMessage, k string) (string, error) {
	s, e := str(m, k)
	if e != nil || !nameRE.MatchString(s) {
		return "", invalid
	}
	return s, nil
}
func number(m map[string]json.RawMessage, k string, optional bool, min, max int64) (int64, bool, error) {
	v, ok := m[k]
	if !ok {
		if optional {
			return 0, false, nil
		}
		return 0, false, invalid
	}
	if len(v) == 0 || v[0] == '"' || v[0] == 'n' || v[0] == 't' || v[0] == 'f' || v[0] == '{' || v[0] == '[' {
		return 0, false, invalid
	}
	n, e := strconv.ParseInt(string(v), 10, 64)
	if e != nil || n < min || n > max {
		return 0, false, invalid
	}
	return n, true, nil
}
func version(m map[string]json.RawMessage, k string) (int64, bool, error) {
	return number(m, k, true, 1, 1<<62)
}
func lookup(q sqler, t, n string) (account, error) {
	var a account
	a.Name = n
	e := q.QueryRowContext(context.Background(), "SELECT balance,reserved,version FROM accounts WHERE tenant=? AND name=?", t, n).Scan(&a.Balance, &a.Reserved, &a.Version)
	if errors.Is(e, sql.ErrNoRows) {
		return a, bad("not_found", 404)
	}
	if e != nil {
		return a, e
	}
	a.Available = a.Balance - a.Reserved
	return a, nil
}
func save(q sqler, t string, a account) error {
	_, e := q.ExecContext(context.Background(), "UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?", a.Balance, a.Reserved, a.Version, t, a.Name)
	return e
}
func checkVersion(a account, n int64, p bool) error {
	if p && a.Version != n {
		return bad("version_conflict", 409)
	}
	return nil
}
func appendEntry(q sqler, t, acct, kind string, bd, rd int64, op string, legacy *int64) error {
	ctx := context.Background()
	_, e := q.ExecContext(ctx, "INSERT INTO tenant_seq(tenant,next_seq) VALUES(?,1) ON CONFLICT(tenant) DO UPDATE SET next_seq=next_seq+1", t)
	if e != nil {
		return e
	}
	var seq int64
	if e = q.QueryRowContext(ctx, "SELECT next_seq FROM tenant_seq WHERE tenant=?", t).Scan(&seq); e != nil {
		return e
	}
	_, e = q.ExecContext(ctx, "INSERT INTO entries(tenant,seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?,?)", t, seq, acct, kind, bd, rd, op, legacy)
	return e
}
func addTransfer(q sqler, t, from, to string, amount int64, kind, original string, legacy *int64) (transfer, error) {
	tr := transfer{ID: id(), From: from, To: to, Amount: amount, LegacyID: legacy}
	_, e := q.ExecContext(context.Background(), "INSERT INTO transfers(tenant,id,from_name,to_name,amount,kind,original_id,legacy_id) VALUES(?,?,?,?,?,?,?,?)", t, tr.ID, from, to, amount, kind, original, legacy)
	return tr, e
}
func getTransfer(q sqler, t, tid string) (transfer, string, error) {
	var tr transfer
	var kind string
	var rev int
	var legacy sql.NullInt64
	tr.ID = tid
	e := q.QueryRowContext(context.Background(), "SELECT from_name,to_name,amount,kind,reversed,legacy_id FROM transfers WHERE tenant=? AND id=?", t, tid).Scan(&tr.From, &tr.To, &tr.Amount, &kind, &rev, &legacy)
	if errors.Is(e, sql.ErrNoRows) {
		return tr, "", bad("not_found", 404)
	}
	if e != nil {
		return tr, "", e
	}
	tr.Reversed = rev != 0
	if legacy.Valid {
		tr.LegacyID = &legacy.Int64
	}
	return tr, kind, nil
}
func getHold(q sqler, t, hid string) (hold, error) {
	var h hold
	h.ID = hid
	e := q.QueryRowContext(context.Background(), "SELECT account,amount,state FROM holds WHERE tenant=? AND id=?", t, hid).Scan(&h.Account, &h.Amount, &h.State)
	if errors.Is(e, sql.ErrNoRows) {
		return h, bad("not_found", 404)
	}
	return h, e
}
func transferApply(q sqler, t, from, to string, amt int64, fv int64, fp bool, tv int64, tp bool, kind, original string) (transfer, account, account, error) {
	var tr transfer
	var a, b account
	var e error
	if from == to {
		return tr, a, b, invalid
	}
	a, e = lookup(q, t, from)
	if e != nil {
		return tr, a, b, e
	}
	b, e = lookup(q, t, to)
	if e != nil {
		return tr, a, b, e
	}
	if e = checkVersion(a, fv, fp); e != nil {
		return tr, a, b, e
	}
	if e = checkVersion(b, tv, tp); e != nil {
		return tr, a, b, e
	}
	if a.Available < amt {
		return tr, a, b, bad("insufficient", 409)
	}
	if !checked(b.Balance + amt) {
		return tr, a, b, invalid
	}
	a.Balance -= amt
	b.Balance += amt
	a.Version++
	b.Version++
	a.Available = a.Balance - a.Reserved
	b.Available = b.Balance - b.Reserved
	if e = save(q, t, a); e != nil {
		return tr, a, b, e
	}
	if e = save(q, t, b); e != nil {
		return tr, a, b, e
	}
	tr, e = addTransfer(q, t, from, to, amt, kind, original, nil)
	if e != nil {
		return tr, a, b, e
	}
	if e = appendEntry(q, t, from, kind, -amt, 0, tr.ID, nil); e != nil {
		return tr, a, b, e
	}
	e = appendEntry(q, t, to, kind, amt, 0, tr.ID, nil)
	return tr, a, b, e
}
func migrate(db *sql.DB) error {
	ctx := context.Background()
	c, e := db.Conn(ctx)
	if e != nil {
		return e
	}
	defer c.Close()
	if _, e = c.ExecContext(ctx, "BEGIN IMMEDIATE"); e != nil {
		return e
	}
	ok := false
	defer func() {
		if !ok {
			_, _ = c.ExecContext(ctx, "ROLLBACK")
		}
	}()
	var uv int
	if e = c.QueryRowContext(ctx, "PRAGMA user_version").Scan(&uv); e != nil {
		return e
	}
	if uv != 0 && uv != 1 && uv != 2 {
		return fmt.Errorf("unsupported schema version %d", uv)
	}
	schema := []string{
		`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name))`,
		`CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,from_name TEXT NOT NULL,to_name TEXT NOT NULL,amount INTEGER NOT NULL,kind TEXT NOT NULL,original_id TEXT NOT NULL DEFAULT '',reversed INTEGER NOT NULL DEFAULT 0,legacy_id INTEGER,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS tenant_seq(tenant TEXT PRIMARY KEY,next_seq INTEGER NOT NULL)`,
		`CREATE TABLE IF NOT EXISTS entries(tenant TEXT NOT NULL,seq INTEGER NOT NULL,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,seq))`,
		`CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body TEXT NOT NULL,status INTEGER NOT NULL,result BLOB NOT NULL,PRIMARY KEY(tenant,key))`,
		`CREATE INDEX IF NOT EXISTS entries_account ON entries(tenant,account,seq)`,
	}
	for _, s := range schema {
		if _, e = c.ExecContext(ctx, s); e != nil {
			return e
		}
	}
	if uv == 1 {
		type row struct {
			tenant, name            string
			final, opening, version int64
		}
		rows, e := c.QueryContext(ctx, "SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name")
		if e != nil {
			return e
		}
		acc := map[string]*row{}
		order := []*row{}
		for rows.Next() {
			r := new(row)
			if e = rows.Scan(&r.tenant, &r.name, &r.final); e != nil {
				rows.Close()
				return e
			}
			r.opening = r.final
			r.version = 1
			acc[r.tenant+"\x00"+r.name] = r
			order = append(order, r)
		}
		e = rows.Err()
		rows.Close()
		if e != nil {
			return e
		}
		type movement struct {
			id, units        int64
			tenant, from, to string
		}
		moves := []movement{}
		rows, e = c.QueryContext(ctx, "SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id")
		if e != nil {
			return e
		}
		for rows.Next() {
			var m movement
			if e = rows.Scan(&m.id, &m.tenant, &m.from, &m.to, &m.units); e != nil {
				rows.Close()
				return e
			}
			a, b := acc[m.tenant+"\x00"+m.from], acc[m.tenant+"\x00"+m.to]
			if a == nil || b == nil || a == b || m.units <= 0 {
				rows.Close()
				return fmt.Errorf("invalid legacy movement %d", m.id)
			}
			a.opening += m.units
			b.opening -= m.units
			a.version++
			b.version++
			moves = append(moves, m)
		}
		e = rows.Err()
		rows.Close()
		if e != nil {
			return e
		}
		for _, a := range order {
			if !checked(a.opening) || !checked(a.final) {
				return fmt.Errorf("invalid legacy account")
			}
			if _, e = c.ExecContext(ctx, "INSERT INTO accounts VALUES(?,?,?,?,?)", a.tenant, a.name, a.final, 0, a.version); e != nil {
				return e
			}
			if e = appendEntry(c, a.tenant, a.name, "opening", a.opening, 0, id(), nil); e != nil {
				return e
			}
		}
		for _, m := range moves {
			tr, e := addTransfer(c, m.tenant, m.from, m.to, m.units, "transfer", "", &m.id)
			if e != nil {
				return e
			}
			if e = appendEntry(c, m.tenant, m.from, "transfer", -m.units, 0, tr.ID, &m.id); e != nil {
				return e
			}
			if e = appendEntry(c, m.tenant, m.to, "transfer", m.units, 0, tr.ID, &m.id); e != nil {
				return e
			}
		}
	}
	if _, e = c.ExecContext(ctx, "PRAGMA user_version=2"); e != nil {
		return e
	}
	if _, e = c.ExecContext(ctx, "COMMIT"); e != nil {
		return e
	}
	ok = true
	return nil
}
func main() {
	path := flag.String("db", "ledger.db", "SQLite database path")
	listen := flag.String("listen", "127.0.0.1:8080", "listen address")
	flag.Parse()
	db, e := platform.Open(*path)
	if e != nil {
		log.Fatal(e)
	}
	defer db.Close()
	if e = migrate(db); e != nil {
		log.Fatal(e)
	}
	s := &store{db}
	srv := &http.Server{Addr: *listen, Handler: s, ReadHeaderTimeout: 5 * time.Second}
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-ch
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = srv.Shutdown(ctx)
	}()
	log.Printf("listening on %s", *listen)
	if e = srv.ListenAndServe(); e != nil && !errors.Is(e, http.ErrServerClosed) {
		log.Fatal(e)
	}
}
func (s *store) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" && r.URL.Path == "/health" {
		write(w, 200, map[string]any{"ok": true})
		return
	}
	tenant := r.Header.Get("X-Tenant")
	if !nameRE.MatchString(tenant) {
		fail(w, invalid)
		return
	}
	path := r.URL.EscapedPath()
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if r.Method == "GET" {
		s.read(w, r, tenant, parts)
		return
	}
	if r.Method != "POST" {
		fail(w, bad("not_found", 404))
		return
	}
	key := r.Header.Get("Idempotency-Key")
	if !keyRE.MatchString(key) {
		fail(w, invalid)
		return
	}
	s.mutate(w, r, tenant, key, parts)
}
func route(parts []string, ss ...string) bool {
	if len(parts) != len(ss) {
		return false
	}
	for i := range ss {
		if ss[i] != "*" && parts[i] != ss[i] {
			return false
		}
	}
	return true
}
func (s *store) mutate(w http.ResponseWriter, r *http.Request, t, key string, p []string) {
	allowed := []string{}
	switch {
	case route(p, "accounts"):
		allowed = []string{"name", "opening"}
	case route(p, "transfers"):
		allowed = []string{"from", "to", "amount", "from_version", "to_version"}
	case route(p, "batches"):
		allowed = []string{"transfers"}
	case route(p, "holds"):
		allowed = []string{"account", "amount", "version"}
	case route(p, "holds", "*", "capture"):
		allowed = []string{"to", "from_version", "to_version"}
	case route(p, "holds", "*", "release"):
		allowed = []string{"version"}
	case route(p, "transfers", "*", "reverse"):
		allowed = []string{"from_version", "to_version"}
	default:
		fail(w, bad("not_found", 404))
		return
	}
	m, canon, e := parseBody(r, allowed...)
	if e != nil {
		fail(w, e)
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
	done := false
	defer func() {
		if !done {
			_, _ = c.ExecContext(context.Background(), "ROLLBACK")
		}
	}()
	var oldpath, oldbody string
	var status int
	var result []byte
	e = c.QueryRowContext(ctx, "SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?", t, key).Scan(&oldpath, &oldbody, &status, &result)
	if e == nil {
		if oldpath != pathOf(p) || oldbody != canon {
			fail(w, bad("idempotency_conflict", 409))
			return
		}
		writeRaw(w, status, result)
		return
	}
	if !errors.Is(e, sql.ErrNoRows) {
		fail(w, e)
		return
	}
	status, obj, e := s.apply(c, t, p, m)
	if e != nil {
		fail(w, e)
		return
	}
	result, e = json.Marshal(obj)
	if e != nil {
		fail(w, e)
		return
	}
	if _, e = c.ExecContext(ctx, "INSERT INTO idempotency VALUES(?,?,?,?,?,?)", t, key, pathOf(p), canon, status, result); e != nil {
		fail(w, e)
		return
	}
	if _, e = c.ExecContext(ctx, "COMMIT"); e != nil {
		fail(w, e)
		return
	}
	done = true
	writeRaw(w, status, result)
}
func writeRaw(w http.ResponseWriter, status int, b []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(append(b, '\n'))
}
func pathOf(p []string) string { return "/" + strings.Join(p, "/") }
func transferRequest(m map[string]json.RawMessage) (string, string, int64, int64, bool, int64, bool, error) {
	f, e := named(m, "from")
	if e != nil {
		return "", "", 0, 0, false, 0, false, e
	}
	t, e := named(m, "to")
	if e != nil {
		return "", "", 0, 0, false, 0, false, e
	}
	n, _, e := number(m, "amount", false, 1, 1000000000)
	if e != nil {
		return "", "", 0, 0, false, 0, false, e
	}
	fv, fp, e := version(m, "from_version")
	if e != nil {
		return "", "", 0, 0, false, 0, false, e
	}
	tv, tp, e := version(m, "to_version")
	return f, t, n, fv, fp, tv, tp, e
}
func (s *store) apply(q sqler, t string, p []string, m map[string]json.RawMessage) (int, any, error) {
	ctx := context.Background()
	switch {
	case route(p, "accounts"):
		n, e := named(m, "name")
		if e != nil {
			return 0, nil, e
		}
		opening, _, e := number(m, "opening", false, 0, 1000000000)
		if e != nil {
			return 0, nil, e
		}
		a := account{n, opening, 0, opening, 1}
		_, e = q.ExecContext(ctx, "INSERT INTO accounts VALUES(?,?,?,?,?)", t, n, opening, 0, 1)
		if e != nil {
			if strings.Contains(e.Error(), "constraint") {
				return 0, nil, bad("exists", 409)
			}
			return 0, nil, e
		}
		if e = appendEntry(q, t, n, "opening", opening, 0, id(), nil); e != nil {
			return 0, nil, e
		}
		return 201, map[string]any{"account": a}, nil
	case route(p, "transfers"):
		f, to, n, fv, fp, tv, tp, e := transferRequest(m)
		if e != nil {
			return 0, nil, e
		}
		tr, a, b, e := transferApply(q, t, f, to, n, fv, fp, tv, tp, "transfer", "")
		if e != nil {
			return 0, nil, e
		}
		return 201, map[string]any{"transfer": tr, "accounts": []account{a, b}}, nil
	case route(p, "batches"):
		raw, ok := m["transfers"]
		if !ok {
			return 0, nil, invalid
		}
		var items []json.RawMessage
		if e := json.Unmarshal(raw, &items); e != nil || len(items) < 1 || len(items) > 20 {
			return 0, nil, invalid
		}
		transfers := make([]transfer, 0, len(items))
		names := map[string]bool{}
		for _, raw := range items {
			var x map[string]json.RawMessage
			if e := json.Unmarshal(raw, &x); e != nil || x == nil {
				return 0, nil, invalid
			}
			for k := range x {
				if k != "from" && k != "to" && k != "amount" && k != "from_version" && k != "to_version" {
					return 0, nil, invalid
				}
			}
			f, to, n, fv, fp, tv, tp, e := transferRequest(x)
			if e != nil {
				return 0, nil, e
			}
			tr, _, _, e := transferApply(q, t, f, to, n, fv, fp, tv, tp, "transfer", "")
			if e != nil {
				return 0, nil, e
			}
			transfers = append(transfers, tr)
			names[f] = true
			names[to] = true
		}
		keys := make([]string, 0, len(names))
		for n := range names {
			keys = append(keys, n)
		}
		sort.Strings(keys)
		accounts := make([]account, 0, len(keys))
		for _, n := range keys {
			a, e := lookup(q, t, n)
			if e != nil {
				return 0, nil, e
			}
			accounts = append(accounts, a)
		}
		return 201, map[string]any{"transfers": transfers, "accounts": accounts}, nil
	case route(p, "holds"):
		n, e := named(m, "account")
		if e != nil {
			return 0, nil, e
		}
		amt, _, e := number(m, "amount", false, 1, 1000000000)
		if e != nil {
			return 0, nil, e
		}
		v, present, e := version(m, "version")
		if e != nil {
			return 0, nil, e
		}
		a, e := lookup(q, t, n)
		if e != nil {
			return 0, nil, e
		}
		if e = checkVersion(a, v, present); e != nil {
			return 0, nil, e
		}
		if a.Available < amt {
			return 0, nil, bad("insufficient", 409)
		}
		a.Reserved += amt
		a.Available -= amt
		a.Version++
		if e = save(q, t, a); e != nil {
			return 0, nil, e
		}
		h := hold{id(), n, amt, "active"}
		if _, e = q.ExecContext(ctx, "INSERT INTO holds VALUES(?,?,?,?,?)", t, h.ID, n, amt, h.State); e != nil {
			return 0, nil, e
		}
		if e = appendEntry(q, t, n, "hold", 0, amt, h.ID, nil); e != nil {
			return 0, nil, e
		}
		return 201, map[string]any{"hold": h, "account": a}, nil
	case route(p, "holds", "*", "release"):
		v, present, e := version(m, "version")
		if e != nil {
			return 0, nil, e
		}
		h, e := getHold(q, t, p[1])
		if e != nil {
			return 0, nil, e
		}
		if h.State != "active" {
			return 0, nil, bad("terminal", 409)
		}
		a, e := lookup(q, t, h.Account)
		if e != nil {
			return 0, nil, e
		}
		if e = checkVersion(a, v, present); e != nil {
			return 0, nil, e
		}
		a.Reserved -= h.Amount
		a.Available += h.Amount
		a.Version++
		if e = save(q, t, a); e != nil {
			return 0, nil, e
		}
		h.State = "released"
		if _, e = q.ExecContext(ctx, "UPDATE holds SET state='released' WHERE tenant=? AND id=?", t, h.ID); e != nil {
			return 0, nil, e
		}
		if e = appendEntry(q, t, a.Name, "release", 0, -h.Amount, h.ID, nil); e != nil {
			return 0, nil, e
		}
		return 200, map[string]any{"hold": h, "account": a}, nil
	case route(p, "holds", "*", "capture"):
		to, e := named(m, "to")
		if e != nil {
			return 0, nil, e
		}
		fv, fp, e := version(m, "from_version")
		if e != nil {
			return 0, nil, e
		}
		tv, tp, e := version(m, "to_version")
		if e != nil {
			return 0, nil, e
		}
		h, e := getHold(q, t, p[1])
		if e != nil {
			return 0, nil, e
		}
		if h.State != "active" {
			return 0, nil, bad("terminal", 409)
		}
		if to == h.Account {
			return 0, nil, invalid
		}
		a, e := lookup(q, t, h.Account)
		if e != nil {
			return 0, nil, e
		}
		b, e := lookup(q, t, to)
		if e != nil {
			return 0, nil, e
		}
		if e = checkVersion(a, fv, fp); e != nil {
			return 0, nil, e
		}
		if e = checkVersion(b, tv, tp); e != nil {
			return 0, nil, e
		}
		if !checked(b.Balance + h.Amount) {
			return 0, nil, invalid
		}
		a.Reserved -= h.Amount
		a.Balance -= h.Amount
		a.Version++
		a.Available = a.Balance - a.Reserved
		b.Balance += h.Amount
		b.Available += h.Amount
		b.Version++
		if e = save(q, t, a); e != nil {
			return 0, nil, e
		}
		if e = save(q, t, b); e != nil {
			return 0, nil, e
		}
		tr, e := addTransfer(q, t, a.Name, b.Name, h.Amount, "capture", "", nil)
		if e != nil {
			return 0, nil, e
		}
		if e = appendEntry(q, t, a.Name, "capture", -h.Amount, -h.Amount, tr.ID, nil); e != nil {
			return 0, nil, e
		}
		if e = appendEntry(q, t, b.Name, "capture", h.Amount, 0, tr.ID, nil); e != nil {
			return 0, nil, e
		}
		h.State = "captured"
		if _, e = q.ExecContext(ctx, "UPDATE holds SET state='captured' WHERE tenant=? AND id=?", t, h.ID); e != nil {
			return 0, nil, e
		}
		return 200, map[string]any{"hold": h, "transfer": tr, "accounts": []account{a, b}}, nil
	case route(p, "transfers", "*", "reverse"):
		fv, fp, e := version(m, "from_version")
		if e != nil {
			return 0, nil, e
		}
		tv, tp, e := version(m, "to_version")
		if e != nil {
			return 0, nil, e
		}
		orig, kind, e := getTransfer(q, t, p[1])
		if e != nil {
			return 0, nil, e
		}
		if kind == "reversal" || orig.Reversed {
			return 0, nil, bad("terminal", 409)
		}
		a, e := lookup(q, t, orig.From)
		if e != nil {
			return 0, nil, e
		}
		b, e := lookup(q, t, orig.To)
		if e != nil {
			return 0, nil, e
		}
		if e = checkVersion(a, fv, fp); e != nil {
			return 0, nil, e
		}
		if e = checkVersion(b, tv, tp); e != nil {
			return 0, nil, e
		}
		if b.Available < orig.Amount {
			return 0, nil, bad("insufficient", 409)
		}
		if !checked(a.Balance + orig.Amount) {
			return 0, nil, invalid
		}
		a.Balance += orig.Amount
		a.Available += orig.Amount
		a.Version++
		b.Balance -= orig.Amount
		b.Available -= orig.Amount
		b.Version++
		if e = save(q, t, a); e != nil {
			return 0, nil, e
		}
		if e = save(q, t, b); e != nil {
			return 0, nil, e
		}
		rev, e := addTransfer(q, t, orig.To, orig.From, orig.Amount, "reversal", orig.ID, nil)
		if e != nil {
			return 0, nil, e
		}
		if _, e = q.ExecContext(ctx, "UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?", t, orig.ID); e != nil {
			return 0, nil, e
		}
		orig.Reversed = true
		if e = appendEntry(q, t, b.Name, "reversal", -orig.Amount, 0, rev.ID, nil); e != nil {
			return 0, nil, e
		}
		if e = appendEntry(q, t, a.Name, "reversal", orig.Amount, 0, rev.ID, nil); e != nil {
			return 0, nil, e
		}
		return 200, map[string]any{"transfer": orig, "reversal": rev, "accounts": []account{a, b}}, nil
	}
	return 0, nil, bad("not_found", 404)
}
func parseQuery(r *http.Request, keys ...string) (map[string]string, error) {
	q := r.URL.Query()
	allow := map[string]bool{}
	for _, k := range keys {
		allow[k] = true
	}
	out := map[string]string{}
	for k, v := range q {
		if !allow[k] || len(v) != 1 {
			return nil, invalid
		}
		out[k] = v[0]
	}
	return out, nil
}
func qnum(m map[string]string, k string, def, min, max int64) (int64, error) {
	s, ok := m[k]
	if !ok {
		return def, nil
	}
	if s == "" || strings.HasPrefix(s, "+") {
		return 0, invalid
	}
	n, e := strconv.ParseInt(s, 10, 64)
	if e != nil || n < min || n > max {
		return 0, invalid
	}
	return n, nil
}
func maxSeq(q sqler, t string) (int64, error) {
	var n int64
	e := q.QueryRowContext(context.Background(), "SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?", t).Scan(&n)
	return n, e
}
func (s *store) read(w http.ResponseWriter, r *http.Request, t string, p []string) {
	switch {
	case route(p, "accounts", "*"):
		if !nameRE.MatchString(p[1]) {
			fail(w, bad("not_found", 404))
			return
		}
		a, e := lookup(s.db, t, p[1])
		if e != nil {
			fail(w, e)
			return
		}
		write(w, 200, map[string]any{"account": a})
	case route(p, "entries"):
		q, e := parseQuery(r, "after", "limit", "snapshot")
		if e != nil {
			fail(w, e)
			return
		}
		tx, e := s.db.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
		if e != nil {
			fail(w, e)
			return
		}
		defer tx.Rollback()
		mx, e := maxSeq(tx, t)
		if e != nil {
			fail(w, e)
			return
		}
		snap, e := qnum(q, "snapshot", mx, 0, mx)
		if e != nil {
			fail(w, e)
			return
		}
		after, e := qnum(q, "after", 0, 0, snap)
		if e != nil {
			fail(w, e)
			return
		}
		limit, e := qnum(q, "limit", 50, 1, 100)
		if e != nil {
			fail(w, e)
			return
		}
		rows, e := tx.Query("SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?", t, after, snap, limit+1)
		if e != nil {
			fail(w, e)
			return
		}
		entries := []entry{}
		for rows.Next() {
			var x entry
			var legacy sql.NullInt64
			if e = rows.Scan(&x.Seq, &x.Account, &x.Kind, &x.BalanceDelta, &x.ReservedDelta, &x.OperationID, &legacy); e != nil {
				break
			}
			if legacy.Valid {
				x.LegacyID = &legacy.Int64
			}
			entries = append(entries, x)
		}
		if e == nil {
			e = rows.Err()
		}
		rows.Close()
		if e != nil {
			fail(w, e)
			return
		}
		more := int64(len(entries)) > limit
		if more {
			entries = entries[:limit]
		}
		next := after
		if len(entries) > 0 {
			next = entries[len(entries)-1].Seq
		}
		if e = tx.Commit(); e != nil {
			fail(w, e)
			return
		}
		write(w, 200, map[string]any{"entries": entries, "snapshot": snap, "next_after": next, "has_more": more})
	case route(p, "summary"):
		q, e := parseQuery(r, "snapshot")
		if e != nil {
			fail(w, e)
			return
		}
		tx, e := s.db.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
		if e != nil {
			fail(w, e)
			return
		}
		defer tx.Rollback()
		mx, e := maxSeq(tx, t)
		if e != nil {
			fail(w, e)
			return
		}
		snap, e := qnum(q, "snapshot", mx, 0, mx)
		if e != nil {
			fail(w, e)
			return
		}
		rows, e := tx.Query(`SELECT account,SUM(balance_delta),SUM(reserved_delta),SUM(CASE WHEN kind='opening' THEN 1 ELSE 0 END) FROM entries WHERE tenant=? AND seq<=? GROUP BY account ORDER BY account`, t, snap)
		if e != nil {
			fail(w, e)
			return
		}
		type item struct {
			Name      string `json:"name"`
			Balance   int64  `json:"balance"`
			Reserved  int64  `json:"reserved"`
			Available int64  `json:"available"`
		}
		accounts := []item{}
		tot := item{}
		for rows.Next() {
			var a item
			var opens int64
			if e = rows.Scan(&a.Name, &a.Balance, &a.Reserved, &opens); e != nil {
				break
			}
			if opens == 0 {
				continue
			}
			a.Available = a.Balance - a.Reserved
			accounts = append(accounts, a)
			tot.Balance += a.Balance
			tot.Reserved += a.Reserved
			tot.Available += a.Available
		}
		if e == nil {
			e = rows.Err()
		}
		rows.Close()
		if e != nil {
			fail(w, e)
			return
		}
		var count int64
		e = tx.QueryRow("SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?", t, snap).Scan(&count)
		if e != nil {
			fail(w, e)
			return
		}
		if e = tx.Commit(); e != nil {
			fail(w, e)
			return
		}
		write(w, 200, map[string]any{"snapshot": snap, "accounts": accounts, "totals": map[string]int64{"balance": tot.Balance, "reserved": tot.Reserved, "available": tot.Available}, "entry_count": count})
	default:
		fail(w, bad("not_found", 404))
	}
}
