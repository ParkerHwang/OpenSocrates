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
	"syscall"
	"time"

	"queueforge/internal/queue"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:0", "loopback listen address")
	path := flag.String("db", "", "absolute SQLite file")
	clock := flag.String("clock-file", "", "test clock file")
	flag.Parse()
	if *path == "" || !isAbsolute(*path) {
		log.Fatal("--db must be an absolute path")
	}
	store, e := queue.Open(*path)
	if e != nil {
		log.Fatal("database initialization failed: ", e)
	}
	defer store.Close()
	host, _, e := net.SplitHostPort(*addr)
	if e != nil || host != "127.0.0.1" && host != "::1" {
		log.Fatal("--addr must use a loopback IP")
	}
	ln, e := net.Listen("tcp", *addr)
	if e != nil {
		log.Fatal(e)
	}
	defer ln.Close()
	srv := &http.Server{Handler: &queue.Server{Store: store, ClockFile: *clock}, ReadHeaderTimeout: 5 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdown)
	}()
	port := ln.Addr().(*net.TCPAddr).Port
	_ = json.NewEncoder(os.Stdout).Encode(map[string]int{"port": port})
	if e := srv.Serve(ln); e != nil && e != http.ErrServerClosed {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
func isAbsolute(p string) bool { return len(p) > 0 && p[0] == '/' }
