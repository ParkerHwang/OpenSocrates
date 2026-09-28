package ledger

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"math"
	"sort"
	"strconv"

	"github.com/google/uuid"
)

const maxBalance int64 = 9_000_000_000_000_000

type Ledger struct{ db *sql.DB }

type Account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}

type SummaryAccount struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
}

type Transfer struct {
	ID         string `json:"id"`
	From       string `json:"from"`
	To         string `json:"to"`
	Amount     int64  `json:"amount"`
	Reversed   bool   `json:"reversed"`
	LegacyID   *int64 `json:"legacy_id,omitempty"`
	ReversalOf string `json:"-"`
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

type accountState struct {
	Name, Tenant      string
	Balance, Reserved int64
	Version           int64
}

type transferRow struct {
	Transfer
	Tenant string
}

type holdRow struct {
	Hold
	Tenant string
}

func New(db *sql.DB) (*Ledger, error) {
	l := &Ledger{db: db}
	if err := db.Ping(); err != nil {
		return nil, err
	}
	if err := l.migrate(context.Background()); err != nil {
		return nil, err
	}
	return l, nil
}

func (l *Ledger) migrate(ctx context.Context) error {
	conn, err := l.beginWrite(ctx)
	if err != nil {
		return err
	}
	defer conn.Close()
	committed := false
	defer func() {
		if !committed {
			_, _ = conn.ExecContext(context.Background(), "ROLLBACK")
		}
	}()
	var version int
	if err := conn.QueryRowContext(ctx, "PRAGMA user_version").Scan(&version); err != nil {
		return err
	}
	if version > 2 {
		return fmt.Errorf("database schema version %d is newer than supported", version)
	}
	if err := createSchema(ctx, conn); err != nil {
		return err
	}
	if version == 1 {
		if err := importLegacy(ctx, conn); err != nil {
			return err
		}
	}
	if _, err := conn.ExecContext(ctx, "PRAGMA user_version=2"); err != nil {
		return err
	}
	if _, err := conn.ExecContext(ctx, "COMMIT"); err != nil {
		return err
	}
	committed = true
	return nil
}

func createSchema(ctx context.Context, c *sql.Conn) error {
	statements := []string{
		`CREATE TABLE IF NOT EXISTS accounts (
		 tenant TEXT NOT NULL, name TEXT NOT NULL, balance INTEGER NOT NULL,
		 reserved INTEGER NOT NULL, version INTEGER NOT NULL,
		 PRIMARY KEY (tenant,name), CHECK(balance >= 0 AND balance <= 9000000000000000),
		 CHECK(reserved >= 0 AND reserved <= balance), CHECK(version >= 1)
		)`,
		`CREATE TABLE IF NOT EXISTS transfers (
		 tenant TEXT NOT NULL, id TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL,
		 amount INTEGER NOT NULL, reversed INTEGER NOT NULL DEFAULT 0,
		 reversal_of TEXT, legacy_id INTEGER,
		 PRIMARY KEY (tenant,id), CHECK(source <> target), CHECK(amount > 0),
		 CHECK(reversed IN (0,1))
		)`,
		`CREATE UNIQUE INDEX IF NOT EXISTS transfers_legacy_id ON transfers(tenant,legacy_id) WHERE legacy_id IS NOT NULL`,
		`CREATE TABLE IF NOT EXISTS holds (
		 tenant TEXT NOT NULL, id TEXT NOT NULL, account TEXT NOT NULL, amount INTEGER NOT NULL,
		 state TEXT NOT NULL, PRIMARY KEY (tenant,id), CHECK(amount > 0),
		 CHECK(state IN ('active','captured','released'))
		)`,
		`CREATE TABLE IF NOT EXISTS entries (
		 seq INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, account TEXT NOT NULL,
		 kind TEXT NOT NULL, balance_delta INTEGER NOT NULL, reserved_delta INTEGER NOT NULL,
		 operation_id TEXT NOT NULL, legacy_id INTEGER,
		 CHECK(kind IN ('opening','transfer','hold','capture','release','reversal'))
		)`,
		`CREATE INDEX IF NOT EXISTS entries_tenant_seq ON entries(tenant,seq)`,
		`CREATE INDEX IF NOT EXISTS entries_tenant_account_seq ON entries(tenant,account,seq)`,
		`CREATE TABLE IF NOT EXISTS idempotency (
		 tenant TEXT NOT NULL, key TEXT NOT NULL, path TEXT NOT NULL, body TEXT NOT NULL,
		 status INTEGER NOT NULL, result TEXT NOT NULL, PRIMARY KEY(tenant,key)
		)`,
	}
	for _, statement := range statements {
		if _, err := c.ExecContext(ctx, statement); err != nil {
			return err
		}
	}
	return nil
}

func (l *Ledger) beginWrite(ctx context.Context) (*sql.Conn, error) {
	conn, err := l.db.Conn(ctx)
	if err != nil {
		return nil, err
	}
	if _, err := conn.ExecContext(ctx, "BEGIN IMMEDIATE"); err != nil {
		_ = conn.Close()
		return nil, err
	}
	return conn, nil
}

type legacyAccount struct {
	tenant, name   string
	final, opening int64
	version        int64
}

type legacyMovement struct {
	id                     int64
	tenant, source, target string
	units                  int64
}

type legacyKey struct{ tenant, name string }

func importLegacy(ctx context.Context, c *sql.Conn) error {
	rows, err := c.QueryContext(ctx, "SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name")
	if err != nil {
		return fmt.Errorf("read legacy accounts: %w", err)
	}
	accounts := make(map[legacyKey]*legacyAccount)
	ordered := make([]*legacyAccount, 0)
	for rows.Next() {
		var a legacyAccount
		if err := rows.Scan(&a.tenant, &a.name, &a.final); err != nil {
			rows.Close()
			return err
		}
		a.opening, a.version = a.final, 1
		accounts[legacyKey{a.tenant, a.name}] = &a
		ordered = append(ordered, &a)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	rows.Close()
	rows, err = c.QueryContext(ctx, "SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id")
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
		source := accounts[legacyKey{m.tenant, m.source}]
		target := accounts[legacyKey{m.tenant, m.target}]
		if source == nil || target == nil || m.source == m.target || m.units <= 0 || m.units > 1_000_000_000 {
			rows.Close()
			return fmt.Errorf("invalid legacy movement %d", m.id)
		}
		if source.opening > math.MaxInt64-m.units || target.opening < math.MinInt64+m.units {
			rows.Close()
			return fmt.Errorf("legacy movement %d overflows inferred opening", m.id)
		}
		source.opening += m.units
		target.opening -= m.units
		source.version++
		target.version++
		movements = append(movements, m)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return err
	}
	rows.Close()
	for _, a := range ordered {
		if a.opening < 0 || a.opening > maxBalance || a.final < 0 || a.final > maxBalance {
			return fmt.Errorf("legacy account %s/%s has an invalid inferred balance", a.tenant, a.name)
		}
		if _, err := c.ExecContext(ctx, "INSERT INTO accounts(tenant,name,balance,reserved,version) VALUES(?,?,?,?,?)", a.tenant, a.name, a.final, 0, a.version); err != nil {
			return err
		}
		opID := "opening-" + uuid.NewString()
		if err := insertEntry(ctx, c, Entry{Account: a.name, Kind: "opening", BalanceDelta: a.opening, OperationID: opID}, a.tenant); err != nil {
			return err
		}
	}
	for _, m := range movements {
		id := "legacy-" + strconv.FormatInt(m.id, 10)
		if _, err := c.ExecContext(ctx, `INSERT INTO transfers(tenant,id,source,target,amount,reversed,legacy_id)
			VALUES(?,?,?,?,?,0,?)`, m.tenant, id, m.source, m.target, m.units, m.id); err != nil {
			return err
		}
		legacyID := m.id
		if err := insertEntry(ctx, c, Entry{Account: m.source, Kind: "transfer", BalanceDelta: -m.units, OperationID: id, LegacyID: &legacyID}, m.tenant); err != nil {
			return err
		}
		if err := insertEntry(ctx, c, Entry{Account: m.target, Kind: "transfer", BalanceDelta: m.units, OperationID: id, LegacyID: &legacyID}, m.tenant); err != nil {
			return err
		}
	}
	return nil
}

func insertEntry(ctx context.Context, c *sql.Conn, e Entry, tenant string) error {
	_, err := c.ExecContext(ctx, `INSERT INTO entries(tenant,account,kind,balance_delta,reserved_delta,operation_id,legacy_id)
		VALUES(?,?,?,?,?,?,?)`, tenant, e.Account, e.Kind, e.BalanceDelta, e.ReservedDelta, e.OperationID, nullableInt(e.LegacyID))
	return err
}

func nullableInt(n *int64) any {
	if n == nil {
		return nil
	}
	return *n
}

func currentAccount(ctx context.Context, c *sql.Conn, tenant, name string) (accountState, bool, error) {
	var a accountState
	a.Name, a.Tenant = name, tenant
	err := c.QueryRowContext(ctx, "SELECT balance,reserved,version FROM accounts WHERE tenant=? AND name=?", tenant, name).
		Scan(&a.Balance, &a.Reserved, &a.Version)
	if errors.Is(err, sql.ErrNoRows) {
		return accountState{}, false, nil
	}
	if err != nil {
		return accountState{}, false, err
	}
	return a, true, nil
}

func readAccount(ctx context.Context, q interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}, tenant, name string) (Account, bool, error) {
	var a Account
	a.Name = name
	err := q.QueryRowContext(ctx, "SELECT balance,reserved,version FROM accounts WHERE tenant=? AND name=?", tenant, name).
		Scan(&a.Balance, &a.Reserved, &a.Version)
	if errors.Is(err, sql.ErrNoRows) {
		return Account{}, false, nil
	}
	if err != nil {
		return Account{}, false, err
	}
	a.Available = a.Balance - a.Reserved
	return a, true, nil
}

