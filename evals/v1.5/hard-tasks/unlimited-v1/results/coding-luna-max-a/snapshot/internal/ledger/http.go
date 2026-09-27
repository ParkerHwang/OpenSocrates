package ledger

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"math/big"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"github.com/google/uuid"
)

var namePattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type OptionalVersion struct {
	Set   bool
	Value int64
}

func (v *OptionalVersion) UnmarshalJSON(data []byte) error {
	v.Set = true
	if bytes.Equal(bytes.TrimSpace(data), []byte("null")) {
		return errors.New("version cannot be null")
	}
	if err := json.Unmarshal(data, &v.Value); err != nil {
		return errors.New("version must be an integer")
	}
	if v.Value <= 0 {
		return errors.New("version must be positive")
	}
	return nil
}

type apiError struct {
	status int
	code   string
}

func problem(status int, code string) *apiError { return &apiError{status: status, code: code} }

type errorResponse struct {
	Error struct {
		Code string `json:"code"`
	} `json:"error"`
}

func writeError(w http.ResponseWriter, e *apiError) {
	if e == nil {
		e = problem(http.StatusInternalServerError, "internal")
	}
	var response errorResponse
	response.Error.Code = e.code
	writeJSON(w, e.status, response)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	b, err := json.Marshal(value)
	if err != nil {
		b = []byte(`{"error":{"code":"internal"}}`)
		status = http.StatusInternalServerError
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(b)
}

func writeRawJSON(w http.ResponseWriter, status int, raw []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(raw)
}

func (l *Ledger) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" {
		if r.Method != http.MethodGet {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		var one, version int
		if err := l.db.QueryRowContext(r.Context(), "SELECT 1").Scan(&one); err != nil || one != 1 {
			writeError(w, problem(http.StatusServiceUnavailable, "internal"))
			return
		}
		if err := l.db.QueryRowContext(r.Context(), "PRAGMA user_version").Scan(&version); err != nil || version != 2 {
			writeError(w, problem(http.StatusServiceUnavailable, "internal"))
			return
		}
		writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
		return
	}
	tenant, valid := requestTenant(r)
	if !valid {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	// A successful tenant-wide key cannot be moved to another POST path, even
	// when that target path or its body would otherwise fail validation.
	if r.Method == http.MethodPost {
		if key, ok := validWriteHeaders(r); ok {
			var oldPath string
			err := l.db.QueryRowContext(r.Context(), "SELECT path FROM idempotency WHERE tenant=? AND key=?", tenant, key).Scan(&oldPath)
			if err == nil && oldPath != r.URL.Path {
				writeError(w, problem(http.StatusConflict, "idempotency_conflict"))
				return
			}
			if err != nil && !errors.Is(err, sql.ErrNoRows) {
				writeError(w, problem(http.StatusInternalServerError, "internal"))
				return
			}
		}
	}
	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/"), "/")
	if strings.HasPrefix(r.URL.Path, "/") == false {
		writeError(w, problem(http.StatusNotFound, "not_found"))
		return
	}
	switch {
	case len(parts) == 1 && parts[0] == "accounts":
		if r.Method != http.MethodPost {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		l.postAccount(w, r, tenant)
	case len(parts) == 2 && parts[0] == "accounts":
		if r.Method != http.MethodGet {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		if !namePattern.MatchString(parts[1]) {
			writeError(w, problem(http.StatusBadRequest, "invalid"))
			return
		}
		l.getAccount(w, r, tenant, parts[1])
	case len(parts) == 1 && parts[0] == "transfers":
		if r.Method != http.MethodPost {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		l.postTransfer(w, r, tenant)
	case len(parts) == 3 && parts[0] == "transfers" && parts[2] == "reverse" && parts[1] != "":
		if r.Method != http.MethodPost {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		l.reverseTransfer(w, r, tenant, parts[1])
	case len(parts) == 1 && parts[0] == "batches":
		if r.Method != http.MethodPost {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		l.postBatch(w, r, tenant)
	case len(parts) == 1 && parts[0] == "holds":
		if r.Method != http.MethodPost {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		l.postHold(w, r, tenant)
	case len(parts) == 3 && parts[0] == "holds" && parts[1] != "" && (parts[2] == "capture" || parts[2] == "release"):
		if r.Method != http.MethodPost {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		if parts[2] == "capture" {
			l.captureHold(w, r, tenant, parts[1])
		} else {
			l.releaseHold(w, r, tenant, parts[1])
		}
	case len(parts) == 1 && parts[0] == "entries":
		if r.Method != http.MethodGet {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		l.getEntries(w, r, tenant)
	case len(parts) == 1 && parts[0] == "summary":
		if r.Method != http.MethodGet {
			writeError(w, problem(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		l.getSummary(w, r, tenant)
	default:
		writeError(w, problem(http.StatusNotFound, "not_found"))
	}
}

func requestTenant(r *http.Request) (string, bool) {
	values := r.Header.Values("X-Tenant")
	if len(values) != 1 || !namePattern.MatchString(values[0]) {
		return "", false
	}
	return values[0], true
}

func parseBody(r *http.Request, target any) bool {
	if r.Body == nil {
		return false
	}
	body, err := io.ReadAll(http.MaxBytesReader(nil, r.Body, 1<<20))
	if err != nil {
		return false
	}
	trimmed := bytes.TrimSpace(body)
	if len(trimmed) == 0 || trimmed[0] != '{' {
		return false
	}
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.DisallowUnknownFields()
	if err := dec.Decode(target); err != nil {
		return false
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		return false
	}
	return true
}

func (l *Ledger) writeInvalidBody(w http.ResponseWriter, r *http.Request, tenant, key string) {
	var exists int
	// Invalid input cannot be identical to a body that previously succeeded.
	// Check the key so such a reuse reports the required conflict code.
	// The caller has already validated the tenant and idempotency-key syntax.
	// DB failures still surface as server errors rather than hiding durability loss.
	err := l.db.QueryRowContext(r.Context(), "SELECT 1 FROM idempotency WHERE tenant=? AND key=?", tenant, key).Scan(&exists)
	if err == nil {
		writeError(w, problem(http.StatusConflict, "idempotency_conflict"))
		return
	}
	if !errors.Is(err, sql.ErrNoRows) {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	writeError(w, problem(http.StatusBadRequest, "invalid"))
}

func canonical(value any) (string, bool) {
	b, err := json.Marshal(value)
	if err != nil {
		return "", false
	}
	return string(b), true
}

func addVersion(m map[string]any, key string, v OptionalVersion) {
	if v.Set {
		m[key] = v.Value
	}
}

func validWriteHeaders(r *http.Request) (string, bool) {
	values := r.Header.Values("Idempotency-Key")
	if len(values) != 1 || !keyPattern.MatchString(values[0]) {
		return "", false
	}
	return values[0], true
}

type writeFn func(*sql.Conn) (int, any, *apiError, error)

func (l *Ledger) idempotent(w http.ResponseWriter, r *http.Request, tenant, key, body string, fn writeFn) {
	ctx := r.Context()
	conn, err := l.beginWrite(ctx)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	defer conn.Close()
	committed := false
	defer func() {
		if !committed {
			_, _ = conn.ExecContext(context.Background(), "ROLLBACK")
		}
	}()
	var oldPath, oldBody, oldResult string
	var oldStatus int
	err = conn.QueryRowContext(ctx, "SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?", tenant, key).
		Scan(&oldPath, &oldBody, &oldStatus, &oldResult)
	if err == nil {
		_, _ = conn.ExecContext(ctx, "ROLLBACK")
		committed = true
		if oldPath != r.URL.Path || oldBody != body {
			writeError(w, problem(http.StatusConflict, "idempotency_conflict"))
			return
		}
		writeRawJSON(w, oldStatus, []byte(oldResult))
		return
	}
	if !errors.Is(err, sql.ErrNoRows) {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	status, payload, apiErr, err := fn(conn)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	if apiErr != nil {
		writeError(w, apiErr)
		return
	}
	result, err := json.Marshal(payload)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	if _, err := conn.ExecContext(ctx, `INSERT INTO idempotency(tenant,key,path,body,status,result) VALUES(?,?,?,?,?,?)`, tenant, key, r.URL.Path, body, status, string(result)); err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	if _, err := conn.ExecContext(ctx, "COMMIT"); err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	committed = true
	writeRawJSON(w, status, result)
}

type accountCreateRequest struct {
	Name    string `json:"name"`
	Opening *int64 `json:"opening"`
}

func (l *Ledger) postAccount(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := validWriteHeaders(r)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	var req accountCreateRequest
	if !parseBody(r, &req) || !namePattern.MatchString(req.Name) || req.Opening == nil || *req.Opening < 0 || *req.Opening > 1_000_000_000 {
		l.writeInvalidBody(w, r, tenant, key)
		return
	}
	body, _ := canonical(map[string]any{"name": req.Name, "opening": *req.Opening})
	l.idempotent(w, r, tenant, key, body, func(c *sql.Conn) (int, any, *apiError, error) {
		if _, found, err := currentAccount(r.Context(), c, tenant, req.Name); err != nil {
			return 0, nil, nil, err
		} else if found {
			return 0, nil, problem(http.StatusConflict, "exists"), nil
		}
		if _, err := c.ExecContext(r.Context(), "INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,?,1)", tenant, req.Name, *req.Opening, 0); err != nil {
			return 0, nil, nil, err
		}
		opID := "opening-" + uuidString()
		if err := insertEntry(r.Context(), c, Entry{Account: req.Name, Kind: "opening", BalanceDelta: *req.Opening, OperationID: opID}, tenant); err != nil {
			return 0, nil, nil, err
		}
		a, _, err := currentAccount(r.Context(), c, tenant, req.Name)
		if err != nil {
			return 0, nil, nil, err
		}
		return http.StatusCreated, map[string]any{"account": publicAccount(a)}, nil, nil
	})
}

func (l *Ledger) getAccount(w http.ResponseWriter, r *http.Request, tenant, name string) {
	a, found, err := readAccount(r.Context(), l.db, tenant, name)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	if !found {
		writeError(w, problem(http.StatusNotFound, "not_found"))
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"account": a})
}

type transferRequest struct {
	From        string          `json:"from"`
	To          string          `json:"to"`
	Amount      int64           `json:"amount"`
	FromVersion OptionalVersion `json:"from_version"`
	ToVersion   OptionalVersion `json:"to_version"`
}

func (req transferRequest) valid() bool {
	return namePattern.MatchString(req.From) && namePattern.MatchString(req.To) && req.From != req.To && req.Amount >= 1 && req.Amount <= 1_000_000_000 && validVersion(req.FromVersion) && validVersion(req.ToVersion)
}

func validVersion(v OptionalVersion) bool { return !v.Set || v.Value > 0 }

func (req transferRequest) semantic() map[string]any {
	m := map[string]any{"from": req.From, "to": req.To, "amount": req.Amount}
	addVersion(m, "from_version", req.FromVersion)
	addVersion(m, "to_version", req.ToVersion)
	return m
}

func (l *Ledger) postTransfer(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := validWriteHeaders(r)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	var req transferRequest
	if !parseBody(r, &req) || !req.valid() {
		l.writeInvalidBody(w, r, tenant, key)
		return
	}
	body, _ := canonical(req.semantic())
	l.idempotent(w, r, tenant, key, body, func(c *sql.Conn) (int, any, *apiError, error) {
		id, err := uniqueID(r.Context(), c, tenant)
		if err != nil {
			return 0, nil, nil, err
		}
		tr, accounts, apiErr, err := applyTransfer(r.Context(), c, tenant, req, id, "transfer", nil)
		if err != nil || apiErr != nil {
			return 0, nil, apiErr, err
		}
		return http.StatusCreated, map[string]any{"transfer": tr, "accounts": accounts}, nil, nil
	})
}

type batchRequest struct {
	Transfers []transferRequest `json:"transfers"`
}

func (l *Ledger) postBatch(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := validWriteHeaders(r)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	var req batchRequest
	if !parseBody(r, &req) || len(req.Transfers) < 1 || len(req.Transfers) > 20 {
		l.writeInvalidBody(w, r, tenant, key)
		return
	}
	semanticTransfers := make([]map[string]any, 0, len(req.Transfers))
	for _, transfer := range req.Transfers {
		if !transfer.valid() {
			l.writeInvalidBody(w, r, tenant, key)
			return
		}
		semanticTransfers = append(semanticTransfers, transfer.semantic())
	}
	body, _ := canonical(map[string]any{"transfers": semanticTransfers})
	l.idempotent(w, r, tenant, key, body, func(c *sql.Conn) (int, any, *apiError, error) {
		transfers := make([]Transfer, 0, len(req.Transfers))
		touched := make(map[string]accountState)
		for _, transferReq := range req.Transfers {
			id, err := uniqueID(r.Context(), c, tenant)
			if err != nil {
				return 0, nil, nil, err
			}
			tr, _, apiErr, err := applyTransfer(r.Context(), c, tenant, transferReq, id, "transfer", nil)
			if err != nil || apiErr != nil {
				return 0, nil, apiErr, err
			}
			transfers = append(transfers, tr)
			touched[transferReq.From] = accountState{Name: transferReq.From, Tenant: tenant}
			touched[transferReq.To] = accountState{Name: transferReq.To, Tenant: tenant}
		}
		states := make(map[string]accountState, len(touched))
		for name := range touched {
			a, found, err := currentAccount(r.Context(), c, tenant, name)
			if err != nil {
				return 0, nil, nil, err
			}
			if !found {
				return 0, nil, problem(http.StatusNotFound, "not_found"), nil
			}
			states[name] = a
		}
		return http.StatusCreated, map[string]any{"transfers": transfers, "accounts": sortedAccounts(states)}, nil, nil
	})
}

func applyTransfer(ctx context.Context, c *sql.Conn, tenant string, req transferRequest, id, kind string, legacyID *int64) (Transfer, []Account, *apiError, error) {
	from, fromFound, err := currentAccount(ctx, c, tenant, req.From)
	if err != nil {
		return Transfer{}, nil, nil, err
	}
	to, toFound, err := currentAccount(ctx, c, tenant, req.To)
	if err != nil {
		return Transfer{}, nil, nil, err
	}
	if !fromFound || !toFound {
		return Transfer{}, nil, problem(http.StatusNotFound, "not_found"), nil
	}
	if apiErr := checkVersion(req.FromVersion, from.Version); apiErr != nil {
		return Transfer{}, nil, apiErr, nil
	}
	if apiErr := checkVersion(req.ToVersion, to.Version); apiErr != nil {
		return Transfer{}, nil, apiErr, nil
	}
	if from.Balance-from.Reserved < req.Amount {
		return Transfer{}, nil, problem(http.StatusConflict, "insufficient"), nil
	}
	if req.Amount > maxBalance-to.Balance {
		return Transfer{}, nil, problem(http.StatusConflict, "insufficient"), nil
	}
	from.Balance -= req.Amount
	to.Balance += req.Amount
	if err := from.advance(); err != nil {
		return Transfer{}, nil, nil, err
	}
	if err := to.advance(); err != nil {
		return Transfer{}, nil, nil, err
	}
	if err := saveAccount(ctx, c, from); err != nil {
		return Transfer{}, nil, nil, err
	}
	if err := saveAccount(ctx, c, to); err != nil {
		return Transfer{}, nil, nil, err
	}
	if _, err := c.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,legacy_id) VALUES(?,?,?,?,?,0,?)`, tenant, id, req.From, req.To, req.Amount, nullableInt(legacyID)); err != nil {
		return Transfer{}, nil, nil, err
	}
	if err := insertEntry(ctx, c, Entry{Account: req.From, Kind: kind, BalanceDelta: -req.Amount, OperationID: id, LegacyID: legacyID}, tenant); err != nil {
		return Transfer{}, nil, nil, err
	}
	if err := insertEntry(ctx, c, Entry{Account: req.To, Kind: kind, BalanceDelta: req.Amount, OperationID: id, LegacyID: legacyID}, tenant); err != nil {
		return Transfer{}, nil, nil, err
	}
	tr := Transfer{ID: id, From: req.From, To: req.To, Amount: req.Amount, Reversed: false, LegacyID: legacyID}
	return tr, []Account{publicAccount(from), publicAccount(to)}, nil, nil
}

func checkVersion(v OptionalVersion, current int64) *apiError {
	if v.Set && current != v.Value {
		return problem(http.StatusConflict, "version_conflict")
	}
	return nil
}

type holdRequest struct {
	Account string          `json:"account"`
	Amount  int64           `json:"amount"`
	Version OptionalVersion `json:"version"`
}

func (l *Ledger) postHold(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := validWriteHeaders(r)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	var req holdRequest
	if !parseBody(r, &req) || !namePattern.MatchString(req.Account) || req.Amount < 1 || req.Amount > 1_000_000_000 || !validVersion(req.Version) {
		l.writeInvalidBody(w, r, tenant, key)
		return
	}
	semantic := map[string]any{"account": req.Account, "amount": req.Amount}
	addVersion(semantic, "version", req.Version)
	body, _ := canonical(semantic)
	l.idempotent(w, r, tenant, key, body, func(c *sql.Conn) (int, any, *apiError, error) {
		a, found, err := currentAccount(r.Context(), c, tenant, req.Account)
		if err != nil {
			return 0, nil, nil, err
		}
		if !found {
			return 0, nil, problem(http.StatusNotFound, "not_found"), nil
		}
		if apiErr := checkVersion(req.Version, a.Version); apiErr != nil {
			return 0, nil, apiErr, nil
		}
		if a.Balance-a.Reserved < req.Amount {
			return 0, nil, problem(http.StatusConflict, "insufficient"), nil
		}
		id, err := uniqueID(r.Context(), c, tenant)
		if err != nil {
			return 0, nil, nil, err
		}
		a.Reserved += req.Amount
		if err := a.advance(); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), c, a); err != nil {
			return 0, nil, nil, err
		}
		if _, err := c.ExecContext(r.Context(), `INSERT INTO holds(tenant,id,account,amount,state) VALUES(?,?,?,?, 'active')`, tenant, id, req.Account, req.Amount); err != nil {
			return 0, nil, nil, err
		}
		if err := insertEntry(r.Context(), c, Entry{Account: req.Account, Kind: "hold", ReservedDelta: req.Amount, OperationID: id}, tenant); err != nil {
			return 0, nil, nil, err
		}
		h := Hold{ID: id, Account: req.Account, Amount: req.Amount, State: "active"}
		return http.StatusCreated, map[string]any{"hold": h, "account": publicAccount(a)}, nil, nil
	})
}

type captureRequest struct {
	To          string          `json:"to"`
	FromVersion OptionalVersion `json:"from_version"`
	ToVersion   OptionalVersion `json:"to_version"`
}

func (req captureRequest) semantic() map[string]any {
	m := map[string]any{"to": req.To}
	addVersion(m, "from_version", req.FromVersion)
	addVersion(m, "to_version", req.ToVersion)
	return m
}

func (l *Ledger) captureHold(w http.ResponseWriter, r *http.Request, tenant, holdID string) {
	key, ok := validWriteHeaders(r)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	var req captureRequest
	if !parseBody(r, &req) || !namePattern.MatchString(req.To) || !validVersion(req.FromVersion) || !validVersion(req.ToVersion) {
		l.writeInvalidBody(w, r, tenant, key)
		return
	}
	body, _ := canonical(req.semantic())
	l.idempotent(w, r, tenant, key, body, func(c *sql.Conn) (int, any, *apiError, error) {
		hold, found, err := scanHold(r.Context(), c, tenant, holdID)
		if err != nil {
			return 0, nil, nil, err
		}
		if !found {
			return 0, nil, problem(http.StatusNotFound, "not_found"), nil
		}
		if hold.State != "active" {
			return 0, nil, problem(http.StatusConflict, "terminal"), nil
		}
		if hold.Account == req.To {
			return 0, nil, problem(http.StatusBadRequest, "invalid"), nil
		}
		from, fromFound, err := currentAccount(r.Context(), c, tenant, hold.Account)
		if err != nil {
			return 0, nil, nil, err
		}
		to, toFound, err := currentAccount(r.Context(), c, tenant, req.To)
		if err != nil {
			return 0, nil, nil, err
		}
		if !fromFound || !toFound {
			return 0, nil, problem(http.StatusNotFound, "not_found"), nil
		}
		if apiErr := checkVersion(req.FromVersion, from.Version); apiErr != nil {
			return 0, nil, apiErr, nil
		}
		if apiErr := checkVersion(req.ToVersion, to.Version); apiErr != nil {
			return 0, nil, apiErr, nil
		}
		if from.Reserved < hold.Amount || hold.Amount > maxBalance-to.Balance {
			return 0, nil, problem(http.StatusConflict, "insufficient"), nil
		}
		id, err := uniqueID(r.Context(), c, tenant)
		if err != nil {
			return 0, nil, nil, err
		}
		from.Reserved -= hold.Amount
		from.Balance -= hold.Amount
		to.Balance += hold.Amount
		if err := from.advance(); err != nil {
			return 0, nil, nil, err
		}
		if err := to.advance(); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), c, from); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), c, to); err != nil {
			return 0, nil, nil, err
		}
		if _, err := c.ExecContext(r.Context(), `INSERT INTO transfers(tenant,id,source,target,amount,reversed) VALUES(?,?,?,?,?,0)`, tenant, id, hold.Account, req.To, hold.Amount); err != nil {
			return 0, nil, nil, err
		}
		if err := insertEntry(r.Context(), c, Entry{Account: hold.Account, Kind: "capture", BalanceDelta: -hold.Amount, ReservedDelta: -hold.Amount, OperationID: id}, tenant); err != nil {
			return 0, nil, nil, err
		}
		if err := insertEntry(r.Context(), c, Entry{Account: req.To, Kind: "capture", BalanceDelta: hold.Amount, OperationID: id}, tenant); err != nil {
			return 0, nil, nil, err
		}
		if _, err := c.ExecContext(r.Context(), "UPDATE holds SET state='captured' WHERE tenant=? AND id=?", tenant, holdID); err != nil {
			return 0, nil, nil, err
		}
		hold.State = "captured"
		tr := Transfer{ID: id, From: hold.Account, To: req.To, Amount: hold.Amount, Reversed: false}
		return http.StatusOK, map[string]any{"hold": hold.Hold, "transfer": tr, "accounts": []Account{publicAccount(from), publicAccount(to)}}, nil, nil
	})
}

type releaseRequest struct {
	Version OptionalVersion `json:"version"`
}

func (l *Ledger) releaseHold(w http.ResponseWriter, r *http.Request, tenant, holdID string) {
	key, ok := validWriteHeaders(r)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	var req releaseRequest
	if !parseBody(r, &req) || !validVersion(req.Version) {
		l.writeInvalidBody(w, r, tenant, key)
		return
	}
	semantic := map[string]any{}
	addVersion(semantic, "version", req.Version)
	body, _ := canonical(semantic)
	l.idempotent(w, r, tenant, key, body, func(c *sql.Conn) (int, any, *apiError, error) {
		hold, found, err := scanHold(r.Context(), c, tenant, holdID)
		if err != nil {
			return 0, nil, nil, err
		}
		if !found {
			return 0, nil, problem(http.StatusNotFound, "not_found"), nil
		}
		if hold.State != "active" {
			return 0, nil, problem(http.StatusConflict, "terminal"), nil
		}
		a, accountFound, err := currentAccount(r.Context(), c, tenant, hold.Account)
		if err != nil {
			return 0, nil, nil, err
		}
		if !accountFound {
			return 0, nil, problem(http.StatusNotFound, "not_found"), nil
		}
		if apiErr := checkVersion(req.Version, a.Version); apiErr != nil {
			return 0, nil, apiErr, nil
		}
		if a.Reserved < hold.Amount {
			return 0, nil, problem(http.StatusConflict, "insufficient"), nil
		}
		a.Reserved -= hold.Amount
		if err := a.advance(); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), c, a); err != nil {
			return 0, nil, nil, err
		}
		if err := insertEntry(r.Context(), c, Entry{Account: hold.Account, Kind: "release", ReservedDelta: -hold.Amount, OperationID: holdID}, tenant); err != nil {
			return 0, nil, nil, err
		}
		if _, err := c.ExecContext(r.Context(), "UPDATE holds SET state='released' WHERE tenant=? AND id=?", tenant, holdID); err != nil {
			return 0, nil, nil, err
		}
		hold.State = "released"
		return http.StatusOK, map[string]any{"hold": hold.Hold, "account": publicAccount(a)}, nil, nil
	})
}

type reverseRequest struct {
	FromVersion OptionalVersion `json:"from_version"`
	ToVersion   OptionalVersion `json:"to_version"`
}

func (l *Ledger) reverseTransfer(w http.ResponseWriter, r *http.Request, tenant, transferID string) {
	key, ok := validWriteHeaders(r)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	var req reverseRequest
	if !parseBody(r, &req) || !validVersion(req.FromVersion) || !validVersion(req.ToVersion) {
		l.writeInvalidBody(w, r, tenant, key)
		return
	}
	semantic := map[string]any{}
	addVersion(semantic, "from_version", req.FromVersion)
	addVersion(semantic, "to_version", req.ToVersion)
	body, _ := canonical(semantic)
	l.idempotent(w, r, tenant, key, body, func(c *sql.Conn) (int, any, *apiError, error) {
		original, found, err := scanTransfer(r.Context(), c, tenant, transferID)
		if err != nil {
			return 0, nil, nil, err
		}
		if !found {
			return 0, nil, problem(http.StatusNotFound, "not_found"), nil
		}
		if original.ReversalOf != "" || original.Reversed {
			return 0, nil, problem(http.StatusConflict, "terminal"), nil
		}
		from, fromFound, err := currentAccount(r.Context(), c, tenant, original.From)
		if err != nil {
			return 0, nil, nil, err
		}
		to, toFound, err := currentAccount(r.Context(), c, tenant, original.To)
		if err != nil {
			return 0, nil, nil, err
		}
		if !fromFound || !toFound {
			return 0, nil, problem(http.StatusNotFound, "not_found"), nil
		}
		if apiErr := checkVersion(req.FromVersion, from.Version); apiErr != nil {
			return 0, nil, apiErr, nil
		}
		if apiErr := checkVersion(req.ToVersion, to.Version); apiErr != nil {
			return 0, nil, apiErr, nil
		}
		if to.Balance-to.Reserved < original.Amount {
			return 0, nil, problem(http.StatusConflict, "insufficient"), nil
		}
		if original.Amount > maxBalance-from.Balance {
			return 0, nil, problem(http.StatusConflict, "insufficient"), nil
		}
		id, err := uniqueID(r.Context(), c, tenant)
		if err != nil {
			return 0, nil, nil, err
		}
		to.Balance -= original.Amount
		from.Balance += original.Amount
		if err := from.advance(); err != nil {
			return 0, nil, nil, err
		}
		if err := to.advance(); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), c, from); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), c, to); err != nil {
			return 0, nil, nil, err
		}
		if _, err := c.ExecContext(r.Context(), `INSERT INTO transfers(tenant,id,source,target,amount,reversed,reversal_of) VALUES(?,?,?,?,?,0,?)`, tenant, id, original.To, original.From, original.Amount, original.ID); err != nil {
			return 0, nil, nil, err
		}
		if err := insertEntry(r.Context(), c, Entry{Account: original.To, Kind: "reversal", BalanceDelta: -original.Amount, OperationID: id}, tenant); err != nil {
			return 0, nil, nil, err
		}
		if err := insertEntry(r.Context(), c, Entry{Account: original.From, Kind: "reversal", BalanceDelta: original.Amount, OperationID: id}, tenant); err != nil {
			return 0, nil, nil, err
		}
		if _, err := c.ExecContext(r.Context(), "UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?", tenant, original.ID); err != nil {
			return 0, nil, nil, err
		}
		original.Reversed = true
		reversal := Transfer{ID: id, From: original.To, To: original.From, Amount: original.Amount, Reversed: false}
		return http.StatusOK, map[string]any{"transfer": original.Transfer, "reversal": reversal, "accounts": []Account{publicAccount(from), publicAccount(to)}}, nil, nil
	})
}

func uniqueID(ctx context.Context, c *sql.Conn, tenant string) (string, error) {
	for i := 0; i < 8; i++ {
		id := uuidString()
		var count int
		if err := c.QueryRowContext(ctx, `SELECT
			(SELECT COUNT(*) FROM transfers WHERE tenant=? AND id=?) +
			(SELECT COUNT(*) FROM holds WHERE tenant=? AND id=?)`, tenant, id, tenant, id).Scan(&count); err != nil {
			return "", err
		}
		if count == 0 {
			return id, nil
		}
	}
	return "", fmt.Errorf("could not allocate unique identifier")
}

func uuidString() string { return uuid.NewString() }

type entriesResponse struct {
	Entries   []Entry `json:"entries"`
	Snapshot  int64   `json:"snapshot"`
	NextAfter int64   `json:"next_after"`
	HasMore   bool    `json:"has_more"`
}

func queryValues(r *http.Request, allowed map[string]bool) (url.Values, bool) {
	values, err := url.ParseQuery(r.URL.RawQuery)
	if err != nil {
		return nil, false
	}
	for key, vals := range values {
		if !allowed[key] || len(vals) != 1 {
			return nil, false
		}
	}
	return values, true
}

func parseNonnegative(values url.Values, key string, fallback int64) (int64, bool) {
	text, present := values[key]
	if !present {
		return fallback, true
	}
	n, err := strconv.ParseInt(text[0], 10, 64)
	return n, err == nil && n >= 0
}

func (l *Ledger) getEntries(w http.ResponseWriter, r *http.Request, tenant string) {
	values, ok := queryValues(r, map[string]bool{"after": true, "limit": true, "snapshot": true})
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	after, ok := parseNonnegative(values, "after", 0)
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	limit := int64(50)
	if raw, present := values["limit"]; present {
		limit, _ = strconv.ParseInt(raw[0], 10, 64)
		if limit < 1 || limit > 100 {
			writeError(w, problem(http.StatusBadRequest, "invalid"))
			return
		}
	}
	current, err := l.maxSequence(r.Context(), tenant)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	snapshot := current
	if raw, present := values["snapshot"]; present {
		snapshot, err = strconv.ParseInt(raw[0], 10, 64)
		if err != nil || snapshot < 0 || snapshot > current {
			writeError(w, problem(http.StatusBadRequest, "invalid"))
			return
		}
	}
	if after > snapshot {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	rows, err := l.db.QueryContext(r.Context(), `SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id
		FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, tenant, after, snapshot, limit+1)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	defer rows.Close()
	entries := make([]Entry, 0, limit+1)
	for rows.Next() {
		var e Entry
		var legacy sql.NullInt64
		if err := rows.Scan(&e.Seq, &e.Account, &e.Kind, &e.BalanceDelta, &e.ReservedDelta, &e.OperationID, &legacy); err != nil {
			writeError(w, problem(http.StatusInternalServerError, "internal"))
			return
		}
		if legacy.Valid {
			e.LegacyID = &legacy.Int64
		}
		entries = append(entries, e)
	}
	if err := rows.Err(); err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	hasMore := int64(len(entries)) > limit
	if hasMore {
		entries = entries[:limit]
	}
	next := after
	if len(entries) != 0 {
		next = entries[len(entries)-1].Seq
	}
	writeJSON(w, http.StatusOK, entriesResponse{Entries: entries, Snapshot: snapshot, NextAfter: next, HasMore: hasMore})
}

type summaryTotals struct {
	Balance   json.Number `json:"balance"`
	Reserved  json.Number `json:"reserved"`
	Available json.Number `json:"available"`
}

func (l *Ledger) getSummary(w http.ResponseWriter, r *http.Request, tenant string) {
	values, ok := queryValues(r, map[string]bool{"snapshot": true})
	if !ok {
		writeError(w, problem(http.StatusBadRequest, "invalid"))
		return
	}
	current, err := l.maxSequence(r.Context(), tenant)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	snapshot := current
	if raw, present := values["snapshot"]; present {
		snapshot, err = strconv.ParseInt(raw[0], 10, 64)
		if err != nil || snapshot < 0 || snapshot > current {
			writeError(w, problem(http.StatusBadRequest, "invalid"))
			return
		}
	}
	rows, err := l.db.QueryContext(r.Context(), `SELECT account,balance_delta,reserved_delta FROM entries
		WHERE tenant=? AND seq<=? ORDER BY seq`, tenant, snapshot)
	if err != nil {
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	type totals struct{ balance, reserved int64 }
	byName := make(map[string]totals)
	var entryCount int64
	for rows.Next() {
		var name string
		var balanceDelta, reservedDelta int64
		if err := rows.Scan(&name, &balanceDelta, &reservedDelta); err != nil {
			rows.Close()
			writeError(w, problem(http.StatusInternalServerError, "internal"))
			return
		}
		state := byName[name]
		if !addInt64(&state.balance, balanceDelta) || !addInt64(&state.reserved, reservedDelta) || state.balance < 0 || state.balance > maxBalance || state.reserved < 0 || state.reserved > state.balance {
			rows.Close()
			writeError(w, problem(http.StatusInternalServerError, "internal"))
			return
		}
		byName[name] = state
		entryCount++
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		writeError(w, problem(http.StatusInternalServerError, "internal"))
		return
	}
	rows.Close()
	names := make([]string, 0, len(byName))
	for name := range byName {
		names = append(names, name)
	}
	sort.Strings(names)
	accounts := make([]SummaryAccount, 0, len(names))
	var totalBalance, totalReserved, totalAvailable big.Int
	for _, name := range names {
		state := byName[name]
		available := state.balance - state.reserved
		accounts = append(accounts, SummaryAccount{Name: name, Balance: state.balance, Reserved: state.reserved, Available: available})
		totalBalance.Add(&totalBalance, big.NewInt(state.balance))
		totalReserved.Add(&totalReserved, big.NewInt(state.reserved))
		totalAvailable.Add(&totalAvailable, big.NewInt(available))
	}
	response := map[string]any{
		"snapshot":    snapshot,
		"accounts":    accounts,
		"totals":      summaryTotals{Balance: json.Number(totalBalance.String()), Reserved: json.Number(totalReserved.String()), Available: json.Number(totalAvailable.String())},
		"entry_count": entryCount,
	}
	writeJSON(w, http.StatusOK, response)
}

func addInt64(dst *int64, delta int64) bool {
	if (delta > 0 && *dst > math.MaxInt64-delta) || (delta < 0 && *dst < math.MinInt64-delta) {
		return false
	}
	*dst += delta
	return true
}
