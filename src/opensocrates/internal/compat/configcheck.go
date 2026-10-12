package compat

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

const MaxConfigCheckOutput = 1 << 20
const MaxConfigCheckLine = 256 << 10
const HostConfigVersion = "0.133.0"
const HostConfigProtocolCommit = "9474e5cfc4494b0ba319352aa86ce436c59e65c8"

type configOutputBudget struct {
	mu     sync.Mutex
	used   int
	cancel context.CancelFunc
}

func (b *configOutputBudget) take(n int) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.used += n
	if b.used > MaxConfigCheckOutput {
		b.cancel()
		return failure(diagnostics.Verification)
	}
	return nil
}

type configStderr struct{ budget *configOutputBudget }

func (w configStderr) Write(p []byte) (int, error) {
	if err := w.budget.take(len(p)); err != nil {
		return 0, err
	}
	return len(p), nil
}

type configStdout struct {
	reader io.Reader
	budget *configOutputBudget
}

func (r configStdout) Read(p []byte) (int, error) {
	n, err := r.reader.Read(p)
	if n > 0 {
		if limitErr := r.budget.take(n); limitErr != nil {
			return n, limitErr
		}
	}
	return n, err
}

// ValidateConfig validates a trust-reset candidate without authentication or a
// model/tool turn. Host configuration qualification is separate from the
// legacy selector's exact0.144.4 pin. A bounded help probe chooses the exposed
// stdio transport, while the closed response shape checks the real capability.
func ValidateConfig(parent context.Context, binary string, contents []byte) error {
	if parent.Err() != nil || len(contents) > 16<<20 || !utf8.Valid(contents) {
		return failure(diagnostics.Verification)
	}
	ctx, cancel := context.WithTimeout(parent, 14*time.Second)
	defer cancel()
	if !filepath.IsAbs(binary) {
		resolved, err := exec.LookPath(binary)
		if err != nil || !filepath.IsAbs(resolved) {
			return failure(diagnostics.HostUnavailable)
		}
		binary = resolved
	}
	root, env, workspace, home, err := configCheckEnvironment()
	if err != nil {
		return err
	}
	defer os.RemoveAll(root)
	if err = platform.AtomicWrite(filepath.Join(home, "config.toml"), contents, 0600); err != nil {
		return failure(diagnostics.Permission)
	}
	version, err := platform.Run(ctx, binary, []string{"--version"}, platform.RunOptions{Dir: workspace, Env: env, OutputLimit: 4096})
	if err != nil {
		return failure(diagnostics.HostUnavailable)
	}
	text := strings.TrimSpace(string(version.Stdout))
	if !strings.HasPrefix(text, "codex-cli ") || !validText(text, 4096, true) {
		return failure(diagnostics.ProtocolIncompatible)
	}
	help, err := platform.Run(ctx, binary, []string{"app-server", "--help"}, platform.RunOptions{Dir: workspace, Env: env, OutputLimit: 16 << 10})
	if err != nil {
		return failure(diagnostics.HostUnavailable)
	}
	transport, err := configCheckTransport(string(help.Stdout))
	if err != nil {
		return err
	}
	budget := &configOutputBudget{cancel: cancel, used: len(version.Stdout) + len(version.Stderr) + len(help.Stdout) + len(help.Stderr)}
	inputRead, inputWrite, err := os.Pipe()
	if err != nil {
		return failure(diagnostics.HostUnavailable)
	}
	outputRead, outputWrite, err := os.Pipe()
	if err != nil {
		inputRead.Close()
		inputWrite.Close()
		return failure(diagnostics.HostUnavailable)
	}
	// This flow never starts a thread, logs in, or reads the user's real home.
	args := []string{"--config", "analytics.enabled=false", "--config", `otel.exporter="none"`, "--config", `otel.trace_exporter="none"`, "--config", `otel.metrics_exporter="none"`, "--config", "otel.log_user_prompt=false", "--config", "features.hooks=false", "--config", "features.plugins=false", "--config", "features.multi_agent=false", "--config", "project_doc_max_bytes=0", "app-server"}
	args = append(args, transport...)
	process, err := platform.Start(ctx, binary, args, platform.RunOptions{Dir: workspace, Env: env, Stdin: inputRead, Stdout: outputWrite, Stderr: configStderr{budget: budget}})
	inputRead.Close()
	outputWrite.Close()
	if err != nil {
		inputWrite.Close()
		outputRead.Close()
		return failure(diagnostics.HostUnavailable)
	}
	defer func() { cancel(); inputWrite.Close(); outputRead.Close(); process.Close(); process.Wait() }()
	done := make(chan error, 1)
	go func() {
		scanner := bufio.NewScanner(configStdout{reader: outputRead, budget: budget})
		scanner.Buffer(make([]byte, 4096), MaxConfigCheckLine+1)
		notifications := 0
		initialized := false
		for scanner.Scan() {
			line := scanner.Bytes()
			if len(line) > MaxConfigCheckLine {
				done <- failure(diagnostics.Verification)
				return
			}
			value, e := contracts.Decode(line)
			if e != nil {
				done <- failure(diagnostics.ProtocolIncompatible)
				return
			}
			m, ok := value.(map[string]any)
			if !ok {
				done <- failure(diagnostics.ProtocolIncompatible)
				return
			}
			id, present := m["id"]
			if !present {
				if _, ok := m["method"].(string); !ok {
					done <- failure(diagnostics.ProtocolIncompatible)
					return
				}
				notifications++
				if notifications > 128 {
					done <- failure(diagnostics.Verification)
					return
				}
				continue
			}
			requestID, ok := contracts.Int(id)
			if !ok || requestID != 1 || initialized || m["method"] != nil || m["error"] != nil {
				done <- failure(diagnostics.ProtocolIncompatible)
				return
			}
			if !validConfigInitialize(m["result"], home) {
				done <- failure(diagnostics.ProtocolIncompatible)
				return
			}
			initialized = true
			// EOF is part of acceptance: config loading must end without a live client,
			// and an executable that emits a valid line then fails is not accepted.
			if e = inputWrite.Close(); e != nil {
				done <- failure(diagnostics.HostUnavailable)
				return
			}
		}
		if scanner.Err() != nil || !initialized {
			done <- failure(diagnostics.ProtocolIncompatible)
			return
		}
		done <- nil
	}()
	request := []byte("{\"id\":1,\"method\":\"initialize\",\"params\":{\"clientInfo\":{\"name\":\"opensocrates_config_validation\",\"title\":\"OpenSocrates\",\"version\":\"1.6.0\"}}}\n")
	deadline, _ := ctx.Deadline()
	if inputWrite.SetWriteDeadline(deadline) != nil {
		return failure(diagnostics.HostUnavailable)
	}
	if _, err = inputWrite.Write(request); err != nil {
		return failure(diagnostics.HostUnavailable)
	}
	select {
	case err = <-done:
		if err != nil {
			return err
		}
	case <-ctx.Done():
		return failure(diagnostics.HostUnavailable)
	}
	exited := make(chan error, 1)
	go func() { exited <- process.Wait() }()
	select {
	case err = <-exited:
		if err != nil || process.Cmd.ProcessState == nil || process.Cmd.ProcessState.ExitCode() != 0 {
			return failure(diagnostics.HostUnavailable)
		}
	case <-ctx.Done():
		return failure(diagnostics.HostUnavailable)
	}
	return nil
}

