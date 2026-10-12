package devtools

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"io"
	"os"
	"path/filepath"
	"testing"
	"time"
)

type nativePipeFixtureReceipt struct {
	MarkerObserved    bool   `json:"marker_observed"`
	ArgvCount         int    `json:"argv_count"`
	ArgvMatched       bool   `json:"argv_matched"`
	EchoMode          bool   `json:"echo_mode"`
	StaticMode        bool   `json:"static_mode"`
	NativeInputLen    int    `json:"native_input_len"`
	NativeInputSHA256 string `json:"native_input_sha256"`
	EOFObserved       bool   `json:"eof_observed"`
	ReadOK            bool   `json:"read_ok"`
	StdoutWriteOK     bool   `json:"stdout_write_ok"`
}

var nativePipeStaticOutput = []byte("한국 $ dollar ` tick\n")

// This native Go fixture records only bounded metadata for fixed synthetic
// input. The receipt distinguishes native execution/EOF from shell capture.
func init() {
	if os.Getenv("OPENSOCRATES_NATIVE_STDIN_FIXTURE") != "1" {
		return
	}
	mode := os.Getenv("OPENSOCRATES_NATIVE_STDIN_MODE")
	receipt := nativePipeFixtureReceipt{MarkerObserved: true, ArgvCount: len(os.Args), ArgvMatched: len(os.Args) == 4 && os.Args[1] == "hook" && os.Args[2] == "codex" && os.Args[3] == "session_started", EchoMode: mode == "" || mode == "echo", StaticMode: mode == "static"}
	save := func() {
		path := os.Getenv("OPENSOCRATES_NATIVE_STDIN_RECEIPT")
		if path == "" {
			return
		}
		b, e := json.Marshal(receipt)
		if e == nil {
			_ = platform.ExclusiveWrite(path, append(b, '\n'), 0600)
		}
	}
	if !receipt.ArgvMatched || (!receipt.EchoMode && !receipt.StaticMode) {
		save()
		os.Exit(2)
	}
	var output []byte
	if receipt.EchoMode {
		raw, e := io.ReadAll(io.LimitReader(os.Stdin, 8193))
		receipt.NativeInputLen = len(raw)
		sum := sha256.Sum256(raw)
		receipt.NativeInputSHA256 = hex.EncodeToString(sum[:])
		receipt.ReadOK = e == nil
		receipt.EOFObserved = e == nil && len(raw) <= 8192
		if e != nil || len(raw) > 8192 {
			save()
			os.Exit(2)
		}
		output = raw
	} else {
		output = nativePipeStaticOutput
	}
	_, e := os.Stdout.Write(output)
	receipt.StdoutWriteOK = e == nil
	save()
	if e != nil {
		os.Exit(2)
	}
	os.Exit(0)
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
	// Transport probes use the copied development test executable. Packaged hook
	// qualification retains its independent two-second deadline/one-second p95.
	run := func(name, binary string, arguments []string, mode string, stdin, expected []byte) bool {
		receiptPath := filepath.Join(root, name+"-receipt.json")
		probeEnv := append(append([]string(nil), env...), "OPENSOCRATES_NATIVE_STDIN_MODE="+mode, "OPENSOCRATES_NATIVE_STDIN_RECEIPT="+receiptPath)
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		started := time.Now()
		result, e := platform.Run(ctx, binary, arguments, platform.RunOptions{Env: probeEnv, Dir: work, Stdin: bytes.NewReader(stdin), OutputLimit: 8 << 20})
		category := "none"
		if e != nil {
			category = string(diagnostics.CodeOf(e))
		}
		expectedHash := sha256.Sum256(expected)
		observedHash := sha256.Sum256(result.Stdout)
		stderrHash := sha256.Sum256(result.Stderr)
		firstMismatch := -1
		for i := 0; i < len(expected) && i < len(result.Stdout); i++ {
			if expected[i] != result.Stdout[i] {
				firstMismatch = i
				break
			}
		}
		if firstMismatch < 0 && len(expected) != len(result.Stdout) {
			firstMismatch = min(len(expected), len(result.Stdout))
		}
		receipt := nativePipeFixtureReceipt{}
		receiptPresent := false
		if b, e := platform.ReadFile(receiptPath, 4096); e == nil && json.Unmarshal(b, &receipt) == nil {
			receiptPresent = true
		}
		t.Logf("native_pipe_diagnostic probe=%s target=%s error_category=%s exit_code=%d deadline_exceeded=%t elapsed_ms=%d expected_len=%d stdout_len=%d stderr_len=%d first_mismatch=%d expected_sha256=%s stdout_sha256=%s stderr_sha256=%s suffix_lf=%t suffix_crlf=%t receipt_present=%t marker_observed=%t argv_count=%d argv_match=%t echo_mode=%t static_mode=%t native_input_len=%d native_input_sha256=%s eof_observed=%t native_read_ok=%t native_stdout_write_ok=%t", name, target, category, result.ExitCode, ctx.Err() == context.DeadlineExceeded, time.Since(started).Milliseconds(), len(expected), len(result.Stdout), len(result.Stderr), firstMismatch, hex.EncodeToString(expectedHash[:]), hex.EncodeToString(observedHash[:]), hex.EncodeToString(stderrHash[:]), bytes.HasSuffix(result.Stdout, []byte{'\n'}), bytes.HasSuffix(result.Stdout, []byte{'\r', '\n'}), receiptPresent, receipt.MarkerObserved, receipt.ArgvCount, receipt.ArgvMatched, receipt.EchoMode, receipt.StaticMode, receipt.NativeInputLen, receipt.NativeInputSHA256, receipt.EOFObserved, receipt.ReadOK, receipt.StdoutWriteOK)
		return e == nil && len(result.Stderr) == 0 && bytes.Equal(result.Stdout, expected) && receiptPresent && receipt.ArgvMatched && receipt.StdoutWriteOK
	}
	direct := run("direct_echo", native, []string{"hook", "codex", "session_started"}, "echo", input, input)
	actual := run("configured_shell_echo", shell, args, "echo", input, input)
	static := run("configured_shell_static_utf8", shell, args, "static", nil, nativePipeStaticOutput)
	if target == "windows-x64" {
		// Exploratory OS-launch candidate only: no production configuration is
		// changed until native receipts establish its byte/exit behavior.
		candidate := `exit (Start-Process -FilePath "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" -ArgumentList 'hook codex session_started' -NoNewWindow -Wait -PassThru).ExitCode`
		run("exploratory_os_launcher_echo", shell, []string{"-NoProfile", "-Command", candidate}, "echo", input, input)
	}
	if !direct || !actual || !static {
		t.Fatal("configured host shell changed native input/output or failed")
	}
}
