package ledger

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"math"
)

type Store struct {
	read  *sql.DB
	write *sql.DB
}

func NewStore(read, write *sql.DB) *Store { return &Store{read: read, write: write} }

func (s *Store) Close() error {
	e1 := s.read.Close()
	e2 := s.write.Close()
	if e1 != nil {
		return e1
	}
	return e2
}

func (s *Store) Migrate(ctx context.Context) error {
	tx, err := s.write.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	var version int
	if err := tx.QueryRowContext(ctx, "PRAGMA user_version").Scan(&version); err != nil {
		return err
	}
	if version > 2 {
		return fmt.Errorf("database version %d is newer than supported", version)
	}
	if version == 2 {
		return tx.Commit()
	}
	if err := createSchema(ctx, tx); err != nil {
		return err
	}
	if version == 1 {
		if err := importLegacy(ctx, tx); err != nil {
			return err
		}
	}
	if _, err := tx.ExecContext(ctx, "PRAGMA user_version=2"); err != nil {
		return err
	}
	return tx.Commit()
}

func createSchema(ctx context.Context, tx *sql.Tx) error {
	statements := []string{
		`CREATE TABLE IF NOT EXISTS accounts (
			tenant TEXT NOT NULL, name TEXT NOT NULL,
			balance INTEGER NOT NULL CHECK(balance >= 0 AND balance <= 9000000000000000),
			reserved INTEGER NOT NULL CHECK(reserved >= 0 AND reserved <= balance),
			version INTEGER NOT NULL CHECK(version > 0),
			PRIMARY KEY(tenant,name)
		)`,
		`CREATE TABLE IF NOT EXISTS ids (tenant TEXT NOT NULL, id TEXT NOT NULL, PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS transfers (
			tenant TEXT NOT NULL, id TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL,
			amount INTEGER NOT NULL, reversed INTEGER NOT NULL DEFAULT 0,
			reversal_of TEXT, legacy_id INTEGER,
			PRIMARY KEY(tenant,id)
		)`,
		`CREATE UNIQUE INDEX IF NOT EXISTS transfers_one_reversal ON transfers(tenant,reversal_of) WHERE reversal_of IS NOT NULL`,
		`CREATE TABLE IF NOT EXISTS holds (
			tenant TEXT NOT NULL, id TEXT NOT NULL, account TEXT NOT NULL,
			amount INTEGER NOT NULL, state TEXT NOT NULL CHECK(state IN ('active','captured','released')),
			PRIMARY KEY(tenant,id)
		)`,
		`CREATE TABLE IF NOT EXISTS entries (
			seq INTEGER PRIMARY KEY AUTOINCREMENT,
			tenant TEXT NOT NULL, account TEXT NOT NULL, kind TEXT NOT NULL,
			balance_delta INTEGER NOT NULL, reserved_delta INTEGER NOT NULL,
			operation_id TEXT NOT NULL, legacy_id INTEGER
		)`,
		`CREATE INDEX IF NOT EXISTS entries_tenant_seq ON entries(tenant,seq)`,
		`CREATE INDEX IF NOT EXISTS entries_tenant_account_seq ON entries(tenant,account,seq)`,
		`CREATE TABLE IF NOT EXISTS idempotency (
			tenant TEXT NOT NULL, key TEXT NOT NULL, path TEXT NOT NULL, body TEXT NOT NULL,
			status INTEGER NOT NULL, result BLOB NOT NULL,
			PRIMARY KEY(tenant,key)
		)`,
	}
	for _, statement := range statements {
		if _, err := tx.ExecContext(ctx, statement); err != nil {
			return err
		}
	}
	return nil
}

type legacyAccount struct {
	tenant string
	name   string
	final  int64
	open   int64
	touch  int64
}

type legacyMovement struct {
	id     int64
	tenant string
	source string
	target string
	units  int64
}

