package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"queueforge/internal/queue"
	"syscall"
	"time"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:0", "listen address")
	dbfile := flag.String("db", "", "SQLite database file")
	clock := flag.String("clock-file", "", "optional clock file")
	maxPending := flag.Int("max-pending", 100000, "tenant ready and leased limit")
	maxInflight := flag.Int("max-inflight", 100000, "tenant queue current lease limit")
	flag.Parse()
	if *dbfile == "" {
		log.Fatal("--db is required")
	}
	if *maxPending <= 0 || *maxInflight <= 0 {
		log.Fatal("capacity flags must be positive")
	}
	var c queue.Clock = queue.RealClock{}
	if *clock != "" {
		c = queue.FileClock{Path: *clock}
	}
	s, e := queue.Open(*dbfile, c)
	if e != nil {
		log.Fatal(e)
	}
	s.SetLimits(*maxPending, *maxInflight)
	defer s.Close()
	ln, e := net.Listen("tcp", *addr)
	if e != nil {
		log.Fatal(e)
	}
	defer ln.Close()
	srv := &http.Server{Handler: queue.API{S: s}, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if e := srv.Serve(ln); e != nil && e != http.ErrServerClosed {
			log.Printf("server: %v", e)
		}
	}()
	port := ln.Addr().(*net.TCPAddr).Port
	if e = json.NewEncoder(os.Stdout).Encode(map[string]int{"port": port}); e != nil {
		log.Fatal(e)
	}
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, os.Interrupt)
	<-sig
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if e = srv.Shutdown(ctx); e != nil {
		fmt.Fprintln(os.Stderr, e)
	}
}
