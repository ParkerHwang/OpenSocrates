package platform

import (
	"context"
	"database/sql"
	"fmt"
	_ "modernc.org/sqlite"
	"net/url"
	"sort"
	"strings"
	"time"
)

func Open(path string) (*sql.DB, error) {
	dsn := "file:" + url.PathEscape(path) + "?_pragma=busy_timeout(10000)&_pragma=foreign_keys(ON)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(8)
	deadline := time.Now().Add(12 * time.Second)
	for {
		err = initDB(db)
		if err == nil {
			return db, nil
		}
		if time.Now().After(deadline) || !(strings.Contains(err.Error(), "SQLITE_BUSY") || strings.Contains(err.Error(), "database is locked")) {
			db.Close()
			return nil, err
		}
		time.Sleep(50 * time.Millisecond)
	}
}
func initDB(db *sql.DB) error {
	ctx := context.Background()
	c, err := db.Conn(ctx)
	if err != nil {
		return err
	}
	defer c.Close()
	if _, err = c.ExecContext(ctx, "PRAGMA journal_mode=WAL"); err != nil {
		return err
	}
	if _, err = c.ExecContext(ctx, "BEGIN IMMEDIATE"); err != nil {
		return err
	}
	ok := false
	defer func() {
		if !ok {
			c.ExecContext(ctx, "ROLLBACK")
		}
	}()
	var ver int
	if err = c.QueryRowContext(ctx, "PRAGMA user_version").Scan(&ver); err != nil {
		return err
	}
	if ver != 0 && ver != 1 && ver != 2 {
		return fmt.Errorf("unsupported database version %d", ver)
	}
	ddl := []string{
		`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name))`,
		`CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL DEFAULT 0,kind TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id))`,
		`CREATE TABLE IF NOT EXISTS entries(tenant TEXT NOT NULL,seq INTEGER NOT NULL,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,seq))`,
		`CREATE TABLE IF NOT EXISTS seqs(tenant TEXT PRIMARY KEY,last_seq INTEGER NOT NULL)`,
		`CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body TEXT NOT NULL,status INTEGER NOT NULL,result BLOB NOT NULL,PRIMARY KEY(tenant,key))`,
		`CREATE INDEX IF NOT EXISTS entries_account ON entries(tenant,account,seq)`,
	}
	for _, s := range ddl {
		if _, err = c.ExecContext(ctx, s); err != nil {
			return err
		}
	}
	if ver == 1 {
		type a struct {
			tenant, name     string
			balance, opening int64
		}
		as := []a{}
		rows, e := c.QueryContext(ctx, `SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name`)
		if e != nil {
			return e
		}
		for rows.Next() {
			var x a
			if e = rows.Scan(&x.tenant, &x.name, &x.balance); e != nil {
				rows.Close()
				return e
			}
			x.opening = x.balance
			as = append(as, x)
		}
		e = rows.Err()
		rows.Close()
		if e != nil {
			return e
		}
		type m struct {
			id, units              int64
			tenant, source, target string
		}
		ms := []m{}
		rows, e = c.QueryContext(ctx, `SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id`)
		if e != nil {
			return e
		}
		for rows.Next() {
			var x m
			if e = rows.Scan(&x.id, &x.tenant, &x.source, &x.target, &x.units); e != nil {
				rows.Close()
				return e
			}
			ms = append(ms, x)
		}
		e = rows.Err()
		rows.Close()
		if e != nil {
			return e
		}
		ix := map[string]int{}
		for i, x := range as {
			ix[x.tenant+"\x00"+x.name] = i
		}
		for _, x := range ms {
			from, ok1 := ix[x.tenant+"\x00"+x.source]
			to, ok2 := ix[x.tenant+"\x00"+x.target]
			if !ok1 || !ok2 {
				return fmt.Errorf("orphan legacy movement %d", x.id)
			}
			as[from].opening += x.units
			as[to].opening -= x.units
		}
		sort.Slice(as, func(i, j int) bool {
			if as[i].tenant == as[j].tenant {
				return as[i].name < as[j].name
			}
			return as[i].tenant < as[j].tenant
		})
		for _, x := range as {
			if x.opening < 0 || x.opening > 1000000000 {
				return fmt.Errorf("invalid inferred opening for %s", x.name)
			}
			if _, e = c.ExecContext(ctx, `INSERT INTO accounts VALUES(?,?,?,0,1)`, x.tenant, x.name, x.opening); e != nil {
				return e
			}
			if e = AddEntry(c, x.tenant, x.name, "opening", x.opening, 0, "legacy-opening-"+x.name, nil); e != nil {
				return e
			}
		}
		for _, x := range ms {
			id := fmt.Sprintf("legacy-%d", x.id)
			if _, e = c.ExecContext(ctx, `INSERT INTO transfers VALUES(?,?,?,?,?,0,'ordinary',?)`, x.tenant, id, x.source, x.target, x.units, x.id); e != nil {
				return e
			}
			if _, e = c.ExecContext(ctx, `UPDATE accounts SET balance=balance-?,version=version+1 WHERE tenant=? AND name=?`, x.units, x.tenant, x.source); e != nil {
				return e
			}
			if _, e = c.ExecContext(ctx, `UPDATE accounts SET balance=balance+?,version=version+1 WHERE tenant=? AND name=?`, x.units, x.tenant, x.target); e != nil {
				return e
			}
			if e = AddEntry(c, x.tenant, x.source, "transfer", -x.units, 0, id, &x.id); e != nil {
				return e
			}
			if e = AddEntry(c, x.tenant, x.target, "transfer", x.units, 0, id, &x.id); e != nil {
				return e
			}
		}
		for _, x := range as {
			var b int64
			if e = c.QueryRowContext(ctx, `SELECT balance FROM accounts WHERE tenant=? AND name=?`, x.tenant, x.name).Scan(&b); e != nil {
				return e
			}
			if b != x.balance {
				return fmt.Errorf("migration balance mismatch")
			}
		}
	}
	if ver != 2 {
		if _, err = c.ExecContext(ctx, "PRAGMA user_version=2"); err != nil {
			return err
		}
	}
	if _, err = c.ExecContext(ctx, "COMMIT"); err != nil {
		return err
	}
	ok = true
	return nil
}
func AddEntry(c *sql.Conn, tenant, account, kind string, bd, rd int64, id string, legacy *int64) error {
	ctx := context.Background()
	_, err := c.ExecContext(ctx, `INSERT INTO seqs(tenant,last_seq) VALUES(?,1) ON CONFLICT(tenant) DO UPDATE SET last_seq=last_seq+1`, tenant)
	if err != nil {
		return err
	}
	var seq int64
	if err = c.QueryRowContext(ctx, `SELECT last_seq FROM seqs WHERE tenant=?`, tenant).Scan(&seq); err != nil {
		return err
	}
	_, err = c.ExecContext(ctx, `INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)`, tenant, seq, account, kind, bd, rd, id, legacy)
	return err
}
