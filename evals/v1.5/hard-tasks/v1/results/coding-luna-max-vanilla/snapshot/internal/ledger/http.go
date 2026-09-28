package ledger

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
)

var namePattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type apiError struct {
	status int
	code   string
}

func apiFail(status int, code string) *apiError { return &apiError{status: status, code: code} }

type Handler struct{ db *sql.DB }

func NewHandler(db *sql.DB) http.Handler { return &Handler{db: db} }

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.EscapedPath()
	if path == "/health" {
		if r.Method != http.MethodGet {
			writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
			return
		}
		var version int
		if err := h.db.QueryRowContext(r.Context(), "PRAGMA user_version").Scan(&version); err != nil || version != 2 {
			writeAPIError(w, apiFail(http.StatusServiceUnavailable, "unavailable"))
			return
		}
		var one int
		if err := h.db.QueryRowContext(r.Context(), "SELECT 1 FROM accounts LIMIT 1").Scan(&one); err != nil && !errors.Is(err, sql.ErrNoRows) {
			writeAPIError(w, apiFail(http.StatusServiceUnavailable, "unavailable"))
			return
		}
		writeJSON(w, http.StatusOK, struct {
			OK bool `json:"ok"`
		}{true})
		return
	}
	tenant := r.Header.Get("X-Tenant")
	if !validName(tenant) {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	parts := splitPath(path)
	if h.route(w, r, tenant, path, parts) {
		return
	}
	writeAPIError(w, apiFail(http.StatusNotFound, "not_found"))
}

func splitPath(path string) []string {
	if path == "/" || path == "" || strings.HasSuffix(path, "/") {
		return nil
	}
	return strings.Split(strings.TrimPrefix(path, "/"), "/")
}

func decodeSegment(s string) (string, bool) {
	value, err := url.PathUnescape(s)
	return value, err == nil
}

func (h *Handler) route(w http.ResponseWriter, r *http.Request, tenant, path string, p []string) bool {
	if path == "/accounts" && len(p) == 1 {
		if r.Method != http.MethodPost {
			writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
			return true
		}
		mutate[createAccountRequest](h, w, r, tenant, path, validateCreateAccount, func(tx *writeTx, req createAccountRequest) (int, any, *apiError, error) {
			return createAccount(tx, tenant, req)
		})
		return true
	}
	if path == "/transfers" && len(p) == 1 {
		if r.Method != http.MethodPost {
			writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
			return true
		}
		mutate[transferRequest](h, w, r, tenant, path, validateTransfer, func(tx *writeTx, req transferRequest) (int, any, *apiError, error) {
			return createTransfer(tx, tenant, req)
		})
		return true
	}
	if path == "/batches" && len(p) == 1 {
		if r.Method != http.MethodPost {
			writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
			return true
		}
		mutate[batchRequest](h, w, r, tenant, path, validateBatch, func(tx *writeTx, req batchRequest) (int, any, *apiError, error) {
			return createBatch(tx, tenant, req)
		})
		return true
	}
	if path == "/holds" && len(p) == 1 {
		if r.Method != http.MethodPost {
			writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
			return true
		}
		mutate[holdRequest](h, w, r, tenant, path, validateHold, func(tx *writeTx, req holdRequest) (int, any, *apiError, error) {
			return createHold(tx, tenant, req)
		})
		return true
	}
	if len(p) == 2 && p[0] == "accounts" && r.Method == http.MethodGet {
		name, ok := decodeSegment(p[1])
		if !ok || !validName(name) {
			writeAPIError(w, apiFail(http.StatusNotFound, "not_found"))
			return true
		}
		a, found, err := getAccount(r.Context(), h.db, tenant, name)
		if err != nil {
			writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		} else if !found {
			writeAPIError(w, apiFail(http.StatusNotFound, "not_found"))
		} else {
			writeJSON(w, http.StatusOK, struct {
				Account accountState `json:"account"`
			}{a})
		}
		return true
	}
	if path == "/entries" && len(p) == 1 && r.Method == http.MethodGet {
		h.getEntries(w, r, tenant)
		return true
	}
	if path == "/summary" && len(p) == 1 && r.Method == http.MethodGet {
		h.getSummary(w, r, tenant)
		return true
	}
	if len(p) == 3 && p[0] == "holds" && (p[2] == "capture" || p[2] == "release") {
		id, ok := decodeSegment(p[1])
		if !ok || id == "" {
			writeAPIError(w, apiFail(http.StatusNotFound, "not_found"))
			return true
		}
		if r.Method != http.MethodPost {
			writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
			return true
		}
		if p[2] == "capture" {
			endpoint := func(tx *writeTx, req captureRequest) (int, any, *apiError, error) {
				return captureHold(tx, tenant, id, req)
			}
			mutate[captureRequest](h, w, r, tenant, path, validateCapture, endpoint)
		} else {
			endpoint := func(tx *writeTx, req releaseRequest) (int, any, *apiError, error) {
				return releaseHold(tx, tenant, id, req)
			}
			mutate[releaseRequest](h, w, r, tenant, path, validateRelease, endpoint)
		}
		return true
	}
	if len(p) == 3 && p[0] == "transfers" && p[2] == "reverse" {
		id, ok := decodeSegment(p[1])
		if !ok || id == "" {
			writeAPIError(w, apiFail(http.StatusNotFound, "not_found"))
			return true
		}
		if r.Method != http.MethodPost {
			writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
			return true
		}
		endpoint := func(tx *writeTx, req reverseRequest) (int, any, *apiError, error) {
			return reverseTransfer(tx, tenant, id, req)
		}
		mutate[reverseRequest](h, w, r, tenant, path, func(reverseRequest) *apiError { return nil }, endpoint)
		return true
	}
	// A known resource path with another method may use 405. Shape recognition
	// stays exact so extra path components never resolve as an object ID.
	if (len(p) == 2 && p[0] == "accounts") || path == "/entries" || path == "/summary" ||
		path == "/accounts" || path == "/transfers" || path == "/batches" || path == "/holds" {
		writeAPIError(w, apiFail(http.StatusMethodNotAllowed, "not_found"))
		return true
	}
	return false
}