func configCheckTransport(help string) ([]string, error) {
	if !validText(help, 16<<10, true) {
		return nil, failure(diagnostics.ProtocolIncompatible)
	}
	hasListen, hasStdio, hasStrict := false, false, false
	for _, token := range strings.Fields(help) {
		token = strings.Trim(token, ",[]")
		if token == "--listen" {
			hasListen = true
		}
		if token == "--stdio" {
			hasStdio = true
		}
		if token == "--strict-config" {
			hasStrict = true
		}
	}
	if !hasStrict {
		return nil, failure(diagnostics.ProtocolIncompatible)
	}
	if hasListen {
		return []string{"--listen", "stdio://", "--strict-config"}, nil
	}
	if hasStdio {
		return []string{"--stdio", "--strict-config"}, nil
	}
	return nil, failure(diagnostics.ProtocolIncompatible)
}

func validConfigInitialize(value any, expectedHome string) bool {
	m, ok := value.(map[string]any)
	if !ok {
		return false
	}
	userAgent, ok := m["userAgent"].(string)
	if !ok || !validText(userAgent, 4096, true) {
		return false
	}
	home, ok := m["codexHome"].(string)
	if !ok || !filepath.IsAbs(home) || !validText(home, 32768, true) {
		return false
	}
	actual, err := filepath.EvalSymlinks(home)
	if err != nil || actual != expectedHome {
		return false
	}
	family := "unix"
	osName := runtime.GOOS
	if osName == "darwin" {
		osName = "macos"
	}
	if runtime.GOOS == "windows" {
		family = "windows"
	}
	return m["platformFamily"] == family && m["platformOs"] == osName
}

