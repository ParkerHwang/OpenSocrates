package platform

import (
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
	"sync/atomic"
	"time"
)

const max int64 = 9000000000000000

var nameRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

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
type API struct{ db *sql.DB }

func Handler(db *sql.DB) http.Handler { return &API{db} }
func Migrate(db *sql.DB) error {
	for _, s := range []string{`PRAGMA journal_mode=WAL`, `PRAGMA synchronous=FULL`} {
		if _, e := db.Exec(s); e != nil {
			return e
		}
	}
	tx, e := db.Begin()
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
	if v != 1 && v != 0 {
		return fmt.Errorf("unsupported schema version %d", v)
	}
	for _, s := range []string{
		`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name))`,
		`CREATE TABLE IF NOT EXISTS entries(tenant TEXT NOT NULL,seq INTEGER PRIMARY KEY AUTOINCREMENT,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER)`,
		`CREATE INDEX IF NOT EXISTS entries_tenant_seq ON entries(tenant,seq)`,
		`CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL DEFAULT 0,reverse_id TEXT,legacy_id INTEGER,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body BLOB NOT NULL,status INTEGER NOT NULL,result BLOB NOT NULL,PRIMARY KEY(tenant,key))`} {
		if _, e = tx.Exec(s); e != nil {
			return e
		}
	}
	if v == 1 {
		if e = migrateV1(tx); e != nil {
			return e
		}
	}
	if _, e = tx.Exec("PRAGMA user_version=2"); e != nil {
		return e
	}
	return tx.Commit()
}
func migrateV1(tx *sql.Tx) error {
	type ar struct {
		t, n string
		b    int64
	}
	rows, e := tx.Query("SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name")
	if e != nil {
		return e
	}
	aa := []ar{}
	for rows.Next() {
		var x ar
		if e = rows.Scan(&x.t, &x.n, &x.b); e != nil {
			rows.Close()
			return e
		}
		aa = append(aa, x)
	}
	rows.Close()
	type mv struct {
		id      int64
		t, s, d string
		u       int64
	}
	mr, e := tx.Query("SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id")
	if e != nil {
		return e
	}
	mm := []mv{}
	for mr.Next() {
		var x mv
		if e = mr.Scan(&x.id, &x.t, &x.s, &x.d, &x.u); e != nil {
			mr.Close()
			return e
		}
		mm = append(mm, x)
	}
	mr.Close()
	out := map[string]map[string]int64{}
	in := map[string]map[string]int64{}
	touch := map[string]map[string]int64{}
	ensure := func(m map[string]map[string]int64, t string) map[string]int64 {
		if m[t] == nil {
			m[t] = map[string]int64{}
		}
		return m[t]
	}
	for _, m := range mm {
		ensure(out, m.t)[m.s] += m.u
		ensure(in, m.t)[m.d] += m.u
		ensure(touch, m.t)[m.s]++
		ensure(touch, m.t)[m.d]++
	}
	for _, x := range aa {
		opening := x.b + out[x.t][x.n] - in[x.t][x.n]
		if opening < 0 || opening > max {
			return fmt.Errorf("invalid inferred opening")
		}
		if _, e = tx.Exec("INSERT INTO accounts VALUES(?,?,?,?,?)", x.t, x.n, x.b, 0, 1+touch[x.t][x.n]); e != nil {
			return e
		}
		if e = entry(tx, x.t, x.n, "opening", opening, 0, fmt.Sprintf("legacy-open-%s", x.n), nil); e != nil {
			return e
		}
	}
	for _, m := range mm {
		id := fmt.Sprintf("legacy-%d", m.id)
		if _, e = tx.Exec("INSERT INTO transfers(tenant,id,source,target,amount,legacy_id) VALUES(?,?,?,?,?,?)", m.t, id, m.s, m.d, m.u, m.id); e != nil {
			return e
		}
		if e = entry(tx, m.t, m.s, "transfer", -m.u, 0, id, &m.id); e != nil {
			return e
		}
		if e = entry(tx, m.t, m.d, "transfer", m.u, 0, id, &m.id); e != nil {
			return e
		}
	}
	return nil
}
func entry(tx *sql.Tx, t, a, k string, b, r int64, id string, l *int64) error {
	_, e := tx.Exec("INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?)", t, a, k, b, r, id, l)
	return e
}
func (a *API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.URL.Path == "/health" && r.Method == "GET" {
		var x int
		if e := a.db.QueryRow("SELECT 1").Scan(&x); e != nil {
			errout(w, 500, "invalid")
		} else {
			write(w, 200, map[string]bool{"ok": true})
		}
		return
	}
	tenant := r.Header.Get("X-Tenant")
	if !nameRE.MatchString(tenant) {
		errout(w, 400, "invalid")
		return
	}
	if r.Method == "GET" {
		a.read(w, r, tenant)
		return
	}
	if r.Method != "POST" {
		errout(w, 404, "not_found")
		return
	}
	key := r.Header.Get("Idempotency-Key")
	if !keyRE.MatchString(key) {
		errout(w, 400, "invalid")
		return
	}
	body, e := readBody(r)
	if e != nil {
		errout(w, 400, "invalid")
		return
	}
	res, status, code := a.mutate(r.URL.Path, tenant, key, body)
	if code != "" {
		errout(w, codeStatus(code), code)
		return
	}
	write(w, status, res)
}
func codeStatus(c string) int {
	if c == "invalid" {
		return 400
	}
	if c == "not_found" {
		return 404
	}
	return 409
}
func errout(w http.ResponseWriter, s int, c string) {
	write(w, s, map[string]any{"error": map[string]string{"code": c}})
}
func write(w http.ResponseWriter, s int, v any) { w.WriteHeader(s); _ = json.NewEncoder(w).Encode(v) }
func readBody(r *http.Request) ([]byte, error) {
	if r.Body == nil {
		return nil, errors.New("body")
	}
	b, e := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if e != nil || len(strings.TrimSpace(string(b))) == 0 {
		return nil, errors.New("empty")
	}
	var m map[string]json.RawMessage
	if json.Unmarshal(b, &m) != nil || m == nil {
		return nil, errors.New("json")
	}
	return b, nil
}
func strict(b []byte, v any) error {
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return e
	}
	if d.Decode(new(any)) != io.EOF {
		return errors.New("trailing")
	}
	return nil
}
func canonical(b []byte) []byte {
	var x any
	_ = json.Unmarshal(b, &x)
	o, _ := json.Marshal(x)
	return o
}
func (a *API) mutate(path, t, k string, b []byte) (any, int, string) {
	tx, e := a.db.Begin()
	if e != nil {
		return nil, 0, "invalid"
	}
	defer tx.Rollback()
	cb := canonical(b)
	var oldpath string
	var oldbody, oldres []byte
	var oldstatus int
	e = tx.QueryRow("SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?", t, k).Scan(&oldpath, &oldbody, &oldstatus, &oldres)
	if e == nil {
		if path != oldpath || string(cb) != string(oldbody) {
			return nil, 0, "idempotency_conflict"
		}
		var v any
		_ = json.Unmarshal(oldres, &v)
		return v, oldstatus, ""
	}
	if e != sql.ErrNoRows {
		return nil, 0, "invalid"
	}
	res, status, code := a.perform(tx, path, t, b)
	if code != "" {
		return nil, 0, code
	}
	encoded, _ := json.Marshal(res)
	if _, e = tx.Exec("INSERT INTO idempotency VALUES(?,?,?,?,?,?)", t, k, path, cb, status, encoded); e != nil {
		return nil, 0, "invalid"
	}
	if e = tx.Commit(); e != nil {
		return nil, 0, "invalid"
	}
	return res, status, ""
}
func (a *API) perform(tx *sql.Tx, p, t string, b []byte) (any, int, string) {
	switch {
	case p == "/accounts":
		var q struct {
			Name    string `json:"name"`
			Opening *int64 `json:"opening"`
		}
		if strict(b, &q) != nil || !nameRE.MatchString(q.Name) || q.Opening == nil || *q.Opening < 0 || *q.Opening > 1_000_000_000 {
			return nil, 0, "invalid"
		}
		_, e := tx.Exec("INSERT INTO accounts VALUES(?,?,?,0,1)", t, q.Name, *q.Opening)
		if e != nil {
			return nil, 0, "exists"
		}
		id := newID()
		_ = entry(tx, t, q.Name, "opening", *q.Opening, 0, id, nil)
		x, _ := getAccount(tx, t, q.Name)
		return map[string]any{"account": x}, 201, ""
	case p == "/transfers":
		var q transferReq
		if strict(b, &q) != nil || versionNull(b, "from_version", "to_version") || !q.valid() {
			return nil, 0, "invalid"
		}
		tr, ac, c := makeTransfer(tx, t, q)
		if c != "" {
			return nil, 0, c
		}
		return map[string]any{"transfer": tr, "accounts": ac}, 201, ""
	case p == "/batches":
		var q struct {
			Transfers []transferReq `json:"transfers"`
		}
		if strict(b, &q) != nil || versionNullBatch(b) || len(q.Transfers) < 1 || len(q.Transfers) > 20 {
			return nil, 0, "invalid"
		}
		ts := make([]Transfer, 0, len(q.Transfers))
		names := map[string]bool{}
		for _, rq := range q.Transfers {
			if !rq.valid() {
				return nil, 0, "invalid"
			}
			tr, _, c := makeTransfer(tx, t, rq)
			if c != "" {
				return nil, 0, c
			}
			ts = append(ts, tr)
			names[rq.From] = true
			names[rq.To] = true
		}
		ns := sorted(names)
		acs := []Account{}
		for _, n := range ns {
			x, _ := getAccount(tx, t, n)
			acs = append(acs, x)
		}
		return map[string]any{"transfers": ts, "accounts": acs}, 201, ""
	case p == "/holds":
		var q struct {
			Account string `json:"account"`
			Amount  int64  `json:"amount"`
			Version *int64 `json:"version"`
		}
		if strict(b, &q) != nil || versionNull(b, "version") || !nameRE.MatchString(q.Account) || q.Amount < 1 || q.Amount > 1e9 || badver(q.Version) {
			return nil, 0, "invalid"
		}
		x, c := accountCheck(tx, t, q.Account, q.Version)
		if c != "" {
			return nil, 0, c
		}
		if x.Available < q.Amount {
			return nil, 0, "insufficient"
		}
		id := newID()
		if _, e := tx.Exec("UPDATE accounts SET reserved=reserved+?,version=version+1 WHERE tenant=? AND name=?", q.Amount, t, q.Account); e != nil {
			return nil, 0, "invalid"
		}
		_, _ = tx.Exec("INSERT INTO holds VALUES(?,?,?,?,?)", t, id, q.Account, q.Amount, "active")
		_ = entry(tx, t, q.Account, "hold", 0, q.Amount, id, nil)
		x, _ = getAccount(tx, t, q.Account)
		return map[string]any{"hold": Hold{id, q.Account, q.Amount, "active"}, "account": x}, 201, ""
	default:
		if strings.HasPrefix(p, "/holds/") && strings.HasSuffix(p, "/capture") {
			id := strings.TrimSuffix(strings.TrimPrefix(p, "/holds/"), "/capture")
			return capture(tx, t, id, b)
		}
		if strings.HasPrefix(p, "/holds/") && strings.HasSuffix(p, "/release") {
			id := strings.TrimSuffix(strings.TrimPrefix(p, "/holds/"), "/release")
			return release(tx, t, id, b)
		}
		if strings.HasPrefix(p, "/transfers/") && strings.HasSuffix(p, "/reverse") {
			id := strings.TrimSuffix(strings.TrimPrefix(p, "/transfers/"), "/reverse")
			return reverse(tx, t, id, b)
		}
		return nil, 0, "not_found"
	}
}

