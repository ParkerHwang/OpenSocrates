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
)

const maxState int64 = 9000000000000000

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
type apiError struct {
	status int
	code   string
}

func (e apiError) Error() string { return e.code }
func bad(code string) error {
	status := 409
	if code == "invalid" {
		status = 400
	}
	if code == "not_found" {
		status = 404
	}
	return apiError{status, code}
}
func response(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func failure(w http.ResponseWriter, err error) {
	var e apiError
	if !errors.As(err, &e) {
		e = apiError{500, "internal"}
	}
	response(w, e.status, map[string]any{"error": map[string]string{"code": e.code}})
}
func newID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b[:])
}
func exec(c *sql.Conn, q string, args ...any) error {
	_, err := c.ExecContext(context.Background(), q, args...)
	return err
}
func begin(db *sql.DB) (*sql.Conn, error) {
	c, err := db.Conn(context.Background())
	if err != nil {
		return nil, err
	}
	if err = exec(c, "BEGIN IMMEDIATE"); err != nil {
		c.Close()
		return nil, err
	}
	return c, nil
}
func beginRead(db *sql.DB) (*sql.Conn, error) {
	c, err := db.Conn(context.Background())
	if err != nil {
		return nil, err
	}
	if err = exec(c, "BEGIN"); err != nil {
		c.Close()
		return nil, err
	}
	return c, nil
}
func commit(c *sql.Conn) error { return exec(c, "COMMIT") }
func rollback(c *sql.Conn)     { _ = exec(c, "ROLLBACK"); _ = c.Close() }
func Migrate(db *sql.DB) error {
	c, err := begin(db)
	if err != nil {
		return err
	}
	defer rollback(c)
	var version int
	if err = c.QueryRowContext(context.Background(), "PRAGMA user_version").Scan(&version); err != nil {
		return err
	}
	if version > 2 {
		return fmt.Errorf("unsupported schema version %d", version)
	}
	schema := []string{
		`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name))`,
		`CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL DEFAULT 0,kind TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS entries(tenant TEXT NOT NULL,seq INTEGER NOT NULL,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,seq))`,
		`CREATE TABLE IF NOT EXISTS tenant_sequences(tenant TEXT PRIMARY KEY,last_seq INTEGER NOT NULL)`,
		`CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body TEXT NOT NULL,status INTEGER NOT NULL,result TEXT NOT NULL,PRIMARY KEY(tenant,key))`,
		`CREATE INDEX IF NOT EXISTS entries_history ON entries(tenant,account,seq)`,
	}
	for _, q := range schema {
		if err = exec(c, q); err != nil {
			return err
		}
	}
	if version == 1 {
		type a struct {
			tenant, name   string
			final, opening int64
		}
		var accounts []a
		rows, e := c.QueryContext(context.Background(), "SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name")
		if e != nil {
			return e
		}
		for rows.Next() {
			var v a
			if e = rows.Scan(&v.tenant, &v.name, &v.final); e != nil {
				rows.Close()
				return e
			}
			v.opening = v.final
			accounts = append(accounts, v)
		}
		e = rows.Err()
		rows.Close()
		if e != nil {
			return e
		}
		type m struct {
			id               int64
			tenant, from, to string
			amount           int64
		}
		var movements []m
		rows, e = c.QueryContext(context.Background(), "SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id")
		if e != nil {
			return e
		}
		for rows.Next() {
			var v m
			if e = rows.Scan(&v.id, &v.tenant, &v.from, &v.to, &v.amount); e != nil {
				rows.Close()
				return e
			}
			movements = append(movements, v)
		}
		e = rows.Err()
		rows.Close()
		if e != nil {
			return e
		}
		lookup := map[string]int{}
		for i, v := range accounts {
			lookup[v.tenant+"\x00"+v.name] = i
		}
		for _, v := range movements {
			fi, ok1 := lookup[v.tenant+"\x00"+v.from]
			ti, ok2 := lookup[v.tenant+"\x00"+v.to]
			if !ok1 || !ok2 || v.amount < 1 {
				return fmt.Errorf("invalid legacy movement %d", v.id)
			}
			accounts[fi].opening += v.amount
			accounts[ti].opening -= v.amount
		}
		for _, v := range accounts {
			if v.opening < 0 || v.opening > maxState {
				return fmt.Errorf("invalid legacy opening")
			}
			if err = exec(c, "INSERT INTO accounts VALUES(?,?,?,?,1)", v.tenant, v.name, v.opening, 0); err != nil {
				return err
			}
			if err = addEntry(c, v.tenant, v.name, "opening", v.opening, 0, newID(), nil); err != nil {
				return err
			}
		}
		for _, v := range movements {
			t := Transfer{ID: newID(), From: v.from, To: v.to, Amount: v.amount, LegacyID: &v.id}
			if err = insertTransfer(c, v.tenant, t, "ordinary"); err != nil {
				return err
			}
			if err = exec(c, "UPDATE accounts SET balance=balance-?,version=version+1 WHERE tenant=? AND name=?", v.amount, v.tenant, v.from); err != nil {
				return err
			}
			if err = exec(c, "UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?", v.amount, v.tenant, v.to); err != nil {
				return err
			}
			if err = addEntry(c, v.tenant, v.from, "transfer", -v.amount, 0, t.ID, &v.id); err != nil {
				return err
			}
			if err = addEntry(c, v.tenant, v.to, "transfer", v.amount, 0, t.ID, &v.id); err != nil {
				return err
			}
		}
		for _, v := range accounts {
			var b int64
			if err = c.QueryRowContext(context.Background(), "SELECT balance FROM accounts WHERE tenant=? AND name=?", v.tenant, v.name).Scan(&b); err != nil {
				return err
			}
			if b != v.final {
				return fmt.Errorf("legacy balance mismatch")
			}
		}
	}
	if err = exec(c, "PRAGMA user_version=2"); err != nil {
		return err
	}
	return commit(c)
}
func addEntry(c *sql.Conn, tenant, account, kind string, bd, rd int64, id string, legacy *int64) error {
	var seq int64
	err := c.QueryRowContext(context.Background(), `INSERT INTO tenant_sequences(tenant,last_seq) VALUES(?,1) ON CONFLICT(tenant) DO UPDATE SET last_seq=last_seq+1 RETURNING last_seq`, tenant).Scan(&seq)
	if err != nil {
		return err
	}
	_, err = c.ExecContext(context.Background(), "INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)", tenant, seq, account, kind, bd, rd, id, legacy)
	return err
}
func insertTransfer(c *sql.Conn, tenant string, t Transfer, kind string) error {
	return exec(c, "INSERT INTO transfers VALUES(?,?,?,?,?,0,?,?)", tenant, t.ID, t.From, t.To, t.Amount, kind, t.LegacyID)
}
func getAccount(c *sql.Conn, tenant, name string) (Account, error) {
	var a Account
	err := c.QueryRowContext(context.Background(), "SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?", tenant, name).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	if errors.Is(err, sql.ErrNoRows) {
		return a, bad("not_found")
	}
	a.Available = a.Balance - a.Reserved
	return a, err
}
func getHold(c *sql.Conn, tenant, id string) (Hold, error) {
	var h Hold
	err := c.QueryRowContext(context.Background(), "SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?", tenant, id).Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	if errors.Is(err, sql.ErrNoRows) {
		return h, bad("not_found")
	}
	return h, err
}
func getTransfer(c *sql.Conn, tenant, id string) (Transfer, string, error) {
	var t Transfer
	var kind string
	var rev int
	var legacy sql.NullInt64
	err := c.QueryRowContext(context.Background(), "SELECT id,source,target,amount,reversed,kind,legacy_id FROM transfers WHERE tenant=? AND id=?", tenant, id).Scan(&t.ID, &t.From, &t.To, &t.Amount, &rev, &kind, &legacy)
	if errors.Is(err, sql.ErrNoRows) {
		return t, "", bad("not_found")
	}
	t.Reversed = rev != 0
	if legacy.Valid {
		t.LegacyID = &legacy.Int64
	}
	return t, kind, err
}
func validState(b, r int64) bool { return b >= 0 && b <= maxState && r >= 0 && r <= b }
func checkVersion(a Account, v *int64) error {
	if v != nil && *v != a.Version {
		return bad("version_conflict")
	}
	return nil
}
func updateAccount(c *sql.Conn, tenant string, a Account) error {
	if !validState(a.Balance, a.Reserved) {
		return bad("invalid")
	}
	return exec(c, "UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?", a.Balance, a.Reserved, a.Version, tenant, a.Name)
}
func amountOK(v int64) bool { return v >= 1 && v <= 1000000000 }
func transfer(c *sql.Conn, tenant, from, to string, amount int64, fv, tv *int64, kind string) (Transfer, []Account, error) {
	var empty Transfer
	if !nameRE.MatchString(from) || !nameRE.MatchString(to) || from == to || !amountOK(amount) {
		return empty, nil, bad("invalid")
	}
	a, e := getAccount(c, tenant, from)
	if e != nil {
		return empty, nil, e
	}
	b, e := getAccount(c, tenant, to)
	if e != nil {
		return empty, nil, e
	}
	if e = checkVersion(a, fv); e != nil {
		return empty, nil, e
	}
	if e = checkVersion(b, tv); e != nil {
		return empty, nil, e
	}
	if a.Available < amount {
		return empty, nil, bad("insufficient")
	}
	if b.Balance > maxState-amount {
		return empty, nil, bad("invalid")
	}
	a.Balance -= amount
	a.Available -= amount
	a.Version++
	b.Balance += amount
	b.Available += amount
	b.Version++
	t := Transfer{ID: newID(), From: from, To: to, Amount: amount}
	if e = insertTransfer(c, tenant, t, kind); e != nil {
		return empty, nil, e
	}
	if e = updateAccount(c, tenant, a); e != nil {
		return empty, nil, e
	}
	if e = updateAccount(c, tenant, b); e != nil {
		return empty, nil, e
	}
	entryKind := "transfer"
	if kind == "reversal" {
		entryKind = "reversal"
	}
	if e = addEntry(c, tenant, from, entryKind, -amount, 0, t.ID, nil); e != nil {
		return empty, nil, e
	}
	if e = addEntry(c, tenant, to, entryKind, amount, 0, t.ID, nil); e != nil {
		return empty, nil, e
	}
	return t, []Account{a, b}, nil
}
func decode(r *http.Request, dst any) (string, error) {
	if r.Body == nil {
		return "", bad("invalid")
	}
	b, err := io.ReadAll(io.LimitReader(r.Body, 1<<20+1))
	if err != nil || len(b) == 0 || len(b) > 1<<20 {
		return "", bad("invalid")
	}
	var raw map[string]json.RawMessage
	if err = json.Unmarshal(b, &raw); err != nil || raw == nil {
		return "", bad("invalid")
	}
	if containsNull(raw) {
		return "", bad("invalid")
	}
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.DisallowUnknownFields()
	if err = d.Decode(dst); err != nil {
		return "", bad("invalid")
	}
	var extra any
	if err = d.Decode(&extra); err != io.EOF {
		return "", bad("invalid")
	}
	canon, err := json.Marshal(dst)
	if err != nil {
		return "", err
	}
	return string(canon), nil
}