func mutate[T any](h *Handler, w http.ResponseWriter, r *http.Request, tenant, path string, validate func(T) *apiError, operation func(*writeTx, T) (int, any, *apiError, error)) {
	key := r.Header.Get("Idempotency-Key")
	if !keyPattern.MatchString(key) {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	body, readErr := io.ReadAll(io.LimitReader(r.Body, 1<<20+1))
	tooLarge := len(body) > 1<<20
	if tooLarge {
		body = body[:1<<20]
	}
	tx, err := beginWrite(r.Context(), h.db)
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	defer tx.rollback()
	var storedPath string
	var storedBody, storedResult []byte
	var storedStatus int
	err = tx.conn.QueryRowContext(r.Context(), "SELECT path,body,status,response FROM idempotency WHERE tenant=? AND key=?", tenant, key).Scan(&storedPath, &storedBody, &storedStatus, &storedResult)
	if err == nil {
		canonical, canonicalErr := canonicalBody(body)
		if readErr == nil && !tooLarge && canonicalErr == nil && storedPath == path && bytes.Equal(storedBody, canonical) {
			tx.rollback()
			writeRawJSON(w, storedStatus, storedResult)
			return
		}
		tx.rollback()
		writeAPIError(w, apiFail(http.StatusConflict, "idempotency_conflict"))
		return
	}
	if !errors.Is(err, sql.ErrNoRows) {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	if readErr != nil || tooLarge || len(bytes.TrimSpace(body)) == 0 {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	var req T
	canonical, err := decodeStrict(body, &req)
	if err != nil {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	if invalid := validate(req); invalid != nil {
		writeAPIError(w, invalid)
		return
	}
	status, result, businessErr, err := operation(tx, req)
	if businessErr != nil {
		writeAPIError(w, businessErr)
		return
	}
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	resultJSON, err := json.Marshal(result)
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	if _, err := tx.conn.ExecContext(r.Context(), "INSERT INTO idempotency(tenant,key,path,body,status,response) VALUES(?,?,?,?,?,?)", tenant, key, path, canonical, status, resultJSON); err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	if err := tx.commit(); err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	writeRawJSON(w, status, resultJSON)
}

func canonicalBody(body []byte) ([]byte, error) {
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	if _, ok := value.(map[string]any); !ok {
		return nil, fmt.Errorf("body must be an object")
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return nil, fmt.Errorf("trailing JSON")
		}
		return nil, err
	}
	return json.Marshal(value)
}

func decodeStrict(body []byte, target any) ([]byte, error) {
	canonical, err := canonicalBody(body)
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return nil, err
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			return nil, fmt.Errorf("trailing JSON")
		}
		return nil, err
	}
	return canonical, nil
}

func writeRawJSON(w http.ResponseWriter, status int, body []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	body, err := json.Marshal(value)
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	writeRawJSON(w, status, body)
}

func writeAPIError(w http.ResponseWriter, e *apiError) {
	if e == nil {
		e = apiFail(http.StatusInternalServerError, "internal")
	}
	writeJSON(w, e.status, struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}{Error: struct {
		Code string `json:"code"`
	}{e.code}})
}

