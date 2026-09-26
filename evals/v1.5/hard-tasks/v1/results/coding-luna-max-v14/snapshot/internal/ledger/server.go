package ledger

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"sort"
	"strings"
)

type Server struct{ db *sql.DB }

func NewServer(db *sql.DB) http.Handler { return &Server{db: db} }

type route struct {
	kind string
	arg  string
	verb string
}

func findRoute(path string) (route, bool) {
	switch path {
	case "/accounts":
		return route{kind: "create_account", verb: http.MethodPost}, true
	case "/transfers":
		return route{kind: "transfer", verb: http.MethodPost}, true
	case "/batches":
		return route{kind: "batch", verb: http.MethodPost}, true
	case "/holds":
		return route{kind: "hold", verb: http.MethodPost}, true
	case "/entries":
		return route{kind: "entries", verb: http.MethodGet}, true
	case "/summary":
		return route{kind: "summary", verb: http.MethodGet}, true
	}
	parts := strings.Split(strings.TrimPrefix(path, "/"), "/")
	if len(parts) == 2 && parts[0] == "accounts" && parts[1] != "" {
		return route{kind: "get_account", arg: parts[1], verb: http.MethodGet}, true
	}
	if len(parts) == 3 && parts[0] == "holds" && parts[1] != "" && (parts[2] == "capture" || parts[2] == "release") {
		return route{kind: "hold_" + parts[2], arg: parts[1], verb: http.MethodPost}, true
	}
	if len(parts) == 3 && parts[0] == "transfers" && parts[1] != "" && parts[2] == "reverse" {
		return route{kind: "reverse", arg: parts[1], verb: http.MethodPost}, true
	}
	return route{}, false
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/health" {
		if r.Method != http.MethodGet {
			writeError(w, 404, "not_found")
			return
		}
		var version int
		if err := s.db.QueryRowContext(r.Context(), `PRAGMA user_version`).Scan(&version); err != nil || version != 2 {
			writeError(w, 503, "not_ready")
			return
		}
		var one int
		if err := s.db.QueryRowContext(r.Context(), `SELECT 1`).Scan(&one); err != nil || one != 1 {
			writeError(w, 503, "not_ready")
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true})
		return
	}
	matched, ok := findRoute(r.URL.Path)
	if !ok {
		writeError(w, 404, "not_found")
		return
	}
	tenant, valid := requestTenant(r)
	if !valid {
		writeError(w, 400, "invalid")
		return
	}
	if r.Method != matched.verb {
		writeError(w, 404, "not_found")
		return
	}
	switch matched.kind {
	case "create_account":
		s.createAccount(w, r, tenant)
	case "get_account":
		if !identifierPattern.MatchString(matched.arg) {
			writeError(w, 400, "invalid")
			return
		}
		s.getAccount(w, r, tenant, matched.arg)
	case "transfer":
		s.createTransfer(w, r, tenant)
	case "batch":
		s.createBatch(w, r, tenant)
	case "hold":
		s.createHold(w, r, tenant)
	case "hold_capture":
		s.captureHold(w, r, tenant, matched.arg)
	case "hold_release":
		s.releaseHold(w, r, tenant, matched.arg)
	case "reverse":
		s.reverseTransfer(w, r, tenant, matched.arg)
	case "entries":
		s.listEntries(w, r, tenant)
	case "summary":
		s.summary(w, r, tenant)
	default:
		writeError(w, 404, "not_found")
	}
}

func requestTenant(r *http.Request) (string, bool) {
	values := r.Header.Values("X-Tenant")
	if len(values) != 1 || !tenantPattern.MatchString(values[0]) {
		return "", false
	}
	return values[0], true
}

func mutationKey(r *http.Request) (string, bool) {
	values := r.Header.Values("Idempotency-Key")
	if len(values) != 1 || !keyPattern.MatchString(values[0]) {
		return "", false
	}
	return values[0], true
}