func containsNull(v any) bool {
	switch x := v.(type) {
	case map[string]json.RawMessage:
		for _, b := range x {
			var nested any
			if json.Unmarshal(b, &nested) != nil || containsNull(nested) {
				return true
			}
		}
	case map[string]any:
		for _, item := range x {
			if containsNull(item) {
				return true
			}
		}
	case []any:
		for _, item := range x {
			if containsNull(item) {
				return true
			}
		}
	case nil:
		return true
	}
	return false
}

type accountReq struct {
	Name    string `json:"name"`
	Opening *int64 `json:"opening"`
}
type transferReq struct {
	From        string `json:"from"`
	To          string `json:"to"`
	Amount      *int64 `json:"amount"`
	FromVersion *int64 `json:"from_version,omitempty"`
	ToVersion   *int64 `json:"to_version,omitempty"`
}
type batchReq struct {
	Transfers []transferReq `json:"transfers"`
}
type holdReq struct {
	Account string `json:"account"`
	Amount  *int64 `json:"amount"`
	Version *int64 `json:"version,omitempty"`
}
type captureReq struct {
	To          string `json:"to"`
	FromVersion *int64 `json:"from_version,omitempty"`
	ToVersion   *int64 `json:"to_version,omitempty"`
}
type releaseReq struct {
	Version *int64 `json:"version,omitempty"`
}
type reverseReq struct {
	FromVersion *int64 `json:"from_version,omitempty"`
	ToVersion   *int64 `json:"to_version,omitempty"`
}