func configCheckEnvironment() (string, []string, string, string, error) {
	temp, err := filepath.EvalSymlinks(os.TempDir())
	if err != nil {
		return "", nil, "", "", failure(diagnostics.Permission)
	}
	nonce := make([]byte, 16)
	if _, err = rand.Read(nonce); err != nil {
		return "", nil, "", "", failure(diagnostics.Permission)
	}
	root := filepath.Join(temp, "opensocrates-config-check-"+hex.EncodeToString(nonce))
	if _, err = os.Lstat(root); !os.IsNotExist(err) {
		return "", nil, "", "", failure(diagnostics.Permission)
	}
	if err = platform.Mkdir(root); err != nil {
		return "", nil, "", "", failure(diagnostics.Permission)
	}
	failed := true
	defer func() {
		if failed {
			os.RemoveAll(root)
		}
	}()
	dirs := map[string]string{}
	for _, name := range []string{"codex-home", "home", "xdg-config", "xdg-cache", "xdg-data", "xdg-state", "tmp", "workspace"} {
		path := filepath.Join(root, name)
		if err = platform.Mkdir(path); err != nil {
			return "", nil, "", "", failure(diagnostics.Permission)
		}
		dirs[name] = path
	}
	envMap := map[string]string{"CODEX_HOME": dirs["codex-home"], "HOME": dirs["home"], "USERPROFILE": dirs["home"], "XDG_CONFIG_HOME": dirs["xdg-config"], "XDG_CACHE_HOME": dirs["xdg-cache"], "XDG_DATA_HOME": dirs["xdg-data"], "XDG_STATE_HOME": dirs["xdg-state"], "TEMP": dirs["tmp"], "TMP": dirs["tmp"], "TMPDIR": dirs["tmp"], "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", RecursionEnvironment: "1"}
	if runtime.GOOS == "windows" {
		windowsDir := os.Getenv("SystemRoot")
		if windowsDir == "" || !filepath.IsAbs(windowsDir) {
			return "", nil, "", "", failure(diagnostics.Unsupported)
		}
		envMap["SystemRoot"] = windowsDir
		envMap["WINDIR"] = windowsDir
		envMap["PATH"] = filepath.Join(windowsDir, "System32") + ";" + windowsDir
		envMap["APPDATA"] = dirs["xdg-config"]
		envMap["LOCALAPPDATA"] = dirs["xdg-data"]
	} else {
		envMap["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
		envMap["SHELL"] = "/bin/sh"
	}
	keys := []string{}
	for key := range envMap {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	env := []string{}
	for _, key := range keys {
		env = append(env, key+"="+envMap[key])
	}
	failed = false
	return root, env, dirs["workspace"], dirs["codex-home"], nil
}
