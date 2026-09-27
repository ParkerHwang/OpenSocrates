package platform

import (
	"bytes"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

const maxUnits int64 = 9000000000000000

var ident = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var idemRE = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type API struct{ DB *sql.DB }
type failure struct {
	status int
	code   string
}

func fail(status int, code string) error { return failure{status, code} }
func (f failure) Error() string          { return f.code }
func id() string                         { var b [16]byte; _, _ = rand.Read(b[:]); return hex.EncodeToString(b[:]) }
func (a *API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if r.URL.Path == "/health" && r.Method == "GET" {
		if a.DB.Ping() != nil {
			writeErr(w, 500, "unavailable")
		} else {
			writeJSON(w, 200, map[string]any{"ok": true})
		}
		return
	}
	tenant := r.Header.Get("X-Tenant")
	if !ident.MatchString(tenant) {
		writeErr(w, 400, "invalid")
		return
	}
	if r.Method == "GET" {
		a.read(w, r, tenant)
		return
	}
	if r.Method != "POST" {
		writeErr(w, 404, "not_found")
		return
	}
	if !knownPost(r.URL.Path) {
		writeErr(w, 404, "not_found")
		return
	}
	key := r.Header.Get("Idempotency-Key")
	if !idemRE.MatchString(key) {
		writeErr(w, 400, "invalid")
		return
	}
	body, e := decodeBody(r)
	if e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	status, result, e := a.mutate(tenant, key, r.URL.Path, body)
	if e != nil {
		var f failure
		if errors.As(e, &f) {
			writeErr(w, f.status, f.code)
		} else {
			writeErr(w, 500, "internal")
		}
		return
	}
	writeJSON(w, status, result)
}
func knownPost(p string) bool {
	if p == "/accounts" || p == "/transfers" || p == "/batches" || p == "/holds" {
		return true
	}
	parts := strings.Split(p, "/")
	return len(parts) == 4 && parts[1] != "" && ((parts[1] == "holds" && (parts[3] == "capture" || parts[3] == "release")) || (parts[1] == "transfers" && parts[3] == "reverse"))
}
func writeJSON(w http.ResponseWriter, s int, v any) {
	w.WriteHeader(s)
	_ = json.NewEncoder(w).Encode(v)
}
func writeErr(w http.ResponseWriter, s int, c string) {
	writeJSON(w, s, map[string]any{"error": map[string]string{"code": c}})
}
func decodeBody(r *http.Request) (json.RawMessage, error) {
	b, e := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if e != nil || len(bytes.TrimSpace(b)) == 0 {
		return nil, fmt.Errorf("empty")
	}
	var x any
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	if e = d.Decode(&x); e != nil {
		return nil, e
	}
	if _, ok := x.(map[string]any); !ok {
		return nil, fmt.Errorf("object required")
	}
	if d.Decode(&struct{}{}) != io.EOF {
		return nil, fmt.Errorf("trailing")
	}
	return b, nil
}
func strict(b []byte, v any) error {
	var fields any
	if json.Unmarshal(b, &fields) == nil {
		if hasNullVersion(fields) {
			return fmt.Errorf("null version")
		}
	}
	d := json.NewDecoder(bytes.NewReader(b))
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return e
	}
	if d.Decode(&struct{}{}) != io.EOF {
		return fmt.Errorf("trailing")
	}
	return nil
}
func hasNullVersion(v any) bool {
	switch x := v.(type) {
	case map[string]any:
		for k, val := range x {
			if (k == "version" || strings.HasSuffix(k, "_version")) && val == nil {
				return true
			}
			if hasNullVersion(val) {
				return true
			}
		}
	case []any:
		for _, val := range x {
			if hasNullVersion(val) {
				return true
			}
		}
	}
	return false
}
func validName(s string) bool { return ident.MatchString(s) }

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
type transferReq struct {
	From        string `json:"from"`
	To          string `json:"to"`
	Amount      int64  `json:"amount"`
	FromVersion *int64 `json:"from_version,omitempty"`
	ToVersion   *int64 `json:"to_version,omitempty"`
}

