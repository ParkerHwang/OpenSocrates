package platform

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

type API struct {
	db *sql.DB
	n  atomic.Uint64
}

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keypat = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

func New(db *sql.DB) (*API, error) {
	a := &API{db: db}
	if _, e := db.Exec(`PRAGMA journal_mode=WAL`); e != nil {
		return nil, e
	}
	if e := a.migrate(); e != nil {
		return nil, e
	}
	return a, nil
}
func (a *API) migrate() error {
	tx, e := a.db.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	var v int
	if e = tx.QueryRow(`PRAGMA user_version`).Scan(&v); e != nil {
		return e
	}
	if v == 2 {
		return tx.Commit()
	}
	if v != 0 && v != 1 {
		return fmt.Errorf("unsupported schema")
	}
	if _, e = tx.Exec(`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT,name TEXT,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name)); CREATE TABLE IF NOT EXISTS entries(tenant TEXT,seq INTEGER PRIMARY KEY AUTOINCREMENT,account TEXT,kind TEXT,balance_delta INTEGER,reserved_delta INTEGER,operation_id TEXT,legacy_id INTEGER); CREATE INDEX IF NOT EXISTS entries_tenant_seq ON entries(tenant,seq); CREATE TABLE IF NOT EXISTS transfers(tenant TEXT,id TEXT,src TEXT,dst TEXT,amount INTEGER,reversed INTEGER DEFAULT 0,reverse_of TEXT,legacy_id INTEGER,PRIMARY KEY(tenant,id)); CREATE TABLE IF NOT EXISTS holds(tenant TEXT,id TEXT,account TEXT,amount INTEGER,state TEXT,PRIMARY KEY(tenant,id)); CREATE TABLE IF NOT EXISTS idem(tenant TEXT,key TEXT,path TEXT,body TEXT,status INTEGER,result TEXT,PRIMARY KEY(tenant,key));`); e != nil {
		return e
	}
	if v == 1 {
		if e = a.importLegacy(tx); e != nil {
			return e
		}
	}
	if _, e = tx.Exec(`PRAGMA user_version=2`); e != nil {
		return e
	}
	return tx.Commit()
}
func (a *API) importLegacy(tx *sql.Tx) error {
	rows, e := tx.Query(`SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name`)
	if e != nil {
		return e
	}
	type ac struct {
		t, n string
		b    int64
	}
	var as []ac
	for rows.Next() {
		var x ac
		if e = rows.Scan(&x.t, &x.n, &x.b); e != nil {
			rows.Close()
			return e
		}
		as = append(as, x)
	}
	rows.Close()
	type mv struct {
		id      int64
		t, s, d string
		u       int64
	}
	mr, e := tx.Query(`SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id`)
	if e != nil {
		return e
	}
	var ms []mv
	for mr.Next() {
		var x mv
		if e = mr.Scan(&x.id, &x.t, &x.s, &x.d, &x.u); e != nil {
			return e
		}
		ms = append(ms, x)
	}
	mr.Close()
	bal := map[string]int64{}
	ver := map[string]int64{}
	for _, x := range as {
		bal[x.t+"\x00"+x.n] = x.b
		ver[x.t+"\x00"+x.n] = 1
	}
	for _, m := range ms {
		bal[m.t+"\x00"+m.s] += m.u
		bal[m.t+"\x00"+m.d] -= m.u
		ver[m.t+"\x00"+m.s]++
		ver[m.t+"\x00"+m.d]++
	}
	for _, x := range as {
		k := x.t + "\x00" + x.n
		if _, e = tx.Exec(`INSERT INTO accounts VALUES(?,?,?,0,?)`, x.t, x.n, bal[k], ver[k]); e != nil {
			return e
		}
		if _, e = tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'opening',?,0,?)`, x.t, x.n, bal[k], newid()); e != nil {
			return e
		}
	}
	for _, m := range ms {
		id := fmt.Sprintf("legacy-%d", m.id)
		if _, e = tx.Exec(`INSERT INTO transfers(tenant,id,src,dst,amount,legacy_id) VALUES(?,?,?,?,?,?)`, m.t, id, m.s, m.d, m.u, m.id); e != nil {
			return e
		}
		if _, e = tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?, 'transfer',?,?,?,?)`, m.t, m.s, -m.u, 0, id, m.id); e != nil {
			return e
		}
		if _, e = tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?, 'transfer',?,?,?,?)`, m.t, m.d, m.u, 0, id, m.id); e != nil {
			return e
		}
	}
	return nil
}
func newid() string { return fmt.Sprintf("%d-%d", time.Now().UnixNano(), seq.Add(1)) }

var seq atomic.Uint64

func (a *API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.URL.Path == "/health" && r.Method == "GET" {
		write(w, 200, map[string]any{"ok": true})
		return
	}
	t := r.Header.Get("X-Tenant")
	if !ident.MatchString(t) {
		errout(w, 400, "invalid")
		return
	}
	path := r.URL.Path
	if strings.HasPrefix(path, "/accounts/") && r.Method == "GET" {
		name := strings.TrimPrefix(path, "/accounts/")
		if strings.Contains(name, "/") || !ident.MatchString(name) {
			errout(w, 404, "not_found")
			return
		}
		x, e := a.account(t, name)
		if e != nil {
			errout(w, 404, "not_found")
		} else {
			write(w, 200, map[string]any{"account": x})
		}
		return
	}
	if path == "/entries" && r.Method == "GET" {
		a.entries(w, r, t)
		return
	}
	if path == "/summary" && r.Method == "GET" {
		a.summary(w, r, t)
		return
	}
	if r.Method != "POST" {
		errout(w, 404, "not_found")
		return
	}
	if !keypat.MatchString(r.Header.Get("Idempotency-Key")) {
		errout(w, 400, "invalid")
		return
	}
	var body map[string]json.RawMessage
	if e := decode(r, &body); e != nil {
		errout(w, 400, "invalid")
		return
	}
	raw, _ := json.Marshal(body)
	canon := string(raw)
	if result, status, found, conf := a.replay(t, r.Header.Get("Idempotency-Key"), path, canon); found {
		if conf {
			errout(w, 409, "idempotency_conflict")
		} else {
			w.WriteHeader(status)
			w.Write(result)
		}
		return
	}
	status, res, code := a.mutate(t, path, body)
	if code != "" {
		sc := 400
		if code == "not_found" {
			sc = 404
		}
		if code != "invalid" && code != "not_found" {
			sc = 409
		}
		errout(w, sc, code)
		return
	}
	tx, e := a.db.Begin()
	if e != nil {
		errout(w, 500, "invalid")
		return
	}
	_, e = tx.Exec(`INSERT INTO idem VALUES(?,?,?,?,?,?)`, t, r.Header.Get("Idempotency-Key"), path, canon, status, string(res))
	if e == nil {
		e = tx.Commit()
	} else {
		tx.Rollback()
	}
	if e != nil {
		if rr, ss, ok, cf := a.replay(t, r.Header.Get("Idempotency-Key"), path, canon); ok && !cf {
			w.WriteHeader(ss)
			w.Write(rr)
			return
		}
		errout(w, 500, "invalid")
		return
	}
	w.WriteHeader(status)
	w.Write(res)
}
func write(w http.ResponseWriter, s int, v any) {
	b, _ := json.Marshal(v)
	w.WriteHeader(s)
	w.Write(b)
}
func errout(w http.ResponseWriter, s int, c string) {
	write(w, s, map[string]any{"error": map[string]string{"code": c}})
}
func decode(r *http.Request, v any) error {
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return e
	}
	var x any
	if e := d.Decode(&x); e != io.EOF {
		return fmt.Errorf("trailing")
	}
	return nil
}
func (a *API) replay(t, k, p, b string) ([]byte, int, bool, bool) {
	var path, body, res string
	var s int
	e := a.db.QueryRow(`SELECT path,body,status,result FROM idem WHERE tenant=? AND key=?`, t, k).Scan(&path, &body, &s, &res)
	if e != nil {
		return nil, 0, false, false
	}
	return []byte(res), s, true, path != p || body != b
}

type Account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}

func (a *API) account(t, n string) (Account, error) {
	var x Account
	e := a.db.QueryRow(`SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&x.Name, &x.Balance, &x.Reserved, &x.Version)
	x.Available = x.Balance - x.Reserved
	return x, e
}
func val(m map[string]json.RawMessage, k string, required bool) (json.RawMessage, bool) {
	v, ok := m[k]
	return v, ok || !required
}
func str(m map[string]json.RawMessage, k string, req bool) (string, bool) {
	v, ok := val(m, k, req)
	if !ok {
		return "", false
	}
	var s string
	if len(v) == 0 || json.Unmarshal(v, &s) != nil {
		return "", false
	}
	return s, true
}
func num(m map[string]json.RawMessage, k string, req bool, min, max int64) (int64, bool, bool) {
	v, ok := val(m, k, req)
	if !ok {
		return 0, false, false
	}
	if len(v) == 0 {
		return 0, true, !req
	}
	var n int64
	if json.Unmarshal(v, &n) != nil {
		return 0, false, false
	}
	return n, true, n >= min && n <= max
}
func (a *API) mutate(t, p string, m map[string]json.RawMessage) (int, []byte, string) {
	tx, e := a.db.Begin()
	if e != nil {
		return 0, nil, "invalid"
	}
	defer tx.Rollback()
	fail := func(c string) (int, []byte, string) { return 0, nil, c }
	commit := func(status int, v any) (int, []byte, string) {
		b, _ := json.Marshal(v)
		if tx.Commit() != nil {
			return 0, nil, "invalid"
		}
		return status, b, ""
	}
	if p == "/accounts" {
		n, o := str(m, "name", true)
		v, ok, rangeok := num(m, "opening", true, 0, 1e9)
		if !o || !ok || !rangeok || !ident.MatchString(n) {
			return fail("invalid")
		}
		_, e = tx.Exec(`INSERT INTO accounts VALUES(?,?,?,0,1)`, t, n, v)
		if e != nil {
			return fail("exists")
		}
		id := newid()
		tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'opening',?,0,?)`, t, n, v, id)
		x := Account{Name: n, Balance: v, Available: v, Version: 1}
		return commit(201, map[string]any{"account": x})
	}
	if p == "/transfers" {
		return a.transferOp(tx, t, m, commit, fail)
	}
	if p == "/batches" {
		var x struct {
			Transfers []json.RawMessage `json:"transfers"`
		}
		if json.Unmarshal(mustJSON(m), &x) != nil || len(x.Transfers) < 1 || len(x.Transfers) > 20 || len(m) != 1 {
			return fail("invalid")
		}
		objects := []any{}
		touched := map[string]bool{}
		for _, b := range x.Transfers {
			var z map[string]json.RawMessage
			json.Unmarshal(b, &z)
			_, st, c := a.transferOp(tx, t, z, nil, fail)
			if c != "" {
				return fail(c)
			}
			var q map[string]any
			_ = json.Unmarshal(st, &q)
			objects = append(objects, q["transfer"])
			var fr, to string
			json.Unmarshal(z["from"], &fr)
			json.Unmarshal(z["to"], &to)
			touched[fr] = true
			touched[to] = true
		}
		names := []string{}
		for n := range touched {
			names = append(names, n)
		}
		sort.Strings(names)
		aa := []Account{}
		for _, n := range names {
			x, e := a.account(t, n)
			if e != nil {
				return fail("not_found")
			}
			aa = append(aa, x)
		}
		return commit(201, map[string]any{"transfers": objects, "accounts": aa})
	}
	if p == "/holds" {
		n, o := str(m, "account", true)
		amt, ok, rng := num(m, "amount", true, 1, 1e9)
		ver, _, vok := num(m, "version", false, 1, 9e15)
		if !o || !ok || !rng || !vok || len(m) > 3 {
			return fail("invalid")
		}
		x, e := a.account(t, n)
		if e != nil {
			return fail("not_found")
		}
		if _, ok := m["version"]; ok && ver != x.Version {
			return fail("version_conflict")
		}
		if amt > x.Available {
			return fail("insufficient")
		}
		id := newid()
		tx.Exec(`UPDATE accounts SET reserved=reserved+?,version=version+1 WHERE tenant=? AND name=?`, amt, t, n)
		tx.Exec(`INSERT INTO holds VALUES(?,?,?,?,'active')`, t, id, n, amt)
		tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'hold',0,?,?)`, t, n, amt, id)
		x, _ = a.account(t, n)
		return commit(201, map[string]any{"hold": map[string]any{"id": id, "account": n, "amount": amt, "state": "active"}, "account": x})
	}
	if strings.HasPrefix(p, "/holds/") {
		parts := strings.Split(p, "/")
		if len(parts) != 4 {
			return fail("not_found")
		}
		id := parts[2]
		var n, state string
		var amt int64
		if tx.QueryRow(`SELECT account,amount,state FROM holds WHERE tenant=? AND id=?`, t, id).Scan(&n, &amt, &state) != nil {
			return fail("not_found")
		}
		if state != "active" {
			return fail("terminal")
		}
		if parts[3] == "release" {
			ver, _, valid := num(m, "version", false, 1, 9e15)
			if !valid {
				return fail("invalid")
			}
			x, _ := a.account(t, n)
			if _, ok := m["version"]; ok && ver != x.Version {
				return fail("version_conflict")
			}
			tx.Exec(`UPDATE accounts SET reserved=reserved-?,version=version+1 WHERE tenant=? AND name=?`, amt, t, n)
			tx.Exec(`UPDATE holds SET state='released' WHERE tenant=? AND id=?`, t, id)
			tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'release',0,?,?)`, t, n, -amt, id)
			x, _ = a.account(t, n)
			return commit(200, map[string]any{"hold": map[string]any{"id": id, "account": n, "amount": amt, "state": "released"}, "account": x})
		}
		if parts[3] == "capture" {
			to, ok := str(m, "to", true)
			if !ok || !ident.MatchString(to) || to == n {
				return fail("invalid")
			}
			toV, _, tv := num(m, "to_version", false, 1, 9e15)
			fromV, _, fv := num(m, "from_version", false, 1, 9e15)
			if !tv || !fv {
				return fail("invalid")
			}
			src, _ := a.account(t, n)
			dst, e := a.account(t, to)
			if e != nil {
				return fail("not_found")
			}
			if _, ok := m["from_version"]; ok && fromV != src.Version || m["to_version"] != nil && toV != dst.Version {
				return fail("version_conflict")
			}
			if dst.Balance > 9e15-amt {
				return fail("invalid")
			}
			tx.Exec(`UPDATE accounts SET balance=balance-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND name=?`, amt, amt, t, n)
			tx.Exec(`UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?`, amt, t, to)
			tid := newid()
			tx.Exec(`INSERT INTO transfers(tenant,id,src,dst,amount) VALUES(?,?,?,?,?)`, t, tid, n, to, amt)
			tx.Exec(`UPDATE holds SET state='captured' WHERE tenant=? AND id=?`, t, id)
			for _, q := range []struct {
				name string
				d    int64
			}{{n, -amt}, {to, amt}} {
				tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'capture',?,0,?)`, t, q.name, q.d, tid)
			}
			src, _ = a.account(t, n)
			dst, _ = a.account(t, to)
			return commit(200, map[string]any{"hold": map[string]any{"id": id, "account": n, "amount": amt, "state": "captured"}, "transfer": map[string]any{"id": tid, "from": n, "to": to, "amount": amt, "reversed": false}, "accounts": []Account{src, dst}})
		}
		return fail("not_found")
	}
	if strings.HasPrefix(p, "/transfers/") {
		return fail("terminal")
	}
	return fail("not_found")
}
func mustJSON(m map[string]json.RawMessage) []byte { b, _ := json.Marshal(m); return b }
func (a *API) transferOp(tx *sql.Tx, t string, m map[string]json.RawMessage, commit func(int, any) (int, []byte, string), fail func(string) (int, []byte, string)) (int, []byte, string) {
	from, o := str(m, "from", true)
	to, q := str(m, "to", true)
	amt, ok, rng := num(m, "amount", true, 1, 1e9)
	fv, _, fok := num(m, "from_version", false, 1, 9e15)
	tv, _, tok := num(m, "to_version", false, 1, 9e15)
	if !o || !q || !ok || !rng || !fok || !tok || !ident.MatchString(from) || !ident.MatchString(to) || from == to {
		return fail("invalid")
	}
	if len(m) > 5 {
		return fail("invalid")
	}
	src, e := a.account(t, from)
	if e != nil {
		return fail("not_found")
	}
	dst, e := a.account(t, to)
	if e != nil {
		return fail("not_found")
	}
	if _, ok := m["from_version"]; ok && fv != src.Version || m["to_version"] != nil && tv != dst.Version {
		return fail("version_conflict")
	}
	if amt > src.Available {
		return fail("insufficient")
	}
	if dst.Balance > 9e15-amt {
		return fail("invalid")
	}
	id := newid()
	tx.Exec(`UPDATE accounts SET balance=balance-?,version=version+1 WHERE tenant=? AND name=?`, amt, t, from)
	tx.Exec(`UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?`, amt, t, to)
	tx.Exec(`INSERT INTO transfers(tenant,id,src,dst,amount) VALUES(?,?,?,?,?)`, t, id, from, to, amt)
	tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'transfer',?,0,?)`, t, from, -amt, id)
	tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'transfer',?,0,?)`, t, to, amt, id)
	src, _ = a.account(t, from)
	dst, _ = a.account(t, to)
	result := map[string]any{"transfer": map[string]any{"id": id, "from": from, "to": to, "amount": amt, "reversed": false}, "accounts": []Account{src, dst}}
	if commit == nil {
		b, _ := json.Marshal(result)
		return 201, b, ""
	}
	return commit(201, result)
}
func (a *API) entries(w http.ResponseWriter, r *http.Request, t string) {
	q := r.URL.Query()
	for k, v := range q {
		if k != "after" && k != "limit" && k != "snapshot" || len(v) != 1 {
			errout(w, 400, "invalid")
			return
		}
	}
	after, e := parseq(q.Get("after"), 0)
	if e != nil {
		errout(w, 400, "invalid")
		return
	}
	lim, e := parseq(q.Get("limit"), 50)
	if e != nil || lim < 1 || lim > 100 {
		errout(w, 400, "invalid")
		return
	}
	max, _ := a.maxseq(t)
	snap := max
	if q.Has("snapshot") {
		snap, e = parseq(q.Get("snapshot"), 0)
		if e != nil || snap > max {
			errout(w, 400, "invalid")
			return
		}
	}
	if after > snap {
		errout(w, 400, "invalid")
		return
	}
	rows, e := a.db.Query(`SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, t, after, snap, lim)
	if e != nil {
		errout(w, 500, "invalid")
		return
	}
	arr := []map[string]any{}
	var last = after
	for rows.Next() {
		var s, d, r int64
		var ac, k, id string
		var legacy sql.NullInt64
		rows.Scan(&s, &ac, &k, &d, &r, &id, &legacy)
		x := map[string]any{"seq": s, "account": ac, "kind": k, "balance_delta": d, "reserved_delta": r, "operation_id": id}
		if legacy.Valid {
			x["legacy_id"] = legacy.Int64
		}
		arr = append(arr, x)
		last = s
	}
	rows.Close()
	var more int
	a.db.QueryRow(`SELECT count(*) FROM entries WHERE tenant=? AND seq>? AND seq<=?`, t, last, snap).Scan(&more)
	write(w, 200, map[string]any{"entries": arr, "snapshot": snap, "next_after": last, "has_more": more > 0})
}
func (a *API) maxseq(t string) (int64, error) {
	var n sql.NullInt64
	e := a.db.QueryRow(`SELECT max(seq) FROM entries WHERE tenant=?`, t).Scan(&n)
	return n.Int64, e
}
func parseq(s string, d int64) (int64, error) {
	if s == "" {
		return d, nil
	}
	return strconv.ParseInt(s, 10, 64)
}
func (a *API) summary(w http.ResponseWriter, r *http.Request, t string) {
	q := r.URL.Query()
	for k, v := range q {
		if k != "snapshot" || len(v) != 1 {
			errout(w, 400, "invalid")
			return
		}
	}
	max, _ := a.maxseq(t)
	snap := max
	var e error
	if q.Has("snapshot") {
		snap, e = parseq(q.Get("snapshot"), 0)
		if e != nil || snap < 0 || snap > max {
			errout(w, 400, "invalid")
			return
		}
	}
	rows, e := a.db.Query(`SELECT account,kind,balance_delta,reserved_delta FROM entries WHERE tenant=? AND seq<=? ORDER BY seq`, t, snap)
	if e != nil {
		errout(w, 500, "invalid")
		return
	}
	m := map[string][2]int64{}
	count := 0
	for rows.Next() {
		var n, k string
		var b, z int64
		rows.Scan(&n, &k, &b, &z)
		v := m[n]
		v[0] += b
		v[1] += z
		m[n] = v
		count++
	}
	rows.Close()
	names := []string{}
	for n := range m {
		names = append(names, n)
	}
	sort.Strings(names)
	aa := []map[string]any{}
	var tb, tr int64
	for _, n := range names {
		v := m[n]
		tb += v[0]
		tr += v[1]
		aa = append(aa, map[string]any{"name": n, "balance": v[0], "reserved": v[1], "available": v[0] - v[1]})
	}
	write(w, 200, map[string]any{"snapshot": snap, "accounts": aa, "totals": map[string]int64{"balance": tb, "reserved": tr, "available": tb - tr}, "entry_count": count})
}
