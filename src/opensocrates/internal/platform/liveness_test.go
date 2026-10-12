package platform

import (
	"context"
	"os"
	"testing"
	"time"
)

func TestLivenessOwnProcessAndStoppedChild(t *testing.T) {
	if alive, e := ProcessAlive(os.Getpid()); e != nil || !alive {
		t.Fatalf("current process missing: %v", e)
	}
	if _, e := ProcessAlive(0); e == nil {
		t.Fatal("zero PID accepted")
	}
	exe, e := os.Executable()
	if e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	child, e := Start(ctx, exe, []string{"-test.run=^TestProcessFixture$"}, fixtureOptions("wait"))
	if e != nil {
		t.Fatal(e)
	}
	pid := child.Cmd.Process.Pid
	if alive, e := ProcessAlive(pid); e != nil || !alive {
		child.Close()
		t.Fatalf("live child missing: %v", e)
	}
	child.Close()
	child.Wait()
	if alive, e := ProcessAlive(pid); e != nil || alive {
		t.Fatalf("stopped child reported alive: %v", e)
	}
}
