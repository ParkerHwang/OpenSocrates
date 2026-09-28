package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
	"net/url"
	"path/filepath"
	"strings"
)

// Open only selects the pinned driver. Schema, locking and transactions belong
// to the implementation. Every connection needs its own SQLite pragmas.
func Open(path string) (*sql.DB, error) {
	var dsn string
	if path == ":memory:" {
		dsn = "file:auditledger-memory?mode=memory&cache=shared"
	} else if strings.HasPrefix(path, "file:") {
		dsn = path
	} else {
		abs, err := filepath.Abs(path)
		if err != nil {
			return nil, err
		}
		dsn = (&url.URL{Scheme: "file", Path: abs}).String()
	}

	u, err := url.Parse(dsn)
	if err != nil {
		return nil, err
	}
	q := u.Query()
	q.Set("_busy_timeout", "10000")
	q.Set("_journal_mode", "WAL")
	q.Set("_foreign_keys", "on")
	q.Set("_txlock", "immediate")
	q.Set("_synchronous", "NORMAL")
	u.RawQuery = q.Encode()
	db, err := sql.Open("sqlite", u.String())
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(16)
	db.SetMaxIdleConns(16)
	return db, nil
}
