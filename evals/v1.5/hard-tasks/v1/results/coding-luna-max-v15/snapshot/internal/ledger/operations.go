package ledger

import (
	"context"
	"database/sql"
	"errors"
	"sort"
)

func loadAccount(ctx context.Context, q interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}, tenant, name string) (Account, error) {
	var balance, reserved, version int64
	err := q.QueryRowContext(ctx, `SELECT balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, tenant, name).
		Scan(&balance, &reserved, &version)
	if err != nil {
		return Account{}, err
	}
	return account(name, balance, reserved, version), nil
}

func storeAccount(ctx context.Context, tx *sql.Tx, tenant string, a Account) error {
	_, err := tx.ExecContext(ctx, `UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?`,
		a.Balance, a.Reserved, a.Version, tenant, a.Name)
	return err
}

func nextVersion(version int64) (int64, error) {
	if version == int64(^uint64(0)>>1) {
		return 0, errors.New("account version overflow")
	}
	return version + 1, nil
}

type createAccountRequest struct {
	Name    string      `json:"name"`
	Opening OptionalInt `json:"opening"`
}

func createAccount(ctx context.Context, tx *sql.Tx, tenant string, raw []byte) (int, any, error) {
	var req createAccountRequest
	if err := decodeBody(raw, &req); err != nil || !validName(req.Name) || !req.Opening.Set || req.Opening.Value < 0 || req.Opening.Value > 1_000_000_000 {
		return 0, nil, invalid()
	}
	var exists int
	err := tx.QueryRowContext(ctx, `SELECT 1 FROM accounts WHERE tenant=? AND name=?`, tenant, req.Name).Scan(&exists)
	if err == nil {
		return 0, nil, conflict("exists")
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return 0, nil, err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,1)`, tenant, req.Name, req.Opening.Value); err != nil {
		return 0, nil, err
	}
	operationID, err := newID(ctx, tx, tenant)
	if err != nil {
		return 0, nil, err
	}
	if err := addEntry(ctx, tx, tenant, req.Name, "opening", req.Opening.Value, 0, operationID, nil); err != nil {
		return 0, nil, err
	}
	return 201, map[string]any{"account": account(req.Name, req.Opening.Value, 0, 1)}, nil
}

type transferRequest struct {
	From        string      `json:"from"`
	To          string      `json:"to"`
	Amount      OptionalInt `json:"amount"`
	FromVersion OptionalInt `json:"from_version"`
	ToVersion   OptionalInt `json:"to_version"`
}

func (r transferRequest) validate() *APIError {
	if !validName(r.From) || !validName(r.To) || r.From == r.To || !validAmount(r.Amount) ||
		!checkOptionalVersions(r.FromVersion, r.ToVersion) {
		return invalid()
	}
	return nil
}

func postTransfer(ctx context.Context, tx *sql.Tx, tenant string, raw []byte) (int, any, error) {
	var req transferRequest
	if err := decodeBody(raw, &req); err != nil {
		return 0, nil, invalid()
	}
	if apiErr := req.validate(); apiErr != nil {
		return 0, nil, apiErr
	}
	staged := make(map[string]Account, 2)
	transfer, _, _, err := applyOrdinaryTransfer(ctx, tx, tenant, req, staged, "transfer")
	if err != nil {
		return 0, nil, err
	}
	accounts := []Account{staged[transfer.From], staged[transfer.To]}
	return 201, map[string]any{"transfer": transfer, "accounts": accounts}, nil
}

type batchRequest struct {
	Transfers []transferRequest `json:"transfers"`
}

func postBatch(ctx context.Context, tx *sql.Tx, tenant string, raw []byte) (int, any, error) {
	var req batchRequest
	if err := decodeBody(raw, &req); err != nil || len(req.Transfers) < 1 || len(req.Transfers) > 20 {
		return 0, nil, invalid()
	}
	staged := make(map[string]Account)
	transfers := make([]Transfer, 0, len(req.Transfers))
	for _, item := range req.Transfers {
		if apiErr := item.validate(); apiErr != nil {
			return 0, nil, apiErr
		}
		transfer, _, _, err := applyOrdinaryTransfer(ctx, tx, tenant, item, staged, "transfer")
		if err != nil {
			return 0, nil, err
		}
		transfers = append(transfers, transfer)
	}
	accounts := make([]Account, 0, len(staged))
	for _, a := range staged {
		accounts = append(accounts, a)
	}
	sort.Slice(accounts, func(i, j int) bool { return accounts[i].Name < accounts[j].Name })
	return 201, map[string]any{"transfers": transfers, "accounts": accounts}, nil
}

