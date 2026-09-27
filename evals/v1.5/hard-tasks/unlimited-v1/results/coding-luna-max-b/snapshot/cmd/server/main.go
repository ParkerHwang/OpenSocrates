package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"auditledger/internal/platform"
)

func main() {
	if err := run(); err != nil {
		log.Printf("server: %v", err)
		os.Exit(1)
	}
}

func run() error {
	dbPath := flag.String("db", "ledger.db", "SQLite database path")
	listen := flag.String("listen", "127.0.0.1:8080", "HTTP listen address")
	flag.Parse()
	db, err := platform.Open(*dbPath)
	if err != nil {
		return err
	}
	defer db.Close()
	server := &http.Server{
		Addr:              *listen,
		Handler:           platform.NewService(db),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	serveErr := make(chan error, 1)
	go func() { serveErr <- server.ListenAndServe() }()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(stop)
	select {
	case err := <-serveErr:
		if err == http.ErrServerClosed {
			return nil
		}
		return err
	case <-stop:
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(ctx); err != nil {
			_ = server.Close()
			return err
		}
		if err := <-serveErr; err != nil && err != http.ErrServerClosed {
			return err
		}
		return nil
	}
}