func validName(s string) bool { return namePattern.MatchString(s) }

type optionalVersion struct {
	Set   bool
	Value int64
}

func (v *optionalVersion) UnmarshalJSON(raw []byte) error {
	v.Set = true
	if bytes.Equal(bytes.TrimSpace(raw), []byte("null")) {
		return errors.New("version cannot be null")
	}
	if err := json.Unmarshal(raw, &v.Value); err != nil {
		return err
	}
	if v.Value <= 0 {
		return errors.New("version must be positive")
	}
	return nil
}

func validateVersion(a accountState, v optionalVersion) *apiError {
	if v.Set && v.Value != a.Version {
		return apiFail(http.StatusConflict, "version_conflict")
	}
	return nil
}

type createAccountRequest struct {
	Name    string `json:"name"`
	Opening *int64 `json:"opening"`
}

func validateCreateAccount(r createAccountRequest) *apiError {
	if !validName(r.Name) || r.Opening == nil || *r.Opening < 0 || *r.Opening > 1_000_000_000 {
		return apiFail(http.StatusBadRequest, "invalid")
	}
	return nil
}

func createAccount(tx *writeTx, tenant string, req createAccountRequest) (int, any, *apiError, error) {
	var exists int
	err := tx.conn.QueryRowContext(tx.ctx, "SELECT 1 FROM accounts WHERE tenant=? AND name=?", tenant, req.Name).Scan(&exists)
	if err == nil {
		return 0, nil, apiFail(http.StatusConflict, "exists"), nil
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return 0, nil, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,1)", tenant, req.Name, *req.Opening); err != nil {
		return 0, nil, nil, err
	}
	opID, err := allocateID(tx.ctx, tx.conn, tenant)
	if err != nil {
		return 0, nil, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, req.Name, "opening", *req.Opening, 0, opID, nil); err != nil {
		return 0, nil, nil, err
	}
	a, _, err := getAccount(tx.ctx, tx.conn, tenant, req.Name)
	return http.StatusCreated, struct {
		Account accountState `json:"account"`
	}{a}, nil, err
}

type transferRequest struct {
	From        string          `json:"from"`
	To          string          `json:"to"`
	Amount      int64           `json:"amount"`
	FromVersion optionalVersion `json:"from_version"`
	ToVersion   optionalVersion `json:"to_version"`
}

func validateTransfer(r transferRequest) *apiError {
	if !validName(r.From) || !validName(r.To) || r.From == r.To || r.Amount < 1 || r.Amount > 1_000_000_000 {
		return apiFail(http.StatusBadRequest, "invalid")
	}
	return nil
}

