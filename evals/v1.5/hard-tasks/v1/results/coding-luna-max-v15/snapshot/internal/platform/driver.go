package platform

import (
	"database/sql"
	"net/url"
	"path/filepath"
	"strings"

	_ "modernc.org/sqlite"
)

// OpenReader opens a read pool with deferred transactions, so historical
// snapshots do not reserve SQLite's single writer lock.
func OpenReader(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", dsn(path, false))
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(8)
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

// OpenWriter opens a pool whose transactions acquire the ordinary SQLite
// write reservation at BEGIN. The lock and busy timeout coordinate processes.
func OpenWriter(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", dsn(path, true))
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(8)
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, err
	}
	var mode string
	if err := db.QueryRow("PRAGMA journal_mode=WAL").Scan(&mode); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

func dsn(path string, immediate bool) string {
	var base string
	if path == ":memory:" || strings.HasPrefix(path, "file:") {
		base = path
	} else {
		abs, err := filepath.Abs(path)
		if err != nil {
			abs = path
		}
		base = (&url.URL{Scheme: "file", Path: filepath.ToSlash(abs)}).String()
	}
	separator := "?"
	if strings.Contains(base, "?") {
		separator = "&"
	}
	base += separator + "_busy_timeout=15000&_foreign_keys=1"
	if immediate {
		base += "&_txlock=immediate"
	}
	return base
}
