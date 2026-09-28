package main

import (
 "database/sql"
 "log"
 "net/http"
 "os"
 _ "github.com/mattn/go-sqlite3"
)

type Server struct { DB *sql.DB }

func main() {
	path := os.Getenv("INCIDENTOPS_DB")
	if path == "" { path = "incidentops.db" }
	addr := os.Getenv("INCIDENTOPS_ADDR")
	if addr == "" { addr = "127.0.0.1:8080" }
	db, err := sql.Open("sqlite3", path)
	if err != nil { log.Fatal(err) }
	defer db.Close()
	db.SetMaxOpenConns(1)
	for _, pragma := range []string{"PRAGMA journal_mode=WAL", "PRAGMA synchronous=NORMAL", "PRAGMA busy_timeout=5000"} {
		if _, err := db.Exec(pragma); err != nil { log.Fatal(err) }
	}
	if err := migrate(db); err != nil { log.Fatal(err) }
	log.Fatal(http.ListenAndServe(addr, (&Server{DB:db}).routes()))
}