func createTransfer(tx *writeTx, tenant string, req transferRequest) (int, any, *apiError, error) {
	t, from, to, businessErr, err := postTransfer(tx, tenant, req.From, req.To, req.Amount, req.FromVersion, req.ToVersion, "transfer")
	if businessErr != nil || err != nil {
		return 0, nil, businessErr, err
	}
	return http.StatusCreated, struct {
		Transfer transferObject `json:"transfer"`
		Accounts []accountState `json:"accounts"`
	}{t, []accountState{from, to}}, nil, nil
}

func postTransfer(tx *writeTx, tenant, fromName, toName string, amount int64, fromVersion, toVersion optionalVersion, entryKind string) (transferObject, accountState, accountState, *apiError, error) {
	from, fromFound, err := getAccount(tx.ctx, tx.conn, tenant, fromName)
	if err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	to, toFound, err := getAccount(tx.ctx, tx.conn, tenant, toName)
	if err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	if !fromFound || !toFound {
		return transferObject{}, accountState{}, accountState{}, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if v := validateVersion(from, fromVersion); v != nil {
		return transferObject{}, accountState{}, accountState{}, v, nil
	}
	if v := validateVersion(to, toVersion); v != nil {
		return transferObject{}, accountState{}, accountState{}, v, nil
	}
	if from.Available < amount || to.Balance > maxAccountValue-amount {
		return transferObject{}, accountState{}, accountState{}, apiFail(http.StatusConflict, "insufficient"), nil
	}
	id, err := allocateID(tx.ctx, tx.conn, tenant)
	if err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "INSERT INTO transfers(tenant,id,source,target,amount,reversed) VALUES(?,?,?,?,?,0)", tenant, id, fromName, toName, amount); err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	from.Balance -= amount
	from.Version++
	from.Available = from.Balance - from.Reserved
	to.Balance += amount
	to.Version++
	to.Available = to.Balance - to.Reserved
	if err := updateAccount(tx.ctx, tx.conn, tenant, from); err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	if err := updateAccount(tx.ctx, tx.conn, tenant, to); err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, fromName, entryKind, -amount, 0, id, nil); err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, toName, entryKind, amount, 0, id, nil); err != nil {
		return transferObject{}, accountState{}, accountState{}, nil, err
	}
	return transferObject{ID: id, From: fromName, To: toName, Amount: amount}, from, to, nil, nil
}

type batchRequest struct {
	Transfers []transferRequest `json:"transfers"`
}

func validateBatch(req batchRequest) *apiError {
	if req.Transfers == nil || len(req.Transfers) < 1 || len(req.Transfers) > 20 {
		return apiFail(http.StatusBadRequest, "invalid")
	}
	for _, t := range req.Transfers {
		if invalid := validateTransfer(t); invalid != nil {
			return invalid
		}
	}
	return nil
}

func createBatch(tx *writeTx, tenant string, req batchRequest) (int, any, *apiError, error) {
	transfers := make([]transferObject, 0, len(req.Transfers))
	touched := make(map[string]accountState)
	for _, request := range req.Transfers {
		t, from, to, businessErr, err := postTransfer(tx, tenant, request.From, request.To, request.Amount, request.FromVersion, request.ToVersion, "transfer")
		if businessErr != nil || err != nil {
			return 0, nil, businessErr, err
		}
		transfers = append(transfers, t)
		touched[from.Name] = from
		touched[to.Name] = to
	}
	return http.StatusCreated, struct {
		Transfers []transferObject `json:"transfers"`
		Accounts  []accountState   `json:"accounts"`
	}{transfers, sortedAccounts(touched)}, nil, nil
}

type holdRequest struct {
	Account string          `json:"account"`
	Amount  int64           `json:"amount"`
	Version optionalVersion `json:"version"`
}

func validateHold(req holdRequest) *apiError {
	if !validName(req.Account) || req.Amount < 1 || req.Amount > 1_000_000_000 {
		return apiFail(http.StatusBadRequest, "invalid")
	}
	return nil
}

