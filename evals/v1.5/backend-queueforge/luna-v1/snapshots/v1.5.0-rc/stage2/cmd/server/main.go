package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	_ "queueforge/internal/platform"
	"queueforge/internal/queue"
	"syscall"
	"time"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:0", "loopback listen address")
	dbpath := flag.String("db", "", "SQLite database path")
	clock := flag.String("clock-file", "", "optional test clock file")
	maxPending := flag.Int("max-pending", 100000, "tenant ready and leased capacity")
	maxInflight := flag.Int("max-inflight", 100000, "tenant queue live lease capacity")
	flag.Parse()
	if *maxPending < 1 || *maxInflight < 1 {
		log.Fatal("capacity limits must be positive")
	}
	if *dbpath == "" || !filepath.IsAbs(*dbpath) {
		log.Fatal("--db must be an absolute path")
	}
	host, _, e := net.SplitHostPort(*addr)
	if e != nil || host != "127.0.0.1" {
		log.Fatal("--addr must bind 127.0.0.1")
	}
	db, e := sql.Open("sqlite", *dbpath+"?_busy_timeout=5000&_txlock=immediate")
	if e != nil {
		log.Fatal(e)
	}
	db.SetMaxOpenConns(1)
	ctx := context.Background()
	svc := &queue.Service{DB: db, MaxPending: *maxPending, MaxInflight: *maxInflight}
	if *clock != "" {
		svc.Clock = queue.FileClock(*clock)
	}
	if e = svc.Init(ctx); e != nil {
		log.Fatal(e)
	}
	ln, e := net.Listen("tcp", *addr)
	if e != nil {
		log.Fatal(e)
	}
	srv := &http.Server{Handler: &queue.API{S: svc}, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if e := srv.Serve(ln); e != nil && e != http.ErrServerClosed {
			log.Printf("server: %v", e)
		}
	}()
	_, port, _ := net.SplitHostPort(ln.Addr().String())
	var p int
	fmt.Sscan(port, &p)
	_ = json.NewEncoder(os.Stdout).Encode(map[string]int{"port": p})
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, os.Interrupt)
	<-sig
	ctx2, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx2)
	_ = db.Close()
}
