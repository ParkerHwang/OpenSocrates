package devtools

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
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
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	started := time.Now()
	result, e := platform.Run(ctx, shell, args, platform.RunOptions{Env: env, Dir: work, Stdin: bytes.NewReader(input), OutputLimit: 8 << 20})
	out, errout := result.Stdout, result.Stderr
	if e != nil || len(errout) != 0 || !bytes.Equal(out, input) {
		category := "none"
		if e != nil {
			category = string(diagnostics.CodeOf(e))
		}
		expectedHash := sha256.Sum256(input)
		observedHash := sha256.Sum256(out)
		stderrHash := sha256.Sum256(errout)
		firstMismatch := -1
		for i := 0; i < len(input) && i < len(out); i++ {
			if input[i] != out[i] {
				firstMismatch = i
				break
			}
		}
		if firstMismatch < 0 && len(input) != len(out) {
			firstMismatch = min(len(input), len(out))
		}
		// The payload is a fixed synthetic literal. Report only bounded outcome
		// metadata, never command text, paths, environment values or stderr bytes.
		t.Logf("native_pipe_diagnostic target=%s error_category=%s exit_code=%d deadline_exceeded=%t elapsed_ms=%d expected_len=%d stdout_len=%d stderr_len=%d first_mismatch=%d expected_sha256=%s stdout_sha256=%s stderr_sha256=%s suffix_lf=%t suffix_crlf=%t", target, category, result.ExitCode, ctx.Err() == context.DeadlineExceeded, time.Since(started).Milliseconds(), len(input), len(out), len(errout), firstMismatch, hex.EncodeToString(expectedHash[:]), hex.EncodeToString(observedHash[:]), hex.EncodeToString(stderrHash[:]), bytes.HasSuffix(out, []byte{'\n'}), bytes.HasSuffix(out, []byte{'\r', '\n'}))
		t.Fatal("configured host shell changed native input/output or failed")
	}
}
