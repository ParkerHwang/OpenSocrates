package managercli

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"testing"
)

func TestUnsupportedUpdateScopeNeverMutates(t *testing.T) {
	dir := t.TempDir()
	state := filepath.Join(dir, "absent-state")
	for _, args := range [][]string{
		{"auto-update", "enable", "--host", "claude", "--state-dir", state},
		{"auto-update", "run", "--channel", "next", "--state-dir", state},
		{"auto-update", "enable", "--scheduled", "--state-dir", state},
		{"auto-update", "run", "--login-delay", "1", "--state-dir", state},
	} {
		var out, errout bytes.Buffer
		if code := RunUpdateContext(context.Background(), args, &out, &errout); code != 2 {
			t.Fatalf("unsupported update accepted: %v", args)
		}
	}
	if _, err := os.Stat(state); !os.IsNotExist(err) {
		t.Fatal("invalid command changed state")
	}
}
