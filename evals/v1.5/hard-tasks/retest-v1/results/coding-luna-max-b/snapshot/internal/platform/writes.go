package platform

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"sort"
)

type Service struct{ db *sql.DB }

func NewService(db *sql.DB) *Service { return &Service{db: db} }

type mutation func(dbRunner) (int, any, *apiError)

func (s *Service) mutate(ctx context.Context, tenant, key, path, canonical string, apply mutation) (int, []byte, *apiError, error) {
	tx, err := s.db.BeginTx(ctx, nil) // DSN sets BEGIN IMMEDIATE for every writer.
	if err != nil {
		return 0, nil, nil, err
	}
	defer tx.Rollback()

	var oldPath, oldBody string
	var oldStatus int
	var oldResult []byte
	err = tx.QueryRowContext(ctx, `SELECT request_path,request_body,status,response_json FROM idempotency WHERE tenant=? AND key=?`, tenant, key).Scan(&oldPath, &oldBody, &oldStatus, &oldResult)
	if err == nil {
		if oldPath != path || oldBody != canonical {
			return 0, nil, conflict("idempotency_conflict"), nil
		}
		return oldStatus, append([]byte(nil), oldResult...), nil, nil
	}
	if err != sql.ErrNoRows {
		return 0, nil, nil, err
	}
	status, result, appErr := apply(tx)
	if appErr != nil {
		return 0, nil, appErr, nil
	}
	body, err := json.Marshal(result)
	if err != nil {
		return 0, nil, nil, err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO idempotency(tenant,key,request_path,request_body,status,response_json) VALUES(?,?,?,?,?,?)`, tenant, key, path, canonical, status, body); err != nil {
		return 0, nil, nil, err
	}
	if err := tx.Commit(); err != nil {
		return 0, nil, nil, err
	}
	return status, body, nil, nil
}

func insertObjectID(tx dbRunner, tenant string) (string, error) {
	for tries := 0; tries < 8; tries++ {
		var random [16]byte
		if _, err := rand.Read(random[:]); err != nil {
			return "", err
		}
		id := hex.EncodeToString(random[:])
		res, err := tx.ExecContext(context.Background(), `INSERT INTO object_ids(tenant,id) VALUES(?,?) ON CONFLICT DO NOTHING`, tenant, id)
		if err != nil {
			return "", err
		}
		n, err := res.RowsAffected()
		if err != nil {
			return "", err
		}
		if n == 1 {
			return id, nil
		}
	}
	return "", fmt.Errorf("could not allocate unique identifier")
}

func loadAccount(tx dbRunner, tenant, name string) (account, *apiError, error) {
	var balance, reserved, version int64
	err := tx.QueryRowContext(context.Background(), `SELECT balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, tenant, name).Scan(&balance, &reserved, &version)
	if err == sql.ErrNoRows {
		return account{}, notFound(), nil
	}
	if err != nil {
		return account{}, nil, err
	}
	return makeAccount(name, balance, reserved, version), nil, nil
}

func saveAccount(tx dbRunner, tenant string, a account) error {
	res, err := tx.ExecContext(context.Background(), `UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?`, a.Balance, a.Reserved, a.Version, tenant, a.Name)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n != 1 {
		return fmt.Errorf("account disappeared during write")
	}
	return nil
}

func nextVersion(a *account) error {
	if a.Version == math.MaxInt64 {
		return fmt.Errorf("account version overflow")
	}
	a.Version++
	return nil
}

func addEntry(tx dbRunner, tenant, name, kind string, balanceDelta, reservedDelta int64, operationID string, legacyID *int64) error {
	if legacyID == nil {
		_, err := tx.ExecContext(context.Background(), `INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id) VALUES(?,?,?,?,?,?)`, tenant, name, kind, balanceDelta, reservedDelta, operationID)
		return err
	}
	_, err := tx.ExecContext(context.Background(), `INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?)`, tenant, name, kind, balanceDelta, reservedDelta, operationID, *legacyID)
	return err
}

func insertTransfer(tx dbRunner, tenant string, t transferObject, reversalOf string) error {
	var parent any
	if reversalOf != "" {
		parent = reversalOf
	}
	_, err := tx.ExecContext(context.Background(), `INSERT INTO transfers(tenant,id,from_name,to_name,amount,reversed,reversal_of) VALUES(?,?,?,?,?,?,?)`, tenant, t.ID, t.From, t.To, t.Amount, boolInt(t.Reversed), parent)
	return err
}

func boolInt(v bool) int {
	if v {
		return 1
	}
	return 0
}

