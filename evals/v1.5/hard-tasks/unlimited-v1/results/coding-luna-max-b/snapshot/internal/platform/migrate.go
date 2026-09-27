package platform

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"math"
)

type dbRunner interface {
	ExecContext(context.Context, string, ...any) (sql.Result, error)
	QueryContext(context.Context, string, ...any) (*sql.Rows, error)
	QueryRowContext(context.Context, string, ...any) *sql.Row
}

const maxBalance int64 = 9_000_000_000_000_000

var schemaStatements = []string{
	`CREATE TABLE IF NOT EXISTS accounts (
		tenant TEXT NOT NULL,
		name TEXT NOT NULL,
		balance INTEGER NOT NULL CHECK(balance BETWEEN 0 AND 9000000000000000),
		reserved INTEGER NOT NULL CHECK(reserved BETWEEN 0 AND balance),
		version INTEGER NOT NULL CHECK(version > 0),
		PRIMARY KEY(tenant, name)
	)`,
	`CREATE TABLE IF NOT EXISTS object_ids (
		tenant TEXT NOT NULL,
		id TEXT NOT NULL CHECK(length(id) > 0),
		PRIMARY KEY(tenant, id)
	)`,
	`CREATE TABLE IF NOT EXISTS transfers (
		tenant TEXT NOT NULL,
		id TEXT NOT NULL,
		from_name TEXT NOT NULL,
		to_name TEXT NOT NULL,
		amount INTEGER NOT NULL CHECK(amount BETWEEN 1 AND 1000000000),
		reversed INTEGER NOT NULL DEFAULT 0 CHECK(reversed IN (0,1)),
		reversal_of TEXT,
		legacy_id INTEGER,
		PRIMARY KEY(tenant, id),
		FOREIGN KEY(tenant, from_name) REFERENCES accounts(tenant, name),
		FOREIGN KEY(tenant, to_name) REFERENCES accounts(tenant, name),
		FOREIGN KEY(tenant, reversal_of) REFERENCES transfers(tenant, id)
	)`,
	`CREATE TABLE IF NOT EXISTS holds (
		tenant TEXT NOT NULL,
		id TEXT NOT NULL,
		account TEXT NOT NULL,
		amount INTEGER NOT NULL CHECK(amount BETWEEN 1 AND 1000000000),
		state TEXT NOT NULL CHECK(state IN ('active','captured','released')),
		PRIMARY KEY(tenant, id),
		FOREIGN KEY(tenant, account) REFERENCES accounts(tenant, name)
	)`,
	`CREATE TABLE IF NOT EXISTS tenant_sequences (
		tenant TEXT PRIMARY KEY,
		last_seq INTEGER NOT NULL CHECK(last_seq > 0)
	)`,
	`CREATE TABLE IF NOT EXISTS entries (
		tenant TEXT NOT NULL,
		seq INTEGER NOT NULL CHECK(seq > 0),
		account TEXT NOT NULL,
		kind TEXT NOT NULL CHECK(kind IN ('opening','transfer','hold','capture','release','reversal')),
		balance_delta INTEGER NOT NULL,
		reserved_delta INTEGER NOT NULL,
		operation_id TEXT NOT NULL,
		legacy_id INTEGER,
		PRIMARY KEY(tenant, seq),
		FOREIGN KEY(tenant, account) REFERENCES accounts(tenant, name),
		FOREIGN KEY(tenant, operation_id) REFERENCES object_ids(tenant, id)
	)`,
	`CREATE TABLE IF NOT EXISTS idempotency (
		tenant TEXT NOT NULL,
		key TEXT NOT NULL,
		request_path TEXT NOT NULL,
		request_body TEXT NOT NULL,
		status INTEGER NOT NULL,
		response_json BLOB NOT NULL,
		PRIMARY KEY(tenant, key)
	)`,
}

func migrate(db *sql.DB) error {
	tx, err := db.BeginTx(context.Background(), nil)
	if err != nil {
		return fmt.Errorf("begin migration: %w", err)
	}
	defer tx.Rollback()
	var version int
	if err := tx.QueryRow("PRAGMA user_version").Scan(&version); err != nil {
		return fmt.Errorf("read user_version: %w", err)
	}
	switch version {
	case 0:
		if err := createSchema(tx); err != nil {
			return err
		}
		if _, err := tx.Exec("PRAGMA user_version = 2"); err != nil {
			return fmt.Errorf("set user_version: %w", err)
		}
	case 1:
		if err := createSchema(tx); err != nil {
			return err
		}
		if err := importLegacy(tx); err != nil {
			return fmt.Errorf("import v1 database: %w", err)
		}
		if _, err := tx.Exec("PRAGMA user_version = 2"); err != nil {
			return fmt.Errorf("set user_version: %w", err)
		}
	case 2:
		var count int
		if err := tx.QueryRow(`SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN ('accounts','entries','transfers','holds','idempotency','object_ids','tenant_sequences')`).Scan(&count); err != nil || count != 7 {
			return fmt.Errorf("version 2 schema is incomplete: %v", err)
		}
	default:
		return fmt.Errorf("unsupported database user_version %d", version)
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("commit migration: %w", err)
	}
	return nil
}

func createSchema(tx *sql.Tx) error {
	for _, stmt := range schemaStatements {
		if _, err := tx.Exec(stmt); err != nil {
			return fmt.Errorf("create schema: %w", err)
		}
	}
	return nil
}