func (s *Server) createAccount(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := mutationKey(r)
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	req, canonical, err := parseCreateAccount(r.Body)
	if err != nil {
		writeError(w, 400, "invalid")
		return
	}
	s.mutate(w, r, tenant, key, r.URL.Path, canonical, func(st *writeState) (int, any, *apiError, error) {
		var one int
		err := st.tx.QueryRowContext(r.Context(), `SELECT 1 FROM accounts WHERE tenant=? AND name=?`, tenant, req.Name).Scan(&one)
		if err == nil {
			return 0, nil, errExists, nil
		}
		if !errors.Is(err, sql.ErrNoRows) {
			return 0, nil, nil, err
		}
		acct := newAccount(req.Name, req.Opening, 0, 1)
		if _, err := st.tx.ExecContext(r.Context(), `INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,1)`, tenant, req.Name, req.Opening); err != nil {
			return 0, nil, nil, err
		}
		if err := st.writer.append(r.Context(), st.tx, req.Name, "opening", req.Opening, 0, newID(), nil); err != nil {
			return 0, nil, nil, err
		}
		return 201, map[string]any{"account": acct}, nil, nil
	})
}

func (s *Server) getAccount(w http.ResponseWriter, r *http.Request, tenant, name string) {
	acct, ae, err := loadAccount(r.Context(), s.db, tenant, name)
	if ae != nil {
		writeAPIError(w, ae)
		return
	}
	if err != nil {
		writeInternal(w)
		return
	}
	writeJSON(w, 200, map[string]any{"account": acct})
}

func (s *Server) createTransfer(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := mutationKey(r)
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	req, canonical, err := parseTransferBody(r.Body)
	if err != nil {
		writeError(w, 400, "invalid")
		return
	}
	s.mutate(w, r, tenant, key, r.URL.Path, canonical, func(st *writeState) (int, any, *apiError, error) {
		transfer, from, to, ae, err := performTransfer(r.Context(), st, req, "transfer")
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		return 201, map[string]any{"transfer": transfer, "accounts": []Account{from, to}}, nil, nil
	})
}

func (s *Server) createBatch(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := mutationKey(r)
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	req, canonical, err := parseBatch(r.Body)
	if err != nil {
		writeError(w, 400, "invalid")
		return
	}
	s.mutate(w, r, tenant, key, r.URL.Path, canonical, func(st *writeState) (int, any, *apiError, error) {
		transfers := make([]Transfer, 0, len(req.Transfers))
		touched := make(map[string]Account)
		for _, request := range req.Transfers {
			transfer, from, to, ae, err := performTransfer(r.Context(), st, request, "transfer")
			if ae != nil || err != nil {
				return 0, nil, ae, err
			}
			transfers = append(transfers, transfer)
			touched[from.Name], touched[to.Name] = from, to
		}
		names := make([]string, 0, len(touched))
		for name := range touched {
			names = append(names, name)
		}
		sort.Strings(names)
		accounts := make([]Account, 0, len(names))
		for _, name := range names {
			accounts = append(accounts, touched[name])
		}
		return 201, map[string]any{"transfers": transfers, "accounts": accounts}, nil, nil
	})
}

func (s *Server) createHold(w http.ResponseWriter, r *http.Request, tenant string) {
	key, ok := mutationKey(r)
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	req, canonical, err := parseHold(r.Body)
	if err != nil {
		writeError(w, 400, "invalid")
		return
	}
	s.mutate(w, r, tenant, key, r.URL.Path, canonical, func(st *writeState) (int, any, *apiError, error) {
		acct, ae, err := loadAccount(r.Context(), st.tx, tenant, req.Account)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		if ae = checkVersion(req.Version, acct.Version); ae != nil {
			return 0, nil, ae, nil
		}
		if acct.Available < req.Amount {
			return 0, nil, errFunds, nil
		}
		reserved, ok := addWithinLimit(acct.Reserved, req.Amount)
		if !ok {
			return 0, nil, errFunds, nil
		}
		version, ok := incrementVersion(acct.Version)
		if !ok {
			return 0, nil, nil, errors.New("account version exhausted")
		}
		acct = newAccount(acct.Name, acct.Balance, reserved, version)
		id := newID()
		if _, err := st.tx.ExecContext(r.Context(), `INSERT INTO holds(tenant,id,account,amount,state) VALUES(?,?,?,?,'active')`, tenant, id, req.Account, req.Amount); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), st.tx, tenant, acct); err != nil {
			return 0, nil, nil, err
		}
		if err := st.writer.append(r.Context(), st.tx, req.Account, "hold", 0, req.Amount, id, nil); err != nil {
			return 0, nil, nil, err
		}
		hold := Hold{ID: id, Account: req.Account, Amount: req.Amount, State: "active"}
		return 201, map[string]any{"hold": hold, "account": acct}, nil, nil
	})
}

