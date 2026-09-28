package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"queueforge/internal/queueforge"
	"syscall"
	"time"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:0", "loopback listen address")
	dbPath := flag.String("db", "", "absolute SQLite file")
	clockFile := flag.String("clock-file", "", "test clock file")
	flag.Parse()
	if *dbPath == "" || !mustAbs(*dbPath) {
		fmt.Fprintln(os.Stderr, "--db must be absolute")
		os.Exit(2)
	}
	host, _, e := net.SplitHostPort(*addr)
	if e != nil || net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback() {
		fmt.Fprintln(os.Stderr, "--addr must be a loopback IP address")
		os.Exit(2)
	}
	var clock queueforge.Clock = queueforge.RealClock
	if *clockFile != "" {
		if !mustAbs(*clockFile) {
			fmt.Fprintln(os.Stderr, "--clock-file must be absolute")
			os.Exit(2)
		}
		clock = queueforge.FileClock(*clockFile)
	}
	s, e := queueforge.Open(*dbPath, clock)
	if e != nil {
		fmt.Fprintln(os.Stderr, "storage initialization failed:", e)
		os.Exit(1)
	}
	defer s.Close()
	ln, e := net.Listen("tcp", *addr)
	if e != nil {
		fmt.Fprintln(os.Stderr, "listen failed:", e)
		os.Exit(1)
	}
	server := &http.Server{Handler: s, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if e := server.Serve(ln); e != nil && e != http.ErrServerClosed {
			fmt.Fprintln(os.Stderr, "serve failed:", e)
		}
	}()
	_ = json.NewEncoder(os.Stdout).Encode(map[string]int{"port": ln.Addr().(*net.TCPAddr).Port})
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM, syscall.SIGINT)
	<-signals
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	_ = server.Shutdown(ctx)
}
func mustAbs(p string) bool { return len(p) > 0 && p[0] == '/' }