func (a *API) mutate(t, k, path string, raw []byte) (int, any, error) {
	tx, e := a.DB.Begin()
	if e != nil {
		return 0, nil, e
	}
	defer tx.Rollback()
	if _, e = tx.Exec(`UPDATE migration_lock SET n=n WHERE id=1`); e != nil {
		return 0, nil, e
	}
	var oldPath string
	var oldBody, oldResult []byte
	var oldStatus int
	e = tx.QueryRow(`SELECT path,body,result,status FROM idempotency WHERE tenant=? AND key=?`, t, k).Scan(&oldPath, &oldBody, &oldResult, &oldStatus)
	// Compare semantic JSON values by canonical decoded representation.
	if e == nil {
		var x, y any
		_ = json.Unmarshal(oldBody, &x)
		_ = json.Unmarshal(raw, &y)
		xb, _ := json.Marshal(x)
		yb, _ := json.Marshal(y)
		if path != oldPath || !bytes.Equal(xb, yb) {
			return 0, nil, fail(409, "idempotency_conflict")
		}
		var v any
		_ = json.Unmarshal(oldResult, &v)
		return oldStatus, v, nil
	}
	if e != sql.ErrNoRows {
		return 0, nil, e
	}
	status, out, e := a.apply(tx, t, path, raw)
	if e != nil {
		return 0, nil, e
	}
	encoded, e := json.Marshal(out)
	if e != nil {
		return 0, nil, e
	}
	if _, e = tx.Exec(`INSERT INTO idempotency VALUES(?,?,?,?,?,?)`, t, k, path, canonical(raw), encoded, status); e != nil {
		return 0, nil, e
	}
	if e = tx.Commit(); e != nil {
		return 0, nil, e
	}
	return status, out, nil
}
func canonical(b []byte) []byte {
	var x any
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	_ = d.Decode(&x)
	c, _ := json.Marshal(x)
	return c
}
func (a *API) apply(tx *sql.Tx, t, path string, b []byte) (int, any, error) {
	switch path {
	case "/accounts":
		var q struct {
			Name    string `json:"name"`
			Opening *int64 `json:"opening"`
		}
		if strict(b, &q) != nil || !validName(q.Name) || q.Opening == nil || *q.Opening < 0 || *q.Opening > 1_000_000_000 {
			return 0, nil, fail(400, "invalid")
		}
		_, e := tx.Exec(`INSERT INTO accounts VALUES(?,?,?,?,?)`, t, q.Name, *q.Opening, 0, 1)
		if e != nil {
			return 0, nil, fail(409, "exists")
		}
		op := id()
		if e = entry(tx, t, q.Name, "opening", *q.Opening, 0, op, nil); e != nil {
			return 0, nil, e
		}
		ac, e := getAccount(tx, t, q.Name)
		return 201, map[string]any{"account": ac}, e
	case "/transfers":
		var q transferReq
		if strict(b, &q) != nil || !validTransfer(q) {
			return 0, nil, fail(400, "invalid")
		}
		tr, acs, e := doTransfer(tx, t, q, "transfer", id(), nil)
		if e != nil {
			return 0, nil, e
		}
		return 201, map[string]any{"transfer": tr, "accounts": acs}, nil
	case "/batches":
		var q struct {
			Transfers []transferReq `json:"transfers"`
		}
		if strict(b, &q) != nil || len(q.Transfers) < 1 || len(q.Transfers) > 20 {
			return 0, nil, fail(400, "invalid")
		}
		trs := make([]Transfer, 0, len(q.Transfers))
		touched := map[string]bool{}
		for _, rq := range q.Transfers {
			if !validTransfer(rq) {
				return 0, nil, fail(400, "invalid")
			}
			tr, _, e := doTransfer(tx, t, rq, "transfer", id(), nil)
			if e != nil {
				return 0, nil, e
			}
			trs = append(trs, tr)
			touched[rq.From] = true
			touched[rq.To] = true
		}
		names := sortedKeys(touched)
		acs := make([]Account, 0, len(names))
		for _, n := range names {
			ac, e := getAccount(tx, t, n)
			if e != nil {
				return 0, nil, e
			}
			acs = append(acs, ac)
		}
		return 201, map[string]any{"transfers": trs, "accounts": acs}, nil
	case "/holds":
		var q struct {
			Account string `json:"account"`
			Amount  int64  `json:"amount"`
			Version *int64 `json:"version,omitempty"`
		}
		if strict(b, &q) != nil || !validName(q.Account) || q.Amount < 1 || q.Amount > 1_000_000_000 || badVersion(q.Version) {
			return 0, nil, fail(400, "invalid")
		}
		ac, e := getAccount(tx, t, q.Account)
		if e != nil {
			return 0, nil, e
		}
		if q.Version != nil && *q.Version != ac.Version {
			return 0, nil, fail(409, "version_conflict")
		}
		if q.Amount > ac.Available {
			return 0, nil, fail(409, "insufficient")
		}
		hid := id()
		if _, e = tx.Exec(`INSERT INTO holds(tenant,id,account,amount,state) VALUES(?,?,?,?,'active')`, t, hid, q.Account, q.Amount); e != nil {
			return 0, nil, e
		}
		ac.Reserved += q.Amount
		ac.Version++
		if _, e = tx.Exec(`UPDATE accounts SET reserved=?,version=? WHERE tenant=? AND name=?`, ac.Reserved, ac.Version, t, q.Account); e != nil {
			return 0, nil, e
		}
		if e = entry(tx, t, q.Account, "hold", 0, q.Amount, hid, nil); e != nil {
			return 0, nil, e
		}
		return 201, map[string]any{"hold": Hold{hid, q.Account, q.Amount, "active"}, "account": ac}, nil
	}
	if strings.HasPrefix(path, "/holds/") {
		parts := strings.Split(path, "/")
		if len(parts) == 4 && (parts[3] == "capture" || parts[3] == "release") {
			return a.holdAction(tx, t, parts[2], parts[3], b)
		}
	}
	if strings.HasPrefix(path, "/transfers/") {
		parts := strings.Split(path, "/")
		if len(parts) == 4 && parts[3] == "reverse" {
			return a.reverse(tx, t, parts[2], b)
		}
	}
	return 0, nil, fail(404, "not_found")
}
func badVersion(v *int64) bool { return v != nil && *v <= 0 }
func validTransfer(q transferReq) bool {
	return validName(q.From) && validName(q.To) && q.From != q.To && q.Amount >= 1 && q.Amount <= 1_000_000_000 && !badVersion(q.FromVersion) && !badVersion(q.ToVersion)
}
func getAccount(tx *sql.Tx, t, n string) (Account, error) {
	var a Account
	e := tx.QueryRow(`SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	if e == sql.ErrNoRows {
		return a, fail(404, "not_found")
	}
	a.Available = a.Balance - a.Reserved
	return a, e
}
func entry(tx *sql.Tx, t, acct, kind string, bd, rd int64, op string, legacy *int64) error {
	_, e := tx.Exec(`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?)`, t, acct, kind, bd, rd, op, legacy)
	return e
}
func doTransfer(tx *sql.Tx, t string, q transferReq, kind, tid string, legacy *int64) (Transfer, []Account, error) {
	from, e := getAccount(tx, t, q.From)
	if e != nil {
		return Transfer{}, nil, e
	}
	to, e := getAccount(tx, t, q.To)
	if e != nil {
		return Transfer{}, nil, e
	}
	if q.FromVersion != nil && *q.FromVersion != from.Version || q.ToVersion != nil && *q.ToVersion != to.Version {
		return Transfer{}, nil, fail(409, "version_conflict")
	}
	if q.Amount > from.Available {
		return Transfer{}, nil, fail(409, "insufficient")
	}
	if to.Balance > maxUnits-q.Amount {
		return Transfer{}, nil, fail(409, "invalid")
	}
	from.Balance -= q.Amount
	to.Balance += q.Amount
	from.Version++
	to.Version++
	_, e = tx.Exec(`UPDATE accounts SET balance=?,version=? WHERE tenant=? AND name=?`, from.Balance, from.Version, t, q.From)
	if e != nil {
		return Transfer{}, nil, e
	}
	_, e = tx.Exec(`UPDATE accounts SET balance=?,version=? WHERE tenant=? AND name=?`, to.Balance, to.Version, t, q.To)
	if e != nil {
		return Transfer{}, nil, e
	}
	if e = entry(tx, t, q.From, kind, -q.Amount, 0, tid, legacy); e != nil {
		return Transfer{}, nil, e
	}
	if e = entry(tx, t, q.To, kind, q.Amount, 0, tid, legacy); e != nil {
		return Transfer{}, nil, e
	}
	tr := Transfer{tid, q.From, q.To, q.Amount, false, legacy}
	_, e = tx.Exec(`INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind,legacy_id) VALUES(?,?,?,?,?,0,?,?)`, t, tid, q.From, q.To, q.Amount, kind, legacy)
	return tr, []Account{from, to}, e
}
func sortedKeys(m map[string]bool) []string {
	a := make([]string, 0, len(m))
	for k := range m {
		a = append(a, k)
	}
	sort.Strings(a)
	return a
}
func positiveInt(s string, def int64) (int64, bool) {
	if s == "" {
		return def, true
	}
	n, e := strconv.ParseInt(s, 10, 64)
	return n, e == nil && n >= 0 && strconv.FormatInt(n, 10) == s
}
func queryInt(q map[string][]string, key string, def int64) (int64, bool) {
	v, ok := q[key]
	if !ok {
		return def, true
	}
	if len(v) != 1 || v[0] == "" {
		return 0, false
	}
	return positiveInt(v[0], def)
}
func checkQuery(r *http.Request, allowed ...string) bool {
	for k, v := range r.URL.Query() {
		ok := false
		for _, a := range allowed {
			if k == a {
				ok = true
			}
		}
		if !ok || len(v) != 1 {
			return false
		}
	}
	return true
}
func (a *API) read(w http.ResponseWriter, r *http.Request, t string) {
	p := r.URL.Path
	if strings.HasPrefix(p, "/accounts/") && len(strings.Split(p, "/")) == 3 && checkQuery(r) {
		n := strings.TrimPrefix(p, "/accounts/")
		if !validName(n) {
			writeErr(w, 404, "not_found")
			return
		}
		ac, e := getAccountDB(a.DB, t, n)
		if e != nil {
			writeErr(w, 404, "not_found")
		} else {
			writeJSON(w, 200, map[string]any{"account": ac})
		}
		return
	}
	if p == "/entries" {
		a.readEntries(w, r, t)
		return
	}
	if p == "/summary" {
		a.summary(w, r, t)
		return
	}
	writeErr(w, 404, "not_found")
}
func getAccountDB(db *sql.DB, t, n string) (Account, error) {
	var a Account
	e := db.QueryRow(`SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, t, n).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	a.Available = a.Balance - a.Reserved
	return a, e
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