func stagedAccount(ctx context.Context, tx *sql.Tx, tenant, name string, staged map[string]Account) (Account, error) {
	if a, ok := staged[name]; ok {
		return a, nil
	}
	a, err := loadAccount(ctx, tx, tenant, name)
	if err != nil {
		return Account{}, err
	}
	return a, nil
}

func checkVersion(expected OptionalInt, current int64) *APIError {
	if expected.Set && expected.Value != current {
		return conflict("version_conflict")
	}
	return nil
}

func applyOrdinaryTransfer(ctx context.Context, tx *sql.Tx, tenant string, req transferRequest, staged map[string]Account, kind string) (Transfer, Account, Account, error) {
	from, err := stagedAccount(ctx, tx, tenant, req.From, staged)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return Transfer{}, Account{}, Account{}, missing()
		}
		return Transfer{}, Account{}, Account{}, err
	}
	to, err := stagedAccount(ctx, tx, tenant, req.To, staged)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return Transfer{}, Account{}, Account{}, missing()
		}
		return Transfer{}, Account{}, Account{}, err
	}
	if apiErr := checkVersion(req.FromVersion, from.Version); apiErr != nil {
		return Transfer{}, Account{}, Account{}, apiErr
	}
	if apiErr := checkVersion(req.ToVersion, to.Version); apiErr != nil {
		return Transfer{}, Account{}, Account{}, apiErr
	}
	amount := req.Amount.Value
	if from.Available < amount {
		return Transfer{}, Account{}, Account{}, conflict("insufficient")
	}
	newToBalance, err := checkedAdd(to.Balance, amount)
	if err != nil || newToBalance > maxValue {
		return Transfer{}, Account{}, Account{}, conflict("insufficient")
	}
	fromVersion, err := nextVersion(from.Version)
	if err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	toVersion, err := nextVersion(to.Version)
	if err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	from = account(from.Name, from.Balance-amount, from.Reserved, fromVersion)
	to = account(to.Name, newToBalance, to.Reserved, toVersion)
	id, err := newID(ctx, tx, tenant)
	if err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,reversal_of,legacy_id) VALUES(?,?,?,?,?,0,NULL,NULL)`,
		tenant, id, req.From, req.To, amount); err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	if err := addEntry(ctx, tx, tenant, req.From, kind, -amount, 0, id, nil); err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	if err := addEntry(ctx, tx, tenant, req.To, kind, amount, 0, id, nil); err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	if err := storeAccount(ctx, tx, tenant, from); err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	if err := storeAccount(ctx, tx, tenant, to); err != nil {
		return Transfer{}, Account{}, Account{}, err
	}
	staged[req.From], staged[req.To] = from, to
	return Transfer{ID: id, From: req.From, To: req.To, Amount: amount}, from, to, nil
}

type createHoldRequest struct {
	Account string      `json:"account"`
	Amount  OptionalInt `json:"amount"`
	Version OptionalInt `json:"version"`
}

func createHold(ctx context.Context, tx *sql.Tx, tenant string, raw []byte) (int, any, error) {
	var req createHoldRequest
	if err := decodeBody(raw, &req); err != nil || !validName(req.Account) || !validAmount(req.Amount) || !checkOptionalVersions(req.Version) {
		return 0, nil, invalid()
	}
	acct, err := loadAccount(ctx, tx, tenant, req.Account)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	if apiErr := checkVersion(req.Version, acct.Version); apiErr != nil {
		return 0, nil, apiErr
	}
	if acct.Available < req.Amount.Value {
		return 0, nil, conflict("insufficient")
	}
	version, err := nextVersion(acct.Version)
	if err != nil {
		return 0, nil, err
	}
	acct = account(acct.Name, acct.Balance, acct.Reserved+req.Amount.Value, version)
	id, err := newID(ctx, tx, tenant)
	if err != nil {
		return 0, nil, err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO holds(tenant,id,account,amount,state) VALUES(?,?,?,?,'active')`, tenant, id, req.Account, req.Amount.Value); err != nil {
		return 0, nil, err
	}
	if err := storeAccount(ctx, tx, tenant, acct); err != nil {
		return 0, nil, err
	}
	if err := addEntry(ctx, tx, tenant, req.Account, "hold", 0, req.Amount.Value, id, nil); err != nil {
		return 0, nil, err
	}
	hold := Hold{ID: id, Account: req.Account, Amount: req.Amount.Value, State: "active"}
	return 201, map[string]any{"hold": hold, "account": acct}, nil
}