func (s *Service) createAccount(ctx context.Context, tenant, key, path, canonical, name string, opening int64) (int, []byte, *apiError, error) {
	return s.mutate(ctx, tenant, key, path, canonical, func(tx dbRunner) (int, any, *apiError) {
		var exists int
		err := tx.QueryRowContext(ctx, `SELECT 1 FROM accounts WHERE tenant=? AND name=?`, tenant, name).Scan(&exists)
		if err == nil {
			return 0, nil, conflict("exists")
		}
		if err != sql.ErrNoRows {
			return 0, nil, internal()
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,1)`, tenant, name, opening); err != nil {
			return 0, nil, internal()
		}
		id, err := insertObjectID(tx, tenant)
		if err != nil {
			return 0, nil, internal()
		}
		if err := addEntry(tx, tenant, name, "opening", opening, 0, id, nil); err != nil {
			return 0, nil, internal()
		}
		a := makeAccount(name, opening, 0, 1)
		return 201, struct {
			Account account `json:"account"`
		}{a}, nil
	})
}

func (s *Service) accountTransfer(tx dbRunner, tenant string, req transferRequest) (transferObject, account, account, *apiError) {
	from, appErr, err := loadAccount(tx, tenant, req.From)
	if err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	if appErr != nil {
		return transferObject{}, account{}, account{}, appErr
	}
	to, appErr, err := loadAccount(tx, tenant, req.To)
	if err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	if appErr != nil {
		return transferObject{}, account{}, account{}, appErr
	}
	if appErr = checkVersion(from.Version, req.FromVersion); appErr != nil {
		return transferObject{}, account{}, account{}, appErr
	}
	if appErr = checkVersion(to.Version, req.ToVersion); appErr != nil {
		return transferObject{}, account{}, account{}, appErr
	}
	if from.Available < req.Amount {
		return transferObject{}, account{}, account{}, conflict("insufficient")
	}
	if to.Balance > maxBalance-req.Amount {
		return transferObject{}, account{}, account{}, conflict("insufficient")
	}
	if err := nextVersion(&from); err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	if err := nextVersion(&to); err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	from.Balance -= req.Amount
	from.Available -= req.Amount
	to.Balance += req.Amount
	to.Available += req.Amount
	id, err := insertObjectID(tx, tenant)
	if err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	t := transferObject{ID: id, From: req.From, To: req.To, Amount: req.Amount}
	if err := saveAccount(tx, tenant, from); err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	if err := saveAccount(tx, tenant, to); err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	if err := insertTransfer(tx, tenant, t, ""); err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	if err := addEntry(tx, tenant, req.From, "transfer", -req.Amount, 0, id, nil); err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	if err := addEntry(tx, tenant, req.To, "transfer", req.Amount, 0, id, nil); err != nil {
		return transferObject{}, account{}, account{}, internal()
	}
	return t, from, to, nil
}

func (s *Service) transfer(ctx context.Context, tenant, key, path, canonical string, req transferRequest) (int, []byte, *apiError, error) {
	return s.mutate(ctx, tenant, key, path, canonical, func(tx dbRunner) (int, any, *apiError) {
		t, from, to, appErr := s.accountTransfer(tx, tenant, req)
		if appErr != nil {
			return 0, nil, appErr
		}
		return 201, struct {
			Transfer transferObject `json:"transfer"`
			Accounts []account      `json:"accounts"`
		}{t, []account{from, to}}, nil
	})
}

func (s *Service) batch(ctx context.Context, tenant, key, path, canonical string, requests []transferRequest) (int, []byte, *apiError, error) {
	return s.mutate(ctx, tenant, key, path, canonical, func(tx dbRunner) (int, any, *apiError) {
		transfers := make([]transferObject, 0, len(requests))
		touched := make(map[string]account)
		for _, req := range requests {
			t, from, to, appErr := s.accountTransfer(tx, tenant, req)
			if appErr != nil {
				return 0, nil, appErr
			}
			transfers = append(transfers, t)
			touched[from.Name] = from
			touched[to.Name] = to
		}
		names := make([]string, 0, len(touched))
		for name := range touched {
			names = append(names, name)
		}
		sort.Strings(names)
		accounts := make([]account, 0, len(names))
		for _, name := range names {
			accounts = append(accounts, touched[name])
		}
		return 201, struct {
			Transfers []transferObject `json:"transfers"`
			Accounts  []account        `json:"accounts"`
		}{transfers, accounts}, nil
	})
}

func (s *Service) createHold(ctx context.Context, tenant, key, path, canonical, name string, amount int64, version OptionalVersion) (int, []byte, *apiError, error) {
	return s.mutate(ctx, tenant, key, path, canonical, func(tx dbRunner) (int, any, *apiError) {
		a, appErr, err := loadAccount(tx, tenant, name)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		if appErr = checkVersion(a.Version, version); appErr != nil {
			return 0, nil, appErr
		}
		if a.Available < amount {
			return 0, nil, conflict("insufficient")
		}
		if err := nextVersion(&a); err != nil {
			return 0, nil, internal()
		}
		a.Reserved += amount
		a.Available -= amount
		id, err := insertObjectID(tx, tenant)
		if err != nil {
			return 0, nil, internal()
		}
		if err := saveAccount(tx, tenant, a); err != nil {
			return 0, nil, internal()
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO holds(tenant,id,account,amount,state) VALUES(?,?,?,?,'active')`, tenant, id, name, amount); err != nil {
			return 0, nil, internal()
		}
		if err := addEntry(tx, tenant, name, "hold", 0, amount, id, nil); err != nil {
			return 0, nil, internal()
		}
		h := holdObject{ID: id, Account: name, Amount: amount, State: "active"}
		return 201, struct {
			Hold    holdObject `json:"hold"`
			Account account    `json:"account"`
		}{h, a}, nil
	})
}

