package ledger

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"math"
	"regexp"
	"sort"
	"strings"
)

const maxAccountValue int64 = 9_000_000_000_000_000

var identifierPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)

const schema = `
CREATE TABLE IF NOT EXISTS accounts (
  tenant TEXT NOT NULL,
  name TEXT NOT NULL,
  balance INTEGER NOT NULL CHECK(balance >= 0 AND balance <= 9000000000000000),
  reserved INTEGER NOT NULL CHECK(reserved >= 0 AND reserved <= balance),
  version INTEGER NOT NULL CHECK(version >= 1),
  PRIMARY KEY(tenant, name)
);
CREATE TABLE IF NOT EXISTS transfers (
  tenant TEXT NOT NULL,
  id TEXT NOT NULL,
  from_account TEXT NOT NULL,
  to_account TEXT NOT NULL,
  amount INTEGER NOT NULL CHECK(amount > 0 AND amount <= 1000000000),
  reversed INTEGER NOT NULL DEFAULT 0 CHECK(reversed IN (0,1)),
  reversal_of TEXT,
  kind TEXT NOT NULL CHECK(kind IN ('transfer','capture','reversal')),
  legacy_id INTEGER,
  PRIMARY KEY(tenant, id),
  UNIQUE(tenant, reversal_of)
);
CREATE TABLE IF NOT EXISTS holds (
  tenant TEXT NOT NULL,
  id TEXT NOT NULL,
  account TEXT NOT NULL,
  amount INTEGER NOT NULL CHECK(amount > 0 AND amount <= 1000000000),
  state TEXT NOT NULL CHECK(state IN ('active','captured','released')),
  PRIMARY KEY(tenant, id)
);
CREATE TABLE IF NOT EXISTS tenant_sequences (
  tenant TEXT PRIMARY KEY,
  seq INTEGER NOT NULL CHECK(seq >= 0)
);
CREATE TABLE IF NOT EXISTS entries (
  tenant TEXT NOT NULL,
  seq INTEGER NOT NULL CHECK(seq > 0),
  account TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('opening','transfer','hold','capture','release','reversal')),
  balance_delta INTEGER NOT NULL,
  reserved_delta INTEGER NOT NULL,
  operation_id TEXT NOT NULL,
  legacy_id INTEGER,
  PRIMARY KEY(tenant, seq)
);
CREATE INDEX IF NOT EXISTS entries_snapshot_idx ON entries(tenant, seq);
CREATE TABLE IF NOT EXISTS idempotency (
  tenant TEXT NOT NULL,
  key TEXT NOT NULL,
  path TEXT NOT NULL,
  body_hash TEXT NOT NULL,
  status INTEGER NOT NULL,
  result_json BLOB NOT NULL,
  PRIMARY KEY(tenant, key)
);
`

type legacyAccount struct {
	tenant   string
	name     string
	final    int64
	outgoing int64
	incoming int64
	touches  int64
}

type legacyMovement struct {
	id     int64
	tenant string
	source string
	target string
	units  int64
}

type accountKey struct{ tenant, name string }

// Migrate serializes schema installation and v1 import in one immediate write
// transaction. The legacy tables are read only and remain intact.
func Migrate(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, &sql.TxOptions{Isolation: sql.LevelSerializable})
	if err != nil {
		return err
	}
	defer tx.Rollback()

	var version int
	if err := tx.QueryRowContext(ctx, `PRAGMA user_version`).Scan(&version); err != nil {
		return err
	}
	if version > 2 {
		return fmt.Errorf("database version %d is newer than supported version 2", version)
	}
	if version == 2 {
		return tx.Commit()
	}
	if err := execSchema(ctx, tx); err != nil {
		return err
	}
	if version == 1 {
		if err := importV1(ctx, tx); err != nil {
			return err
		}
	}
	if _, err := tx.ExecContext(ctx, `PRAGMA user_version = 2`); err != nil {
		return err
	}
	return tx.Commit()
}

func execSchema(ctx context.Context, tx *sql.Tx) error {
	for _, statement := range strings.Split(schema, ";") {
		statement = strings.TrimSpace(statement)
		if statement == "" {
			continue
		}
		if _, err := tx.ExecContext(ctx, statement); err != nil {
			return err
		}
	}
	return nil
}

