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
	"runtime"
	"strings"
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
	ReadStarted       bool   `json:"read_started"`
	ReadCompleted     bool   `json:"read_completed"`
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
			os.Exit(2)
		}
		b, e := json.Marshal(receipt)
		if e != nil {
			os.Exit(2)
		}
		if _, statError := os.Lstat(path); os.IsNotExist(statError) {
			e = platform.ExclusiveWrite(path, append(b, '\n'), 0600)
		} else if statError == nil {
			e = platform.AtomicWrite(path, append(b, '\n'), 0600)
		} else {
			e = statError
		}
		if e != nil {
			os.Exit(2)
		}
	}
	if !receipt.ArgvMatched || (!receipt.EchoMode && !receipt.StaticMode) {
		save()
		os.Exit(2)
	}
	save()
	var output []byte
	if receipt.EchoMode {
		receipt.ReadStarted = true
		save()
		type inputResult struct {
			raw []byte
			err error
		}
		completed := make(chan inputResult, 1)
		go func() { raw, e := io.ReadAll(io.LimitReader(os.Stdin, 8193)); completed <- inputResult{raw, e} }()
		var raw []byte
		var e error
		select {
		case read := <-completed:
			raw, e = read.raw, read.err
			receipt.ReadCompleted = true
		case <-time.After(10 * time.Second):
			save()
			os.Exit(2)
		}
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
	if target == "windows-x64" {
		// Initialize only this developer test fixture's private shell profile/cache.
		// Actual packaged timing below has no warmup and retains every cold sample.
		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		started := time.Now()
		ready := []byte("opensocrates-fixture-shell-ready")
		result, setupError := platform.Run(ctx, shell, []string{"-NoProfile", "-Command", "[Console]::Out.Write('opensocrates-fixture-shell-ready')"}, platform.RunOptions{Env: env, Dir: work, OutputLimit: 4096})
		cancel()
		category := "none"
		if setupError != nil {
			category = string(diagnostics.CodeOf(setupError))
		}
		t.Logf("native_fixture_shell_setup elapsed_ms=%d error_category=%s exit_code=%d stdout_len=%d stderr_len=%d", time.Since(started).Milliseconds(), category, result.ExitCode, len(result.Stdout), len(result.Stderr))
		if setupError != nil || len(result.Stderr) != 0 || !bytes.Equal(result.Stdout, ready) {
			t.Fatal("private native shell fixture initialization failed")
		}
	}
	input := []byte("{\"unicode\":\"한국\",\"numeric\":9007199254740993,\"text\":\"$ dollar ` tick\"}\n")
	// Transport probes use the copied development test executable. Packaged hook
	// qualification retains its independent two-second deadline/one-second p95.
	run := func(name, binary string, arguments []string, mode string, stdin, expected []byte) bool {
		receiptPath := filepath.Join(root, name+"-receipt.json")
		probeEnv := append(append([]string(nil), env...), "OPENSOCRATES_NATIVE_STDIN_MODE="+mode, "OPENSOCRATES_NATIVE_STDIN_RECEIPT="+receiptPath)
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		started := time.Now()
		var result platform.Result
		var e error
		result, e = platform.Run(ctx, binary, arguments, platform.RunOptions{Env: probeEnv, Dir: work, Stdin: bytes.NewReader(stdin), OutputLimit: 8 << 20})
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
		t.Logf("native_receipt_phase probe=%s native_read_started=%t native_read_completed=%t", name, receipt.ReadStarted, receipt.ReadCompleted)
		return e == nil && len(result.Stderr) == 0 && bytes.Equal(result.Stdout, expected) && receiptPresent && receipt.ArgvMatched && receipt.StdoutWriteOK
	}
	direct := run("direct_echo", native, []string{"hook", "codex", "session_started"}, "echo", input, input)
	actual := run("configured_shell_echo", shell, args, "echo", input, input)
	static := run("configured_shell_static_utf8", shell, args, "static", nil, nativePipeStaticOutput)

	if !direct || !actual || !static {
		t.Fatal("configured host shell changed native input/output or failed")
	}
}

func TestIsolatedAcceptanceEnvironmentKeepsOSDiscoveryAndExcludesCredentials(t *testing.T) {
	for _, key := range []string{"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "HTTPS_PROXY", "COMPLUS_Profiling", "COR_ENABLE_PROFILING", "PSExecutionPolicyPreference"} {
		t.Setenv(key, "synthetic-value-that-must-not-be-inherited")
	}
	t.Setenv("PSModulePath", "synthetic-user-module-path")
	t.Setenv("ProgramData", "synthetic-os-program-data")
	t.Setenv("PATHEXT", ".PS1;.JS;.UNKNOWN")
	root, e := platform.MkdirTemp("", "opensocrates-environment-test-")
	if e != nil {
		t.Fatal(e)
	}
	defer os.RemoveAll(root)
	values, work, e := isolatedAcceptanceEnvironment(root)
	if e != nil {
		t.Fatal(e)
	}
	env := map[string]string{}
	for _, entry := range values {
		parts := strings.SplitN(entry, "=", 2)
		env[strings.ToUpper(parts[0])] = parts[1]
	}
	for _, key := range []string{"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "HTTPS_PROXY", "COMPLUS_PROFILING", "COR_ENABLE_PROFILING", "PSEXECUTIONPOLICYPREFERENCE"} {
		if _, exists := env[key]; exists {
			t.Fatal("credential or caller code-loading override inherited")
		}
	}
	for _, key := range []string{"HOME", "USERPROFILE", "CODEX_HOME", "OPENSOCRATES_STATE_DIR", "TMPDIR", "TMP", "TEMP"} {
		relative, e := filepath.Rel(root, env[key])
		if e != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
			t.Fatal("fixture state or temporary directory escaped isolated root")
		}
	}
	if work != filepath.Join(root, "workspace") {
		t.Fatal("fixture workspace was not isolated")
	}
	if runtime.GOOS == "windows" {
		for _, key := range []string{"APPDATA", "LOCALAPPDATA"} {
			relative, e := filepath.Rel(root, env[key])
			if e != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
				t.Fatal("Windows special folder escaped isolated root")
			}
			if platform.Guard(env[key]) != nil {
				t.Fatal("Windows private special folder missing")
			}
		}
		if env["PROGRAMDATA"] != "synthetic-os-program-data" || env["PATHEXT"] != ".COM;.EXE;.BAT;.CMD" {
			t.Fatal("closed OS environment not preserved")
		}
		if env["HOMEDRIVE"]+env["HOMEPATH"] != env["USERPROFILE"] {
			t.Fatal("Windows home variables were inconsistent")
		}
		if strings.Contains(env["PSMODULEPATH"], "synthetic-user-module-path") {
			t.Fatal("user PowerShell module path inherited")
		}
		if !strings.Contains(env["PSMODULEPATH"], filepath.Join(env["USERPROFILE"], "Documents", "WindowsPowerShell", "Modules")) {
			t.Fatal("isolated module directory missing")
		}
		if filepath.Dir(env["PSMODULEANALYSISCACHEPATH"]) != filepath.Join(env["LOCALAPPDATA"], "Microsoft", "Windows", "PowerShell") {
			t.Fatal("PowerShell analysis cache was not isolated")
		}
	}
}
