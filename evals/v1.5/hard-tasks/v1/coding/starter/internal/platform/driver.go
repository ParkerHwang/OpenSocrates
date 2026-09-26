package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
)

// Open only selects the pinned driver. Schema, locking and transactions belong
// to the implementation. Every connection needs its own SQLite pragmas.
func Open(path string) (*sql.DB, error) { return sql.Open("sqlite", path) }
