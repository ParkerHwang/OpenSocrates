package devtools

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
	"unicode/utf16"
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
			return
		}
		b, e := json.Marshal(receipt)
		if e == nil {
			if _, statError := os.Lstat(path); os.IsNotExist(statError) {
				_ = platform.ExclusiveWrite(path, append(b, '\n'), 0600)
			} else if statError == nil {
				_ = platform.AtomicWrite(path, append(b, '\n'), 0600)
			}
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
		if strings.HasPrefix(name, "plain_") {
			command := exec.CommandContext(ctx, binary, arguments...)
			command.Env = probeEnv
			command.Dir = work
			command.Stdin = bytes.NewReader(stdin)
			command.WaitDelay = time.Second
			var stdoutBuffer, stderrBuffer bytes.Buffer
			command.Stdout = &stdoutBuffer
			command.Stderr = &stderrBuffer
			e = command.Run()
			result.Stdout, result.Stderr = stdoutBuffer.Bytes(), stderrBuffer.Bytes()
			if command.ProcessState != nil {
				result.ExitCode = command.ProcessState.ExitCode()
			}
		} else {
			result, e = platform.Run(ctx, binary, arguments, platform.RunOptions{Env: probeEnv, Dir: work, Stdin: bytes.NewReader(stdin), OutputLimit: 8 << 20})
		}
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
		t.Logf("shell_fixed_marker probe=%s before_seen=%t after_seen=%t fixture_flag_true=%t root_present=%t", name, bytes.Contains(result.Stdout, []byte("opensocrates-before;")), bytes.Contains(result.Stdout, []byte("opensocrates-after;")), bytes.Contains(result.Stdout, []byte("fixture=True;")), bytes.Contains(result.Stdout, []byte("root=True;")))
		return e == nil && len(result.Stderr) == 0 && bytes.Equal(result.Stdout, expected) && receiptPresent && receipt.ArgvMatched && receipt.StdoutWriteOK
	}
	direct := run("direct_echo", native, []string{"hook", "codex", "session_started"}, "echo", input, input)
	actual := run("configured_shell_echo", shell, args, "echo", input, input)
	static := run("configured_shell_static_utf8", shell, args, "static", nil, nativePipeStaticOutput)
	if target == "windows-x64" {
		run("plain_current_shell_echo", shell, args, "echo", input, input)
		// Fixed ASCII controls have no native child, so plain execution can be
		// compared to containment without launching an uncontrolled host process.
		ascii := `Write-Output 'opensocrates-probe'`
		for _, inherited := range []bool{false, true} {
			controlEnv := env
			if inherited {
				controlEnv = os.Environ()
			}
			for _, encoded := range []bool{false, true} {
				controlArgs := []string{"-NoProfile", "-Command", ascii}
				if encoded {
					controlArgs = []string{"-NoProfile", "-EncodedCommand", encodePipeDiagnosticCommand(ascii)}
				}
				for _, plain := range []bool{false, true} {
					ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
					started := time.Now()
					var out, stderr []byte
					var err error
					exitCode := 0
					if plain {
						command := exec.CommandContext(ctx, shell, controlArgs...)
						command.Env = controlEnv
						command.Dir = work
						var stdoutBuffer, stderrBuffer bytes.Buffer
						command.Stdout = &stdoutBuffer
						command.Stderr = &stderrBuffer
						err = command.Run()
						out, stderr = stdoutBuffer.Bytes(), stderrBuffer.Bytes()
						if command.ProcessState != nil {
							exitCode = command.ProcessState.ExitCode()
						}
					} else {
						result, e := platform.Run(ctx, shell, controlArgs, platform.RunOptions{Env: controlEnv, Dir: work, OutputLimit: 8192})
						out, stderr, err, exitCode = result.Stdout, result.Stderr, e, result.ExitCode
					}
					category := "none"
					if err != nil {
						category = string(diagnostics.CodeOf(err))
					}
					hash := sha256.Sum256(out)
					t.Logf("ascii_shell_control plain_exec=%t inherited_env=%t encoded_command=%t error_category=%s exit_code=%d deadline_exceeded=%t elapsed_ms=%d stdout_len=%d stderr_len=%d stdout_sha256=%s ascii_marker_seen=%t", plain, inherited, encoded, category, exitCode, ctx.Err() == context.DeadlineExceeded, time.Since(started).Milliseconds(), len(out), len(stderr), hex.EncodeToString(hash[:]), bytes.Contains(out, []byte("opensocrates-probe")))
					cancel()
				}
			}
		}
		wrapped := `[Console]::Out.Write('opensocrates-before;'); [Console]::Out.Write(('fixture=' + [bool]($env:OPENSOCRATES_NATIVE_STDIN_FIXTURE -eq '1') + ';root=' + [bool]($env:PLUGIN_ROOT) + ';')); & "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" hook codex session_started; [Console]::Out.Write('opensocrates-after;')`
		run("wrapped_shell_command", shell, []string{"-NoProfile", "-Command", wrapped}, "echo", input, input)
		run("wrapped_shell_encoded", shell, []string{"-NoProfile", "-EncodedCommand", encodePipeDiagnosticCommand(wrapped)}, "echo", input, input)
		// Exploratory OS-launch candidate only: no production configuration is
		// changed until native receipts establish its byte/exit behavior.
		candidate := `exit (Start-Process -FilePath "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" -ArgumentList 'hook codex session_started' -NoNewWindow -Wait -PassThru).ExitCode`
		run("exploratory_os_launcher_echo", shell, []string{"-NoProfile", "-Command", candidate}, "echo", input, input)
	}
	if !direct || !actual || !static {
		t.Fatal("configured host shell changed native input/output or failed")
	}
}

func encodePipeDiagnosticCommand(command string) string {
	words := utf16.Encode([]rune(command))
	raw := make([]byte, len(words)*2)
	for i, w := range words {
		binary.LittleEndian.PutUint16(raw[i*2:], w)
	}
	return base64.StdEncoding.EncodeToString(raw)
}
