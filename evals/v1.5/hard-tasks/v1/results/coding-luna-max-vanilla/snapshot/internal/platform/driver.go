package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
	"net/url"
	"path/filepath"
)

// Open only selects the pinned driver. Schema, locking and transactions belong
// to the implementation. Every connection needs its own SQLite pragmas.
func Open(path string) (*sql.DB, error) {
	// Put connection-local settings in the DSN so every pooled connection has
	// the same lock wait and foreign-key behavior. Immediate write transactions
	// are opened explicitly by the ledger store.
	var dsn string
	if path == ":memory:" {
		dsn = "file::memory:?cache=shared"
	} else if len(path) >= 5 && path[:5] == "file:" {
		dsn = path
	} else {
		abs, err := filepath.Abs(path)
		if err != nil {
			return nil, err
		}
		dsn = (&url.URL{Scheme: "file", Path: abs}).String()
	}
	sep := "?"
	if len(dsn) > 0 && containsQuery(dsn) {
		sep = "&"
	}
	dsn += sep + "_busy_timeout=10000&_pragma=foreign_keys(1)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(16)
	db.SetMaxIdleConns(16)
	return db, nil
}

func containsQuery(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] == '?' {
			return true
		}
	}
	return false
}
