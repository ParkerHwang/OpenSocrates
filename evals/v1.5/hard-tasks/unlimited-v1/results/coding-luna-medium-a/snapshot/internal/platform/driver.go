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
	"sync/atomic"
	"time"
)

const cap int64 = 9000000000000000

type Server struct {
	DB  *sql.DB
	ids atomic.Uint64
}

func Open(path string) (*sql.DB, error) {
	sep := "?"
	if strings.Contains(path, "?") {
		sep = "&"
	}
	db, e := sql.Open("sqlite", path+sep+"_txlock=immediate&_pragma=busy_timeout(10000)")
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(8)
	db.SetConnMaxLifetime(0)
	return db, nil
}
func New(db *sql.DB) (*Server, error) {
	s := &Server{DB: db}
	if _, e := db.Exec(`PRAGMA busy_timeout=10000`); e != nil {
		return nil, e
	}
	if e := s.migrate(); e != nil {
		return nil, e
	}
	return s, nil
}
func (s *Server) migrate() error {
	_, e := s.DB.Exec(`PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name)); CREATE TABLE IF NOT EXISTS entries(tenant TEXT NOT NULL,seq INTEGER PRIMARY KEY AUTOINCREMENT,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER); CREATE INDEX IF NOT EXISTS entries_tenant_seq ON entries(tenant,seq); CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,src TEXT NOT NULL,dst TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL DEFAULT 0,legacy_id INTEGER,PRIMARY KEY(tenant,id)); CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id)); CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body TEXT NOT NULL,status INTEGER NOT NULL,result TEXT NOT NULL,PRIMARY KEY(tenant,key));`)
	if e != nil {
		return e
	}
	return s.migrateLegacy()
}
func (s *Server) migrateLegacy() error {
	tx, e := s.DB.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	var v int
	if e = tx.QueryRow("PRAGMA user_version").Scan(&v); e != nil {
		return e
	}
	if v == 2 {
		return tx.Commit()
	}
	if v != 0 && v != 1 {
		return fmt.Errorf("unsupported db version %d", v)
	}
	if v == 1 {
		rows, e := tx.Query("SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name")
		if e != nil {
			return e
		}
		type acct struct {
			t, n string
			b    int64
		}
		as := []acct{}
		for rows.Next() {
			var a acct
			if e = rows.Scan(&a.t, &a.n, &a.b); e != nil {
				rows.Close()
				return e
			}
			as = append(as, a)
		}
		rows.Close()
		type mv struct {
			id          int64
			t, src, dst string
			u           int64
		}
		ms := []mv{}
		rows, e = tx.Query("SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id")
		if e != nil {
			return e
		}
		for rows.Next() {
			var m mv
			if e = rows.Scan(&m.id, &m.t, &m.src, &m.dst, &m.u); e != nil {
				rows.Close()
				return e
			}
			ms = append(ms, m)
		}
		rows.Close()
		out, in := map[string]int64{}, map[string]int64{}
		touch := map[string]int64{}
		for _, m := range ms {
			out[m.t+"\x00"+m.src] += m.u
			in[m.t+"\x00"+m.dst] += m.u
			touch[m.t+"\x00"+m.src]++
			touch[m.t+"\x00"+m.dst]++
		}
		for _, a := range as {
			key := a.t + "\x00" + a.n
			opening := a.b + out[key] - in[key]
			if opening < 0 || opening > cap {
				return fmt.Errorf("invalid legacy inferred opening")
			}
			_, e = tx.Exec("INSERT INTO accounts VALUES(?,?,?,?,?)", a.t, a.n, a.b, 0, 1+touch[key])
			if e != nil {
				return e
			}
			id := fmt.Sprintf("legacy-opening-%s-%s", a.t, a.n)
			_, e = tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'opening',?,0,?)", a.t, a.n, opening, id)
			if e != nil {
				return e
			}
		}
		for _, m := range ms {
			id := fmt.Sprintf("legacy-%d", m.id)
			_, e = tx.Exec("INSERT INTO transfers VALUES(?,?,?,?,?,0,?)", m.t, id, m.src, m.dst, m.u, m.id)
			if e != nil {
				return e
			}
			for i, a := range []string{m.src, m.dst} {
				d := m.u
				if i == 0 {
					d = -d
				}
				_, e = tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?, 'transfer',?,0,?,?)", m.t, a, d, id, m.id)
				if e != nil {
					return e
				}
			}
		}
	}
	_, e = tx.Exec("PRAGMA user_version=2")
	if e != nil {
		return e
	}
	return tx.Commit()
}

var nameRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type failure struct {
	status int
	code   string
}

func (f failure) Error() string { return f.code }

func fail(status int, code string) error { return failure{status, code} }
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" && r.Method == "GET" {
		var x int
		if e := s.DB.QueryRow("SELECT 1").Scan(&x); e != nil {
			writeErr(w, 500, "invalid")
			return
		}
		write(w, 200, map[string]bool{"ok": true})
		return
	}
	t := r.Header.Get("X-Tenant")
	if !nameRE.MatchString(t) {
		writeErr(w, 400, "invalid")
		return
	}
	if r.Method == "GET" {
		switch {
		case r.URL.Path == "/entries":
			s.entries(w, r, t)
			return
		case r.URL.Path == "/summary":
			s.summary(w, r, t)
			return
		case strings.HasPrefix(r.URL.Path, "/accounts/"):
			n := strings.TrimPrefix(r.URL.Path, "/accounts/")
			if strings.Contains(n, "/") || !nameRE.MatchString(n) {
				writeErr(w, 404, "not_found")
				return
			}
			a, e := getAccount(s.DB, t, n)
			if e != nil {
				writeError(w, e)
				return
			}
			write(w, 200, map[string]any{"account": a})
			return
		}
	}
	if r.Method != "POST" {
		writeErr(w, 404, "not_found")
		return
	}
	key := r.Header.Get("Idempotency-Key")
	if !keyRE.MatchString(key) {
		writeErr(w, 400, "invalid")
		return
	}
	body, e := readObject(r)
	if e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	canonical, _ := json.Marshal(body)
	tx, e := s.DB.Begin()
	if e != nil {
		writeErr(w, 500, "invalid")
		return
	}
	defer tx.Rollback()
	var oldPath, oldBody, oldResult string
	var oldStatus int
	e = tx.QueryRow("SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?", t, key).Scan(&oldPath, &oldBody, &oldStatus, &oldResult)
	if e == nil {
		if oldPath != r.URL.Path || oldBody != string(canonical) {
			writeErr(w, 409, "idempotency_conflict")
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(oldStatus)
		io.WriteString(w, oldResult)
		return
	} else if e != sql.ErrNoRows {
		writeErr(w, 500, "invalid")
		return
	}
	status, result, e := s.mutate(tx, t, r.URL.Path, body)
	if e != nil {
		writeError(w, e)
		return
	}
	encoded, _ := json.Marshal(result)
	if _, e = tx.Exec("INSERT INTO idempotency VALUES(?,?,?,?,?,?)", t, key, r.URL.Path, string(canonical), status, string(encoded)); e != nil {
		writeError(w, e)
		return
	}
	if e = tx.Commit(); e != nil {
		writeError(w, e)
		return
	}
	write(w, status, result)
}
func readObject(r *http.Request) (map[string]json.RawMessage, error) {
	if r.Body == nil {
		return nil, errors.New("body")
	}
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	var m map[string]json.RawMessage
	if e := d.Decode(&m); e != nil || m == nil {
		return nil, errors.New("json")
	}
	var extra any
	if e := d.Decode(&extra); e != io.EOF {
		return nil, errors.New("trailing")
	}
	return m, nil
}
func get[T any](m map[string]json.RawMessage, k string, required bool) (T, bool, error) {
	var z T
	b, ok := m[k]
	if !ok {
		if required {
			return z, false, errors.New("missing")
		}
		return z, false, nil
	}
	e := json.Unmarshal(b, &z)
	return z, true, e
}
func validName(s string) bool { return nameRE.MatchString(s) }
func (s *Server) mutate(tx *sql.Tx, t, path string, m map[string]json.RawMessage) (int, any, error) {
	allowed := map[string][]string{"/accounts": {"name", "opening"}, "/transfers": {"from", "to", "amount", "from_version", "to_version"}, "/batches": {"transfers"}, "/holds": {"account", "amount", "version"}}
	fields, known := allowed[path]
	if !known {
		if !(strings.HasPrefix(path, "/holds/") && strings.HasSuffix(path, "/release")) && !(strings.HasPrefix(path, "/holds/") && strings.HasSuffix(path, "/capture")) && !(strings.HasPrefix(path, "/transfers/") && strings.HasSuffix(path, "/reverse")) {
			return 0, nil, fail(404, "not_found")
		}
		if strings.HasSuffix(path, "/release") {
			fields = []string{"version"}
		} else if strings.HasSuffix(path, "/capture") {
			fields = []string{"to", "from_version", "to_version"}
		} else {
			fields = []string{"from_version", "to_version"}
		}
	}
	for k := range m {
		ok := false
		for _, f := range fields {
			if k == f {
				ok = true
			}
		}
		if !ok {
			return 0, nil, fail(400, "invalid")
		}
	}
	switch {
	case path == "/accounts":
		n, _, e := get[string](m, "name", true)
		if e != nil || !validName(n) {
			return 0, nil, fail(400, "invalid")
		}
		op, _, e := get[int64](m, "opening", true)
		if e != nil || op < 0 || op > 1e9 {
			return 0, nil, fail(400, "invalid")
		}
		_, e = tx.Exec("INSERT INTO accounts VALUES(?,?,?,0,1)", t, n, op)
		if e != nil {
			if strings.Contains(e.Error(), "UNIQUE") {
				return 0, nil, fail(409, "exists")
			}
			return 0, nil, e
		}
		id := s.id("o")
		tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'opening',?,0,?)", t, n, op, id)
		a, _ := getAccount(tx, t, n)
		return 201, map[string]any{"account": a}, nil
	case path == "/transfers":
		req, e := parseTransfer(m)
		if e != nil {
			return 0, nil, e
		}
		obj, as, e := s.transfer(tx, t, req, "transfer")
		if e != nil {
			return 0, nil, e
		}
		return 201, map[string]any{"transfer": obj, "accounts": as}, nil
	case path == "/batches":
		raw, ok := m["transfers"]
		if !ok {
			return 0, nil, fail(400, "invalid")
		}
		var list []json.RawMessage
		if json.Unmarshal(raw, &list) != nil || len(list) < 1 || len(list) > 20 {
			return 0, nil, fail(400, "invalid")
		}
		objs := []any{}
		touched := map[string]bool{}
		for _, b := range list {
			var mm map[string]json.RawMessage
			if json.Unmarshal(b, &mm) != nil {
				return 0, nil, fail(400, "invalid")
			}
			q, e := parseTransfer(mm)
			if e != nil {
				return 0, nil, e
			}
			o, _, e := s.transfer(tx, t, q, "transfer")
			if e != nil {
				return 0, nil, e
			}
			objs = append(objs, o)
			touched[q.from] = true
			touched[q.to] = true
		}
		names := keys(touched)
		as := []any{}
		for _, n := range names {
			a, _ := getAccount(tx, t, n)
			as = append(as, a)
		}
		return 201, map[string]any{"transfers": objs, "accounts": as}, nil
	case path == "/holds":
		n, _, e := get[string](m, "account", true)
		if e != nil || !validName(n) {
			return 0, nil, fail(400, "invalid")
		}
		amt, _, e := get[int64](m, "amount", true)
		if e != nil || amt < 1 || amt > 1e9 {
			return 0, nil, fail(400, "invalid")
		}
		ver, has, e := version(m, "version")
		if e != nil {
			return 0, nil, e
		}
		a, e := load(tx, t, n)
		if e != nil {
			return 0, nil, e
		}
		if has && ver != a.Version {
			return 0, nil, fail(409, "version_conflict")
		}
		if a.Balance-a.Reserved < amt {
			return 0, nil, fail(409, "insufficient")
		}
		id := s.id("h")
		tx.Exec("UPDATE accounts SET reserved=reserved+?,version=version+1 WHERE tenant=? AND name=?", amt, t, n)
		tx.Exec("INSERT INTO holds VALUES(?,?,?,?, 'active')", t, id, n, amt)
		tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'hold',0,?,?)", t, n, amt, id)
		a, _ = getAccount(tx, t, n)
		return 201, map[string]any{"hold": hold{id, n, amt, "active"}, "account": a}, nil
	case strings.HasPrefix(path, "/holds/") && strings.HasSuffix(path, "/release"):
		id := strings.TrimSuffix(strings.TrimPrefix(path, "/holds/"), "/release")
		if id == "" || strings.Contains(id, "/") {
			return 0, nil, fail(404, "not_found")
		}
		return s.release(tx, t, id, m)
	case strings.HasPrefix(path, "/holds/") && strings.HasSuffix(path, "/capture"):
		id := strings.TrimSuffix(strings.TrimPrefix(path, "/holds/"), "/capture")
		if id == "" || strings.Contains(id, "/") {
			return 0, nil, fail(404, "not_found")
		}
		return s.capture(tx, t, id, m)
	case strings.HasPrefix(path, "/transfers/") && strings.HasSuffix(path, "/reverse"):
		id := strings.TrimSuffix(strings.TrimPrefix(path, "/transfers/"), "/reverse")
		if id == "" || strings.Contains(id, "/") {
			return 0, nil, fail(404, "not_found")
		}
		return s.reverse(tx, t, id, m)
	default:
		return 0, nil, fail(404, "not_found")
	}
}
func (s *Server) id(p string) string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%s_%d_%d", p, time.Now().UnixNano(), s.ids.Add(1))
	}
	return p + "_" + hex.EncodeToString(b)
}

