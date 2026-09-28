package ledger

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"math/big"
	"sort"
)

const maxAccountValue int64 = 9_000_000_000_000_000

type writeTx struct {
	conn *sql.Conn
	ctx  context.Context
	open bool
}

func beginWrite(ctx context.Context, db *sql.DB) (*writeTx, error) {
	conn, err := db.Conn(ctx)
	if err != nil {
		return nil, err
	}
	if _, err = conn.ExecContext(ctx, "BEGIN IMMEDIATE"); err != nil {
		_ = conn.Close()
		return nil, err
	}
	return &writeTx{conn: conn, ctx: ctx, open: true}, nil
}

func (tx *writeTx) rollback() {
	if tx == nil || !tx.open {
		return
	}
	_, _ = tx.conn.ExecContext(context.Background(), "ROLLBACK")
	tx.open = false
	_ = tx.conn.Close()
}

func (tx *writeTx) commit() error {
	if !tx.open {
		return errors.New("transaction is closed")
	}
	_, err := tx.conn.ExecContext(tx.ctx, "COMMIT")
	if err != nil {
		_, _ = tx.conn.ExecContext(context.Background(), "ROLLBACK")
	}
	tx.open = false
	closeErr := tx.conn.Close()
	if err != nil {
		return err
	}
	return closeErr
}

const schemaSQL = `
CREATE TABLE IF NOT EXISTS object_ids (
    tenant TEXT NOT NULL,
    id TEXT NOT NULL,
    PRIMARY KEY (tenant, id)
);
CREATE TABLE IF NOT EXISTS accounts (
    tenant TEXT NOT NULL,
    name TEXT NOT NULL,
    balance INTEGER NOT NULL CHECK (balance >= 0 AND balance <= 9000000000000000),
    reserved INTEGER NOT NULL CHECK (reserved >= 0 AND reserved <= balance),
    version INTEGER NOT NULL CHECK (version >= 1),
    PRIMARY KEY (tenant, name)
);
CREATE TABLE IF NOT EXISTS entries (
    tenant TEXT NOT NULL,
    seq INTEGER NOT NULL CHECK (seq > 0),
    account TEXT NOT NULL,
    kind TEXT NOT NULL,
    balance_delta INTEGER NOT NULL,
    reserved_delta INTEGER NOT NULL,
    operation_id TEXT NOT NULL,
    legacy_id INTEGER,
    PRIMARY KEY (tenant, seq)
);
CREATE INDEX IF NOT EXISTS entries_by_account ON entries (tenant, account, seq);
CREATE TABLE IF NOT EXISTS transfers (
    tenant TEXT NOT NULL,
    id TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0 AND amount <= 1000000000),
    reversed INTEGER NOT NULL DEFAULT 0 CHECK (reversed IN (0, 1)),
    reversal_of TEXT,
    legacy_id INTEGER,
    PRIMARY KEY (tenant, id),
    UNIQUE (tenant, reversal_of)
);
CREATE TABLE IF NOT EXISTS holds (
    tenant TEXT NOT NULL,
    id TEXT NOT NULL,
    account TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0 AND amount <= 1000000000),
    state TEXT NOT NULL CHECK (state IN ('active', 'captured', 'released')),
    PRIMARY KEY (tenant, id)
);
CREATE TABLE IF NOT EXISTS idempotency (
    tenant TEXT NOT NULL,
    key TEXT NOT NULL,
    path TEXT NOT NULL,
    body BLOB NOT NULL,
    status INTEGER NOT NULL,
    response BLOB NOT NULL,
    PRIMARY KEY (tenant, key)
);
`

// Migrate holds an immediate SQLite write lock from version inspection through
// schema installation and legacy import, so two simultaneous starters cannot
// both import the same v1 rows.
func Migrate(ctx context.Context, db *sql.DB) error {
	if err := db.PingContext(ctx); err != nil {
		return err
	}
	tx, err := beginWrite(ctx, db)
	if err != nil {
		return err
	}
	defer tx.rollback()
	var version int
	if err := tx.conn.QueryRowContext(ctx, "PRAGMA user_version").Scan(&version); err != nil {
		return err
	}
	if version > 2 || version < 0 {
		return fmt.Errorf("unsupported SQLite user_version %d", version)
	}
	if _, err := tx.conn.ExecContext(ctx, schemaSQL); err != nil {
		return err
	}
	if version == 1 {
		if err := importLegacy(ctx, tx.conn); err != nil {
			return err
		}
	}
	if version != 2 {
		if _, err := tx.conn.ExecContext(ctx, "PRAGMA user_version = 2"); err != nil {
			return err
		}
	}
	return tx.commit()
}

type legacyAccount struct {
	tenant  string
	name    string
	final   int64
	open    *big.Int
	version int64
}

type legacyMovement struct {
	id     int64
	tenant string
	source string
	target string
	units  int64
}