func (s *Server) captureHold(w http.ResponseWriter, r *http.Request, tenant, id string) {
	key, ok := mutationKey(r)
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	req, canonical, err := parseCapture(r.Body)
	if err != nil {
		writeError(w, 400, "invalid")
		return
	}
	s.mutate(w, r, tenant, key, r.URL.Path, canonical, func(st *writeState) (int, any, *apiError, error) {
		hold, ae, err := loadHold(r.Context(), st.tx, tenant, id)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		if hold.State != "active" {
			return 0, nil, errTerminal, nil
		}
		if hold.Account == req.To {
			return 0, nil, errInvalid, nil
		}
		from, ae, err := loadAccount(r.Context(), st.tx, tenant, hold.Account)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		to, ae, err := loadAccount(r.Context(), st.tx, tenant, req.To)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		if ae = checkVersion(req.FromVersion, from.Version); ae != nil {
			return 0, nil, ae, nil
		}
		if ae = checkVersion(req.ToVersion, to.Version); ae != nil {
			return 0, nil, ae, nil
		}
		if from.Reserved < hold.Amount || from.Balance < hold.Amount {
			return 0, nil, nil, errors.New("hold/account invariant violated")
		}
		newToBalance, ok := addWithinLimit(to.Balance, hold.Amount)
		if !ok {
			return 0, nil, errFunds, nil
		}
		fromVersion, ok := incrementVersion(from.Version)
		if !ok {
			return 0, nil, nil, errors.New("account version exhausted")
		}
		toVersion, ok := incrementVersion(to.Version)
		if !ok {
			return 0, nil, nil, errors.New("account version exhausted")
		}
		from = newAccount(from.Name, from.Balance-hold.Amount, from.Reserved-hold.Amount, fromVersion)
		to = newAccount(to.Name, newToBalance, to.Reserved, toVersion)
		transferID := newID()
		if err := saveAccount(r.Context(), st.tx, tenant, from); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), st.tx, tenant, to); err != nil {
			return 0, nil, nil, err
		}
		if _, err := st.tx.ExecContext(r.Context(), `INSERT INTO transfers(tenant,id,from_account,to_account,amount,reversed,reversal_of,kind,legacy_id) VALUES(?,?,?,?,?,0,NULL,'capture',NULL)`, tenant, transferID, from.Name, to.Name, hold.Amount); err != nil {
			return 0, nil, nil, err
		}
		if _, err := st.tx.ExecContext(r.Context(), `UPDATE holds SET state='captured' WHERE tenant=? AND id=?`, tenant, id); err != nil {
			return 0, nil, nil, err
		}
		if err := st.writer.append(r.Context(), st.tx, from.Name, "capture", -hold.Amount, -hold.Amount, transferID, nil); err != nil {
			return 0, nil, nil, err
		}
		if err := st.writer.append(r.Context(), st.tx, to.Name, "capture", hold.Amount, 0, transferID, nil); err != nil {
			return 0, nil, nil, err
		}
		hold.State = "captured"
		transfer := Transfer{ID: transferID, From: from.Name, To: to.Name, Amount: hold.Amount, Reversed: false}
		return 200, map[string]any{"hold": hold, "transfer": transfer, "accounts": []Account{from, to}}, nil, nil
	})
}