func importLegacy(ctx context.Context, tx *sql.Tx) error {
	var legacyTable string
	if err := tx.QueryRowContext(ctx, `SELECT name FROM sqlite_master WHERE type='table' AND name='legacy_accounts'`).Scan(&legacyTable); err != nil {
		return errors.New("version 1 database is missing legacy_accounts")
	}
	accounts := make([]legacyAccount, 0)
	accountIndex := make(map[string]int)
	rows, err := tx.QueryContext(ctx, `SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name`)
	if err != nil {
		return err
	}
	for rows.Next() {
		var a legacyAccount
		if err := rows.Scan(&a.tenant, &a.name, &a.final); err != nil {
			rows.Close()
			return err
		}
		accountIndex[legacyKey(a.tenant, a.name)] = len(accounts)
		accounts = append(accounts, a)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	if err := rows.Close(); err != nil {
		return err
	}
	movements := make([]legacyMovement, 0)
	rows, err = tx.QueryContext(ctx, `SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id`)
	if err != nil {
		return err
	}
	for rows.Next() {
		var m legacyMovement
		if err := rows.Scan(&m.id, &m.tenant, &m.source, &m.target, &m.units); err != nil {
			rows.Close()
			return err
		}
		if m.units <= 0 || m.units > 1_000_000_000 || m.source == m.target {
			rows.Close()
			return errors.New("invalid legacy movement")
		}
		si, sok := accountIndex[legacyKey(m.tenant, m.source)]
		ti, tok := accountIndex[legacyKey(m.tenant, m.target)]
		if !sok || !tok {
			rows.Close()
			return errors.New("legacy movement references a missing account")
		}
		accounts[si].open, err = checkedAdd(accounts[si].open, m.units)
		if err == nil {
			accounts[ti].open, err = checkedAdd(accounts[ti].open, -m.units)
		}
		if err != nil {
			rows.Close()
			return errors.New("legacy opening balance overflow")
		}
		accounts[si].touch++
		accounts[ti].touch++
		movements = append(movements, m)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	if err := rows.Close(); err != nil {
		return err
	}
	for i := range accounts {
		a := &accounts[i]
		if a.final < 0 || a.final > maxValue {
			return errors.New("legacy account balance is outside the supported range")
		}
		// The legacy opening is final + outgoing - incoming. The accumulator above
		// stores outgoing minus incoming, so add the final balance once.
		a.open, err = checkedAdd(a.final, a.open)
		if err != nil || a.open < 0 || a.open > maxValue {
			return errors.New("legacy inferred opening balance is outside the supported range")
		}
		if _, err := tx.ExecContext(ctx,
			`INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,?)`,
			a.tenant, a.name, a.final, a.touch+1); err != nil {
			return err
		}
		openingID, err := newID(ctx, tx, a.tenant)
		if err != nil {
			return err
		}
		if err := addEntry(ctx, tx, a.tenant, a.name, "opening", a.open, 0, openingID, nil); err != nil {
			return err
		}
	}
	for _, m := range movements {
		transferID, err := newID(ctx, tx, m.tenant)
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx,
			`INSERT INTO transfers(tenant,id,source,target,amount,reversed,reversal_of,legacy_id) VALUES(?,?,?,?,?,0,NULL,?)`,
			m.tenant, transferID, m.source, m.target, m.units, m.id); err != nil {
			return err
		}
		legacyID := m.id
		if err := addEntry(ctx, tx, m.tenant, m.source, "transfer", -m.units, 0, transferID, &legacyID); err != nil {
			return err
		}
		if err := addEntry(ctx, tx, m.tenant, m.target, "transfer", m.units, 0, transferID, &legacyID); err != nil {
			return err
		}
	}
	return nil
}

func legacyKey(tenant, name string) string { return tenant + "\x00" + name }

func checkedAdd(a, b int64) (int64, error) {
	if (b > 0 && a > math.MaxInt64-b) || (b < 0 && a < math.MinInt64-b) {
		return 0, errors.New("integer overflow")
	}
	return a + b, nil
}

func newID(ctx context.Context, tx *sql.Tx, tenant string) (string, error) {
	for attempt := 0; attempt < 8; attempt++ {
		id, err := randomID()
		if err != nil {
			return "", err
		}
		result, err := tx.ExecContext(ctx, `INSERT OR IGNORE INTO ids(tenant,id) VALUES(?,?)`, tenant, id)
		if err != nil {
			return "", err
		}
		n, err := result.RowsAffected()
		if err != nil {
			return "", err
		}
		if n == 1 {
			return id, nil
		}
	}
	return "", errors.New("could not allocate unique identifier")
}

func addEntry(ctx context.Context, tx *sql.Tx, tenant, name, kind string, balanceDelta, reservedDelta int64, operationID string, legacyID *int64) error {
	_, err := tx.ExecContext(ctx,
		`INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?)`,
		tenant, name, kind, balanceDelta, reservedDelta, operationID, legacyID)
	return err
}