func importLegacy(ctx context.Context, conn *sql.Conn) error {
	rows, err := conn.QueryContext(ctx, "SELECT tenant, name, balance FROM legacy_accounts ORDER BY tenant, name")
	if err != nil {
		return fmt.Errorf("read legacy accounts: %w", err)
	}
	accounts := make(map[string]*legacyAccount)
	orderedAccounts := make([]*legacyAccount, 0)
	for rows.Next() {
		var a legacyAccount
		if err := rows.Scan(&a.tenant, &a.name, &a.final); err != nil {
			rows.Close()
			return err
		}
		a.open = big.NewInt(a.final)
		a.version = 1
		key := a.tenant + "\x00" + a.name
		accounts[key] = &a
		orderedAccounts = append(orderedAccounts, &a)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	if err := rows.Close(); err != nil {
		return err
	}
	rows, err = conn.QueryContext(ctx, "SELECT id, tenant, source, target, units FROM legacy_movements ORDER BY id")
	if err != nil {
		return fmt.Errorf("read legacy movements: %w", err)
	}
	movements := make([]legacyMovement, 0)
	for rows.Next() {
		var m legacyMovement
		if err := rows.Scan(&m.id, &m.tenant, &m.source, &m.target, &m.units); err != nil {
			rows.Close()
			return err
		}
		if m.units <= 0 || m.units > 1_000_000_000 || m.source == m.target {
			rows.Close()
			return fmt.Errorf("invalid legacy movement %d", m.id)
		}
		source := accounts[m.tenant+"\x00"+m.source]
		target := accounts[m.tenant+"\x00"+m.target]
		if source == nil || target == nil {
			rows.Close()
			return fmt.Errorf("legacy movement %d references a missing account", m.id)
		}
		source.open.Add(source.open, big.NewInt(m.units))
		target.open.Sub(target.open, big.NewInt(m.units))
		source.version++
		target.version++
		movements = append(movements, m)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	if err := rows.Close(); err != nil {
		return err
	}

	// legacy_accounts contains final balances. Back out all movements first,
	// then replay the immutable opening and movement history into the ledger.
	for _, a := range orderedAccounts {
		if a.final < 0 || a.final > maxAccountValue || a.open.Sign() < 0 || !a.open.IsInt64() || a.open.Int64() > maxAccountValue {
			return fmt.Errorf("legacy account %s/%s has an invalid inferred opening", a.tenant, a.name)
		}
		if _, err := conn.ExecContext(ctx, "INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,?)", a.tenant, a.name, a.final, a.version); err != nil {
			return err
		}
		opID, err := allocateID(ctx, conn, a.tenant)
		if err != nil {
			return err
		}
		if err := insertEntry(ctx, conn, a.tenant, a.name, "opening", a.open.Int64(), 0, opID, nil); err != nil {
			return err
		}
	}
	for _, m := range movements {
		id, err := allocateID(ctx, conn, m.tenant)
		if err != nil {
			return err
		}
		if _, err := conn.ExecContext(ctx, "INSERT INTO transfers(tenant,id,source,target,amount,reversed,legacy_id) VALUES(?,?,?,?,?,0,?)", m.tenant, id, m.source, m.target, m.units, m.id); err != nil {
			return err
		}
		legacyID := m.id
		if err := insertEntry(ctx, conn, m.tenant, m.source, "transfer", -m.units, 0, id, &legacyID); err != nil {
			return err
		}
		if err := insertEntry(ctx, conn, m.tenant, m.target, "transfer", m.units, 0, id, &legacyID); err != nil {
			return err
		}
	}
	return nil
}

func allocateID(ctx context.Context, conn *sql.Conn, tenant string) (string, error) {
	for tries := 0; tries < 8; tries++ {
		var raw [16]byte
		if _, err := rand.Read(raw[:]); err != nil {
			return "", err
		}
		id := hex.EncodeToString(raw[:])
		res, err := conn.ExecContext(ctx, "INSERT OR IGNORE INTO object_ids(tenant,id) VALUES(?,?)", tenant, id)
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
	return "", errors.New("could not allocate unique identifier")
}

func insertEntry(ctx context.Context, conn *sql.Conn, tenant, account, kind string, balanceDelta, reservedDelta int64, operationID string, legacyID *int64) error {
	var seq int64
	if err := conn.QueryRowContext(ctx, "SELECT COALESCE(MAX(seq),0)+1 FROM entries WHERE tenant=?", tenant).Scan(&seq); err != nil {
		return err
	}
	var legacy any
	if legacyID != nil {
		legacy = *legacyID
	}
	_, err := conn.ExecContext(ctx, "INSERT INTO entries(tenant,seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?,?)", tenant, seq, account, kind, balanceDelta, reservedDelta, operationID, legacy)
	return err
}

type accountState struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}

func getAccount(ctx context.Context, q interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}, tenant, name string) (accountState, bool, error) {
	var a accountState
	err := q.QueryRowContext(ctx, "SELECT name,balance,reserved,version FROM accounts WHERE tenant=? AND name=?", tenant, name).Scan(&a.Name, &a.Balance, &a.Reserved, &a.Version)
	if errors.Is(err, sql.ErrNoRows) {
		return accountState{}, false, nil
	}
	if err != nil {
		return accountState{}, false, err
	}
	a.Available = a.Balance - a.Reserved
	return a, true, nil
}

func updateAccount(ctx context.Context, conn *sql.Conn, tenant string, a accountState) error {
	if a.Balance < 0 || a.Reserved < 0 || a.Reserved > a.Balance || a.Balance > maxAccountValue {
		return errors.New("account invariant violated")
	}
	_, err := conn.ExecContext(ctx, "UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?", a.Balance, a.Reserved, a.Version, tenant, a.Name)
	return err
}

type transferObject struct {
	ID       string `json:"id"`
	From     string `json:"from"`
	To       string `json:"to"`
	Amount   int64  `json:"amount"`
	Reversed bool   `json:"reversed"`
	LegacyID *int64 `json:"legacy_id,omitempty"`
}

type holdObject struct {
	ID      string `json:"id"`
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	State   string `json:"state"`
}

func sortedAccounts(m map[string]accountState) []accountState {
	names := make([]string, 0, len(m))
	for name := range m {
		names = append(names, name)
	}
	sort.Strings(names)
	result := make([]accountState, 0, len(names))
	for _, name := range names {
		result = append(result, m[name])
	}
	return result
}