func (s *Server) releaseHold(w http.ResponseWriter, r *http.Request, tenant, id string) {
	key, ok := mutationKey(r)
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	req, canonical, err := parseRelease(r.Body)
	if err != nil {
		writeError(w, 400, "invalid")
		return
	}
	s.mutate(w, r, tenant, key, r.URL.Path, canonical, func(st *writeState) (int, any, *apiError, error) {
		hold, ae, err := loadHold(r.Context(), st.tx, tenant, id)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		if hold.State != "active" {
			return 0, nil, errTerminal, nil
		}
		acct, ae, err := loadAccount(r.Context(), st.tx, tenant, hold.Account)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		if ae = checkVersion(req.Version, acct.Version); ae != nil {
			return 0, nil, ae, nil
		}
		if acct.Reserved < hold.Amount {
			return 0, nil, nil, errors.New("hold/account invariant violated")
		}
		version, ok := incrementVersion(acct.Version)
		if !ok {
			return 0, nil, nil, errors.New("account version exhausted")
		}
		acct = newAccount(acct.Name, acct.Balance, acct.Reserved-hold.Amount, version)
		if err := saveAccount(r.Context(), st.tx, tenant, acct); err != nil {
			return 0, nil, nil, err
		}
		if _, err := st.tx.ExecContext(r.Context(), `UPDATE holds SET state='released' WHERE tenant=? AND id=?`, tenant, id); err != nil {
			return 0, nil, nil, err
		}
		if err := st.writer.append(r.Context(), st.tx, hold.Account, "release", 0, -hold.Amount, id, nil); err != nil {
			return 0, nil, nil, err
		}
		hold.State = "released"
		return 200, map[string]any{"hold": hold, "account": acct}, nil, nil
	})
}

func (s *Server) reverseTransfer(w http.ResponseWriter, r *http.Request, tenant, id string) {
	key, ok := mutationKey(r)
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	req, canonical, err := parseReverse(r.Body)
	if err != nil {
		writeError(w, 400, "invalid")
		return
	}
	s.mutate(w, r, tenant, key, r.URL.Path, canonical, func(st *writeState) (int, any, *apiError, error) {
		original, ae, err := loadTransfer(r.Context(), st.tx, tenant, id)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		if original.ReversalOf.Valid || original.Kind == "reversal" || original.Reversed {
			return 0, nil, errTerminal, nil
		}
		from, ae, err := loadAccount(r.Context(), st.tx, tenant, original.From)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		to, ae, err := loadAccount(r.Context(), st.tx, tenant, original.To)
		if ae != nil || err != nil {
			return 0, nil, ae, err
		}
		if ae = checkVersion(req.FromVersion, from.Version); ae != nil {
			return 0, nil, ae, nil
		}
		if ae = checkVersion(req.ToVersion, to.Version); ae != nil {
			return 0, nil, ae, nil
		}
		if to.Available < original.Amount {
			return 0, nil, errFunds, nil
		}
		newFromBalance, ok := addWithinLimit(from.Balance, original.Amount)
		if !ok {
			return 0, nil, errFunds, nil
		}
		fromVersion, ok := incrementVersion(from.Version)
		if !ok {
			return 0, nil, nil, errors.New("account version exhausted")
		}
		toVersion, ok := incrementVersion(to.Version)
		if !ok {
			return 0, nil, nil, errors.New("account version exhausted")
		}
		from = newAccount(from.Name, newFromBalance, from.Reserved, fromVersion)
		to = newAccount(to.Name, to.Balance-original.Amount, to.Reserved, toVersion)
		if err := saveAccount(r.Context(), st.tx, tenant, from); err != nil {
			return 0, nil, nil, err
		}
		if err := saveAccount(r.Context(), st.tx, tenant, to); err != nil {
			return 0, nil, nil, err
		}
		if _, err := st.tx.ExecContext(r.Context(), `UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?`, tenant, id); err != nil {
			return 0, nil, nil, err
		}
		reversalID := newID()
		if _, err := st.tx.ExecContext(r.Context(), `INSERT INTO transfers(tenant,id,from_account,to_account,amount,reversed,reversal_of,kind,legacy_id) VALUES(?,?,?,?,?,0,?,'reversal',NULL)`, tenant, reversalID, original.To, original.From, original.Amount, original.ID); err != nil {
			return 0, nil, nil, err
		}
		if err := st.writer.append(r.Context(), st.tx, original.To, "reversal", -original.Amount, 0, reversalID, nil); err != nil {
			return 0, nil, nil, err
		}
		if err := st.writer.append(r.Context(), st.tx, original.From, "reversal", original.Amount, 0, reversalID, nil); err != nil {
			return 0, nil, nil, err
		}
		original.Reversed = true
		reversal := Transfer{ID: reversalID, From: original.To, To: original.From, Amount: original.Amount, Reversed: false}
		return 200, map[string]any{"transfer": original.Transfer, "reversal": reversal, "accounts": []Account{from, to}}, nil, nil
	})
}

