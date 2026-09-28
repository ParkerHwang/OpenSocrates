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
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"auditledger/internal/platform"
)

const capUnits int64 = 9000000000000000

var nameRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)
var errInvalid = apiError{400, "invalid"}
var errMissing = apiError{404, "not_found"}

type apiError struct {
	status int
	code   string
}

func (e apiError) Error() string { return e.code }

type Account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}
type Hold struct {
	ID      string `json:"id"`
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	State   string `json:"state"`
}
type Transfer struct {
	ID       string `json:"id"`
	From     string `json:"from"`
	To       string `json:"to"`
	Amount   int64  `json:"amount"`
	Reversed bool   `json:"reversed"`
	LegacyID *int64 `json:"legacy_id,omitempty"`
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
type DB struct{ *sql.DB }

func Open(path string) (*DB, error) {
	db, e := platform.Open(path)
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	if _, e = db.Exec(`PRAGMA busy_timeout=15000`); e != nil {
		db.Close()
		return nil, e
	}
	l := &DB{db}
	if e = l.migrate(); e != nil {
		db.Close()
		return nil, e
	}
	return l, nil
}
func (l *DB) writeConn(ctx context.Context) (*sql.Conn, error) {
	c, e := l.Conn(ctx)
	if e != nil {
		return nil, e
	}
	if _, e = c.ExecContext(ctx, "BEGIN IMMEDIATE"); e != nil {
		c.Close()
		return nil, e
	}
	return c, nil
}
func rollback(c *sql.Conn) { c.ExecContext(context.Background(), "ROLLBACK"); c.Close() }
func commit(c *sql.Conn) error {
	_, e := c.ExecContext(context.Background(), "COMMIT")
	c.Close()
	return e
}
func (l *DB) migrate() error {
	c, e := l.writeConn(context.Background())
	if e != nil {
		return e
	}
	defer rollback(c)
	var v int
	if e = c.QueryRowContext(context.Background(), "PRAGMA user_version").Scan(&v); e != nil {
		return e
	}
	if v == 2 {
		return commit(c)
	}
	if v != 0 && v != 1 {
		return fmt.Errorf("unsupported database version %d", v)
	}
	schema := []string{
		`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name))`,
		`CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL DEFAULT 0,is_reversal INTEGER NOT NULL DEFAULT 0,legacy_id INTEGER,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS entries(tenant TEXT NOT NULL,seq INTEGER NOT NULL,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,seq))`,
		`CREATE TABLE IF NOT EXISTS retries(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body TEXT NOT NULL,status INTEGER NOT NULL,result BLOB NOT NULL,PRIMARY KEY(tenant,key))`,
	}
	for _, s := range schema {
		if _, e = c.ExecContext(context.Background(), s); e != nil {
			return e
		}
	}
	if v == 1 {
		if e = migrateLegacy(c); e != nil {
			return e
		}
	}
	if _, e = c.ExecContext(context.Background(), "PRAGMA user_version=2"); e != nil {
		return e
	}
	return commit(c)
}
func migrateLegacy(c *sql.Conn) error {
	type oldAcc struct {
		tenant, name            string
		final, opening, version int64
	}
	rows, e := c.QueryContext(context.Background(), `SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name`)
	if e != nil {
		return e
	}
	acc := map[string]*oldAcc{}
	ordered := []*oldAcc{}
	for rows.Next() {
		a := new(oldAcc)
		if e = rows.Scan(&a.tenant, &a.name, &a.final); e != nil {
			rows.Close()
			return e
		}
		a.opening = a.final
		a.version = 1
		acc[a.tenant+"\x00"+a.name] = a
		ordered = append(ordered, a)
	}
	e = rows.Err()
	rows.Close()
	if e != nil {
		return e
	}
	type movement struct {
		id               int64
		tenant, from, to string
		units            int64
	}
	ms := []movement{}
	rows, e = c.QueryContext(context.Background(), `SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id`)
	if e != nil {
		return e
	}
	for rows.Next() {
		var m movement
		if e = rows.Scan(&m.id, &m.tenant, &m.from, &m.to, &m.units); e != nil {
			rows.Close()
			return e
		}
		f, t := acc[m.tenant+"\x00"+m.from], acc[m.tenant+"\x00"+m.to]
		if f == nil || t == nil || m.units < 1 || m.units > 1000000000 || f == t {
			rows.Close()
			return fmt.Errorf("invalid legacy movement %d", m.id)
		}
		f.opening += m.units
		t.opening -= m.units
		f.version++
		t.version++
		ms = append(ms, m)
	}
	e = rows.Err()
	rows.Close()
	if e != nil {
		return e
	}
	seq := map[string]int64{}
	for _, a := range ordered {
		if a.opening < 0 || a.opening > capUnits || a.final < 0 || a.final > capUnits {
			return fmt.Errorf("invalid legacy balance")
		}
		_, e = c.ExecContext(context.Background(), `INSERT INTO accounts VALUES(?,?,?,?,?)`, a.tenant, a.name, a.final, 0, a.version)
		if e != nil {
			return e
		}
		seq[a.tenant]++
		_, e = c.ExecContext(context.Background(), `INSERT INTO entries VALUES(?,?,?,?,?,?,?,NULL)`, a.tenant, seq[a.tenant], a.name, "opening", a.opening, 0, newID())
		if e != nil {
			return e
		}
	}
	for _, m := range ms {
		id := newID()
		_, e = c.ExecContext(context.Background(), `INSERT INTO transfers(tenant,id,source,target,amount,legacy_id) VALUES(?,?,?,?,?,?)`, m.tenant, id, m.from, m.to, m.units, m.id)
		if e != nil {
			return e
		}
		for _, x := range []struct {
			name  string
			delta int64
		}{{m.from, -m.units}, {m.to, m.units}} {
			seq[m.tenant]++
			_, e = c.ExecContext(context.Background(), `INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)`, m.tenant, seq[m.tenant], x.name, "transfer", x.delta, 0, id, m.id)
			if e != nil {
				return e
			}
		}
	}
	return nil
}
func newID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}
func validName(s string) bool { return nameRE.MatchString(s) }
func jsonOut(w http.ResponseWriter, status int, v any) {
	b, e := json.Marshal(v)
	if e != nil {
		http.Error(w, "internal error", 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	w.Write(b)
}
func fail(w http.ResponseWriter, e error) {
	var a apiError
	if errors.As(e, &a) {
		jsonOut(w, a.status, map[string]any{"error": map[string]string{"code": a.code}})
	} else {
		jsonOut(w, 500, map[string]any{"error": map[string]string{"code": "internal"}})
	}
}
func bad(code string) error { return apiError{409, code} }
func parseBody(r *http.Request) (map[string]json.RawMessage, string, error) {
	d := json.NewDecoder(r.Body)
	var m map[string]json.RawMessage
	if e := d.Decode(&m); e != nil || m == nil {
		return nil, "", errInvalid
	}
	var more any
	if e := d.Decode(&more); e != io.EOF {
		return nil, "", errInvalid
	}
	// Decode again with json.Number so nested object key order and whitespace do
	// not change retry identity while large integer values remain exact.
	var normalized any
	nd := json.NewDecoder(strings.NewReader(mustJSON(m)))
	nd.UseNumber()
	if e := nd.Decode(&normalized); e != nil {
		return nil, "", errInvalid
	}
	b, e := json.Marshal(normalized)
	if e != nil {
		return nil, "", errInvalid
	}
	return m, string(b), nil
}
func mustJSON(v any) string { b, _ := json.Marshal(v); return string(b) }
func fields(m map[string]json.RawMessage, allowed ...string) error {
	a := map[string]bool{}
	for _, x := range allowed {
		a[x] = true
	}
	for k := range m {
		if !a[k] {
			return errInvalid
		}
	}
	return nil
}
func str(m map[string]json.RawMessage, k string, required bool) (string, error) {
	v, ok := m[k]
	if !ok {
		if required {
			return "", errInvalid
		}
		return "", nil
	}
	var s string
	if e := json.Unmarshal(v, &s); e != nil || !validName(s) {
		return "", errInvalid
	}
	return s, nil
}
func amount(m map[string]json.RawMessage, k string, min, max int64) (int64, error) {
	v, ok := m[k]
	if !ok {
		return 0, errInvalid
	}
	s := string(v)
	if strings.ContainsAny(s, ".eE") || s == "null" {
		return 0, errInvalid
	}
	n, e := strconv.ParseInt(s, 10, 64)
	if e != nil || n < min || n > max {
		return 0, errInvalid
	}
	return n, nil
}
func version(m map[string]json.RawMessage, k string) (*int64, error) {
	if _, ok := m[k]; !ok {
		return nil, nil
	}
	n, e := amount(m, k, 1, 1<<62)
	if e != nil {
		return nil, e
	}
	return &n, nil
}
func checkVersion(a Account, v *int64) error {
	if v != nil && *v != a.Version {
		return bad("version_conflict")
	}
	return nil
}
func getAccount(c *sql.Conn, t, n string) (Account, error) {
	var a Account
	e := c.QueryRowContext(context.Background(), `SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	if e == sql.ErrNoRows {
		return a, errMissing
	}
	if e != nil {
		return a, e
	}
	a.Available = a.Balance - a.Reserved
	return a, nil
}
func saveAccount(c *sql.Conn, t string, a Account) error {
	if a.Balance < 0 || a.Balance > capUnits || a.Reserved < 0 || a.Reserved > capUnits || a.Reserved > a.Balance {
		return errInvalid
	}
	a.Available = a.Balance - a.Reserved
	_, e := c.ExecContext(context.Background(), `UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?`, a.Balance, a.Reserved, a.Version, t, a.Name)
	return e
}
func appendEntry(c *sql.Conn, t, n, k string, bd, rd int64, id string, legacy *int64) error {
	var seq int64
	e := c.QueryRowContext(context.Background(), `SELECT COALESCE(MAX(seq),0)+1 FROM entries WHERE tenant=?`, t).Scan(&seq)
	if e != nil {
		return e
	}
	_, e = c.ExecContext(context.Background(), `INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)`, t, seq, n, k, bd, rd, id, legacy)
	return e
}
func transfer(c *sql.Conn, t, from, to string, n int64, fv, tv *int64, kind string, reversal bool) (Transfer, []Account, error) {
	tr := Transfer{}
	if from == to {
		return tr, nil, errInvalid
	}
	a, e := getAccount(c, t, from)
	if e != nil {
		return tr, nil, e
	}
	b, e := getAccount(c, t, to)
	if e != nil {
		return tr, nil, e
	}
	if e = checkVersion(a, fv); e != nil {
		return tr, nil, e
	}
	if e = checkVersion(b, tv); e != nil {
		return tr, nil, e
	}
	if a.Available < n {
		return tr, nil, bad("insufficient")
	}
	if b.Balance > capUnits-n {
		return tr, nil, errInvalid
	}
	a.Balance -= n
	b.Balance += n
	a.Version++
	b.Version++
	a.Available = a.Balance - a.Reserved
	b.Available = b.Balance - b.Reserved
	if e = saveAccount(c, t, a); e != nil {
		return tr, nil, e
	}
	if e = saveAccount(c, t, b); e != nil {
		return tr, nil, e
	}
	tr = Transfer{ID: newID(), From: from, To: to, Amount: n}
	rv := 0
	if reversal {
		rv = 1
	}
	_, e = c.ExecContext(context.Background(), `INSERT INTO transfers(tenant,id,source,target,amount,is_reversal) VALUES(?,?,?,?,?,?)`, t, tr.ID, from, to, n, rv)
	if e != nil {
		return tr, nil, e
	}
	if e = appendEntry(c, t, from, kind, -n, 0, tr.ID, nil); e != nil {
		return tr, nil, e
	}
	if e = appendEntry(c, t, to, kind, n, 0, tr.ID, nil); e != nil {
		return tr, nil, e
	}
	return tr, []Account{a, b}, nil
}
func getHold(c *sql.Conn, t, id string) (Hold, error) {
	var h Hold
	e := c.QueryRowContext(context.Background(), `SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?`, t, id).Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	if e == sql.ErrNoRows {
		return h, errMissing
	}
	return h, e
}
func getTransfer(c *sql.Conn, t, id string) (Transfer, bool, error) {
	var tr Transfer
	var rev, ir int
	var lid sql.NullInt64
	e := c.QueryRowContext(context.Background(), `SELECT id,source,target,amount,reversed,is_reversal,legacy_id FROM transfers WHERE tenant=? AND id=?`, t, id).Scan(&tr.ID, &tr.From, &tr.To, &tr.Amount, &rev, &ir, &lid)
	if e == sql.ErrNoRows {
		return tr, false, errMissing
	}
	tr.Reversed = rev != 0
	if lid.Valid {
		tr.LegacyID = &lid.Int64
	}
	return tr, ir != 0, e
}
func validateTransfer(m map[string]json.RawMessage) (string, string, int64, *int64, *int64, error) {
	if e := fields(m, "from", "to", "amount", "from_version", "to_version"); e != nil {
		return "", "", 0, nil, nil, e
	}
	f, e := str(m, "from", true)
	if e != nil {
		return "", "", 0, nil, nil, e
	}
	t, e := str(m, "to", true)
	if e != nil {
		return "", "", 0, nil, nil, e
	}
	if f == t {
		return "", "", 0, nil, nil, errInvalid
	}
	n, e := amount(m, "amount", 1, 1000000000)
	if e != nil {
		return "", "", 0, nil, nil, e
	}
	fv, e := version(m, "from_version")
	if e != nil {
		return "", "", 0, nil, nil, e
	}
	tv, e := version(m, "to_version")
	return f, t, n, fv, tv, e
}
func (l *DB) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" && r.URL.Path == "/health" {
		jsonOut(w, 200, map[string]bool{"ok": true})
		return
	}
	t := r.Header.Get("X-Tenant")
	if !validName(t) {
		fail(w, errInvalid)
		return
	}
	if r.Method == "GET" {
		l.read(w, r, t)
		return
	}
	if r.Method != "POST" {
		fail(w, errMissing)
		return
	}
	path := r.URL.Path
	parts := strings.Split(strings.Trim(path, "/"), "/")
	route := ""
	switch {
	case path == "/accounts":
		route = "account"
	case path == "/transfers":
		route = "transfer"
	case path == "/batches":
		route = "batch"
	case path == "/holds":
		route = "hold"
	case len(parts) == 3 && parts[0] == "holds" && parts[2] == "capture" && validName(parts[1]):
		route = "capture"
	case len(parts) == 3 && parts[0] == "holds" && parts[2] == "release" && validName(parts[1]):
		route = "release"
	case len(parts) == 3 && parts[0] == "transfers" && parts[2] == "reverse" && validName(parts[1]):
		route = "reverse"
	}
	if route == "" {
		fail(w, errMissing)
		return
	}
	key := r.Header.Get("Idempotency-Key")
	if !keyRE.MatchString(key) {
		fail(w, errInvalid)
		return
	}
	m, canon, e := parseBody(r)
	if e != nil {
		fail(w, e)
		return
	}
	// Validate the complete request before consulting durable retries.
	if e = validate(route, m); e != nil {
		fail(w, e)
		return
	}
	c, e := l.writeConn(r.Context())
	if e != nil {
		fail(w, e)
		return
	}
	defer rollback(c)
	var oldpath, oldbody string
	var status int
	var oldresult []byte
	e = c.QueryRowContext(r.Context(), `SELECT path,body,status,result FROM retries WHERE tenant=? AND key=?`, t, key).Scan(&oldpath, &oldbody, &status, &oldresult)
	if e == nil {
		if oldpath != path || oldbody != canon {
			fail(w, bad("idempotency_conflict"))
			return
		}
		if e = commit(c); e != nil {
			fail(w, e)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		w.Write(oldresult)
		return
	}
	if e != sql.ErrNoRows {
		fail(w, e)
		return
	}
	status, result, e := apply(c, t, route, parts, m)
	if e != nil {
		fail(w, e)
		return
	}
	b, e := json.Marshal(result)
	if e != nil {
		fail(w, e)
		return
	}
	_, e = c.ExecContext(r.Context(), `INSERT INTO retries VALUES(?,?,?,?,?,?)`, t, key, path, canon, status, b)
	if e != nil {
		fail(w, e)
		return
	}
	if e = commit(c); e != nil {
		fail(w, e)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	w.Write(b)
}
func validate(route string, m map[string]json.RawMessage) error {
	switch route {
	case "account":
		if e := fields(m, "name", "opening"); e != nil {
			return e
		}
		if _, e := str(m, "name", true); e != nil {
			return e
		}
		_, e := amount(m, "opening", 0, 1000000000)
		return e
	case "transfer":
		_, _, _, _, _, e := validateTransfer(m)
		return e
	case "batch":
		if e := fields(m, "transfers"); e != nil {
			return e
		}
		v, ok := m["transfers"]
		if !ok {
			return errInvalid
		}
		var list []map[string]json.RawMessage
		if e := json.Unmarshal(v, &list); e != nil || len(list) < 1 || len(list) > 20 {
			return errInvalid
		}
		for _, x := range list {
			if x == nil {
				return errInvalid
			}
			if _, _, _, _, _, e := validateTransfer(x); e != nil {
				return e
			}
		}
		return nil
	case "hold":
		if e := fields(m, "account", "amount", "version"); e != nil {
			return e
		}
		if _, e := str(m, "account", true); e != nil {
			return e
		}
		if _, e := amount(m, "amount", 1, 1000000000); e != nil {
			return e
		}
		_, e := version(m, "version")
		return e
	case "capture":
		if e := fields(m, "to", "from_version", "to_version"); e != nil {
			return e
		}
		if _, e := str(m, "to", true); e != nil {
			return e
		}
		if _, e := version(m, "from_version"); e != nil {
			return e
		}
		_, e := version(m, "to_version")
		return e
	case "release":
		if e := fields(m, "version"); e != nil {
			return e
		}
		_, e := version(m, "version")
		return e
	case "reverse":
		if e := fields(m, "from_version", "to_version"); e != nil {
			return e
		}
		if _, e := version(m, "from_version"); e != nil {
			return e
		}
		_, e := version(m, "to_version")
		return e
	}
	return errMissing
}
func apply(c *sql.Conn, t, route string, parts []string, m map[string]json.RawMessage) (int, any, error) {
	switch route {
	case "account":
		n, _ := str(m, "name", true)
		opening, _ := amount(m, "opening", 0, 1000000000)
		var exists int
		e := c.QueryRowContext(context.Background(), `SELECT 1 FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&exists)
		if e == nil {
			return 0, nil, bad("exists")
		}
		if e != sql.ErrNoRows {
			return 0, nil, e
		}
		a := Account{n, opening, 0, opening, 1}
		_, e = c.ExecContext(context.Background(), `INSERT INTO accounts VALUES(?,?,?,?,?)`, t, n, opening, 0, 1)
		if e != nil {
			return 0, nil, e
		}
		e = appendEntry(c, t, n, "opening", opening, 0, newID(), nil)
		return 201, map[string]any{"account": a}, e
	case "transfer":
		f, to, n, fv, tv, _ := validateTransfer(m)
		tr, as, e := transfer(c, t, f, to, n, fv, tv, "transfer", false)
		return 201, map[string]any{"transfer": tr, "accounts": as}, e
	case "batch":
		var list []map[string]json.RawMessage
		json.Unmarshal(m["transfers"], &list)
		trs := make([]Transfer, 0, len(list))
		names := map[string]bool{}
		for _, x := range list {
			f, to, n, fv, tv, _ := validateTransfer(x)
			tr, _, e := transfer(c, t, f, to, n, fv, tv, "transfer", false)
			if e != nil {
				return 0, nil, e
			}
			trs = append(trs, tr)
			names[f] = true
			names[to] = true
		}
		ns := make([]string, 0, len(names))
		for n := range names {
			ns = append(ns, n)
		}
		sort.Strings(ns)
		as := make([]Account, 0, len(ns))
		for _, n := range ns {
			a, e := getAccount(c, t, n)
			if e != nil {
				return 0, nil, e
			}
			as = append(as, a)
		}
		return 201, map[string]any{"transfers": trs, "accounts": as}, nil
	case "hold":
		n, _ := str(m, "account", true)
		amount, _ := amount(m, "amount", 1, 1000000000)
		v, _ := version(m, "version")
		a, e := getAccount(c, t, n)
		if e != nil {
			return 0, nil, e
		}
		if e = checkVersion(a, v); e != nil {
			return 0, nil, e
		}
		if a.Available < amount {
			return 0, nil, bad("insufficient")
		}
		a.Reserved += amount
		a.Available -= amount
		a.Version++
		if e = saveAccount(c, t, a); e != nil {
			return 0, nil, e
		}
		h := Hold{newID(), n, amount, "active"}
		_, e = c.ExecContext(context.Background(), `INSERT INTO holds VALUES(?,?,?,?,?)`, t, h.ID, n, amount, h.State)
		if e != nil {
			return 0, nil, e
		}
		e = appendEntry(c, t, n, "hold", 0, amount, h.ID, nil)
		return 201, map[string]any{"hold": h, "account": a}, e
	case "release":
		h, e := getHold(c, t, parts[1])
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
		v, _ := version(m, "version")
		if e = checkVersion(a, v); e != nil {
			return 0, nil, e
		}
		a.Reserved -= h.Amount
		a.Available += h.Amount
		a.Version++
		if e = saveAccount(c, t, a); e != nil {
			return 0, nil, e
		}
		h.State = "released"
		_, e = c.ExecContext(context.Background(), `UPDATE holds SET state=? WHERE tenant=? AND id=?`, h.State, t, h.ID)
		if e != nil {
			return 0, nil, e
		}
		e = appendEntry(c, t, a.Name, "release", 0, -h.Amount, h.ID, nil)
		return 200, map[string]any{"hold": h, "account": a}, e
	case "capture":
		h, e := getHold(c, t, parts[1])
		if e != nil {
			return 0, nil, e
		}
		if h.State != "active" {
			return 0, nil, bad("terminal")
		}
		to, _ := str(m, "to", true)
		if to == h.Account {
			return 0, nil, errInvalid
		}
		a, e := getAccount(c, t, h.Account)
		if e != nil {
			return 0, nil, e
		}
		b, e := getAccount(c, t, to)
		if e != nil {
			return 0, nil, e
		}
		fv, _ := version(m, "from_version")
		tv, _ := version(m, "to_version")
		if e = checkVersion(a, fv); e != nil {
			return 0, nil, e
		}
		if e = checkVersion(b, tv); e != nil {
			return 0, nil, e
		}
		if b.Balance > capUnits-h.Amount {
			return 0, nil, errInvalid
		}
		a.Balance -= h.Amount
		a.Reserved -= h.Amount
		a.Version++
		a.Available = a.Balance - a.Reserved
		b.Balance += h.Amount
		b.Available = b.Balance - b.Reserved
		b.Version++
		if e = saveAccount(c, t, a); e != nil {
			return 0, nil, e
		}
		if e = saveAccount(c, t, b); e != nil {
			return 0, nil, e
		}
		h.State = "captured"
		_, e = c.ExecContext(context.Background(), `UPDATE holds SET state=? WHERE tenant=? AND id=?`, h.State, t, h.ID)
		if e != nil {
			return 0, nil, e
		}
		tr := Transfer{ID: newID(), From: a.Name, To: b.Name, Amount: h.Amount}
		_, e = c.ExecContext(context.Background(), `INSERT INTO transfers(tenant,id,source,target,amount) VALUES(?,?,?,?,?)`, t, tr.ID, tr.From, tr.To, tr.Amount)
		if e != nil {
			return 0, nil, e
		}
		if e = appendEntry(c, t, a.Name, "capture", -h.Amount, -h.Amount, tr.ID, nil); e != nil {
			return 0, nil, e
		}
		e = appendEntry(c, t, b.Name, "capture", h.Amount, 0, tr.ID, nil)
		return 200, map[string]any{"hold": h, "transfer": tr, "accounts": []Account{a, b}}, e
	case "reverse":
		orig, isRev, e := getTransfer(c, t, parts[1])
		if e != nil {
			return 0, nil, e
		}
		if orig.Reversed || isRev {
			return 0, nil, bad("terminal")
		}
		fv, _ := version(m, "from_version")
		tv, _ := version(m, "to_version")
		rev, as, e := transfer(c, t, orig.To, orig.From, orig.Amount, tv, fv, "reversal", true)
		if e != nil {
			return 0, nil, e
		}
		_, e = c.ExecContext(context.Background(), `UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?`, t, orig.ID)
		if e != nil {
			return 0, nil, e
		}
		orig.Reversed = true
		return 200, map[string]any{"transfer": orig, "reversal": rev, "accounts": []Account{as[1], as[0]}}, nil
	}
	return 0, nil, errMissing
}
func queryInt(q url.Values, k string, def, min, max int64) (int64, error) {
	v, ok := q[k]
	if !ok {
		return def, nil
	}
	if len(v) != 1 || v[0] == "" {
		return 0, errInvalid
	}
	for _, r := range v[0] {
		if r < '0' || r > '9' {
			return 0, errInvalid
		}
	}
	n, e := strconv.ParseInt(v[0], 10, 64)
	if e != nil || n < min || n > max {
		return 0, errInvalid
	}
	return n, nil
}
func maxSeq(db *sql.DB, t string) (int64, error) {
	var n int64
	e := db.QueryRow(`SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?`, t).Scan(&n)
	return n, e
}
func (l *DB) read(w http.ResponseWriter, r *http.Request, t string) {
	p := r.URL.Path
	if strings.HasPrefix(p, "/accounts/") && strings.Count(p, "/") == 2 {
		n := strings.TrimPrefix(p, "/accounts/")
		if !validName(n) {
			fail(w, errMissing)
			return
		}
		var a Account
		e := l.QueryRow(`SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
		if e == sql.ErrNoRows {
			fail(w, errMissing)
			return
		}
		if e != nil {
			fail(w, e)
			return
		}
		a.Available = a.Balance - a.Reserved
		jsonOut(w, 200, map[string]any{"account": a})
		return
	}
	if p != "/entries" && p != "/summary" {
		fail(w, errMissing)
		return
	}
	q := r.URL.Query()
	for k := range q {
		if k != "snapshot" && (p != "/entries" || k != "after" && k != "limit") {
			fail(w, errInvalid)
			return
		}
	}
	current, e := maxSeq(l.DB, t)
	if e != nil {
		fail(w, e)
		return
	}
	snap, e := queryInt(q, "snapshot", current, 0, current)
	if e != nil {
		fail(w, e)
		return
	}
	if p == "/entries" {
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
		rows, e := l.Query(`SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, t, after, snap, limit+1)
		if e != nil {
			fail(w, e)
			return
		}
		es := []Entry{}
		for rows.Next() {
			var x Entry
			var lid sql.NullInt64
			if e = rows.Scan(&x.Seq, &x.Account, &x.Kind, &x.BalanceDelta, &x.ReservedDelta, &x.OperationID, &lid); e != nil {
				break
			}
			if lid.Valid {
				x.LegacyID = &lid.Int64
			}
			es = append(es, x)
		}
		if e == nil {
			e = rows.Err()
		}
		rows.Close()
		if e != nil {
			fail(w, e)
			return
		}
		more := len(es) > int(limit)
		if more {
			es = es[:limit]
		}
		next := after
		if len(es) > 0 {
			next = es[len(es)-1].Seq
		}
		jsonOut(w, 200, map[string]any{"entries": es, "snapshot": snap, "next_after": next, "has_more": more})
		return
	}
	rows, e := l.Query(`SELECT account,SUM(balance_delta),SUM(reserved_delta),MAX(CASE WHEN kind='opening' THEN 1 ELSE 0 END) FROM entries WHERE tenant=? AND seq<=? GROUP BY account HAVING MAX(CASE WHEN kind='opening' THEN 1 ELSE 0 END)=1 ORDER BY account`, t, snap)
	if e != nil {
		fail(w, e)
		return
	}
	type sumAcc struct {
		Name      string `json:"name"`
		Balance   int64  `json:"balance"`
		Reserved  int64  `json:"reserved"`
		Available int64  `json:"available"`
	}
	as := []sumAcc{}
	tot := struct {
		Balance   int64 `json:"balance"`
		Reserved  int64 `json:"reserved"`
		Available int64 `json:"available"`
	}{}
	for rows.Next() {
		var a sumAcc
		var opening int
		if e = rows.Scan(&a.Name, &a.Balance, &a.Reserved, &opening); e != nil {
			break
		}
		a.Available = a.Balance - a.Reserved
		tot.Balance += a.Balance
		tot.Reserved += a.Reserved
		tot.Available += a.Available
		as = append(as, a)
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
	e = l.QueryRow(`SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?`, t, snap).Scan(&count)
	if e != nil {
		fail(w, e)
		return
	}
	jsonOut(w, 200, map[string]any{"snapshot": snap, "accounts": as, "totals": tot, "entry_count": count})
}
