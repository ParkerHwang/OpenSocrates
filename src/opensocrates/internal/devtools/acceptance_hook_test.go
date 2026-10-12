package devtools

import (
	"bytes"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"io"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// Re-execution is a native Go process fixture. The shell receives the same hook
// command/arguments as a generated package, with no first-party script wrapper.
func init() {
	if os.Getenv("OPENSOCRATES_NATIVE_STDIN_FIXTURE") == "1" && len(os.Args) == 4 && os.Args[1] == "hook" && os.Args[2] == "codex" && os.Args[3] == "session_started" {
		raw, e := io.ReadAll(io.LimitReader(os.Stdin, 8193))
		if e != nil || len(raw) > 8192 {
			os.Exit(2)
		}
		if _, e = os.Stdout.Write(raw); e != nil {
			os.Exit(2)
		}
		os.Exit(0)
	}
}
func TestActualConfiguredShellPreservesNativeStdinAndUnsafeLookingPaths(t *testing.T) {
	target := nativeAcceptanceTarget()
	if target == "unsupported" {
		t.Skip("native macOS ARM64 or Windows x64 evidence required")
	}
	root := filepath.Join(t.TempDir(), "한국 $ dollar ` tick and spaces")
	native := filepath.Join(root, "runtime", target, "opensocrates")
	if target == "windows-x64" {
		native += ".exe"
	}
	if e := platform.Mkdir(filepath.Dir(native)); e != nil {
		t.Fatal("private native fixture directory unavailable")
	}
	self, e := os.Executable()
	if e != nil {
		t.Fatal(e)
	}
	raw, e := os.ReadFile(self)
	if e != nil {
		t.Fatal(e)
	}
	if e = platform.AtomicWrite(native, raw, 0755); e != nil {
		t.Fatal("native fixture unavailable")
	}
	command := `"$PLUGIN_ROOT/runtime/darwin-arm64/opensocrates" hook codex session_started`
	if target == "windows-x64" {
		command = `& "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" hook codex session_started`
	}
	shell, args, e := configuredHookInvocation(command, "codex", target)
	if e != nil {
		t.Fatal("qualified shell unavailable")
	}
	env, work, e := isolatedAcceptanceEnvironment(filepath.Join(root, "fixture"))
	if e != nil {
		t.Fatal(e)
	}
	env = append(env, "PLUGIN_ROOT="+root, "OPENSOCRATES_NATIVE_STDIN_FIXTURE=1")
	input := []byte("{\"unicode\":\"한국\",\"numeric\":9007199254740993,\"text\":\"$ dollar ` tick\"}\n")
	// This test checks byte transport through a copied development test executable.
	// Cold PowerShell/test initialization has a separate deadline; packaged hook
	// qualification still requires its two-second host deadline and one-second p95.
	out, errout, e := runAcceptanceProcess(shell, args, input, env, work, 15*time.Second)
	if e != nil || len(errout) != 0 || !bytes.Equal(out, input) {
		t.Fatal("configured host shell changed native input/output or failed")
	}
}
