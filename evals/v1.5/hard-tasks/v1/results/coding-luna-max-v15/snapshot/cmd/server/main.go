package main

import (
	"context"
	"errors"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"auditledger/internal/ledger"
	"auditledger/internal/platform"
)

func main() {
	dbPath := flag.String("db", "ledger.db", "SQLite database path")
	listen := flag.String("listen", "127.0.0.1:8080", "HTTP listen address")
	flag.Parse()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := run(ctx, *dbPath, *listen); err != nil {
		log.Printf("server stopped: %v", err)
		os.Exit(1)
	}
}

func run(ctx context.Context, dbPath, listen string) error {
	writer, err := platform.OpenWriter(dbPath)
	if err != nil {
		return err
	}
	defer writer.Close()
	reader, err := platform.OpenReader(dbPath)
	if err != nil {
		return err
	}
	defer reader.Close()
	store := ledger.NewStore(reader, writer)
	if err := store.Migrate(ctx); err != nil {
		return err
	}

	server := &http.Server{
		Addr:              listen,
		Handler:           ledger.NewAPI(store),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	serveErr := make(chan error, 1)
	go func() { serveErr <- server.ListenAndServe() }()
	select {
	case err := <-serveErr:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			_ = server.Close()
			return err
		}
		err := <-serveErr
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}
