package platform

import (
	"database/sql"
	"fmt"
	"sort"
)

func Initialize(db *sql.DB) error {
	tx, e := db.Begin()
	if e != nil {
		return e
	}
	defer tx.Rollback()
	// A write lock serializes startup migration across processes.
	if _, e = tx.Exec(`CREATE TABLE IF NOT EXISTS migration_lock(id INTEGER PRIMARY KEY CHECK(id=1), n INTEGER NOT NULL); INSERT OR IGNORE INTO migration_lock VALUES(1,0); UPDATE migration_lock SET n=n WHERE id=1`); e != nil {
		return e
	}
	var v int
	if e = tx.QueryRow(`PRAGMA user_version`).Scan(&v); e != nil {
		return e
	}
	if v > 2 {
		return fmt.Errorf("unsupported database version %d", v)
	}
	if e = makeSchema(tx); e != nil {
		return e
	}
	if v == 1 {
		if e = migrate(tx); e != nil {
			return e
		}
	}
	if _, e = tx.Exec(`PRAGMA user_version=2`); e != nil {
		return e
	}
	return tx.Commit()
}
func makeSchema(tx *sql.Tx) error {
	_, e := tx.Exec(`CREATE TABLE IF NOT EXISTS accounts(tenant TEXT NOT NULL,name TEXT NOT NULL,balance INTEGER NOT NULL,reserved INTEGER NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(tenant,name));
 CREATE TABLE IF NOT EXISTS entries(seq INTEGER PRIMARY KEY AUTOINCREMENT,tenant TEXT NOT NULL,account TEXT NOT NULL,kind TEXT NOT NULL,balance_delta INTEGER NOT NULL,reserved_delta INTEGER NOT NULL,operation_id TEXT NOT NULL,legacy_id INTEGER);
 CREATE INDEX IF NOT EXISTS entries_tenant_seq ON entries(tenant,seq);
 CREATE TABLE IF NOT EXISTS transfers(tenant TEXT NOT NULL,id TEXT NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,amount INTEGER NOT NULL,reversed INTEGER NOT NULL,kind TEXT NOT NULL,legacy_id INTEGER,PRIMARY KEY(tenant,id));
 CREATE TABLE IF NOT EXISTS holds(tenant TEXT NOT NULL,id TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL,state TEXT NOT NULL,PRIMARY KEY(tenant,id));
 CREATE TABLE IF NOT EXISTS idempotency(tenant TEXT NOT NULL,key TEXT NOT NULL,path TEXT NOT NULL,body BLOB NOT NULL,result BLOB NOT NULL,status INTEGER NOT NULL,PRIMARY KEY(tenant,key));`)
	return e
}
func migrate(tx *sql.Tx) error {
	type acct struct {
		tenant, name string
		final        int64
	}
	rows, e := tx.Query(`SELECT tenant,name,balance FROM legacy_accounts ORDER BY tenant,name`)
	if e != nil {
		return e
	}
	accounts := []acct{}
	for rows.Next() {
		var a acct
		if e = rows.Scan(&a.tenant, &a.name, &a.final); e != nil {
			rows.Close()
			return e
		}
		accounts = append(accounts, a)
	}
	if e = rows.Err(); e != nil {
		rows.Close()
		return e
	}
	rows.Close()
	type mov struct {
		id                     int64
		tenant, source, target string
		units                  int64
	}
	mr, e := tx.Query(`SELECT id,tenant,source,target,units FROM legacy_movements ORDER BY id`)
	if e != nil {
		return e
	}
	moves := []mov{}
	for mr.Next() {
		var m mov
		if e = mr.Scan(&m.id, &m.tenant, &m.source, &m.target, &m.units); e != nil {
			mr.Close()
			return e
		}
		moves = append(moves, m)
	}
	if e = mr.Err(); e != nil {
		mr.Close()
		return e
	}
	mr.Close()
	openings := map[string]int64{}
	touches := map[string]int64{}
	key := func(t, n string) string { return t + "\x00" + n }
	for _, a := range accounts {
		openings[key(a.tenant, a.name)] = a.final
	}
	for _, m := range moves {
		sk, tk := key(m.tenant, m.source), key(m.tenant, m.target)
		if _, ok := openings[sk]; !ok {
			return fmt.Errorf("legacy source account missing")
		}
		if _, ok := openings[tk]; !ok {
			return fmt.Errorf("legacy target account missing")
		}
		openings[sk] += m.units
		openings[tk] -= m.units
		touches[sk]++
		touches[tk]++
	}
	// Legacy balances represent the final state. Reject impossible reconstruction.
	for _, a := range accounts {
		n := openings[key(a.tenant, a.name)]
		if n < 0 || n > maxUnits {
			return fmt.Errorf("invalid reconstructed opening")
		}
	}
	sort.Slice(accounts, func(i, j int) bool {
		if accounts[i].tenant == accounts[j].tenant {
			return accounts[i].name < accounts[j].name
		}
		return accounts[i].tenant < accounts[j].tenant
	})
	for _, a := range accounts {
		o := openings[key(a.tenant, a.name)]
		if _, e = tx.Exec(`INSERT INTO accounts VALUES(?,?,?,?,?)`, a.tenant, a.name, a.final, 0, 1+touches[key(a.tenant, a.name)]); e != nil {
			return e
		}
		op := id()
		if e = entry(tx, a.tenant, a.name, "opening", o, 0, op, nil); e != nil {
			return e
		}
	}
	for _, m := range moves {
		tid := fmt.Sprintf("legacy-%d", m.id)
		lid := m.id
		if _, e = tx.Exec(`INSERT INTO transfers VALUES(?,?,?,?,?,0,'transfer',?)`, m.tenant, tid, m.source, m.target, m.units, lid); e != nil {
			return e
		}
		if e = entry(tx, m.tenant, m.source, "transfer", -m.units, 0, tid, &lid); e != nil {
			return e
		}
		if e = entry(tx, m.tenant, m.target, "transfer", m.units, 0, tid, &lid); e != nil {
			return e
		}
	}
	return nil
}