func maxSeq(db *sql.DB, t string) (int64, error) {
	var n int64
	e := db.QueryRow(`SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?`, t).Scan(&n)
	return n, e
}
func parseSnapshot(db *sql.DB, r *http.Request, t string) (int64, error) {
	max, e := maxSeq(db, t)
	if e != nil {
		return 0, e
	}
	s, ok := queryInt(r.URL.Query(), "snapshot", max)
	if !ok || s > max {
		return 0, fail(400, "invalid")
	}
	return s, nil
}
func (a *API) readEntries(w http.ResponseWriter, r *http.Request, t string) {
	if !checkQuery(r, "after", "limit", "snapshot") {
		writeErr(w, 400, "invalid")
		return
	}
	snap, e := parseSnapshot(a.DB, r, t)
	if e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	after, ok := queryInt(r.URL.Query(), "after", 0)
	if !ok || after > snap {
		writeErr(w, 400, "invalid")
		return
	}
	lim, ok := queryInt(r.URL.Query(), "limit", 50)
	if !ok || lim < 1 || lim > 100 {
		writeErr(w, 400, "invalid")
		return
	}
	rows, e := a.DB.Query(`SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, t, after, snap, lim)
	if e != nil {
		writeErr(w, 500, "internal")
		return
	}
	defer rows.Close()
	out := []Entry{}
	for rows.Next() {
		var x Entry
		var lid sql.NullInt64
		if rows.Scan(&x.Seq, &x.Account, &x.Kind, &x.BalanceDelta, &x.ReservedDelta, &x.OperationID, &lid) != nil {
			writeErr(w, 500, "internal")
			return
		}
		if lid.Valid {
			x.LegacyID = &lid.Int64
		}
		out = append(out, x)
	}
	next := after
	if len(out) > 0 {
		next = out[len(out)-1].Seq
	}
	var more int
	_ = a.DB.QueryRow(`SELECT 1 FROM entries WHERE tenant=? AND seq>? AND seq<=? LIMIT 1`, t, next, snap).Scan(&more)
	writeJSON(w, 200, map[string]any{"entries": out, "snapshot": snap, "next_after": next, "has_more": more == 1})
}
func (a *API) summary(w http.ResponseWriter, r *http.Request, t string) {
	snap, e := parseSnapshot(a.DB, r, t)
	if e != nil {
		writeErr(w, 400, "invalid")
		return
	}
	rows, e := a.DB.Query(`SELECT account,SUM(balance_delta),SUM(reserved_delta),MIN(seq) FROM entries WHERE tenant=? AND seq<=? GROUP BY account HAVING MIN(seq) IS NOT NULL ORDER BY account`, t, snap)
	if e != nil {
		writeErr(w, 500, "internal")
		return
	}
	defer rows.Close()
	type summaryAccount struct {
		Name      string `json:"name"`
		Balance   int64  `json:"balance"`
		Reserved  int64  `json:"reserved"`
		Available int64  `json:"available"`
	}
	acs := []summaryAccount{}
	var bal, res int64
	for rows.Next() {
		var x summaryAccount
		if rows.Scan(&x.Name, &x.Balance, &x.Reserved, new(int64)) != nil {
			writeErr(w, 500, "internal")
			return
		}
		x.Available = x.Balance - x.Reserved
		bal += x.Balance
		res += x.Reserved
		acs = append(acs, x)
	}
	var cnt int64
	_ = a.DB.QueryRow(`SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?`, t, snap).Scan(&cnt)
	writeJSON(w, 200, map[string]any{"snapshot": snap, "accounts": acs, "totals": map[string]int64{"balance": bal, "reserved": res, "available": bal - res}, "entry_count": cnt})
}
func (a *API) holdAction(tx *sql.Tx, t, hid, action string, b []byte) (int, any, error) {
	if hid == "" || strings.Contains(hid, "/") {
		return 0, nil, fail(404, "not_found")
	}
	if action == "release" {
		var q struct {
			Version *int64 `json:"version,omitempty"`
		}
		if strict(b, &q) != nil || badVersion(q.Version) {
			return 0, nil, fail(400, "invalid")
		}
		var h Hold
		var state string
		e := tx.QueryRow(`SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?`, t, hid).Scan(&h.ID, &h.Account, &h.Amount, &state)
		if e == sql.ErrNoRows {
			return 0, nil, fail(404, "not_found")
		}
		if e != nil {
			return 0, nil, e
		}
		h.State = state
		if state != "active" {
			return 0, nil, fail(409, "terminal")
		}
		ac, e := getAccount(tx, t, h.Account)
		if e != nil {
			return 0, nil, e
		}
		if q.Version != nil && *q.Version != ac.Version {
			return 0, nil, fail(409, "version_conflict")
		}
		ac.Reserved -= h.Amount
		ac.Version++
		_, e = tx.Exec(`UPDATE accounts SET reserved=?,version=? WHERE tenant=? AND name=?`, ac.Reserved, ac.Version, t, h.Account)
		if e != nil {
			return 0, nil, e
		}
		_, e = tx.Exec(`UPDATE holds SET state='released' WHERE tenant=? AND id=?`, t, hid)
		if e != nil {
			return 0, nil, e
		}
		if e = entry(tx, t, h.Account, "release", 0, -h.Amount, hid, nil); e != nil {
			return 0, nil, e
		}
		h.State = "released"
		return 200, map[string]any{"hold": h, "account": ac}, nil
	}
	var q struct {
		To          string `json:"to"`
		FromVersion *int64 `json:"from_version,omitempty"`
		ToVersion   *int64 `json:"to_version,omitempty"`
	}
	if strict(b, &q) != nil || !validName(q.To) || badVersion(q.FromVersion) || badVersion(q.ToVersion) {
		return 0, nil, fail(400, "invalid")
	}
	var h Hold
	var state string
	e := tx.QueryRow(`SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?`, t, hid).Scan(&h.ID, &h.Account, &h.Amount, &state)
	if e == sql.ErrNoRows {
		return 0, nil, fail(404, "not_found")
	}
	if e != nil {
		return 0, nil, e
	}
	h.State = state
	if state != "active" {
		return 0, nil, fail(409, "terminal")
	}
	if h.Account == q.To {
		return 0, nil, fail(400, "invalid")
	}
	src, e := getAccount(tx, t, h.Account)
	if e != nil {
		return 0, nil, e
	}
	dst, e := getAccount(tx, t, q.To)
	if e != nil {
		return 0, nil, e
	}
	if q.FromVersion != nil && *q.FromVersion != src.Version || q.ToVersion != nil && *q.ToVersion != dst.Version {
		return 0, nil, fail(409, "version_conflict")
	}
	if dst.Balance > maxUnits-h.Amount {
		return 0, nil, fail(409, "invalid")
	}
	src.Balance -= h.Amount
	src.Reserved -= h.Amount
	src.Version++
	dst.Balance += h.Amount
	dst.Version++
	_, e = tx.Exec(`UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?`, src.Balance, src.Reserved, src.Version, t, src.Name)
	if e != nil {
		return 0, nil, e
	}
	_, e = tx.Exec(`UPDATE accounts SET balance=?,version=? WHERE tenant=? AND name=?`, dst.Balance, dst.Version, t, dst.Name)
	if e != nil {
		return 0, nil, e
	}
	tid := id()
	if e = entry(tx, t, src.Name, "capture", -h.Amount, -h.Amount, tid, nil); e != nil {
		return 0, nil, e
	}
	if e = entry(tx, t, dst.Name, "capture", h.Amount, 0, tid, nil); e != nil {
		return 0, nil, e
	}
	_, e = tx.Exec(`INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind,legacy_id) VALUES(?,?,?,?,?,0,'capture',NULL)`, t, tid, src.Name, dst.Name, h.Amount)
	if e != nil {
		return 0, nil, e
	}
	_, e = tx.Exec(`UPDATE holds SET state='captured' WHERE tenant=? AND id=?`, t, hid)
	if e != nil {
		return 0, nil, e
	}
	h.State = "captured"
	tr := Transfer{tid, src.Name, dst.Name, h.Amount, false, nil}
	return 200, map[string]any{"hold": h, "transfer": tr, "accounts": []Account{src, dst}}, nil
}
func (a *API) reverse(tx *sql.Tx, t, tid string, b []byte) (int, any, error) {
	if tid == "" || strings.Contains(tid, "/") {
		return 0, nil, fail(404, "not_found")
	}
	var q struct {
		FromVersion *int64 `json:"from_version,omitempty"`
		ToVersion   *int64 `json:"to_version,omitempty"`
	}
	if strict(b, &q) != nil || badVersion(q.FromVersion) || badVersion(q.ToVersion) {
		return 0, nil, fail(400, "invalid")
	}
	var orig Transfer
	var kind string
	var rev int
	e := tx.QueryRow(`SELECT id,source,target,amount,reversed,kind,legacy_id FROM transfers WHERE tenant=? AND id=?`, t, tid).Scan(&orig.ID, &orig.From, &orig.To, &orig.Amount, &rev, &kind, &orig.LegacyID)
	if e == sql.ErrNoRows {
		return 0, nil, fail(404, "not_found")
	}
	if e != nil {
		return 0, nil, e
	}
	orig.Reversed = rev != 0
	if kind == "reversal" || orig.Reversed {
		return 0, nil, fail(409, "terminal")
	}
	from, e := getAccount(tx, t, orig.From)
	if e != nil {
		return 0, nil, e
	}
	to, e := getAccount(tx, t, orig.To)
	if e != nil {
		return 0, nil, e
	}
	if q.FromVersion != nil && *q.FromVersion != from.Version || q.ToVersion != nil && *q.ToVersion != to.Version {
		return 0, nil, fail(409, "version_conflict")
	}
	if orig.Amount > to.Available {
		return 0, nil, fail(409, "insufficient")
	}
	from.Balance += orig.Amount
	if from.Balance > maxUnits {
		return 0, nil, fail(409, "invalid")
	}
	to.Balance -= orig.Amount
	from.Version++
	to.Version++
	_, e = tx.Exec(`UPDATE accounts SET balance=?,version=? WHERE tenant=? AND name=?`, from.Balance, from.Version, t, from.Name)
	if e != nil {
		return 0, nil, e
	}
	_, e = tx.Exec(`UPDATE accounts SET balance=?,version=? WHERE tenant=? AND name=?`, to.Balance, to.Version, t, to.Name)
	if e != nil {
		return 0, nil, e
	}
	rid := id()
	if e = entry(tx, t, to.Name, "reversal", -orig.Amount, 0, rid, nil); e != nil {
		return 0, nil, e
	}
	if e = entry(tx, t, from.Name, "reversal", orig.Amount, 0, rid, nil); e != nil {
		return 0, nil, e
	}
	_, e = tx.Exec(`INSERT INTO transfers(tenant,id,source,target,amount,reversed,kind,legacy_id) VALUES(?,?,?,?,?,0,'reversal',NULL)`, t, rid, orig.To, orig.From, orig.Amount)
	if e != nil {
		return 0, nil, e
	}
	_, e = tx.Exec(`UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?`, t, tid)
	if e != nil {
		return 0, nil, e
	}
	orig.Reversed = true
	reversal := Transfer{rid, orig.To, orig.From, orig.Amount, false, nil}
	return 200, map[string]any{"transfer": orig, "reversal": reversal, "accounts": []Account{from, to}}, nil
}

var _ = math.MaxInt64
var _ = strconv.IntSize
var _ = strings.TrimSpace