type transferReq struct {
	From        string `json:"from"`
	To          string `json:"to"`
	Amount      int64  `json:"amount"`
	FromVersion *int64 `json:"from_version"`
	ToVersion   *int64 `json:"to_version"`
}

func (q transferReq) valid() bool {
	return nameRE.MatchString(q.From) && nameRE.MatchString(q.To) && q.From != q.To && q.Amount >= 1 && q.Amount <= 1e9 && !badver(q.FromVersion) && !badver(q.ToVersion)
}
func badver(v *int64) bool { return v != nil && *v <= 0 }
func versionNull(b []byte, keys ...string) bool {
	var m map[string]json.RawMessage
	if json.Unmarshal(b, &m) != nil {
		return true
	}
	for _, k := range keys {
		if v, ok := m[k]; ok && string(v) == "null" {
			return true
		}
	}
	return false
}
func versionNullBatch(b []byte) bool {
	var m struct {
		Transfers []json.RawMessage `json:"transfers"`
	}
	if json.Unmarshal(b, &m) != nil {
		return true
	}
	for _, x := range m.Transfers {
		if versionNull(x, "from_version", "to_version") {
			return true
		}
	}
	return false
}
func accountCheck(tx *sql.Tx, t, n string, v *int64) (Account, string) {
	x, e := getAccount(tx, t, n)
	if e != nil {
		return x, "not_found"
	}
	if v != nil && x.Version != *v {
		return x, "version_conflict"
	}
	return x, ""
}
func getAccount(q interface{ QueryRow(string, ...any) *sql.Row }, t, n string) (Account, error) {
	var x Account
	e := q.QueryRow("SELECT name,balance,reserved,balance-reserved,version FROM accounts WHERE tenant=? AND name=?", t, n).Scan(&x.Name, &x.Balance, &x.Reserved, &x.Available, &x.Version)
	return x, e
}
func makeTransfer(tx *sql.Tx, t string, q transferReq) (Transfer, []Account, string) {
	f, c := accountCheck(tx, t, q.From, q.FromVersion)
	if c != "" {
		return Transfer{}, nil, c
	}
	to, c := accountCheck(tx, t, q.To, q.ToVersion)
	if c != "" {
		return Transfer{}, nil, c
	}
	if f.Available < q.Amount {
		return Transfer{}, nil, "insufficient"
	}
	if to.Balance > max-q.Amount {
		return Transfer{}, nil, "invalid"
	}
	id := newID()
	_, e := tx.Exec("UPDATE accounts SET balance=balance-?,version=version+1 WHERE tenant=? AND name=?", q.Amount, t, q.From)
	if e != nil {
		return Transfer{}, nil, "invalid"
	}
	_, e = tx.Exec("UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?", q.Amount, t, q.To)
	if e != nil {
		return Transfer{}, nil, "invalid"
	}
	_, _ = tx.Exec("INSERT INTO transfers(tenant,id,source,target,amount) VALUES(?,?,?,?,?)", t, id, q.From, q.To, q.Amount)
	_ = entry(tx, t, q.From, "transfer", -q.Amount, 0, id, nil)
	_ = entry(tx, t, q.To, "transfer", q.Amount, 0, id, nil)
	f, _ = getAccount(tx, t, q.From)
	to, _ = getAccount(tx, t, q.To)
	return Transfer{id, q.From, q.To, q.Amount, false, nil}, []Account{f, to}, ""
}
func newID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err == nil {
		return hex.EncodeToString(b)
	}
	return strconv.FormatInt(time.Now().UnixNano(), 36) + "-" + strconv.FormatInt(idCounter.Add(1), 36)
}

