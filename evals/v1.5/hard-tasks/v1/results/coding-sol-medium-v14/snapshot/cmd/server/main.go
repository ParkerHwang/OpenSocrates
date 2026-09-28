package main

import (
	"auditledger/internal/ledger"
	"auditledger/internal/platform"
	"context"
	"errors"
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
	app := &ledger.Ledger{DB: db}
	if err = app.Init(context.Background()); err != nil {
		log.Fatal(err)
	}
	srv := &http.Server{Addr: *listen, Handler: app}
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	go func() { <-sig; ledger.ShutdownGracefully(srv) }()
	if err = srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}
