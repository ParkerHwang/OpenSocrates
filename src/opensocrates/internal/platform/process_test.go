package platform

import (
	"bytes"
	"context"
	"os"
	"testing"
	"time"
)

func TestProcessFixture(t *testing.T) {
	if os.Getenv("OPENSOCRATES_PLATFORM_PROCESS_TEST") != "1" {
		return
	}
	switch os.Getenv("OPENSOCRATES_PLATFORM_PROCESS_KIND") {
	case "wait":
		time.Sleep(10 * time.Second)
	case "output":
		os.Stdout.Write(bytes.Repeat([]byte("x"), 4096))
	default:
		os.Stdout.Write([]byte("한글"))
	}
	os.Exit(0)
}
func fixtureOptions(kind string) RunOptions {
	return RunOptions{Env: append(os.Environ(), "OPENSOCRATES_PLATFORM_PROCESS_TEST=1", "OPENSOCRATES_PLATFORM_PROCESS_KIND="+kind)}
}
func TestProcessDeadlineAndBoundedOutput(t *testing.T) {
	exe, e := os.Executable()
	if e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	start := time.Now()
	if _, e = Run(ctx, exe, []string{"-test.run=^TestProcessFixture$"}, fixtureOptions("wait")); e == nil {
		t.Fatal("cancelled process succeeded")
	}
	if time.Since(start) > 3*time.Second {
		t.Fatal("process cleanup unbounded")
	}
	opts := fixtureOptions("output")
	opts.OutputLimit = 100
	if _, e = Run(context.Background(), exe, []string{"-test.run=^TestProcessFixture$"}, opts); e == nil {
		t.Fatal("output limit ignored")
	}
	r, e := Run(context.Background(), exe, []string{"-test.run=^TestProcessFixture$"}, fixtureOptions("normal"))
	if e != nil || string(r.Stdout) != "한글" || r.ExitCode != 0 {
		t.Fatalf("process output incorrect: %v", e)
	}
}