type storedTransfer struct {
	Transfer
	ReversalOf sql.NullString
	Kind       string
}

func loadAccount(ctx context.Context, q interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}, tenant, name string) (Account, *apiError, error) {
	var balance, reserved, version int64
	err := q.QueryRowContext(ctx, `SELECT balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, tenant, name).Scan(&balance, &reserved, &version)
	if errors.Is(err, sql.ErrNoRows) {
		return Account{}, errMissing, nil
	}
	if err != nil {
		return Account{}, nil, err
	}
	return newAccount(name, balance, reserved, version), nil, nil
}

func saveAccount(ctx context.Context, tx *sql.Tx, tenant string, acct Account) error {
	res, err := tx.ExecContext(ctx, `UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?`, acct.Balance, acct.Reserved, acct.Version, tenant, acct.Name)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n != 1 {
		return errors.New("account vanished during transaction")
	}
	return nil
}

func performTransfer(ctx context.Context, st *writeState, req transferRequest, kind string) (Transfer, Account, Account, *apiError, error) {
	if req.From == req.To || !identifierPattern.MatchString(req.From) || !identifierPattern.MatchString(req.To) {
		return Transfer{}, Account{}, Account{}, errInvalid, nil
	}
	from, ae, err := loadAccount(ctx, st.tx, st.tenant, req.From)
	if ae != nil || err != nil {
		return Transfer{}, Account{}, Account{}, ae, err
	}
	to, ae, err := loadAccount(ctx, st.tx, st.tenant, req.To)
	if ae != nil || err != nil {
		return Transfer{}, Account{}, Account{}, ae, err
	}
	if ae = checkVersion(req.FromVersion, from.Version); ae != nil {
		return Transfer{}, Account{}, Account{}, ae, nil
	}
	if ae = checkVersion(req.ToVersion, to.Version); ae != nil {
		return Transfer{}, Account{}, Account{}, ae, nil
	}
	if from.Available < req.Amount {
		return Transfer{}, Account{}, Account{}, errFunds, nil
	}
	newToBalance, ok := addWithinLimit(to.Balance, req.Amount)
	if !ok {
		return Transfer{}, Account{}, Account{}, errFunds, nil
	}
	fromVersion, ok := incrementVersion(from.Version)
	if !ok {
		return Transfer{}, Account{}, Account{}, nil, errors.New("account version exhausted")
	}
	toVersion, ok := incrementVersion(to.Version)
	if !ok {
		return Transfer{}, Account{}, Account{}, nil, errors.New("account version exhausted")
	}
	from = newAccount(from.Name, from.Balance-req.Amount, from.Reserved, fromVersion)
	to = newAccount(to.Name, newToBalance, to.Reserved, toVersion)
	if err := saveAccount(ctx, st.tx, st.tenant, from); err != nil {
		return Transfer{}, Account{}, Account{}, nil, err
	}
	if err := saveAccount(ctx, st.tx, st.tenant, to); err != nil {
		return Transfer{}, Account{}, Account{}, nil, err
	}
	id := newID()
	if _, err := st.tx.ExecContext(ctx, `INSERT INTO transfers(tenant,id,from_account,to_account,amount,reversed,reversal_of,kind,legacy_id) VALUES(?,?,?,?,?,0,NULL,?,NULL)`, st.tenant, id, req.From, req.To, req.Amount, kind); err != nil {
		return Transfer{}, Account{}, Account{}, nil, err
	}
	if err := st.writer.append(ctx, st.tx, req.From, "transfer", -req.Amount, 0, id, nil); err != nil {
		return Transfer{}, Account{}, Account{}, nil, err
	}
	if err := st.writer.append(ctx, st.tx, req.To, "transfer", req.Amount, 0, id, nil); err != nil {
		return Transfer{}, Account{}, Account{}, nil, err
	}
	return Transfer{ID: id, From: req.From, To: req.To, Amount: req.Amount, Reversed: false}, from, to, nil, nil
}

func loadHold(ctx context.Context, tx *sql.Tx, tenant, id string) (Hold, *apiError, error) {
	var hold Hold
	hold.ID = id
	err := tx.QueryRowContext(ctx, `SELECT account,amount,state FROM holds WHERE tenant=? AND id=?`, tenant, id).Scan(&hold.Account, &hold.Amount, &hold.State)
	if errors.Is(err, sql.ErrNoRows) {
		return Hold{}, errMissing, nil
	}
	if err != nil {
		return Hold{}, nil, err
	}
	return hold, nil, nil
}

func loadTransfer(ctx context.Context, tx *sql.Tx, tenant, id string) (storedTransfer, *apiError, error) {
	var tr storedTransfer
	tr.ID = id
	var reversed int
	var legacyID sql.NullInt64
	err := tx.QueryRowContext(ctx, `SELECT from_account,to_account,amount,reversed,reversal_of,kind,legacy_id FROM transfers WHERE tenant=? AND id=?`, tenant, id).Scan(&tr.From, &tr.To, &tr.Amount, &reversed, &tr.ReversalOf, &tr.Kind, &legacyID)
	if errors.Is(err, sql.ErrNoRows) {
		return storedTransfer{}, errMissing, nil
	}
	if err != nil {
		return storedTransfer{}, nil, err
	}
	tr.Reversed = reversed != 0
	if legacyID.Valid {
		tr.LegacyID = &legacyID.Int64
	}
	return tr, nil, nil
}

type writeState struct {
	tx     *sql.Tx
	tenant string
	writer *entryWriter
}

func (s *Server) mutate(w http.ResponseWriter, r *http.Request, tenant, key, path string, canonical []byte, fn func(*writeState) (int, any, *apiError, error)) {
	hash := sha256.Sum256(canonical)
	bodyHash := hex.EncodeToString(hash[:])
	tx, err := s.db.BeginTx(r.Context(), &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		writeInternal(w)
		return
	}
	defer tx.Rollback()

	var oldPath, oldHash string
	var oldStatus int
	var oldResult []byte
	err = tx.QueryRowContext(r.Context(), `SELECT path,body_hash,status,result_json FROM idempotency WHERE tenant=? AND key=?`, tenant, key).Scan(&oldPath, &oldHash, &oldStatus, &oldResult)
	if err == nil {
		if oldPath != path || oldHash != bodyHash {
			writeAPIError(w, errIdem)
			return
		}
		if err := tx.Commit(); err != nil {
			writeInternal(w)
			return
		}
		writeBytes(w, oldStatus, oldResult)
		return
	}
	if !errors.Is(err, sql.ErrNoRows) {
		writeInternal(w)
		return
	}
	writer, err := newEntryWriter(r.Context(), tx, tenant)
	if err != nil {
		writeInternal(w)
		return
	}
	st := &writeState{tx: tx, tenant: tenant, writer: writer}
	status, payload, ae, err := fn(st)
	if ae != nil {
		writeAPIError(w, ae)
		return
	}
	if err != nil {
		writeInternal(w)
		return
	}
	if err := writer.flush(r.Context(), tx); err != nil {
		writeInternal(w)
		return
	}
	result, err := json.Marshal(payload)
	if err != nil {
		writeInternal(w)
		return
	}
	if _, err := tx.ExecContext(r.Context(), `INSERT INTO idempotency(tenant,key,path,body_hash,status,result_json) VALUES(?,?,?,?,?,?)`, tenant, key, path, bodyHash, status, result); err != nil {
		writeInternal(w)
		return
	}
	if err := tx.Commit(); err != nil {
		writeInternal(w)
		return
	}
	writeBytes(w, status, result)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	b, err := json.Marshal(value)
	if err != nil {
		writeInternal(w)
		return
	}
	writeBytes(w, status, b)
}

func writeBytes(w http.ResponseWriter, status int, b []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(b)
}

func writeAPIError(w http.ResponseWriter, ae *apiError) {
	if ae == nil {
		writeInternal(w)
		return
	}
	writeError(w, ae.status, ae.code)
}

func writeInternal(w http.ResponseWriter) { writeError(w, 500, "internal") }

func writeError(w http.ResponseWriter, status int, code string) {
	writeJSON(w, status, map[string]any{"error": map[string]string{"code": code}})
}
