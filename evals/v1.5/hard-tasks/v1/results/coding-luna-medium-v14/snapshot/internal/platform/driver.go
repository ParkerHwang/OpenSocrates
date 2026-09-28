package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
	"strings"
)

// Open only selects the pinned driver. Schema, locking and transactions belong
// to the implementation. Every connection needs its own SQLite pragmas.
func Open(path string) (*sql.DB, error) {
	sep := "?"
	if strings.Contains(path, "?") {
		sep = "&"
	}
	db, e := sql.Open("sqlite", path+sep+"_txlock=immediate&_busy_timeout=10000")
	if e == nil {
		db.SetMaxOpenConns(1)
	}
	return db, e
}
