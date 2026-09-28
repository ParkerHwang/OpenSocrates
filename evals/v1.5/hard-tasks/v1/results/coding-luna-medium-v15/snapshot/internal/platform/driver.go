package platform

import (
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	_ "modernc.org/sqlite"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const max int64 = 9000000000000000

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type API struct{ DB *sql.DB }
type Account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
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
type Entry struct {
	Seq           int64  `json:"seq"`
	Account       string `json:"account"`
	Kind          string `json:"kind"`
	BalanceDelta  int64  `json:"balance_delta"`
	ReservedDelta int64  `json:"reserved_delta"`
	OperationID   string `json:"operation_id"`
	LegacyID      *int64 `json:"legacy_id,omitempty"`
}
type failure struct {
	status int
	code   string
}

func (f failure) Error() string { return f.code }

func fail(s int, c string) error { return failure{s, c} }
func Open(path string) (*sql.DB, error) {
	d, e := sql.Open("sqlite", path)
	if e != nil {
		return nil, e
	}
	d.SetMaxOpenConns(8)
	d.SetMaxIdleConns(8)
	dsn := path
	if !strings.HasPrefix(path, "file:") {
		dsn = "file:" + path
	}
	if strings.Contains(dsn, "?") {
		dsn += "&"
	} else {
		dsn += "?"
	}
	dsn += "_pragma=busy_timeout(10000)&_pragma=foreign_keys(1)&_pragma=journal_mode(WAL)&_txlock=immediate"
	d.Close()
	d, e = sql.Open("sqlite", dsn)
	if e != nil {
		return nil, e
	}
	d.SetMaxOpenConns(8)
	d.SetMaxIdleConns(8)
	if e = d.Ping(); e != nil {
		d.Close()
		return nil, e
	}
	if e = migrate(d); e != nil {
		d.Close()
		return nil, e
	}
	return d, nil
}
func migrate(d *sql.DB) error {
	tx, e := d.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	var v int
	if e = tx.QueryRow("PRAGMA user_version").Scan(&v); e != nil {
		return e
	}
	if v > 2 {
		return fmt.Errorf("unsupported schema %d", v)
	}
	if v == 0 || v == 1 {
		_, e = tx.Exec(`CREATE TABLE accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL DEFAULT 0,version INTEGER NOT NULL,PRIMARY KEY(tenant,name)); CREATE TABLE entries(seq INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER); CREATE INDEX entries_tenant_seq ON entries(tenant,seq); CREATE TABLE transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,src TEXT NOT NULL,dst TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL DEFAULT 0,reverse_of TEXT,legacy_id INTEGER,PRIMARY KEY(tenant,id)); CREATE TABLE holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id)); CREATE TABLE idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body TEXT NOT NULL,status INTEGER NOT NULL,result TEXT NOT NULL,PRIMARY KEY(tenant,key));`)
		if e != nil {
			return e
		}
		if e = migrateLegacy(tx); e != nil {
			return e
		}
		_, e = tx.Exec("PRAGMA user_version=2")
	}
	if e != nil {
		return e
	}
	return tx.Commit()
}
func migrateLegacy(tx *sql.Tx) error {
	var n int
	_ = tx.QueryRow("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='legacy_accounts'").Scan(&n)
	if n == 0 {
		return nil
	}
	rows, e := tx.Query("SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name")
	if e != nil {
		return e
	}
	type a struct {
		t, n string
		b    int64
	}
	as := []a{}
	for rows.Next() {
		var x a
		if e = rows.Scan(&x.t, &x.n, &x.b); e != nil {
			rows.Close()
			return e
		}
		as = append(as, x)
	}
	rows.Close()
	type m struct {
		id      int64
		t, s, d string
		u       int64
	}
	ms := []m{}
	rs, e := tx.Query("SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id")
	if e != nil {
		return e
	}
	for rs.Next() {
		var x m
		if e = rs.Scan(&x.id, &x.t, &x.s, &x.d, &x.u); e != nil {
			rs.Close()
			return e
		}
		ms = append(ms, x)
	}
	rs.Close()
	out, in, touch := map[string]int64{}, map[string]int64{}, map[string]int64{}
	for _, x := range ms {
		out[x.t+"\x00"+x.s] += x.u
		in[x.t+"\x00"+x.d] += x.u
		touch[x.t+"\x00"+x.s]++
		touch[x.t+"\x00"+x.d]++
	}
	for _, x := range as {
		k := x.t + "\x00" + x.n
		o := x.b + out[k] - in[k]
		if o < 0 || o > max {
			return fmt.Errorf("invalid legacy inferred opening")
		}
		if _, e = tx.Exec("INSERT INTO accounts VALUES(?,?,?,0,?)", x.t, x.n, x.b, 1+touch[k]); e != nil {
			return e
		}
		if _, e = tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'opening',?,0,?)", x.t, x.n, o, "legacy-opening-"+x.n); e != nil {
			return e
		}
	}
	for _, x := range ms {
		id := fmt.Sprintf("legacy-%d", x.id)
		if _, e = tx.Exec("INSERT INTO transfers(tenant,id,src,dst,amount,legacy_id) VALUES(?,?,?,?,?,?)", x.t, id, x.s, x.d, x.u, x.id); e != nil {
			return e
		}
		for _, q := range []struct {
			n string
			d int64
		}{{x.s, -x.u}, {x.d, x.u}} {
			if _, e = tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?, 'transfer',?,0,?,?)", x.t, q.n, q.d, id, x.id); e != nil {
				return e
			}
		}
	}
	return nil
}
func (a *API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.URL.Path == "/health" && r.Method == "GET" {
		if a.DB.Ping() != nil {
			writeErr(w, 500, "invalid")
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true})
		return
	}
	tenant := r.Header.Get("X-Tenant")
	if !ident.MatchString(tenant) {
		writeErr(w, 400, "invalid")
		return
	}
	defer r.Body.Close()
	if r.Method == "GET" {
		a.read(w, r, tenant)
		return
	}
	key := r.Header.Get("Idempotency-Key")
	if !keyRE.MatchString(key) {
		writeErr(w, 400, "invalid")
		return
	}
	raw, e := readBody(r)
	if e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	var obj any
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	dec.DisallowUnknownFields()
	if e = dec.Decode(&obj); e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	var trailing any
	if e = dec.Decode(&trailing); e != io.EOF {
		writeErr(w, 400, "invalid")
		return
	}
	canonical, _ := json.Marshal(obj)
	tx, e := a.DB.Begin()
	if e != nil {
		writeErr(w, 500, "invalid")
		return
	}
	defer tx.Rollback()
	var oldpath, oldbody, oldresult string
	var oldstatus int
	e = tx.QueryRow("SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?", tenant, key).Scan(&oldpath, &oldbody, &oldstatus, &oldresult)
	if e == nil {
		if oldpath != r.URL.Path || oldbody != string(canonical) {
			writeErr(w, 409, "idempotency_conflict")
			return
		}
		if tx.Commit() == nil {
			w.WriteHeader(oldstatus)
			w.Write([]byte(oldresult))
		}
		return
	} else if !errors.Is(e, sql.ErrNoRows) {
		writeErr(w, 500, "invalid")
		return
	}
	status, result, err := a.mutate(tx, tenant, r.URL.Path, obj)
	if err != nil {
		tx.Rollback()
		respondError(w, err)
		return
	}
	b, _ := json.Marshal(result)
	if _, e = tx.Exec("INSERT INTO idempotency VALUES(?,?,?,?,?,?)", tenant, key, r.URL.Path, string(canonical), status, string(b)); e != nil {
		respondError(w, fail(500, "invalid"))
		return
	}
	if e = tx.Commit(); e != nil {
		respondError(w, e)
		return
	}
	writeJSON(w, status, result)
}
func readBody(r *http.Request) ([]byte, error) {
	if r.Body == nil {
		return nil, errors.New("body")
	}
	var b strings.Builder
	buf := make([]byte, 4096)
	for {
		n, e := r.Body.Read(buf)
		if n > 0 {
			b.Write(buf[:n])
			if b.Len() > 1<<20 {
				return nil, errors.New("large")
			}
		}
		if e != nil {
			if e.Error() == "EOF" {
				break
			}
			return nil, e
		}
	}
	if strings.TrimSpace(b.String()) == "" {
		return nil, errors.New("empty")
	}
	return []byte(b.String()), nil
}
func decode(b []byte, v any) error {
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.UseNumber()
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return e
	}
	var x any
	if e := d.Decode(&x); e != io.EOF {
		return errors.New("trailing")
	}
	return nil
}
func writeJSON(w http.ResponseWriter, s int, v any) {
	w.WriteHeader(s)
	_ = json.NewEncoder(w).Encode(v)
}
func writeErr(w http.ResponseWriter, s int, c string) {
	writeJSON(w, s, map[string]any{"error": map[string]string{"code": c}})
}
func respondError(w http.ResponseWriter, e error) {
	if f, ok := e.(failure); ok {
		writeErr(w, f.status, f.code)
	} else {
		writeErr(w, 500, "invalid")
	}
}
func requiredString(m map[string]json.RawMessage, k string) (string, bool) {
	var s string
	b, ok := m[k]
	if !ok || json.Unmarshal(b, &s) != nil || !ident.MatchString(s) {
		return "", false
	}
	return s, true
}
func integer(m map[string]json.RawMessage, k string, lo, hi int64, required bool) (int64, bool) {
	b, ok := m[k]
	if !ok {
		return 0, !required
	}
	if string(b) == "null" {
		return 0, false
	}
	var n json.Number
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.UseNumber()
	if d.Decode(&n) != nil {
		return 0, false
	}
	x, e := strconv.ParseInt(n.String(), 10, 64)
	return x, e == nil && x >= lo && x <= hi
}
func object(v any) (map[string]json.RawMessage, bool) {
	b, e := json.Marshal(v)
	if e != nil {
		return nil, false
	}
	var m map[string]json.RawMessage
	e = json.Unmarshal(b, &m)
	return m, e == nil && m != nil
}
func (a *API) mutate(tx *sql.Tx, t, p string, v any) (int, any, error) {
	m, ok := object(v)
	if !ok {
		return 0, nil, fail(400, "invalid")
	}
	switch {
	case p == "/accounts":
		n, nok := requiredString(m, "name")
		o, ook := integer(m, "opening", 0, 1000000000, true)
		if !nok || !ook || len(m) != 2 {
			return 0, nil, fail(400, "invalid")
		}
		_, e := tx.Exec("INSERT INTO accounts VALUES(?,?,?,0,1)", t, n, o)
		if e != nil {
			return 0, nil, fail(409, "exists")
		}
		id := newID()
		if e = entry(tx, t, n, "opening", o, 0, id, nil); e != nil {
			return 0, nil, e
		}
		ac, e := getAccount(tx, t, n)
		return 201, map[string]any{"account": ac}, e
	case p == "/transfers":
		q, e := parseTransfer(m)
		if e != nil {
			return 0, nil, e
		}
		tr, acs, e := doTransfer(tx, t, q, nil)
		return 201, map[string]any{"transfer": tr, "accounts": acs}, e
	case p == "/batches":
		if len(m) != 1 {
			return 0, nil, fail(400, "invalid")
		}
		var arr []json.RawMessage
		if json.Unmarshal(m["transfers"], &arr) != nil || len(arr) < 1 || len(arr) > 20 {
			return 0, nil, fail(400, "invalid")
		}
		trs := []Transfer{}
		touched := map[string]bool{}
		for _, b := range arr {
			var raw any
			if decode(b, &raw) != nil {
				return 0, nil, fail(400, "invalid")
			}
			om, valid := object(raw)
			if !valid {
				return 0, nil, fail(400, "invalid")
			}
			q, e := parseTransfer(om)
			if e != nil {
				return 0, nil, e
			}
			tr, _, e := doTransfer(tx, t, q, nil)
			if e != nil {
				return 0, nil, e
			}
			trs = append(trs, tr)
			touched[q.from] = true
			touched[q.to] = true
		}
		names := make([]string, 0, len(touched))
		for n := range touched {
			names = append(names, n)
		}
		sort.Strings(names)
		acs := []Account{}
		for _, n := range names {
			x, e := getAccount(tx, t, n)
			if e != nil {
				return 0, nil, e
			}
			acs = append(acs, x)
		}
		return 201, map[string]any{"transfers": trs, "accounts": acs}, nil
	case p == "/holds":
		n, nok := requiredString(m, "account")
		amt, aok := integer(m, "amount", 1, 1000000000, true)
		ver, vok := integer(m, "version", 1, max, false)
		if !nok || !aok || !vok || unknown(m, "account", "amount", "version") {
			return 0, nil, fail(400, "invalid")
		}
		ac, e := checked(tx, t, n, ver, m["version"] != nil)
		if e != nil {
			return 0, nil, e
		}
		if ac.Available < amt {
			return 0, nil, fail(409, "insufficient")
		}
		ac.Reserved += amt
		ac.Available = ac.Balance - ac.Reserved
		ac.Version++
		if e = saveAccount(tx, t, ac); e != nil {
			return 0, nil, e
		}
		id := newID()
		if e = entry(tx, t, n, "hold", 0, amt, id, nil); e != nil {
			return 0, nil, e
		}
		h := Hold{id, n, amt, "active"}
		_, e = tx.Exec("INSERT INTO holds VALUES(?,?,?,?,?)", t, id, n, amt, "active")
		return 201, map[string]any{"hold": h, "account": ac}, e
	case strings.HasPrefix(p, "/holds/") && (strings.HasSuffix(p, "/capture") || strings.HasSuffix(p, "/release")):
		return a.holdMutation(tx, t, p, m)
	case strings.HasPrefix(p, "/transfers/") && strings.HasSuffix(p, "/reverse"):
		return a.reverse(tx, t, p, m)
	default:
		return 0, nil, fail(404, "not_found")
	}
}
func unknown(m map[string]json.RawMessage, ks ...string) bool {
	for k := range m {
		ok := false
		for _, x := range ks {
			if x == k {
				ok = true
			}
		}
		if !ok {
			return true
		}
	}
	return false
}