type Account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}
type transferReq struct {
	from, to       string
	amount, fv, tv int64
	hasF, hasT     bool
}
type transferObj struct {
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

func parseTransfer(m map[string]json.RawMessage) (transferReq, error) {
	var q transferReq
	for k := range m {
		if k != "from" && k != "to" && k != "amount" && k != "from_version" && k != "to_version" {
			return q, fail(400, "invalid")
		}
	}
	var e error
	q.from, _, e = get[string](m, "from", true)
	if e != nil {
		return q, fail(400, "invalid")
	}
	q.to, _, e = get[string](m, "to", true)
	if e != nil {
		return q, fail(400, "invalid")
	}
	q.amount, _, e = get[int64](m, "amount", true)
	if e != nil || q.amount < 1 || q.amount > 1e9 || !validName(q.from) || !validName(q.to) || q.from == q.to {
		return q, fail(400, "invalid")
	}
	q.fv, q.hasF, e = version(m, "from_version")
	if e != nil {
		return q, e
	}
	q.tv, q.hasT, e = version(m, "to_version")
	return q, e
}
func version(m map[string]json.RawMessage, k string) (int64, bool, error) {
	v, ok, e := get[int64](m, k, false)
	if e != nil || ok && v <= 0 {
		return 0, false, fail(400, "invalid")
	}
	return v, ok, nil
}
func load(tx *sql.Tx, t, n string) (Account, error) {
	var a Account
	e := tx.QueryRow("SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?", t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	if e == sql.ErrNoRows {
		return a, fail(404, "not_found")
	}
	a.Available = a.Balance - a.Reserved
	return a, e
}
func getAccount(q interface{ QueryRow(string, ...any) *sql.Row }, t, n string) (Account, error) {
	var a Account
	e := q.QueryRow("SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?", t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	a.Available = a.Balance - a.Reserved
	return a, e
}
func (s *Server) transfer(tx *sql.Tx, t string, q transferReq, kind string) (transferObj, []any, error) {
	a, e := load(tx, t, q.from)
	if e != nil {
		return transferObj{}, nil, e
	}
	b, e := load(tx, t, q.to)
	if e != nil {
		return transferObj{}, nil, e
	}
	if q.hasF && q.fv != a.Version || q.hasT && q.tv != b.Version {
		return transferObj{}, nil, fail(409, "version_conflict")
	}
	if a.Available < q.amount {
		return transferObj{}, nil, fail(409, "insufficient")
	}
	if b.Balance > cap-q.amount {
		return transferObj{}, nil, fail(400, "invalid")
	}
	id := s.id("t")
	tx.Exec("INSERT INTO transfers VALUES(?,?,?,?,?,0,NULL)", t, id, q.from, q.to, q.amount)
	tx.Exec("UPDATE accounts SET balance=balance-?,version=version+1 WHERE tenant=? AND name=?", q.amount, t, q.from)
	tx.Exec("UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?", q.amount, t, q.to)
	for i, n := range []string{q.from, q.to} {
		d := q.amount
		if i == 0 {
			d = -d
		}
		tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?,?, ?,0,?)", t, n, kind, d, id)
	}
	a, _ = getAccount(tx, t, q.from)
	b, _ = getAccount(tx, t, q.to)
	return transferObj{id, q.from, q.to, q.amount, false, nil}, []any{a, b}, nil
}
func (s *Server) release(tx *sql.Tx, t, id string, m map[string]json.RawMessage) (int, any, error) {
	var h hold
	e := tx.QueryRow("SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?", t, id).Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	if e == sql.ErrNoRows {
		return 0, nil, fail(404, "not_found")
	}
	if e != nil {
		return 0, nil, e
	}
	if h.State != "active" {
		return 0, nil, fail(409, "terminal")
	}
	v, has, e := version(m, "version")
	if e != nil {
		return 0, nil, e
	}
	a, e := load(tx, t, h.Account)
	if e != nil {
		return 0, nil, e
	}
	if has && v != a.Version {
		return 0, nil, fail(409, "version_conflict")
	}
	tx.Exec("UPDATE accounts SET reserved=reserved-?,version=version+1 WHERE tenant=? AND name=?", h.Amount, t, h.Account)
	tx.Exec("UPDATE holds SET state='released' WHERE tenant=? AND id=?", t, id)
	tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'release',0,?,?)", t, h.Account, -h.Amount, id)
	h.State = "released"
	a, _ = getAccount(tx, t, h.Account)
	return 200, map[string]any{"hold": h, "account": a}, nil
}
func (s *Server) capture(tx *sql.Tx, t, id string, m map[string]json.RawMessage) (int, any, error) {
	var h hold
	e := tx.QueryRow("SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?", t, id).Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	if e == sql.ErrNoRows {
		return 0, nil, fail(404, "not_found")
	}
	if e != nil {
		return 0, nil, e
	}
	if h.State != "active" {
		return 0, nil, fail(409, "terminal")
	}
	to, _, e := get[string](m, "to", true)
	if e != nil || !validName(to) || to == h.Account {
		return 0, nil, fail(400, "invalid")
	}
	fv, fh, e := version(m, "from_version")
	if e != nil {
		return 0, nil, e
	}
	tv, th, e := version(m, "to_version")
	if e != nil {
		return 0, nil, e
	}
	a, e := load(tx, t, h.Account)
	if e != nil {
		return 0, nil, e
	}
	b, e := load(tx, t, to)
	if e != nil {
		return 0, nil, e
	}
	if fh && fv != a.Version || th && tv != b.Version {
		return 0, nil, fail(409, "version_conflict")
	}
	if b.Balance > cap-h.Amount {
		return 0, nil, fail(400, "invalid")
	}
	tid := s.id("t")
	tx.Exec("INSERT INTO transfers VALUES(?,?,?,?,?,0,NULL)", t, tid, h.Account, to, h.Amount)
	tx.Exec("UPDATE accounts SET balance=balance-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND name=?", h.Amount, h.Amount, t, h.Account)
	tx.Exec("UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?", h.Amount, t, to)
	tx.Exec("UPDATE holds SET state='captured' WHERE tenant=? AND id=?", t, id)
	for i, n := range []string{h.Account, to} {
		d := h.Amount
		if i == 0 {
			d = -d
		}
		rd := int64(0)
		if i == 0 {
			rd = -h.Amount
		}
		tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'capture',?,?,?)", t, n, d, rd, tid)
	}
	h.State = "captured"
	a, _ = getAccount(tx, t, h.Account)
	b, _ = getAccount(tx, t, to)
	tr := transferObj{tid, h.Account, to, h.Amount, false, nil}
	return 200, map[string]any{"hold": h, "transfer": tr, "accounts": []any{a, b}}, nil
}
func (s *Server) reverse(tx *sql.Tx, t, id string, m map[string]json.RawMessage) (int, any, error) {
	var tr transferObj
	e := tx.QueryRow("SELECT id,src,dst,amount,reversed,legacy_id FROM transfers WHERE tenant=? AND id=?", t, id).Scan(&tr.ID, &tr.From, &tr.To, &tr.Amount, &tr.Reversed, &tr.LegacyID)
	if e == sql.ErrNoRows {
		return 0, nil, fail(404, "not_found")
	}
	if e != nil {
		return 0, nil, e
	}
	if tr.Reversed {
		return 0, nil, fail(409, "terminal")
	}
	fv, fh, e := version(m, "from_version")
	if e != nil {
		return 0, nil, e
	}
	tv, th, e := version(m, "to_version")
	if e != nil {
		return 0, nil, e
	}
	src, e := load(tx, t, tr.From)
	if e != nil {
		return 0, nil, e
	}
	dst, e := load(tx, t, tr.To)
	if e != nil {
		return 0, nil, e
	}
	if fh && fv != src.Version || th && tv != dst.Version {
		return 0, nil, fail(409, "version_conflict")
	}
	if dst.Available < tr.Amount {
		return 0, nil, fail(409, "insufficient")
	}
	if src.Balance > cap-tr.Amount {
		return 0, nil, fail(400, "invalid")
	}
	rid := s.id("t")
	tx.Exec("UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?", t, id)
	tx.Exec("INSERT INTO transfers VALUES(?,?,?,?,?,0,NULL)", t, rid, tr.To, tr.From, tr.Amount)
	tx.Exec("UPDATE accounts SET balance=balance-?,version=version+1 WHERE tenant=? AND name=?", tr.Amount, t, tr.To)
	tx.Exec("UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?", tr.Amount, t, tr.From)
	for i, n := range []string{tr.To, tr.From} {
		d := tr.Amount
		if i == 0 {
			d = -d
		}
		tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?, 'reversal',?,0,?)", t, n, d, rid)
	}
	src, _ = getAccount(tx, t, tr.From)
	dst, _ = getAccount(tx, t, tr.To)
	return 200, map[string]any{"transfer": tr, "reversal": transferObj{rid, tr.To, tr.From, tr.Amount, false, nil}, "accounts": []any{src, dst}}, nil
}
func keys(m map[string]bool) []string {
	a := []string{}
	for k := range m {
		a = append(a, k)
	}
	sort.Strings(a)
	return a
}
func write(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
func writeErr(w http.ResponseWriter, status int, code string) {
	write(w, status, map[string]any{"error": map[string]string{"code": code}})
}
func writeError(w http.ResponseWriter, e error) {
	var f failure
	if errors.As(e, &f) {
		writeErr(w, f.status, f.code)
		return
	}
	writeErr(w, 500, "invalid")
}
func (s *Server) entries(w http.ResponseWriter, r *http.Request, t string) {
	q, e := query(r, "after", "limit", "snapshot")
	if e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	after := int64(0)
	limit := int64(50)
	if x := first(q, "after"); x != "" {
		after, e = strconv.ParseInt(x, 10, 64)
		if e != nil || after < 0 {
			writeErr(w, 400, "invalid")
			return
		}
	}
	if x := first(q, "limit"); x != "" {
		limit, e = strconv.ParseInt(x, 10, 64)
		if e != nil || limit < 1 || limit > 100 {
			writeErr(w, 400, "invalid")
			return
		}
	}
	max, e := maxSeq(s.DB, t)
	if e != nil {
		writeErr(w, 500, "invalid")
		return
	}
	snap, ok := q["snapshot"]
	sn := max
	if ok {
		sn, e = strconv.ParseInt(snap[0], 10, 64)
		if e != nil || sn < 0 || sn > max {
			writeErr(w, 400, "invalid")
			return
		}
	}
	if after > sn {
		writeErr(w, 400, "invalid")
		return
	}
	rows, e := s.DB.Query("SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?", t, after, sn, limit)
	if e != nil {
		writeErr(w, 500, "invalid")
		return
	}
	defer rows.Close()
	a := []any{}
	last := after
	for rows.Next() {
		var x struct {
			Seq           int64  `json:"seq"`
			Account       string `json:"account"`
			Kind          string `json:"kind"`
			BalanceDelta  int64  `json:"balance_delta"`
			ReservedDelta int64  `json:"reserved_delta"`
			OperationID   string `json:"operation_id"`
			LegacyID      *int64 `json:"legacy_id,omitempty"`
		}
		rows.Scan(&x.Seq, &x.Account, &x.Kind, &x.BalanceDelta, &x.ReservedDelta, &x.OperationID, &x.LegacyID)
		a = append(a, x)
		last = x.Seq
	}
	var more int
	s.DB.QueryRow("SELECT count(*) FROM entries WHERE tenant=? AND seq>? AND seq<=?", t, last, sn).Scan(&more)
	write(w, 200, map[string]any{"entries": a, "snapshot": sn, "next_after": last, "has_more": more > 0})
}
func first(q map[string][]string, k string) string {
	if a := q[k]; len(a) > 0 {
		return a[0]
	}
	return ""
}
func query(r *http.Request, keys ...string) (map[string][]string, error) {
	v := r.URL.Query()
	out := map[string][]string{}
	for k, a := range v {
		valid := false
		for _, x := range keys {
			if x == k {
				valid = true
			}
		}
		if !valid || len(a) != 1 {
			return nil, errors.New("query")
		}
		out[k] = a
	}
	return out, nil
}
func maxSeq(db *sql.DB, t string) (int64, error) {
	var n sql.NullInt64
	e := db.QueryRow("SELECT max(seq) FROM entries WHERE tenant=?", t).Scan(&n)
	return n.Int64, e
}
func (s *Server) summary(w http.ResponseWriter, r *http.Request, t string) {
	q, e := query(r, "snapshot")
	if e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	max, e := maxSeq(s.DB, t)
	if e != nil {
		writeErr(w, 500, "invalid")
		return
	}
	snap := max
	if x, ok := q["snapshot"]; ok {
		snap, e = strconv.ParseInt(x[0], 10, 64)
		if e != nil || snap < 0 || snap > max {
			writeErr(w, 400, "invalid")
			return
		}
	}
	rows, e := s.DB.Query("SELECT account,sum(balance_delta),sum(reserved_delta) FROM entries WHERE tenant=? AND seq<=? GROUP BY account ORDER BY account", t, snap)
	if e != nil {
		writeErr(w, 500, "invalid")
		return
	}
	defer rows.Close()
	type item struct {
		Name      string `json:"name"`
		Balance   int64  `json:"balance"`
		Reserved  int64  `json:"reserved"`
		Available int64  `json:"available"`
	}
	a := []item{}
	var bal, res int64
	for rows.Next() {
		var x item
		rows.Scan(&x.Name, &x.Balance, &x.Reserved)
		x.Available = x.Balance - x.Reserved
		bal += x.Balance
		res += x.Reserved
		a = append(a, x)
	}
	var count int
	s.DB.QueryRow("SELECT count(*) FROM entries WHERE tenant=? AND seq<=?", t, snap).Scan(&count)
	write(w, 200, map[string]any{"snapshot": snap, "accounts": a, "totals": map[string]int64{"balance": bal, "reserved": res, "available": bal - res}, "entry_count": count})
}
