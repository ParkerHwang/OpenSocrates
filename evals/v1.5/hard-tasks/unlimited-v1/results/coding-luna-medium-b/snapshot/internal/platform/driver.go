package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
)

// Open configures ordinary SQLite locking for independent server processes.
func Open(path string) (*sql.DB, error) {
	db, e := sql.Open("sqlite", path+"?_pragma=busy_timeout(15000)&_pragma=journal_mode(WAL)&_pragma=foreign_keys(1)")
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(8)
	return db, nil
}