type trReq struct {
	from, to   string
	amount     int64
	fv, tv     int64
	hasF, hasT bool
}

func parseTransfer(m map[string]json.RawMessage) (trReq, error) {
	f, fok := requiredString(m, "from")
	to, tok := requiredString(m, "to")
	amt, aok := integer(m, "amount", 1, 1000000000, true)
	fv, fvok := integer(m, "from_version", 1, max, false)
	tv, tvok := integer(m, "to_version", 1, max, false)
	if !fok || !tok || !aok || !fvok || !tvok || unknown(m, "from", "to", "amount", "from_version", "to_version") {
		return trReq{}, fail(400, "invalid")
	}
	if f == to {
		return trReq{}, fail(400, "invalid")
	}
	return trReq{f, to, amt, fv, tv, m["from_version"] != nil, m["to_version"] != nil}, nil
}
func doTransfer(tx *sql.Tx, t string, q trReq, kind *string) (Transfer, []Account, error) {
	src, e := checked(tx, t, q.from, q.fv, q.hasF)
	if e != nil {
		return Transfer{}, nil, e
	}
	dst, e := checked(tx, t, q.to, q.tv, q.hasT)
	if e != nil {
		return Transfer{}, nil, e
	}
	if src.Available < q.amount {
		return Transfer{}, nil, fail(409, "insufficient")
	}
	if dst.Balance > max-q.amount {
		return Transfer{}, nil, fail(400, "invalid")
	}
	src.Balance -= q.amount
	dst.Balance += q.amount
	src.Available = src.Balance - src.Reserved
	dst.Available = dst.Balance - dst.Reserved
	src.Version++
	dst.Version++
	if e = saveAccount(tx, t, src); e != nil {
		return Transfer{}, nil, e
	}
	if e = saveAccount(tx, t, dst); e != nil {
		return Transfer{}, nil, e
	}
	id := newID()
	k := "transfer"
	if kind != nil {
		k = *kind
	}
	if _, e = tx.Exec("INSERT INTO transfers(tenant,id,src,dst,amount) VALUES(?,?,?,?,?)", t, id, q.from, q.to, q.amount); e != nil {
		return Transfer{}, nil, e
	}
	if e = entry(tx, t, q.from, k, -q.amount, 0, id, nil); e != nil {
		return Transfer{}, nil, e
	}
	if e = entry(tx, t, q.to, k, q.amount, 0, id, nil); e != nil {
		return Transfer{}, nil, e
	}
	return Transfer{id, q.from, q.to, q.amount, false, nil}, []Account{src, dst}, nil
}
func newID() string {
	b := make([]byte, 16)
	if _, e := rand.Read(b); e == nil {
		return hex.EncodeToString(b)
	}
	return fmt.Sprintf("%x", time.Now().UnixNano())
}
func entry(tx *sql.Tx, t, n, k string, b, r int64, id string, l *int64) error {
	_, e := tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?)", t, n, k, b, r, id, l)
	return e
}
func getAccount(tx *sql.Tx, t, n string) (Account, error) {
	var x Account
	e := tx.QueryRow("SELECT name,balance,reserved,balance-reserved,version FROM accounts WHERE tenant=? AND name=?", t, n).Scan(&x.Name, &x.Balance, &x.Reserved, &x.Available, &x.Version)
	if errors.Is(e, sql.ErrNoRows) {
		return x, fail(404, "not_found")
	}
	return x, e
}
func checked(tx *sql.Tx, t, n string, v int64, has bool) (Account, error) {
	x, e := getAccount(tx, t, n)
	if e != nil {
		return x, e
	}
	if has && x.Version != v {
		return x, fail(409, "version_conflict")
	}
	return x, nil
}
func saveAccount(tx *sql.Tx, t string, x Account) error {
	if x.Balance < 0 || x.Reserved < 0 || x.Reserved > x.Balance || x.Balance > max {
		return fail(400, "invalid")
	}
	_, e := tx.Exec("UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?", x.Balance, x.Reserved, x.Version, t, x.Name)
	return e
}
func (a *API) holdMutation(tx *sql.Tx, t, p string, m map[string]json.RawMessage) (int, any, error) {
	parts := strings.Split(p, "/")
	if len(parts) != 4 || parts[1] == "" || !strings.Contains(p, "/holds/") {
		return 0, nil, fail(404, "not_found")
	}
	id := parts[2]
	var h Hold
	e := tx.QueryRow("SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?", t, id).Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	if errors.Is(e, sql.ErrNoRows) {
		return 0, nil, fail(404, "not_found")
	}
	if e != nil {
		return 0, nil, e
	}
	if h.State != "active" {
		return 0, nil, fail(409, "terminal")
	}
	if strings.HasSuffix(p, "/release") {
		v, ok := integer(m, "version", 1, max, false)
		if !ok || unknown(m, "version") {
			return 0, nil, fail(400, "invalid")
		}
		ac, e := checked(tx, t, h.Account, v, m["version"] != nil)
		if e != nil {
			return 0, nil, e
		}
		ac.Reserved -= h.Amount
		ac.Available = ac.Balance - ac.Reserved
		ac.Version++
		if e = saveAccount(tx, t, ac); e != nil {
			return 0, nil, e
		}
		if _, e = tx.Exec("UPDATE holds SET state='released' WHERE tenant=? AND id=?", t, id); e != nil {
			return 0, nil, e
		}
		if e = entry(tx, t, h.Account, "release", 0, -h.Amount, id, nil); e != nil {
			return 0, nil, e
		}
		h.State = "released"
		return 200, map[string]any{"hold": h, "account": ac}, nil
	}
	to, ok := requiredString(m, "to")
	fv, fok := integer(m, "from_version", 1, max, false)
	tv, tok := integer(m, "to_version", 1, max, false)
	if !ok || !fok || !tok || unknown(m, "to", "from_version", "to_version") {
		return 0, nil, fail(400, "invalid")
	}
	if to == h.Account {
		return 0, nil, fail(400, "invalid")
	}
	src, e := checked(tx, t, h.Account, fv, m["from_version"] != nil)
	if e != nil {
		return 0, nil, e
	}
	dst, e := checked(tx, t, to, tv, m["to_version"] != nil)
	if e != nil {
		return 0, nil, e
	}
	if dst.Balance > max-h.Amount {
		return 0, nil, fail(400, "invalid")
	}
	src.Reserved -= h.Amount
	src.Balance -= h.Amount
	dst.Balance += h.Amount
	src.Available = src.Balance - src.Reserved
	dst.Available = dst.Balance - dst.Reserved
	src.Version++
	dst.Version++
	if e = saveAccount(tx, t, src); e != nil {
		return 0, nil, e
	}
	if e = saveAccount(tx, t, dst); e != nil {
		return 0, nil, e
	}
	idtr := newID()
	if _, e = tx.Exec("INSERT INTO transfers(tenant,id,src,dst,amount) VALUES(?,?,?,?,?)", t, idtr, h.Account, to, h.Amount); e != nil {
		return 0, nil, e
	}
	if _, e = tx.Exec("UPDATE holds SET state='captured' WHERE tenant=? AND id=?", t, id); e != nil {
		return 0, nil, e
	}
	if e = entry(tx, t, h.Account, "capture", -h.Amount, -h.Amount, idtr, nil); e != nil {
		return 0, nil, e
	}
	if e = entry(tx, t, to, "capture", h.Amount, 0, idtr, nil); e != nil {
		return 0, nil, e
	}
	h.State = "captured"
	return 200, map[string]any{"hold": h, "transfer": Transfer{idtr, h.Account, to, h.Amount, false, nil}, "accounts": []Account{src, dst}}, nil
}
func (a *API) reverse(tx *sql.Tx, t, p string, m map[string]json.RawMessage) (int, any, error) {
	parts := strings.Split(p, "/")
	if len(parts) != 4 || parts[1] == "" {
		return 0, nil, fail(404, "not_found")
	}
	id := parts[2]
	fv, fok := integer(m, "from_version", 1, max, false)
	tv, tok := integer(m, "to_version", 1, max, false)
	if !fok || !tok || unknown(m, "from_version", "to_version") {
		return 0, nil, fail(400, "invalid")
	}
	var tr Transfer
	var rev sql.NullString
	e := tx.QueryRow("SELECT id,src,dst,amount,reversed,reverse_of FROM transfers WHERE tenant=? AND id=?", t, id).Scan(&tr.ID, &tr.From, &tr.To, &tr.Amount, &tr.Reversed, &rev)
	if errors.Is(e, sql.ErrNoRows) {
		return 0, nil, fail(404, "not_found")
	}
	if e != nil {
		return 0, nil, e
	}
	if tr.Reversed || rev.Valid {
		return 0, nil, fail(409, "terminal")
	}
	// Version fields follow the original transfer's from/to account order.
	dst, e := checked(tx, t, tr.From, fv, m["from_version"] != nil)
	if e != nil {
		return 0, nil, e
	}
	src, e := checked(tx, t, tr.To, tv, m["to_version"] != nil)
	if e != nil {
		return 0, nil, e
	}
	if src.Available < tr.Amount {
		return 0, nil, fail(409, "insufficient")
	}
	if dst.Balance > max-tr.Amount {
		return 0, nil, fail(400, "invalid")
	}
	src.Balance -= tr.Amount
	dst.Balance += tr.Amount
	src.Available = src.Balance - src.Reserved
	dst.Available = dst.Balance - dst.Reserved
	src.Version++
	dst.Version++
	if e = saveAccount(tx, t, src); e != nil {
		return 0, nil, e
	}
	if e = saveAccount(tx, t, dst); e != nil {
		return 0, nil, e
	}
	rid := newID()
	if _, e = tx.Exec("INSERT INTO transfers(tenant,id,src,dst,amount,reverse_of) VALUES(?,?,?,?,?,?)", t, rid, tr.To, tr.From, tr.Amount, id); e != nil {
		return 0, nil, e
	}
	if _, e = tx.Exec("UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?", t, id); e != nil {
		return 0, nil, e
	}
	tr.Reversed = true
	r := Transfer{rid, tr.To, tr.From, tr.Amount, false, nil}
	if e = entry(tx, t, tr.To, "reversal", -tr.Amount, 0, rid, nil); e != nil {
		return 0, nil, e
	}
	if e = entry(tx, t, tr.From, "reversal", tr.Amount, 0, rid, nil); e != nil {
		return 0, nil, e
	}
	return 200, map[string]any{"transfer": tr, "reversal": r, "accounts": []Account{dst, src}}, nil
}
func (a *API) read(w http.ResponseWriter, r *http.Request, t string) {
	tx, e := a.DB.Begin()
	if e != nil {
		writeErr(w, 500, "invalid")
		return
	}
	defer tx.Rollback()
	p := r.URL.Path
	if strings.HasPrefix(p, "/accounts/") {
		if strings.Contains(strings.TrimPrefix(p, "/accounts/"), "/") {
			writeErr(w, 404, "not_found")
			return
		}
		n := strings.TrimPrefix(p, "/accounts/")
		if !ident.MatchString(n) || r.URL.RawQuery != "" {
			writeErr(w, 400, "invalid")
			return
		}
		x, e := getAccount(tx, t, n)
		if e != nil {
			respondError(w, e)
			return
		}
		writeJSON(w, 200, map[string]any{"account": x})
		return
	}
	if p == "/entries" || p == "/summary" {
		q := r.URL.Query()
		for k, v := range q {
			if p == "/entries" && k != "after" && k != "limit" && k != "snapshot" || p == "/summary" && k != "snapshot" || len(v) != 1 {
				writeErr(w, 400, "invalid")
				return
			}
		}
		var current int64
		_ = tx.QueryRow("SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?", t).Scan(&current)
		snap := current
		if s := q.Get("snapshot"); s != "" {
			n, er := strconv.ParseInt(s, 10, 64)
			if er != nil || n < 0 || n > current {
				writeErr(w, 400, "invalid")
				return
			}
			snap = n
		}
		if p == "/summary" {
			if _, ok := q["snapshot"]; ok && q.Get("snapshot") == "" {
				writeErr(w, 400, "invalid")
				return
			}
			type SAccount struct {
				Name      string `json:"name"`
				Balance   int64  `json:"balance"`
				Reserved  int64  `json:"reserved"`
				Available int64  `json:"available"`
			}
			rows, e := tx.Query("SELECT account,SUM(balance_delta),SUM(reserved_delta) FROM entries WHERE tenant=? AND seq<=? GROUP BY account HAVING SUM(CASE WHEN kind='opening' THEN 1 ELSE 0 END)>0 ORDER BY account", t, snap)
			if e != nil {
				writeErr(w, 500, "invalid")
				return
			}
			as := []SAccount{}
			var btot, rtot int64
			for rows.Next() {
				var x SAccount
				if rows.Scan(&x.Name, &x.Balance, &x.Reserved) != nil {
					rows.Close()
					writeErr(w, 500, "invalid")
					return
				}
				x.Available = x.Balance - x.Reserved
				btot += x.Balance
				rtot += x.Reserved
				as = append(as, x)
			}
			rows.Close()
			var cnt int64
			_ = tx.QueryRow("SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?", t, snap).Scan(&cnt)
			writeJSON(w, 200, map[string]any{"snapshot": snap, "accounts": as, "totals": map[string]int64{"balance": btot, "reserved": rtot, "available": btot - rtot}, "entry_count": cnt})
			return
		}
		after := int64(0)
		limit := int64(50)
		if _, ok := q["after"]; ok && q.Get("after") == "" {
			writeErr(w, 400, "invalid")
			return
		}
		if _, ok := q["limit"]; ok && q.Get("limit") == "" {
			writeErr(w, 400, "invalid")
			return
		}
		if _, ok := q["snapshot"]; ok && q.Get("snapshot") == "" {
			writeErr(w, 400, "invalid")
			return
		}
		if s := q.Get("after"); s != "" {
			n, er := strconv.ParseInt(s, 10, 64)
			if er != nil || n < 0 {
				writeErr(w, 400, "invalid")
				return
			}
			after = n
		}
		if s := q.Get("limit"); s != "" {
			n, er := strconv.ParseInt(s, 10, 64)
			if er != nil || n < 1 || n > 100 {
				writeErr(w, 400, "invalid")
				return
			}
			limit = n
		}
		if after > snap {
			writeErr(w, 400, "invalid")
			return
		}
		rows, e := tx.Query("SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?", t, after, snap, limit)
		if e != nil {
			writeErr(w, 500, "invalid")
			return
		}
		es := []Entry{}
		for rows.Next() {
			var x Entry
			var l sql.NullInt64
			if rows.Scan(&x.Seq, &x.Account, &x.Kind, &x.BalanceDelta, &x.ReservedDelta, &x.OperationID, &l) != nil {
				rows.Close()
				writeErr(w, 500, "invalid")
				return
			}
			if l.Valid {
				x.LegacyID = &l.Int64
			}
			es = append(es, x)
		}
		rows.Close()
		next := after
		if len(es) > 0 {
			next = es[len(es)-1].Seq
		}
		var more int
		_ = tx.QueryRow("SELECT EXISTS(SELECT 1 FROM entries WHERE tenant=? AND seq>? AND seq<=?)", t, next, snap).Scan(&more)
		writeJSON(w, 200, map[string]any{"entries": es, "snapshot": snap, "next_after": next, "has_more": more != 0})
		return
	}
	writeErr(w, 404, "not_found")
}