type legacyAccount struct {
	tenant  string
	name    string
	final   int64
	open    int64
	touch   int64
	current int64
}

type legacyMovement struct {
	id     int64
	tenant string
	source string
	target string
	units  int64
}

func importLegacy(tx *sql.Tx) error {
	accounts := make(map[string]*legacyAccount)
	ordered := make([]*legacyAccount, 0)
	rows, err := tx.Query(`SELECT tenant, name, balance FROM legacy_accounts ORDER BY tenant, name`)
	if err != nil {
		return fmt.Errorf("read legacy accounts: %w", err)
	}
	for rows.Next() {
		a := new(legacyAccount)
		if err := rows.Scan(&a.tenant, &a.name, &a.final); err != nil {
			rows.Close()
			return fmt.Errorf("scan legacy account: %w", err)
		}
		if !validName(a.tenant) || !validName(a.name) || a.final < 0 || a.final > maxBalance {
			rows.Close()
			return fmt.Errorf("legacy account has invalid tenant, name, or balance")
		}
		key := a.tenant + "\x00" + a.name
		if _, exists := accounts[key]; exists {
			rows.Close()
			return fmt.Errorf("duplicate legacy account")
		}
		accounts[key] = a
		ordered = append(ordered, a)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return fmt.Errorf("read legacy accounts: %w", err)
	}
	if err := rows.Close(); err != nil {
		return err
	}

	movements := make([]legacyMovement, 0)
	rows, err = tx.Query(`SELECT id, tenant, source, target, units FROM legacy_movements ORDER BY id`)
	if err != nil {
		return fmt.Errorf("read legacy movements: %w", err)
	}
	for rows.Next() {
		var m legacyMovement
		if err := rows.Scan(&m.id, &m.tenant, &m.source, &m.target, &m.units); err != nil {
			rows.Close()
			return fmt.Errorf("scan legacy movement: %w", err)
		}
		if m.id <= 0 || !validName(m.tenant) || !validName(m.source) || !validName(m.target) || m.source == m.target || m.units < 1 || m.units > 1_000_000_000 {
			rows.Close()
			return fmt.Errorf("legacy movement has invalid identity or amount")
		}
		movements = append(movements, m)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return fmt.Errorf("read legacy movements: %w", err)
	}
	if err := rows.Close(); err != nil {
		return err
	}

	for _, m := range movements {
		source := accounts[m.tenant+"\x00"+m.source]
		target := accounts[m.tenant+"\x00"+m.target]
		if source == nil || target == nil {
			return fmt.Errorf("legacy movement references a missing account")
		}
		// The FINAL values are retained separately below; these accumulators are
		// temporary outbound/inbound totals encoded through signed intermediates.
		if source.open > math.MaxInt64-m.units || target.open < math.MinInt64+m.units {
			return fmt.Errorf("legacy movement totals overflow")
		}
		source.open += m.units
		target.open -= m.units
		source.touch++
		target.touch++
	}
	for _, a := range ordered {
		// open currently stores outgoing minus incoming. Recovering it this way
		// avoids changing or replaying the final legacy balance itself.
		opening, ok := checkedAdd(a.final, a.open)
		if !ok || opening < 0 || opening > maxBalance {
			return fmt.Errorf("legacy account implies an out-of-range opening balance")
		}
		a.open = opening
		a.current = opening
		version := a.touch + 1
		if version <= 0 {
			return errors.New("legacy account version overflow")
		}
		if _, err := tx.Exec(`INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,?)`, a.tenant, a.name, a.final, version); err != nil {
			return fmt.Errorf("import account %s/%s: %w", a.tenant, a.name, err)
		}
	}
	for _, a := range ordered {
		id, err := insertObjectID(tx, a.tenant)
		if err != nil {
			return err
		}
		if err := addEntry(tx, a.tenant, a.name, "opening", a.open, 0, id, nil); err != nil {
			return fmt.Errorf("import opening entry: %w", err)
		}
	}
	for _, m := range movements {
		source := accounts[m.tenant+"\x00"+m.source]
		target := accounts[m.tenant+"\x00"+m.target]
		if source.current < m.units || target.current > maxBalance-m.units {
			return fmt.Errorf("legacy movement cannot be replayed within balance limits")
		}
		source.current -= m.units
		target.current += m.units
		id, err := insertObjectID(tx, m.tenant)
		if err != nil {
			return err
		}
		if _, err := tx.Exec(`INSERT INTO transfers(tenant,id,from_name,to_name,amount,reversed,legacy_id) VALUES(?,?,?,?,?,0,?)`, m.tenant, id, m.source, m.target, m.units, m.id); err != nil {
			return fmt.Errorf("import transfer %d: %w", m.id, err)
		}
		if err := addEntry(tx, m.tenant, m.source, "transfer", -m.units, 0, id, &m.id); err != nil {
			return fmt.Errorf("import source entry %d: %w", m.id, err)
		}
		if err := addEntry(tx, m.tenant, m.target, "transfer", m.units, 0, id, &m.id); err != nil {
			return fmt.Errorf("import target entry %d: %w", m.id, err)
		}
	}
	for _, a := range ordered {
		if a.current != a.final {
			return fmt.Errorf("legacy movement replay does not reach final balance for %s/%s", a.tenant, a.name)
		}
	}
	return nil
}

func checkedAdd(a, b int64) (int64, bool) {
	if (b > 0 && a > math.MaxInt64-b) || (b < 0 && a < math.MinInt64-b) {
		return 0, false
	}
	return a + b, true
}