func publicAccount(a accountState) Account {
	return Account{Name: a.Name, Balance: a.Balance, Reserved: a.Reserved, Available: a.Balance - a.Reserved, Version: a.Version}
}

func (a *accountState) advance() error {
	if a.Version == math.MaxInt64 {
		return fmt.Errorf("account version overflow")
	}
	a.Version++
	return nil
}

func saveAccount(ctx context.Context, c *sql.Conn, a accountState) error {
	_, err := c.ExecContext(ctx, "UPDATE accounts SET balance=?,reserved=?,version=? WHERE tenant=? AND name=?", a.Balance, a.Reserved, a.Version, a.Tenant, a.Name)
	return err
}

func (l *Ledger) maxSequence(ctx context.Context, tenant string) (int64, error) {
	var seq int64
	err := l.db.QueryRowContext(ctx, "SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?", tenant).Scan(&seq)
	return seq, err
}

func scanTransfer(ctx context.Context, c *sql.Conn, tenant, id string) (transferRow, bool, error) {
	var t transferRow
	var reversed int
	var legacy sql.NullInt64
	var reversalOf sql.NullString
	err := c.QueryRowContext(ctx, `SELECT id,source,target,amount,reversed,reversal_of,legacy_id
		FROM transfers WHERE tenant=? AND id=?`, tenant, id).Scan(&t.ID, &t.From, &t.To, &t.Amount, &reversed, &reversalOf, &legacy)
	if errors.Is(err, sql.ErrNoRows) {
		return transferRow{}, false, nil
	}
	if err != nil {
		return transferRow{}, false, err
	}
	t.Tenant, t.Reversed = tenant, reversed != 0
	if reversalOf.Valid {
		t.ReversalOf = reversalOf.String
	}
	if legacy.Valid {
		t.LegacyID = &legacy.Int64
	}
	return t, true, nil
}

func scanHold(ctx context.Context, c *sql.Conn, tenant, id string) (holdRow, bool, error) {
	var h holdRow
	err := c.QueryRowContext(ctx, `SELECT id,account,amount,state FROM holds WHERE tenant=? AND id=?`, tenant, id).
		Scan(&h.ID, &h.Account, &h.Amount, &h.State)
	if errors.Is(err, sql.ErrNoRows) {
		return holdRow{}, false, nil
	}
	if err != nil {
		return holdRow{}, false, err
	}
	h.Tenant = tenant
	return h, true, nil
}

func sortedAccounts(m map[string]accountState) []Account {
	names := make([]string, 0, len(m))
	for name := range m {
		names = append(names, name)
	}
	sort.Strings(names)
	out := make([]Account, 0, len(names))
	for _, name := range names {
		out = append(out, publicAccount(m[name]))
	}
	return out
}
