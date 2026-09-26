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
	"strings"
	"syscall"
	"time"

	"queueforge/internal/queue"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:0", "loopback listen address")
	path := flag.String("db", "", "absolute SQLite file")
	clockFile := flag.String("clock-file", "", "test clock file")
	flag.Parse()
	if !strings.HasPrefix(*addr, "127.0.0.1:") || !strings.HasPrefix(*path, "/") {
		log.Fatal("loopback address and absolute database path required")
	}
	clock := queue.RealClock
	if *clockFile != "" {
		if !strings.HasPrefix(*clockFile, "/") {
			log.Fatal("absolute clock file required")
		}
		clock = queue.FileClock(*clockFile)
	}
	store, e := queue.New(*path, clock)
	if e != nil {
		log.Fatal(e)
	}
	defer store.Close()
	listener, e := net.Listen("tcp", *addr)
	if e != nil {
		log.Fatal(e)
	}
	server := &http.Server{Handler: queue.Handler{Store: store}, ReadHeaderTimeout: 5 * time.Second}
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		<-sig
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(ctx)
	}()
	b, _ := json.Marshal(map[string]int{"port": listener.Addr().(*net.TCPAddr).Port})
	fmt.Println(string(b))
	if e = server.Serve(listener); e != nil && e != http.ErrServerClosed {
		log.Fatal(e)
	}
}
