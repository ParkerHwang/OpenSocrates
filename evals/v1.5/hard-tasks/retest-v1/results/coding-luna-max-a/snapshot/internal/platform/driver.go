package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
	"strings"
)

// Open only selects the pinned driver. Schema, locking and transactions belong
// to the implementation. Every connection needs its own SQLite pragmas.
func Open(path string) (*sql.DB, error) {
	// The driver applies these pragmas to every connection it opens. WAL lets
	// readers continue during a write, and busy_timeout coordinates independent
	// server processes using the same local database.
	sep := "?"
	if strings.Contains(path, "?") {
		sep = "&"
	}
	dsn := path + sep + "_busy_timeout=15000&_journal_mode=WAL&_synchronous=FULL&_foreign_keys=on"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(16)
	db.SetMaxIdleConns(16)
	return db, nil
}