func createHold(tx *writeTx, tenant string, req holdRequest) (int, any, *apiError, error) {
	a, found, err := getAccount(tx.ctx, tx.conn, tenant, req.Account)
	if err != nil {
		return 0, nil, nil, err
	}
	if !found {
		return 0, nil, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if v := validateVersion(a, req.Version); v != nil {
		return 0, nil, v, nil
	}
	if a.Available < req.Amount {
		return 0, nil, apiFail(http.StatusConflict, "insufficient"), nil
	}
	id, err := allocateID(tx.ctx, tx.conn, tenant)
	if err != nil {
		return 0, nil, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "INSERT INTO holds(tenant,id,account,amount,state) VALUES(?,?,?,?,'active')", tenant, id, req.Account, req.Amount); err != nil {
		return 0, nil, nil, err
	}
	a.Reserved += req.Amount
	a.Version++
	a.Available = a.Balance - a.Reserved
	if err := updateAccount(tx.ctx, tx.conn, tenant, a); err != nil {
		return 0, nil, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, req.Account, "hold", 0, req.Amount, id, nil); err != nil {
		return 0, nil, nil, err
	}
	return http.StatusCreated, struct {
		Hold    holdObject   `json:"hold"`
		Account accountState `json:"account"`
	}{holdObject{ID: id, Account: req.Account, Amount: req.Amount, State: "active"}, a}, nil, nil
}

type captureRequest struct {
	To          string          `json:"to"`
	FromVersion optionalVersion `json:"from_version"`
	ToVersion   optionalVersion `json:"to_version"`
}

func validateCapture(req captureRequest) *apiError {
	if !validName(req.To) {
		return apiFail(http.StatusBadRequest, "invalid")
	}
	return nil
}

func captureHold(tx *writeTx, tenant, id string, req captureRequest) (int, any, *apiError, error) {
	var hold holdObject
	err := tx.conn.QueryRowContext(tx.ctx, "SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?", tenant, id).Scan(&hold.ID, &hold.Account, &hold.Amount, &hold.State)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, nil, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if err != nil {
		return 0, nil, nil, err
	}
	if hold.State != "active" {
		return 0, nil, apiFail(http.StatusConflict, "terminal"), nil
	}
	if req.To == hold.Account {
		return 0, nil, apiFail(http.StatusBadRequest, "invalid"), nil
	}
	from, fromFound, err := getAccount(tx.ctx, tx.conn, tenant, hold.Account)
	if err != nil {
		return 0, nil, nil, err
	}
	to, toFound, err := getAccount(tx.ctx, tx.conn, tenant, req.To)
	if err != nil {
		return 0, nil, nil, err
	}
	if !fromFound || !toFound {
		return 0, nil, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if v := validateVersion(from, req.FromVersion); v != nil {
		return 0, nil, v, nil
	}
	if v := validateVersion(to, req.ToVersion); v != nil {
		return 0, nil, v, nil
	}
	if from.Reserved < hold.Amount || from.Balance < hold.Amount || to.Balance > maxAccountValue-hold.Amount {
		return 0, nil, apiFail(http.StatusConflict, "insufficient"), nil
	}
	transferID, err := allocateID(tx.ctx, tx.conn, tenant)
	if err != nil {
		return 0, nil, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "INSERT INTO transfers(tenant,id,source,target,amount,reversed) VALUES(?,?,?,?,?,0)", tenant, transferID, hold.Account, req.To, hold.Amount); err != nil {
		return 0, nil, nil, err
	}
	from.Balance -= hold.Amount
	from.Reserved -= hold.Amount
	from.Version++
	from.Available = from.Balance - from.Reserved
	to.Balance += hold.Amount
	to.Version++
	to.Available = to.Balance - to.Reserved
	if err := updateAccount(tx.ctx, tx.conn, tenant, from); err != nil {
		return 0, nil, nil, err
	}
	if err := updateAccount(tx.ctx, tx.conn, tenant, to); err != nil {
		return 0, nil, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, hold.Account, "capture", -hold.Amount, -hold.Amount, transferID, nil); err != nil {
		return 0, nil, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, req.To, "capture", hold.Amount, 0, transferID, nil); err != nil {
		return 0, nil, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "UPDATE holds SET state='captured' WHERE tenant=? AND id=?", tenant, id); err != nil {
		return 0, nil, nil, err
	}
	hold.State = "captured"
	transfer := transferObject{ID: transferID, From: hold.Account, To: req.To, Amount: hold.Amount}
	return http.StatusOK, struct {
		Hold     holdObject     `json:"hold"`
		Transfer transferObject `json:"transfer"`
		Accounts []accountState `json:"accounts"`
	}{hold, transfer, []accountState{from, to}}, nil, nil
}

type releaseRequest struct {
	Version optionalVersion `json:"version"`
}

func validateRelease(releaseRequest) *apiError { return nil }

func releaseHold(tx *writeTx, tenant, id string, req releaseRequest) (int, any, *apiError, error) {
	var hold holdObject
	err := tx.conn.QueryRowContext(tx.ctx, "SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?", tenant, id).Scan(&hold.ID, &hold.Account, &hold.Amount, &hold.State)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, nil, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if err != nil {
		return 0, nil, nil, err
	}
	if hold.State != "active" {
		return 0, nil, apiFail(http.StatusConflict, "terminal"), nil
	}
	a, found, err := getAccount(tx.ctx, tx.conn, tenant, hold.Account)
	if err != nil {
		return 0, nil, nil, err
	}
	if !found {
		return 0, nil, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if v := validateVersion(a, req.Version); v != nil {
		return 0, nil, v, nil
	}
	if a.Reserved < hold.Amount {
		return 0, nil, apiFail(http.StatusConflict, "insufficient"), nil
	}
	a.Reserved -= hold.Amount
	a.Version++
	a.Available = a.Balance - a.Reserved
	if err := updateAccount(tx.ctx, tx.conn, tenant, a); err != nil {
		return 0, nil, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, a.Name, "release", 0, -hold.Amount, id, nil); err != nil {
		return 0, nil, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "UPDATE holds SET state='released' WHERE tenant=? AND id=?", tenant, id); err != nil {
		return 0, nil, nil, err
	}
	hold.State = "released"
	return http.StatusOK, struct {
		Hold    holdObject   `json:"hold"`
		Account accountState `json:"account"`
	}{hold, a}, nil, nil
}

type reverseRequest struct {
	FromVersion optionalVersion `json:"from_version"`
	ToVersion   optionalVersion `json:"to_version"`
}

func reverseTransfer(tx *writeTx, tenant, id string, req reverseRequest) (int, any, *apiError, error) {
	var original transferObject
	var reversalOf sql.NullString
	var reversed int
	var legacyID sql.NullInt64
	err := tx.conn.QueryRowContext(tx.ctx, "SELECT id,source,target,amount,reversed,reversal_of,legacy_id FROM transfers WHERE tenant=? AND id=?", tenant, id).Scan(&original.ID, &original.From, &original.To, &original.Amount, &reversed, &reversalOf, &legacyID)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, nil, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if err != nil {
		return 0, nil, nil, err
	}
	if reversed != 0 || reversalOf.Valid {
		return 0, nil, apiFail(http.StatusConflict, "terminal"), nil
	}
	if legacyID.Valid {
		v := legacyID.Int64
		original.LegacyID = &v
	}
	from, fromFound, err := getAccount(tx.ctx, tx.conn, tenant, original.From)
	if err != nil {
		return 0, nil, nil, err
	}
	to, toFound, err := getAccount(tx.ctx, tx.conn, tenant, original.To)
	if err != nil {
		return 0, nil, nil, err
	}
	if !fromFound || !toFound {
		return 0, nil, apiFail(http.StatusNotFound, "not_found"), nil
	}
	if v := validateVersion(from, req.FromVersion); v != nil {
		return 0, nil, v, nil
	}
	if v := validateVersion(to, req.ToVersion); v != nil {
		return 0, nil, v, nil
	}
	// The reversal debits the original destination and credits its source.
	if to.Available < original.Amount || from.Balance > maxAccountValue-original.Amount {
		return 0, nil, apiFail(http.StatusConflict, "insufficient"), nil
	}
	reversalID, err := allocateID(tx.ctx, tx.conn, tenant)
	if err != nil {
		return 0, nil, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "INSERT INTO transfers(tenant,id,source,target,amount,reversed,reversal_of) VALUES(?,?,?,?,?,0,?)", tenant, reversalID, original.To, original.From, original.Amount, original.ID); err != nil {
		return 0, nil, nil, err
	}
	to.Balance -= original.Amount
	to.Version++
	to.Available = to.Balance - to.Reserved
	from.Balance += original.Amount
	from.Version++
	from.Available = from.Balance - from.Reserved
	if err := updateAccount(tx.ctx, tx.conn, tenant, to); err != nil {
		return 0, nil, nil, err
	}
	if err := updateAccount(tx.ctx, tx.conn, tenant, from); err != nil {
		return 0, nil, nil, err
	}
	if _, err := tx.conn.ExecContext(tx.ctx, "UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?", tenant, original.ID); err != nil {
		return 0, nil, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, original.To, "reversal", -original.Amount, 0, reversalID, nil); err != nil {
		return 0, nil, nil, err
	}
	if err := insertEntry(tx.ctx, tx.conn, tenant, original.From, "reversal", original.Amount, 0, reversalID, nil); err != nil {
		return 0, nil, nil, err
	}
	original.Reversed = true
	reversal := transferObject{ID: reversalID, From: original.To, To: original.From, Amount: original.Amount}
	return http.StatusOK, struct {
		Transfer transferObject `json:"transfer"`
		Reversal transferObject `json:"reversal"`
		Accounts []accountState `json:"accounts"`
	}{original, reversal, []accountState{from, to}}, nil, nil
}

type entryObject struct {
	Seq           int64  `json:"seq"`
	Account       string `json:"account"`
	Kind          string `json:"kind"`
	BalanceDelta  int64  `json:"balance_delta"`
	ReservedDelta int64  `json:"reserved_delta"`
	OperationID   string `json:"operation_id"`
	LegacyID      *int64 `json:"legacy_id,omitempty"`
}

func (h *Handler) getEntries(w http.ResponseWriter, r *http.Request, tenant string) {
	q, ok := requestQuery(r, "after", "limit", "snapshot")
	if !ok {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	after := int64(0)
	limit := int64(50)
	var snapshot *int64
	if v, exists := q["after"]; exists {
		n, valid := parseNonnegative(v)
		if !valid {
			writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
			return
		}
		after = n
	}
	if v, exists := q["limit"]; exists {
		n, valid := parseNonnegative(v)
		if !valid || n < 1 || n > 100 {
			writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
			return
		}
		limit = n
	}
	if v, exists := q["snapshot"]; exists {
		n, valid := parseNonnegative(v)
		if !valid {
			writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
			return
		}
		snapshot = &n
	}
	tx, err := h.db.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	defer tx.Rollback()
	var current int64
	if err := tx.QueryRowContext(r.Context(), "SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?", tenant).Scan(&current); err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	if snapshot == nil {
		snapshot = &current
	}
	if *snapshot > current || after > *snapshot {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	rows, err := tx.QueryContext(r.Context(), "SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?", tenant, after, *snapshot, limit+1)
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	entries := make([]entryObject, 0, limit)
	for rows.Next() {
		var entry entryObject
		var legacy sql.NullInt64
		if err := rows.Scan(&entry.Seq, &entry.Account, &entry.Kind, &entry.BalanceDelta, &entry.ReservedDelta, &entry.OperationID, &legacy); err != nil {
			rows.Close()
			writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
			return
		}
		if legacy.Valid {
			v := legacy.Int64
			entry.LegacyID = &v
		}
		entries = append(entries, entry)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	if err := rows.Close(); err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	hasMore := int64(len(entries)) > limit
	if hasMore {
		entries = entries[:limit]
	}
	nextAfter := after
	if len(entries) > 0 {
		nextAfter = entries[len(entries)-1].Seq
	}
	writeJSON(w, http.StatusOK, struct {
		Entries   []entryObject `json:"entries"`
		Snapshot  int64         `json:"snapshot"`
		NextAfter int64         `json:"next_after"`
		HasMore   bool          `json:"has_more"`
	}{entries, *snapshot, nextAfter, hasMore})
}

type summaryAccount struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
}

func (h *Handler) getSummary(w http.ResponseWriter, r *http.Request, tenant string) {
	q, ok := requestQuery(r, "snapshot")
	if !ok {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	var requested *int64
	if v, exists := q["snapshot"]; exists {
		n, valid := parseNonnegative(v)
		if !valid {
			writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
			return
		}
		requested = &n
	}
	tx, err := h.db.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	defer tx.Rollback()
	var current int64
	if err := tx.QueryRowContext(r.Context(), "SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?", tenant).Scan(&current); err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	snapshot := current
	if requested != nil {
		snapshot = *requested
	}
	if snapshot > current {
		writeAPIError(w, apiFail(http.StatusBadRequest, "invalid"))
		return
	}
	rows, err := tx.QueryContext(r.Context(), "SELECT account, SUM(balance_delta), SUM(reserved_delta) FROM entries WHERE tenant=? AND seq<=? GROUP BY account ORDER BY account", tenant, snapshot)
	if err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	accounts := make([]summaryAccount, 0)
	totalBalance, totalReserved := new(big.Int), new(big.Int)
	for rows.Next() {
		var a summaryAccount
		if err := rows.Scan(&a.Name, &a.Balance, &a.Reserved); err != nil {
			rows.Close()
			writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
			return
		}
		a.Available = a.Balance - a.Reserved
		if a.Balance < 0 || a.Reserved < 0 || a.Reserved > a.Balance || a.Balance > maxAccountValue {
			rows.Close()
			writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
			return
		}
		totalBalance.Add(totalBalance, big.NewInt(a.Balance))
		totalReserved.Add(totalReserved, big.NewInt(a.Reserved))
		accounts = append(accounts, a)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	if err := rows.Close(); err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	var entryCount int64
	if err := tx.QueryRowContext(r.Context(), "SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?", tenant, snapshot).Scan(&entryCount); err != nil {
		writeAPIError(w, apiFail(http.StatusInternalServerError, "internal"))
		return
	}
	available := new(big.Int).Sub(new(big.Int).Set(totalBalance), totalReserved)
	writeJSON(w, http.StatusOK, struct {
		Snapshot int64            `json:"snapshot"`
		Accounts []summaryAccount `json:"accounts"`
		Totals   struct {
			Balance   json.Number `json:"balance"`
			Reserved  json.Number `json:"reserved"`
			Available json.Number `json:"available"`
		} `json:"totals"`
		EntryCount int64 `json:"entry_count"`
	}{Snapshot: snapshot, Accounts: accounts, Totals: struct {
		Balance   json.Number `json:"balance"`
		Reserved  json.Number `json:"reserved"`
		Available json.Number `json:"available"`
	}{json.Number(totalBalance.String()), json.Number(totalReserved.String()), json.Number(available.String())}, EntryCount: entryCount})
}

func parseQuery(values url.Values, allowed ...string) (map[string]string, bool) {
	allow := make(map[string]bool, len(allowed))
	for _, key := range allowed {
		allow[key] = true
	}
	result := make(map[string]string, len(values))
	for key, vals := range values {
		if !allow[key] || len(vals) != 1 {
			return nil, false
		}
		result[key] = vals[0]
	}
	return result, true
}

func requestQuery(r *http.Request, allowed ...string) (map[string]string, bool) {
	values, err := url.ParseQuery(r.URL.RawQuery)
	if err != nil {
		return nil, false
	}
	return parseQuery(values, allowed...)
}

func parseNonnegative(raw string) (int64, bool) {
	if raw == "" {
		return 0, false
	}
	for _, c := range raw {
		if c < '0' || c > '9' {
			return 0, false
		}
	}
	n, err := strconv.ParseInt(raw, 10, 64)
	return n, err == nil
}