type holdRecord struct {
	object holdObject
}

func loadHold(tx dbRunner, tenant, id string) (holdRecord, *apiError, error) {
	var h holdRecord
	err := tx.QueryRowContext(context.Background(), `SELECT account,amount,state FROM holds WHERE tenant=? AND id=?`, tenant, id).Scan(&h.object.Account, &h.object.Amount, &h.object.State)
	if err == sql.ErrNoRows {
		return holdRecord{}, notFound(), nil
	}
	if err != nil {
		return holdRecord{}, nil, err
	}
	h.object.ID = id
	return h, nil, nil
}

func (s *Service) releaseHold(ctx context.Context, tenant, key, path, canonical, id string, version OptionalVersion) (int, []byte, *apiError, error) {
	return s.mutate(ctx, tenant, key, path, canonical, func(tx dbRunner) (int, any, *apiError) {
		h, appErr, err := loadHold(tx, tenant, id)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		if h.object.State != "active" {
			return 0, nil, conflict("terminal")
		}
		a, appErr, err := loadAccount(tx, tenant, h.object.Account)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		if appErr = checkVersion(a.Version, version); appErr != nil {
			return 0, nil, appErr
		}
		if a.Reserved < h.object.Amount {
			return 0, nil, internal()
		}
		if err := nextVersion(&a); err != nil {
			return 0, nil, internal()
		}
		a.Reserved -= h.object.Amount
		a.Available += h.object.Amount
		if err := saveAccount(tx, tenant, a); err != nil {
			return 0, nil, internal()
		}
		if _, err := tx.ExecContext(ctx, `UPDATE holds SET state='released' WHERE tenant=? AND id=?`, tenant, id); err != nil {
			return 0, nil, internal()
		}
		if err := addEntry(tx, tenant, a.Name, "release", 0, -h.object.Amount, id, nil); err != nil {
			return 0, nil, internal()
		}
		h.object.State = "released"
		return 200, struct {
			Hold    holdObject `json:"hold"`
			Account account    `json:"account"`
		}{h.object, a}, nil
	})
}

func (s *Service) captureHold(ctx context.Context, tenant, key, path, canonical, id, destination string, fromVersion, toVersion OptionalVersion) (int, []byte, *apiError, error) {
	return s.mutate(ctx, tenant, key, path, canonical, func(tx dbRunner) (int, any, *apiError) {
		h, appErr, err := loadHold(tx, tenant, id)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		if h.object.State != "active" {
			return 0, nil, conflict("terminal")
		}
		if destination == h.object.Account {
			return 0, nil, invalid()
		}
		from, appErr, err := loadAccount(tx, tenant, h.object.Account)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		to, appErr, err := loadAccount(tx, tenant, destination)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		if appErr = checkVersion(from.Version, fromVersion); appErr != nil {
			return 0, nil, appErr
		}
		if appErr = checkVersion(to.Version, toVersion); appErr != nil {
			return 0, nil, appErr
		}
		if from.Reserved < h.object.Amount || from.Balance < h.object.Amount {
			return 0, nil, internal()
		}
		if to.Balance > maxBalance-h.object.Amount {
			return 0, nil, conflict("insufficient")
		}
		if err := nextVersion(&from); err != nil {
			return 0, nil, internal()
		}
		if err := nextVersion(&to); err != nil {
			return 0, nil, internal()
		}
		from.Balance -= h.object.Amount
		from.Reserved -= h.object.Amount
		from.Available = from.Balance - from.Reserved
		to.Balance += h.object.Amount
		to.Available += h.object.Amount
		transferID, err := insertObjectID(tx, tenant)
		if err != nil {
			return 0, nil, internal()
		}
		t := transferObject{ID: transferID, From: from.Name, To: to.Name, Amount: h.object.Amount}
		if err := saveAccount(tx, tenant, from); err != nil {
			return 0, nil, internal()
		}
		if err := saveAccount(tx, tenant, to); err != nil {
			return 0, nil, internal()
		}
		if err := insertTransfer(tx, tenant, t, ""); err != nil {
			return 0, nil, internal()
		}
		if _, err := tx.ExecContext(ctx, `UPDATE holds SET state='captured' WHERE tenant=? AND id=?`, tenant, id); err != nil {
			return 0, nil, internal()
		}
		if err := addEntry(tx, tenant, from.Name, "capture", -h.object.Amount, -h.object.Amount, transferID, nil); err != nil {
			return 0, nil, internal()
		}
		if err := addEntry(tx, tenant, to.Name, "capture", h.object.Amount, 0, transferID, nil); err != nil {
			return 0, nil, internal()
		}
		h.object.State = "captured"
		return 200, struct {
			Hold     holdObject     `json:"hold"`
			Transfer transferObject `json:"transfer"`
			Accounts []account      `json:"accounts"`
		}{h.object, t, []account{from, to}}, nil
	})
}