type captureHoldRequest struct {
	To          string      `json:"to"`
	FromVersion OptionalInt `json:"from_version"`
	ToVersion   OptionalInt `json:"to_version"`
}

type storedHold struct {
	id      string
	account string
	amount  int64
	state   string
}

func findHold(ctx context.Context, tx *sql.Tx, tenant, id string) (storedHold, error) {
	var h storedHold
	err := tx.QueryRowContext(ctx, `SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?`, tenant, id).
		Scan(&h.id, &h.account, &h.amount, &h.state)
	return h, err
}

func captureHold(ctx context.Context, tx *sql.Tx, tenant, holdID string, raw []byte) (int, any, error) {
	var req captureHoldRequest
	if err := decodeBody(raw, &req); err != nil || !validName(req.To) || !checkOptionalVersions(req.FromVersion, req.ToVersion) {
		return 0, nil, invalid()
	}
	h, err := findHold(ctx, tx, tenant, holdID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	if h.state != "active" {
		return 0, nil, conflict("terminal")
	}
	if h.account == req.To {
		return 0, nil, invalid()
	}
	from, err := loadAccount(ctx, tx, tenant, h.account)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	to, err := loadAccount(ctx, tx, tenant, req.To)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	if apiErr := checkVersion(req.FromVersion, from.Version); apiErr != nil {
		return 0, nil, apiErr
	}
	if apiErr := checkVersion(req.ToVersion, to.Version); apiErr != nil {
		return 0, nil, apiErr
	}
	if from.Reserved < h.amount || from.Balance < h.amount {
		return 0, nil, errors.New("hold/account invariant violated")
	}
	newToBalance, err := checkedAdd(to.Balance, h.amount)
	if err != nil || newToBalance > maxValue {
		return 0, nil, conflict("insufficient")
	}
	fromVersion, err := nextVersion(from.Version)
	if err != nil {
		return 0, nil, err
	}
	toVersion, err := nextVersion(to.Version)
	if err != nil {
		return 0, nil, err
	}
	from = account(from.Name, from.Balance-h.amount, from.Reserved-h.amount, fromVersion)
	to = account(to.Name, newToBalance, to.Reserved, toVersion)
	id, err := newID(ctx, tx, tenant)
	if err != nil {
		return 0, nil, err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,reversal_of,legacy_id) VALUES(?,?,?,?,?,0,NULL,NULL)`,
		tenant, id, h.account, req.To, h.amount); err != nil {
		return 0, nil, err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE holds SET state='captured' WHERE tenant=? AND id=?`, tenant, holdID); err != nil {
		return 0, nil, err
	}
	if err := storeAccount(ctx, tx, tenant, from); err != nil {
		return 0, nil, err
	}
	if err := storeAccount(ctx, tx, tenant, to); err != nil {
		return 0, nil, err
	}
	if err := addEntry(ctx, tx, tenant, h.account, "capture", -h.amount, -h.amount, id, nil); err != nil {
		return 0, nil, err
	}
	if err := addEntry(ctx, tx, tenant, req.To, "capture", h.amount, 0, id, nil); err != nil {
		return 0, nil, err
	}
	hold := Hold{ID: h.id, Account: h.account, Amount: h.amount, State: "captured"}
	transfer := Transfer{ID: id, From: h.account, To: req.To, Amount: h.amount}
	return 200, map[string]any{"hold": hold, "transfer": transfer, "accounts": []Account{from, to}}, nil
}

type releaseHoldRequest struct {
	Version OptionalInt `json:"version"`
}