func versionOK(v *int64) bool { return v == nil || *v > 0 }
func validTransferReq(t transferReq) bool {
	return nameRE.MatchString(t.From) && nameRE.MatchString(t.To) && t.From != t.To && t.Amount != nil && amountOK(*t.Amount) && versionOK(t.FromVersion) && versionOK(t.ToVersion)
}

type Server struct{ db *sql.DB }

func New(db *sql.DB) http.Handler { return &Server{db} }
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" && r.URL.Path == "/health" {
		response(w, 200, map[string]bool{"ok": true})
		return
	}
	tenant := r.Header.Get("X-Tenant")
	if !nameRE.MatchString(tenant) {
		failure(w, bad("invalid"))
		return
	}
	path := r.URL.Path
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if r.Method == "GET" {
		s.read(w, r, tenant, parts)
		return
	}
	if r.Method != "POST" {
		failure(w, bad("not_found"))
		return
	}
	key := r.Header.Get("Idempotency-Key")
	if !keyRE.MatchString(key) {
		failure(w, bad("invalid"))
		return
	}
	var req any
	var kind string
	switch {
	case path == "/accounts":
		req = &accountReq{}
		kind = "account"
	case path == "/transfers":
		req = &transferReq{}
		kind = "transfer"
	case path == "/batches":
		req = &batchReq{}
		kind = "batch"
	case path == "/holds":
		req = &holdReq{}
		kind = "hold"
	case len(parts) == 3 && parts[0] == "holds" && parts[2] == "capture" && parts[1] != "":
		req = &captureReq{}
		kind = "capture"
	case len(parts) == 3 && parts[0] == "holds" && parts[2] == "release" && parts[1] != "":
		req = &releaseReq{}
		kind = "release"
	case len(parts) == 3 && parts[0] == "transfers" && parts[2] == "reverse" && parts[1] != "":
		req = &reverseReq{}
		kind = "reverse"
	default:
		failure(w, bad("not_found"))
		return
	}
	canon, err := decode(r, req)
	if err != nil {
		failure(w, err)
		return
	}
	if err = validate(kind, req); err != nil {
		failure(w, err)
		return
	}
	c, err := begin(s.db)
	if err != nil {
		failure(w, err)
		return
	}
	defer rollback(c)
	var oldPath, oldBody, result string
	var status int
	err = c.QueryRowContext(r.Context(), "SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?", tenant, key).Scan(&oldPath, &oldBody, &status, &result)
	if err == nil {
		if oldPath != path || oldBody != canon {
			failure(w, bad("idempotency_conflict"))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_, _ = io.WriteString(w, result)
		return
	}
	if !errors.Is(err, sql.ErrNoRows) {
		failure(w, err)
		return
	}
	var out any
	status = 201
	switch kind {
	case "account":
		q := req.(*accountReq)
		var exists int
		err = c.QueryRowContext(r.Context(), "SELECT 1 FROM accounts WHERE tenant=? AND name=?", tenant, q.Name).Scan(&exists)
		if err == nil {
			err = bad("exists")
			break
		}
		if !errors.Is(err, sql.ErrNoRows) {
			break
		}
		a := Account{q.Name, *q.Opening, 0, *q.Opening, 1}
		err = exec(c, "INSERT INTO accounts VALUES(?,?,?,?,1)", tenant, q.Name, *q.Opening, 0)
		if err == nil {
			err = addEntry(c, tenant, q.Name, "opening", *q.Opening, 0, newID(), nil)
		}
		out = map[string]any{"account": a}
	case "transfer":
		q := req.(*transferReq)
		var t Transfer
		var aa []Account
		t, aa, err = transfer(c, tenant, q.From, q.To, *q.Amount, q.FromVersion, q.ToVersion, "ordinary")
		out = map[string]any{"transfer": t, "accounts": aa}
	case "batch":
		q := req.(*batchReq)
		ts := make([]Transfer, 0, len(q.Transfers))
		touched := map[string]bool{}
		for _, v := range q.Transfers {
			var t Transfer
			t, _, err = transfer(c, tenant, v.From, v.To, *v.Amount, v.FromVersion, v.ToVersion, "ordinary")
			if err != nil {
				break
			}
			ts = append(ts, t)
			touched[v.From] = true
			touched[v.To] = true
		}
		if err == nil {
			names := make([]string, 0, len(touched))
			for n := range touched {
				names = append(names, n)
			}
			sort.Strings(names)
			aa := make([]Account, 0, len(names))
			for _, n := range names {
				var a Account
				a, err = getAccount(c, tenant, n)
				if err != nil {
					break
				}
				aa = append(aa, a)
			}
			out = map[string]any{"transfers": ts, "accounts": aa}
		}
	case "hold":
		q := req.(*holdReq)
		var a Account
		a, err = getAccount(c, tenant, q.Account)
		if err != nil {
			break
		}
		if err = checkVersion(a, q.Version); err != nil {
			break
		}
		if a.Available < *q.Amount {
			err = bad("insufficient")
			break
		}
		a.Reserved += *q.Amount
		a.Available -= *q.Amount
		a.Version++
		h := Hold{newID(), q.Account, *q.Amount, "active"}
		err = exec(c, "INSERT INTO holds VALUES(?,?,?,?,?)", tenant, h.ID, h.Account, h.Amount, h.State)
		if err == nil {
			err = updateAccount(c, tenant, a)
		}
		if err == nil {
			err = addEntry(c, tenant, a.Name, "hold", 0, h.Amount, h.ID, nil)
		}
		out = map[string]any{"hold": h, "account": a}
	case "capture":
		status = 200
		q := req.(*captureReq)
		var h Hold
		h, err = getHold(c, tenant, parts[1])
		if err != nil {
			break
		}
		if h.State != "active" {
			err = bad("terminal")
			break
		}
		if h.Account == q.To {
			err = bad("invalid")
			break
		}
		var a, b Account
		a, err = getAccount(c, tenant, h.Account)
		if err != nil {
			break
		}
		b, err = getAccount(c, tenant, q.To)
		if err != nil {
			break
		}
		if err = checkVersion(a, q.FromVersion); err != nil {
			break
		}
		if err = checkVersion(b, q.ToVersion); err != nil {
			break
		}
		if b.Balance > maxState-h.Amount {
			err = bad("invalid")
			break
		}
		a.Reserved -= h.Amount
		a.Balance -= h.Amount
		a.Version++
		b.Balance += h.Amount
		b.Available += h.Amount
		b.Version++
		t := Transfer{ID: newID(), From: a.Name, To: b.Name, Amount: h.Amount}
		err = insertTransfer(c, tenant, t, "capture")
		if err == nil {
			err = updateAccount(c, tenant, a)
		}
		if err == nil {
			err = updateAccount(c, tenant, b)
		}
		if err == nil {
			err = exec(c, "UPDATE holds SET state='captured' WHERE tenant=? AND id=?", tenant, h.ID)
		}
		h.State = "captured"
		if err == nil {
			err = addEntry(c, tenant, a.Name, "capture", -h.Amount, -h.Amount, t.ID, nil)
		}
		if err == nil {
			err = addEntry(c, tenant, b.Name, "capture", h.Amount, 0, t.ID, nil)
		}
		a.Available = a.Balance - a.Reserved
		out = map[string]any{"hold": h, "transfer": t, "accounts": []Account{a, b}}
	case "release":
		status = 200
		q := req.(*releaseReq)
		var h Hold
		h, err = getHold(c, tenant, parts[1])
		if err != nil {
			break
		}
		if h.State != "active" {
			err = bad("terminal")
			break
		}
		var a Account
		a, err = getAccount(c, tenant, h.Account)
		if err != nil {
			break
		}
		if err = checkVersion(a, q.Version); err != nil {
			break
		}
		a.Reserved -= h.Amount
		a.Available += h.Amount
		a.Version++
		err = updateAccount(c, tenant, a)
		if err == nil {
			err = exec(c, "UPDATE holds SET state='released' WHERE tenant=? AND id=?", tenant, h.ID)
		}
		h.State = "released"
		if err == nil {
			err = addEntry(c, tenant, a.Name, "release", 0, -h.Amount, h.ID, nil)
		}
		out = map[string]any{"hold": h, "account": a}
	case "reverse":
		status = 200
		q := req.(*reverseReq)
		var orig Transfer
		var k string
		orig, k, err = getTransfer(c, tenant, parts[1])
		if err != nil {
			break
		}
		if orig.Reversed || k == "reversal" {
			err = bad("terminal")
			break
		}
		var rev Transfer
		var aa []Account
		rev, aa, err = transfer(c, tenant, orig.To, orig.From, orig.Amount, q.ToVersion, q.FromVersion, "reversal")
		if err != nil {
			break
		}
		err = exec(c, "UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?", tenant, orig.ID)
		orig.Reversed = true
		out = map[string]any{"transfer": orig, "reversal": rev, "accounts": []Account{aa[1], aa[0]}}
	}
	if err != nil {
		failure(w, err)
		return
	}
	b, err := json.Marshal(out)
	if err != nil {
		failure(w, err)
		return
	}
	result = string(b) + "\n"
	err = exec(c, "INSERT INTO idempotency VALUES(?,?,?,?,?,?)", tenant, key, path, canon, status, result)
	if err != nil {
		failure(w, err)
		return
	}
	if err = commit(c); err != nil {
		failure(w, err)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = io.WriteString(w, result)
}
func validate(kind string, v any) error {
	ok := false
	switch kind {
	case "account":
		q := v.(*accountReq)
		ok = nameRE.MatchString(q.Name) && q.Opening != nil && *q.Opening >= 0 && *q.Opening <= 1000000000
	case "transfer":
		ok = validTransferReq(*v.(*transferReq))
	case "batch":
		q := v.(*batchReq)
		ok = len(q.Transfers) >= 1 && len(q.Transfers) <= 20
		for _, t := range q.Transfers {
			ok = ok && validTransferReq(t)
		}
	case "hold":
		q := v.(*holdReq)
		ok = nameRE.MatchString(q.Account) && q.Amount != nil && amountOKValue(q.Amount) && versionOK(q.Version)
	case "capture":
		q := v.(*captureReq)
		ok = nameRE.MatchString(q.To) && versionOK(q.FromVersion) && versionOK(q.ToVersion)
	case "release":
		ok = versionOK(v.(*releaseReq).Version)
	case "reverse":
		q := v.(*reverseReq)
		ok = versionOK(q.FromVersion) && versionOK(q.ToVersion)
	}
	if !ok {
		return bad("invalid")
	}
	return nil
}
func amountOKValue(v *int64) bool { return v != nil && amountOK(*v) }
func queryInt(s string, def, min, max int64) (int64, error) {
	if s == "" {
		return def, nil
	}
	v, e := strconv.ParseInt(s, 10, 64)
	if e != nil || v < min || v > max {
		return 0, bad("invalid")
	}
	return v, nil
}
func maxSeq(db *sql.DB, tenant string) (int64, error) {
	var n int64
	err := db.QueryRow("SELECT COALESCE(last_seq,0) FROM tenant_sequences WHERE tenant=?", tenant).Scan(&n)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, nil
	}
	return n, err
}
func (s *Server) read(w http.ResponseWriter, r *http.Request, tenant string, parts []string) {
	path := r.URL.Path
	if len(parts) == 2 && parts[0] == "accounts" && parts[1] != "" {
		if !nameRE.MatchString(parts[1]) {
			failure(w, bad("not_found"))
			return
		}
		c, e := s.db.Conn(r.Context())
		if e != nil {
			failure(w, e)
			return
		}
		defer c.Close()
		a, e := getAccount(c, tenant, parts[1])
		if e != nil {
			failure(w, e)
			return
		}
		response(w, 200, map[string]any{"account": a})
		return
	}
	if path != "/entries" && path != "/summary" {
		failure(w, bad("not_found"))
		return
	}
	q := r.URL.Query()
	for k, v := range q {
		if (path == "/entries" && k != "after" && k != "limit" && k != "snapshot") || (path == "/summary" && k != "snapshot") || len(v) != 1 {
			failure(w, bad("invalid"))
			return
		}
	}
	c, e := beginRead(s.db)
	if e != nil {
		failure(w, e)
		return
	}
	defer rollback(c)
	var current int64
	e = c.QueryRowContext(r.Context(), "SELECT COALESCE((SELECT last_seq FROM tenant_sequences WHERE tenant=?),0)", tenant).Scan(&current)
	if e != nil {
		failure(w, e)
		return
	}
	snapshot := current
	if q.Has("snapshot") {
		snapshot, e = queryInt(q.Get("snapshot"), -1, 0, current)
		if e != nil || snapshot < 0 {
			failure(w, bad("invalid"))
			return
		}
	}
	if path == "/entries" {
		after := int64(0)
		limit := int64(50)
		if q.Has("after") {
			after, e = queryInt(q.Get("after"), -1, 0, snapshot)
			if e != nil || after < 0 {
				failure(w, bad("invalid"))
				return
			}
		}
		if q.Has("limit") {
			limit, e = queryInt(q.Get("limit"), -1, 1, 100)
			if e != nil || limit < 1 {
				failure(w, bad("invalid"))
				return
			}
		}
		rows, err := c.QueryContext(r.Context(), "SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?", tenant, after, snapshot, limit+1)
		if err != nil {
			failure(w, err)
			return
		}
		items := make([]Entry, 0)
		for rows.Next() {
			var v Entry
			var legacy sql.NullInt64
			if err = rows.Scan(&v.Seq, &v.Account, &v.Kind, &v.BalanceDelta, &v.ReservedDelta, &v.OperationID, &legacy); err != nil {
				break
			}
			if legacy.Valid {
				v.LegacyID = &legacy.Int64
			}
			items = append(items, v)
		}
		if err == nil {
			err = rows.Err()
		}
		rows.Close()
		if err != nil {
			failure(w, err)
			return
		}
		more := int64(len(items)) > limit
		if more {
			items = items[:limit]
		}
		next := after
		if len(items) > 0 {
			next = items[len(items)-1].Seq
		}
		_ = commit(c)
		response(w, 200, map[string]any{"entries": items, "snapshot": snapshot, "next_after": next, "has_more": more})
		return
	}
	rows, err := c.QueryContext(r.Context(), `SELECT a.name,COALESCE(SUM(e.balance_delta),0),COALESCE(SUM(e.reserved_delta),0) FROM (SELECT DISTINCT account AS name FROM entries WHERE tenant=? AND kind='opening' AND seq<=?) a JOIN entries e ON e.tenant=? AND e.account=a.name AND e.seq<=? GROUP BY a.name ORDER BY a.name`, tenant, snapshot, tenant, snapshot)
	if err != nil {
		failure(w, err)
		return
	}
	type summaryAccount struct {
		Name      string `json:"name"`
		Balance   int64  `json:"balance"`
		Reserved  int64  `json:"reserved"`
		Available int64  `json:"available"`
	}
	items := make([]summaryAccount, 0)
	var total summaryAccount
	for rows.Next() {
		var v summaryAccount
		if err = rows.Scan(&v.Name, &v.Balance, &v.Reserved); err != nil {
			break
		}
		v.Available = v.Balance - v.Reserved
		items = append(items, v)
		total.Balance += v.Balance
		total.Reserved += v.Reserved
		total.Available += v.Available
	}
	if err == nil {
		err = rows.Err()
	}
	rows.Close()
	if err != nil {
		failure(w, err)
		return
	}
	var count int64
	err = c.QueryRowContext(r.Context(), "SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?", tenant, snapshot).Scan(&count)
	if err != nil {
		failure(w, err)
		return
	}
	_ = commit(c)
	response(w, 200, map[string]any{"snapshot": snapshot, "accounts": items, "totals": map[string]int64{"balance": total.Balance, "reserved": total.Reserved, "available": total.Available}, "entry_count": count})
}