type transferRecord struct {
	object     transferObject
	reversalOf string
}

func loadTransfer(tx dbRunner, tenant, id string) (transferRecord, *apiError, error) {
	var t transferRecord
	var reversed int
	var parent sql.NullString
	err := tx.QueryRowContext(context.Background(), `SELECT from_name,to_name,amount,reversed,reversal_of FROM transfers WHERE tenant=? AND id=?`, tenant, id).Scan(&t.object.From, &t.object.To, &t.object.Amount, &reversed, &parent)
	if err == sql.ErrNoRows {
		return transferRecord{}, notFound(), nil
	}
	if err != nil {
		return transferRecord{}, nil, err
	}
	t.object.ID = id
	t.object.Reversed = reversed != 0
	if parent.Valid {
		t.reversalOf = parent.String
	}
	return t, nil, nil
}

func (s *Service) reverseTransfer(ctx context.Context, tenant, key, path, canonical, id string, fromVersion, toVersion OptionalVersion) (int, []byte, *apiError, error) {
	return s.mutate(ctx, tenant, key, path, canonical, func(tx dbRunner) (int, any, *apiError) {
		original, appErr, err := loadTransfer(tx, tenant, id)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		if original.reversalOf != "" || original.object.Reversed {
			return 0, nil, conflict("terminal")
		}
		from, appErr, err := loadAccount(tx, tenant, original.object.From)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		to, appErr, err := loadAccount(tx, tenant, original.object.To)
		if err != nil {
			return 0, nil, internal()
		}
		if appErr != nil {
			return 0, nil, appErr
		}
		if appErr = checkVersion(from.Version, fromVersion); appErr != nil {
			return 0, nil, appErr
		}
		if appErr = checkVersion(to.Version, toVersion); appErr != nil {
			return 0, nil, appErr
		}
		if to.Available < original.object.Amount {
			return 0, nil, conflict("insufficient")
		}
		if from.Balance > maxBalance-original.object.Amount {
			return 0, nil, conflict("insufficient")
		}
		if err := nextVersion(&from); err != nil {
			return 0, nil, internal()
		}
		if err := nextVersion(&to); err != nil {
			return 0, nil, internal()
		}
		from.Balance += original.object.Amount
		from.Available += original.object.Amount
		to.Balance -= original.object.Amount
		to.Available -= original.object.Amount
		reversalID, err := insertObjectID(tx, tenant)
		if err != nil {
			return 0, nil, internal()
		}
		reversal := transferObject{ID: reversalID, From: original.object.To, To: original.object.From, Amount: original.object.Amount}
		if err := saveAccount(tx, tenant, from); err != nil {
			return 0, nil, internal()
		}
		if err := saveAccount(tx, tenant, to); err != nil {
			return 0, nil, internal()
		}
		if err := insertTransfer(tx, tenant, reversal, id); err != nil {
			return 0, nil, internal()
		}
		if _, err := tx.ExecContext(ctx, `UPDATE transfers SET reversed=1 WHERE tenant=? AND id=?`, tenant, id); err != nil {
			return 0, nil, internal()
		}
		if err := addEntry(tx, tenant, reversal.From, "reversal", -reversal.Amount, 0, reversal.ID, nil); err != nil {
			return 0, nil, internal()
		}
		if err := addEntry(tx, tenant, reversal.To, "reversal", reversal.Amount, 0, reversal.ID, nil); err != nil {
			return 0, nil, internal()
		}
		original.object.Reversed = true
		return 200, struct {
			Transfer transferObject `json:"transfer"`
			Reversal transferObject `json:"reversal"`
			Accounts []account      `json:"accounts"`
		}{original.object, reversal, []account{from, to}}, nil
	})
}