var idCounter atomicCounter

type atomicCounter struct{ v int64 }

func (c *atomicCounter) Add(n int64) int64 { return atomic.AddInt64(&c.v, n) }
func sorted(m map[string]bool) []string {
	a := make([]string, 0, len(m))
	for n := range m {
		a = append(a, n)
	}
	sort.Strings(a)
	return a
}
func getHold(tx *sql.Tx, t, id string) (Hold, error) {
	var h Hold
	e := tx.QueryRow("SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?", t, id).Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	return h, e
}
func capture(tx *sql.Tx, t, id string, b []byte) (any, int, string) {
	var q struct {
		To          string `json:"to"`
		FromVersion *int64 `json:"from_version"`
		ToVersion   *int64 `json:"to_version"`
	}
	if strict(b, &q) != nil || versionNull(b, "from_version", "to_version") || !nameRE.MatchString(q.To) || badver(q.FromVersion) || badver(q.ToVersion) {
		return nil, 0, "invalid"
	}
	h, e := getHold(tx, t, id)
	if e != nil {
		return nil, 0, "not_found"
	}
	if h.State != "active" {
		return nil, 0, "terminal"
	}
	if h.Account == q.To {
		return nil, 0, "invalid"
	}
	f, c := accountCheck(tx, t, h.Account, q.FromVersion)
	if c != "" {
		return nil, 0, c
	}
	d, c := accountCheck(tx, t, q.To, q.ToVersion)
	if c != "" {
		return nil, 0, c
	}
	if f.Reserved < h.Amount || d.Balance > max-h.Amount {
		return nil, 0, "invalid"
	}
	tid := newID()
	_, _ = tx.Exec("UPDATE accounts SET balance=balance-?,reserved=reserved-?,version=version+1 WHERE tenant=? AND name=?", h.Amount, h.Amount, t, h.Account)
	_, _ = tx.Exec("UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?", h.Amount, t, q.To)
	_, _ = tx.Exec("UPDATE holds SET state='captured' WHERE tenant=? AND id=?", t, id)
	_, _ = tx.Exec("INSERT INTO transfers(tenant,id,source,target,amount) VALUES(?,?,?,?,?)", t, tid, h.Account, q.To, h.Amount)
	_ = entry(tx, t, h.Account, "capture", -h.Amount, -h.Amount, tid, nil)
	_ = entry(tx, t, q.To, "capture", h.Amount, 0, tid, nil)
	f, _ = getAccount(tx, t, h.Account)
	d, _ = getAccount(tx, t, q.To)
	tr := Transfer{tid, h.Account, q.To, h.Amount, false, nil}
	return map[string]any{"hold": Hold{id, h.Account, h.Amount, "captured"}, "transfer": tr, "accounts": []Account{f, d}}, 200, ""
}
func release(tx *sql.Tx, t, id string, b []byte) (any, int, string) {
	var q struct {
		Version *int64 `json:"version"`
	}
	if strict(b, &q) != nil || versionNull(b, "version") || badver(q.Version) {
		return nil, 0, "invalid"
	}
	h, e := getHold(tx, t, id)
	if e != nil {
		return nil, 0, "not_found"
	}
	if h.State != "active" {
		return nil, 0, "terminal"
	}
	x, c := accountCheck(tx, t, h.Account, q.Version)
	if c != "" {
		return nil, 0, c
	}
	if x.Reserved < h.Amount {
		return nil, 0, "invalid"
	}
	_, _ = tx.Exec("UPDATE accounts SET reserved=reserved-?,version=version+1 WHERE tenant=? AND name=?", h.Amount, t, h.Account)
	_, _ = tx.Exec("UPDATE holds SET state='released' WHERE tenant=? AND id=?", t, id)
	_ = entry(tx, t, h.Account, "release", 0, -h.Amount, id, nil)
	x, _ = getAccount(tx, t, h.Account)
	return map[string]any{"hold": Hold{id, h.Account, h.Amount, "released"}, "account": x}, 200, ""
}
func reverse(tx *sql.Tx, t, id string, b []byte) (any, int, string) {
	var q struct {
		FromVersion *int64 `json:"from_version"`
		ToVersion   *int64 `json:"to_version"`
	}
	if strict(b, &q) != nil || versionNull(b, "from_version", "to_version") || badver(q.FromVersion) || badver(q.ToVersion) {
		return nil, 0, "invalid"
	}
	var src, dst string
	var amt int64
	var reversed int
	var reverseID sql.NullString
	var legacy sql.NullInt64
	e := tx.QueryRow("SELECT source,target,amount,reversed,reverse_id,legacy_id FROM transfers WHERE tenant=? AND id=?", t, id).Scan(&src, &dst, &amt, &reversed, &reverseID, &legacy)
	if e != nil {
		return nil, 0, "not_found"
	}
	if reversed != 0 || reverseID.Valid {
		return nil, 0, "terminal"
	}
	to, c := accountCheck(tx, t, src, q.FromVersion)
	if c != "" {
		return nil, 0, c
	}
	from, c := accountCheck(tx, t, dst, q.ToVersion)
	if c != "" {
		return nil, 0, c
	}
	if from.Available < amt {
		return nil, 0, "insufficient"
	}
	if to.Balance > max-amt {
		return nil, 0, "invalid"
	}
	rid := newID()
	_, _ = tx.Exec("UPDATE accounts SET balance=balance-?,version=version+1 WHERE tenant=? AND name=?", amt, t, dst)
	_, _ = tx.Exec("UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?", amt, t, src)
	_, _ = tx.Exec("UPDATE transfers SET reversed=1,reverse_id=? WHERE tenant=? AND id=?", rid, t, id)
	_, _ = tx.Exec("INSERT INTO transfers(tenant,id,source,target,amount,reversed) VALUES(?,?,?,?,?,0)", t, rid, dst, src, amt)
	_ = entry(tx, t, dst, "reversal", -amt, 0, rid, nil)
	_ = entry(tx, t, src, "reversal", amt, 0, rid, nil)
	from, _ = getAccount(tx, t, dst)
	to, _ = getAccount(tx, t, src)
	var legacyID *int64
	if legacy.Valid {
		legacyID = &legacy.Int64
	}
	orig := Transfer{id, src, dst, amt, true, legacyID}
	rev := Transfer{rid, dst, src, amt, false, nil}
	return map[string]any{"transfer": orig, "reversal": rev, "accounts": []Account{to, from}}, 200, ""
}
func (a *API) read(w http.ResponseWriter, r *http.Request, t string) {
	p := r.URL.Path
	if strings.HasPrefix(p, "/accounts/") {
		n := strings.TrimPrefix(p, "/accounts/")
		if strings.Contains(n, "/") || !nameRE.MatchString(n) {
			errout(w, 404, "not_found")
			return
		}
		x, e := getAccount(a.db, t, n)
		if e != nil {
			errout(w, 404, "not_found")
		} else {
			write(w, 200, map[string]any{"account": x})
		}
		return
	}
	if p != "/entries" && p != "/summary" {
		errout(w, 404, "not_found")
		return
	}
	vals := r.URL.Query()
	allowed := map[string]bool{}
	if p == "/entries" {
		allowed = map[string]bool{"after": true, "limit": true, "snapshot": true}
	} else {
		allowed = map[string]bool{"snapshot": true}
	}
	for k, v := range vals {
		if !allowed[k] || len(v) != 1 {
			errout(w, 400, "invalid")
			return
		}
	}
	var after, limit int64
	limit = 50
	var e error
	if p == "/entries" {
		after, e = queryInt(vals, "after", 0)
		if e == nil {
			limit, e = queryInt(vals, "limit", 50)
		}
		if e != nil || limit < 1 || limit > 100 {
			errout(w, 400, "invalid")
			return
		}
	}
	var current int64
	_ = a.db.QueryRow("SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?", t).Scan(&current)
	snap := current
	if vals.Has("snapshot") {
		snap, e = queryInt(vals, "snapshot", 0)
		if e != nil || snap < 0 || snap > current {
			errout(w, 400, "invalid")
			return
		}
	}
	if p == "/entries" {
		if after < 0 || after > snap {
			errout(w, 400, "invalid")
			return
		}
		rows, e := a.db.Query("SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?", t, after, snap, limit)
		if e != nil {
			errout(w, 500, "invalid")
			return
		}
		es := []Entry{}
		for rows.Next() {
			var x Entry
			var l sql.NullInt64
			_ = rows.Scan(&x.Seq, &x.Account, &x.Kind, &x.BalanceDelta, &x.ReservedDelta, &x.OperationID, &l)
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
		_ = a.db.QueryRow("SELECT EXISTS(SELECT 1 FROM entries WHERE tenant=? AND seq>? AND seq<=?)", t, next, snap).Scan(&more)
		write(w, 200, map[string]any{"entries": es, "snapshot": snap, "next_after": next, "has_more": more != 0})
		return
	}
	rows, e := a.db.Query("SELECT account,SUM(balance_delta),SUM(reserved_delta) FROM entries WHERE tenant=? AND seq<=? GROUP BY account ORDER BY account", t, snap)
	if e != nil {
		errout(w, 500, "invalid")
		return
	}
	type hist struct {
		Name      string `json:"name"`
		Balance   int64  `json:"balance"`
		Reserved  int64  `json:"reserved"`
		Available int64  `json:"available"`
	}
	as := []hist{}
	var tb, tr int64
	for rows.Next() {
		var x hist
		_ = rows.Scan(&x.Name, &x.Balance, &x.Reserved)
		x.Available = x.Balance - x.Reserved
		tb += x.Balance
		tr += x.Reserved
		as = append(as, x)
	}
	rows.Close()
	var count int64
	_ = a.db.QueryRow("SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?", t, snap).Scan(&count)
	write(w, 200, map[string]any{"snapshot": snap, "accounts": as, "totals": map[string]int64{"balance": tb, "reserved": tr, "available": tb - tr}, "entry_count": count})
}
func queryInt(v map[string][]string, k string, d int64) (int64, error) {
	s, ok := v[k]
	if !ok {
		return d, nil
	}
	if s[0] == "" {
		return 0, errors.New("empty")
	}
	n, e := strconv.ParseInt(s[0], 10, 64)
	if e != nil {
		return 0, e
	}
	return n, nil
}
