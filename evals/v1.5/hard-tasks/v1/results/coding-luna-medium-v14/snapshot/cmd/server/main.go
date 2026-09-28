package main

import (
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
	p := flag.String("db", "ledger.db", "SQLite database path")
	a := flag.String("listen", "127.0.0.1:8080", "HTTP listen address")
	flag.Parse()
	db, e := platform.Open(*p)
	if e != nil {
		log.Fatal(e)
	}
	defer db.Close()
	if e = platform.Migrate(db); e != nil {
		log.Fatal(e)
	}
	s := &http.Server{Addr: *a, Handler: platform.Handler(db), ReadHeaderTimeout: 5 * time.Second}
	go func() {
		c := make(chan os.Signal, 1)
		signal.Notify(c, os.Interrupt, syscall.SIGTERM)
		<-c
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if e := s.Shutdown(ctx); e != nil {
			_ = s.Close()
		}
	}()
	if e = s.ListenAndServe(); e != nil && e != http.ErrServerClosed {
		log.Fatal(e)
	}
}
