package main

import (
	"auditledger/internal/platform"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
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
	s, err := platform.New(db)
	if err != nil {
		log.Fatal(err)
	}
	h := &http.Server{Addr: *listen, Handler: s}
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	go func() { <-stop; _ = h.Close() }()
	if err = h.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
