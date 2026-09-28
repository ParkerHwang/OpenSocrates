package platform

import (
	"database/sql"
	_ "modernc.org/sqlite"
	"net/url"
)

func Open(path string) (*sql.DB, error) {
	dsn := "file:" + url.PathEscape(path) + "?_pragma=busy_timeout(10000)&_pragma=foreign_keys(ON)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(16)
	if err = db.Ping(); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}
