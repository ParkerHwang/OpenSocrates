package main

import (
	"auditledger/internal/ledger"
	"auditledger/internal/platform"
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
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
	api, err := ledger.New(db)
	if err != nil {
		log.Fatalf("initialize ledger: %v", err)
	}
	srv := &http.Server{
		Addr:              *listen,
		Handler:           api,
		ReadHeaderTimeout: 5 * time.Second,
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	errCh := make(chan error, 1)
	go func() { errCh <- srv.ListenAndServe() }()
	select {
	case err := <-errCh:
		if err != nil && err != http.ErrServerClosed {
			log.Fatalf("serve: %v", err)
		}
	case <-ctx.Done():
		shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := srv.Shutdown(shutdown); err != nil {
			log.Printf("graceful shutdown: %v", err)
			_ = srv.Close()
		}
		if err := <-errCh; err != nil && err != http.ErrServerClosed {
			log.Printf("serve: %v", err)
		}
	}
}
