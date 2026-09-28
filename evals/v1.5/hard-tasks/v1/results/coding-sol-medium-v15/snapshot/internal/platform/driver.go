package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
	"net/url"
	"path/filepath"
	"time"
)

func Open(path string) (*sql.DB, error) {
	abs, err := filepath.Abs(path)
	if err != nil {
		return nil, err
	}
	u := url.URL{Scheme: "file", Path: abs}
	q := u.Query()
	q.Add("_pragma", "busy_timeout(15000)")
	q.Add("_pragma", "foreign_keys(1)")
	u.RawQuery = q.Encode()
	db, e := sql.Open("sqlite", u.String())
	if e != nil {
		return nil, e
	}
	db.SetMaxOpenConns(1)
	db.SetConnMaxLifetime(0)
	if e = db.Ping(); e != nil {
		db.Close()
		return nil, e
	}
	db.SetConnMaxIdleTime(5 * time.Minute)
	return db, nil
}