func importV1(ctx context.Context, tx *sql.Tx) error {
	accounts := map[accountKey]*legacyAccount{}
	rows, err := tx.QueryContext(ctx, `SELECT tenant, name, balance FROM legacy_accounts ORDER BY tenant, name`)
	if err != nil {
		return fmt.Errorf("read legacy accounts: %w", err)
	}
	for rows.Next() {
		var a legacyAccount
		if err := rows.Scan(&a.tenant, &a.name, &a.final); err != nil {
			rows.Close()
			return err
		}
		if !identifierPattern.MatchString(a.tenant) || !identifierPattern.MatchString(a.name) || a.final < 0 || a.final > maxAccountValue {
			rows.Close()
			return errors.New("invalid legacy account row")
		}
		key := accountKey{a.tenant, a.name}
		accounts[key] = &a
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	rows.Close()

	movements := make([]legacyMovement, 0)
	rows, err = tx.QueryContext(ctx, `SELECT id, tenant, source, target, units FROM legacy_movements ORDER BY id`)
	if err != nil {
		return fmt.Errorf("read legacy movements: %w", err)
	}
	for rows.Next() {
		var m legacyMovement
		if err := rows.Scan(&m.id, &m.tenant, &m.source, &m.target, &m.units); err != nil {
			rows.Close()
			return err
		}
		if !identifierPattern.MatchString(m.tenant) || !identifierPattern.MatchString(m.source) || !identifierPattern.MatchString(m.target) || m.source == m.target || m.units < 1 || m.units > 1_000_000_000 {
			rows.Close()
			return errors.New("invalid legacy movement row")
		}
		source := accounts[accountKey{m.tenant, m.source}]
		target := accounts[accountKey{m.tenant, m.target}]
		if source == nil || target == nil {
			rows.Close()
			return errors.New("legacy movement references missing account")
		}
		var ok bool
		if source.outgoing, ok = checkedAdd(source.outgoing, m.units); !ok {
			rows.Close()
			return errors.New("legacy movement overflow")
		}
		if target.incoming, ok = checkedAdd(target.incoming, m.units); !ok {
			rows.Close()
			return errors.New("legacy movement overflow")
		}
		source.touches++
		target.touches++
		movements = append(movements, m)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	rows.Close()

	keys := make([]accountKey, 0, len(accounts))
	for key := range accounts {
		keys = append(keys, key)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].tenant != keys[j].tenant {
			return keys[i].tenant < keys[j].tenant
		}
		return keys[i].name < keys[j].name
	})
	writers := map[string]*entryWriter{}
	writerFor := func(tenant string) (*entryWriter, error) {
		if w := writers[tenant]; w != nil {
			return w, nil
		}
		w, err := newEntryWriter(ctx, tx, tenant)
		if err != nil {
			return nil, err
		}
		writers[tenant] = w
		return w, nil
	}

	for _, key := range keys {
		a := accounts[key]
		opening, ok := checkedAdd(a.final, a.outgoing)
		if !ok || a.incoming < 0 || opening < a.incoming {
			return errors.New("invalid legacy opening balance")
		}
		opening -= a.incoming
		if opening < 0 || opening > maxAccountValue || a.touches == math.MaxInt64 {
			return errors.New("invalid legacy opening balance")
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,0,?)`, a.tenant, a.name, a.final, 1+a.touches); err != nil {
			return err
		}
		w, err := writerFor(a.tenant)
		if err != nil {
			return err
		}
		if err := w.append(ctx, tx, a.name, "opening", opening, 0, newID(), nil); err != nil {
			return err
		}
	}

	for _, m := range movements {
		id := newID()
		if _, err := tx.ExecContext(ctx, `INSERT INTO transfers(tenant,id,from_account,to_account,amount,reversed,reversal_of,kind,legacy_id) VALUES(?,?,?,?,?,0,NULL,'transfer',?)`, m.tenant, id, m.source, m.target, m.units, m.id); err != nil {
			return err
		}
		w, err := writerFor(m.tenant)
		if err != nil {
			return err
		}
		legacyID := m.id
		if err := w.append(ctx, tx, m.source, "transfer", -m.units, 0, id, &legacyID); err != nil {
			return err
		}
		if err := w.append(ctx, tx, m.target, "transfer", m.units, 0, id, &legacyID); err != nil {
			return err
		}
	}
	for _, w := range writers {
		if err := w.flush(ctx, tx); err != nil {
			return err
		}
	}
	return nil
}

func checkedAdd(a, b int64) (int64, bool) {
	if b > 0 && a > math.MaxInt64-b {
		return 0, false
	}
	if b < 0 && a < math.MinInt64-b {
		return 0, false
	}
	return a + b, true
}
