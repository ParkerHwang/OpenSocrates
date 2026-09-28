package main

import (
	"auditledger/internal/platform"
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
	a := flag.String("listen", "127.0.0.1:8080", "listen address")
	flag.Parse()
	db, e := platform.Open(*p)
	if e != nil {
		log.Fatal(e)
	}
	defer db.Close()
	h, e := platform.New(db)
	if e != nil {
		log.Fatal(e)
	}
	s := &http.Server{Addr: *a, Handler: h, ReadHeaderTimeout: 5 * time.Second}
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	go func() { <-c; _ = s.Close() }()
	if e = s.ListenAndServe(); e != nil && e != http.ErrServerClosed {
		log.Fatal(e)
	}
}
