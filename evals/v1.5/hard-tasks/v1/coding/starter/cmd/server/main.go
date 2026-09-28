package main

import (
	"auditledger/internal/platform"
	"flag"
	"log"
)

func main() {
	dbPath := flag.String("db", "ledger.db", "SQLite database path")
	listen := flag.String("listen", "127.0.0.1:8080", "HTTP listen address")
	flag.Parse()
	db, err := platform.Open(*dbPath)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	_ = listen
	log.Fatal("TODO: implement AuditLedger HTTP API and migration")
}
