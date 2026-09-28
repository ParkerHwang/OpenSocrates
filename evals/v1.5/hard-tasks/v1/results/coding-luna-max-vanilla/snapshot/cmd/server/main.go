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
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := ledger.Migrate(ctx, db); err != nil {
		log.Fatalf("database migration: %v", err)
	}
	server := &http.Server{
		Addr:              *listen,
		Handler:           ledger.NewHandler(db),
		ReadHeaderTimeout: 5 * time.Second,
	}
	serverErr := make(chan error, 1)
	go func() {
		log.Printf("AuditLedger listening on %s", *listen)
		serverErr <- server.ListenAndServe()
	}()
	select {
	case err := <-serverErr:
		if err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP server: %v", err)
		}
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("graceful shutdown: %v", err)
			_ = server.Close()
		}
		if err := <-serverErr; err != nil && err != http.ErrServerClosed {
			log.Printf("HTTP server: %v", err)
		}
	}
}