func releaseHold(ctx context.Context, tx *sql.Tx, tenant, holdID string, raw []byte) (int, any, error) {
	var req releaseHoldRequest
	if err := decodeBody(raw, &req); err != nil || !checkOptionalVersions(req.Version) {
		return 0, nil, invalid()
	}
	h, err := findHold(ctx, tx, tenant, holdID)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	if h.state != "active" {
		return 0, nil, conflict("terminal")
	}
	acct, err := loadAccount(ctx, tx, tenant, h.account)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	if apiErr := checkVersion(req.Version, acct.Version); apiErr != nil {
		return 0, nil, apiErr
	}
	if acct.Reserved < h.amount {
		return 0, nil, errors.New("hold/account invariant violated")
	}
	version, err := nextVersion(acct.Version)
	if err != nil {
		return 0, nil, err
	}
	acct = account(acct.Name, acct.Balance, acct.Reserved-h.amount, version)
	if err := storeAccount(ctx, tx, tenant, acct); err != nil {
		return 0, nil, err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE holds SET state='released' WHERE tenant=? AND id=?`, tenant, holdID); err != nil {
		return 0, nil, err
	}
	if err := addEntry(ctx, tx, tenant, h.account, "release", 0, -h.amount, h.id, nil); err != nil {
		return 0, nil, err
	}
	hold := Hold{ID: h.id, Account: h.account, Amount: h.amount, State: "released"}
	return 200, map[string]any{"hold": hold, "account": acct}, nil
}

type reverseRequest struct {
	FromVersion OptionalInt `json:"from_version"`
	ToVersion   OptionalInt `json:"to_version"`
}

func reverseTransfer(ctx context.Context, tx *sql.Tx, tenant, transferID string, raw []byte) (int, any, error) {
	var req reverseRequest
	if err := decodeBody(raw, &req); err != nil || !checkOptionalVersions(req.FromVersion, req.ToVersion) {
		return 0, nil, invalid()
	}
	var original Transfer
	var reversalOf sql.NullString
	var reversed int
	var legacy sql.NullInt64
	err := tx.QueryRowContext(ctx, `SELECT id,source,target,amount,reversed,reversal_of,legacy_id FROM transfers WHERE tenant=? AND id=?`, tenant, transferID).
		Scan(&original.ID, &original.From, &original.To, &original.Amount, &reversed, &reversalOf, &legacy)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	original.Reversed = reversed != 0
	if legacy.Valid {
		value := legacy.Int64
		original.LegacyID = &value
	}
	if original.Reversed || reversalOf.Valid {
		return 0, nil, conflict("terminal")
	}
	from, err := loadAccount(ctx, tx, tenant, original.From)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	to, err := loadAccount(ctx, tx, tenant, original.To)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return 0, nil, missing()
		}
		return 0, nil, err
	}
	if apiErr := checkVersion(req.FromVersion, from.Version); apiErr != nil {
		return 0, nil, apiErr
	}
	if apiErr := checkVersion(req.ToVersion, to.Version); apiErr != nil {
		return 0, nil, apiErr
	}
	if to.Available < original.Amount {
		return 0, nil, conflict("insufficient")
	}
	newFromBalance, err := checkedAdd(from.Balance, original.Amount)
	if err != nil || newFromBalance > maxValue {
		return 0, nil, conflict("insufficient")
	}
	fromVersion, err := nextVersion(from.Version)
	if err != nil {
		return 0, nil, err
	}
	toVersion, err := nextVersion(to.Version)
	if err != nil {
		return 0, nil, err
	}
	from = account(from.Name, newFromBalance, from.Reserved, fromVersion)
	to = account(to.Name, to.Balance-original.Amount, to.Reserved, toVersion)
	id, err := newID(ctx, tx, tenant)
	if err != nil {
		return 0, nil, err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,reversal_of,legacy_id) VALUES(?,?,?,?,?,0,?,NULL)`,
		tenant, id, original.To, original.From, original.Amount, original.ID); err != nil {
		return 0, nil, err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?`, tenant, original.ID); err != nil {
		return 0, nil, err
	}
	original.Reversed = true
	if err := storeAccount(ctx, tx, tenant, from); err != nil {
		return 0, nil, err
	}
	if err := storeAccount(ctx, tx, tenant, to); err != nil {
		return 0, nil, err
	}
	if err := addEntry(ctx, tx, tenant, original.To, "reversal", -original.Amount, 0, id, nil); err != nil {
		return 0, nil, err
	}
	if err := addEntry(ctx, tx, tenant, original.From, "reversal", original.Amount, 0, id, nil); err != nil {
		return 0, nil, err
	}
	reversal := Transfer{ID: id, From: original.To, To: original.From, Amount: original.Amount}
	return 200, map[string]any{"transfer": original, "reversal": reversal, "accounts": []Account{from, to}}, nil
}
