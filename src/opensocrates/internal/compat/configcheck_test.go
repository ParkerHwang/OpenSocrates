package compat

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func fixtureConfigInitialize(m wireMessage, send func(any)) {
	home := os.Getenv("CODEX_HOME")
	raw, _ := os.ReadFile(filepath.Join(home, "config.toml"))
	mode := string(raw)
	if _, err := os.Stat(filepath.Join(home, "auth.json")); !os.IsNotExist(err) {
		os.Exit(71)
	}
	if os.Getenv("OPENAI_API_KEY") != "" || os.Getenv("SECRET_CONFIG_TEST_VALUE") != "" {
		os.Exit(72)
	}
	if strings.Contains(mode, "fixture_invalid_config") {
		strict := false
		for _, arg := range os.Args {
			if arg == "--strict-config" {
				strict = true
			}
		}
		if strict {
			os.Exit(73)
		}
	}
	if strings.Contains(mode, "fixture_hang") {
		time.Sleep(30 * time.Second)
		return
	}
	if strings.Contains(mode, "fixture_notifications") {
		for i := 0; i < 129; i++ {
			send(map[string]any{"method": "config/warning", "params": map[string]string{"message": "synthetic"}})
		}
	}
	if strings.Contains(mode, "fixture_stderr_limit") {
		fmt.Fprint(os.Stderr, strings.Repeat("x", MaxConfigCheckOutput+1))
	}
	if strings.Contains(mode, "fixture_long_line") {
		fmt.Println(strings.Repeat("x", MaxConfigCheckLine+1))
		return
	}
	if strings.Contains(mode, "fixture_wrong_home") {
		home = filepath.Dir(home)
	}
	family, osName := "unix", runtime.GOOS
	if osName == "darwin" {
		osName = "macos"
	}
	if osName == "windows" {
		family = "windows"
	}
	send(map[string]any{"id": json.RawMessage(m.ID), "result": map[string]string{"userAgent": "codex-cli/" + CodexVersion, "codexHome": home, "platformFamily": family, "platformOs": osName}})
	if strings.Contains(mode, "fixture_failure_after_init") {
		os.Exit(17)
	}
	if strings.Contains(mode, "fixture_extra_response") {
		send(map[string]any{"id": 2, "result": map[string]string{}})
	}
}
func TestConfigValidatorPrivateNoAuth(t *testing.T) {
	binary, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("OPENAI_API_KEY", "private-parent-value")
	t.Setenv("SECRET_CONFIG_TEST_VALUE", "private-parent-value")
	if err = ValidateConfig(context.Background(), binary, []byte("# synthetic config only\n")); err != nil {
		t.Fatalf("private noauth config validation: %v", err)
	}
}
func TestConfigValidatorRejectsUnsafeResults(t *testing.T) {
	binary, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	for _, mode := range []string{"fixture_invalid_config", "fixture_wrong_home", "fixture_failure_after_init", "fixture_extra_response", "fixture_notifications", "fixture_stderr_limit", "fixture_long_line"} {
		t.Run(mode, func(t *testing.T) {
			if err := ValidateConfig(context.Background(), binary, []byte("# "+mode+"\n")); err == nil {
				t.Fatal("unsafe validator result accepted")
			}
		})
	}
}
func TestConfigValidatorDeadlineCleanup(t *testing.T) {
	binary, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 300*time.Millisecond)
	defer cancel()
	started := time.Now()
	if err = ValidateConfig(ctx, binary, []byte("# fixture_hang\n")); err == nil {
		t.Fatal("stalled appserver accepted")
	}
	if time.Since(started) > 1300*time.Millisecond {
		t.Fatal("deadline cleanup exceeded reserve")
	}
}
func TestConfigValidatorFeatureProbe(t *testing.T) {
	for _, help := range []string{"Usage\n --listen <URL>\n --strict-config", "Usage\n --stdio\n --strict-config"} {
		if _, err := configCheckTransport(help); err != nil {
			t.Fatal("supported feature rejected")
		}
	}
	for _, help := range []string{"Usage\n --server", "Usage\n --listen <URL>"} {
		if _, err := configCheckTransport(help); err == nil {
			t.Fatal("unknown transport or strict validation guessed")
		}
	}
}

func TestConfigRequestWriteWithoutPipeDeadline(t *testing.T) {
	reader, writer := io.Pipe()
	defer reader.Close()
	defer writer.Close()
	read := make(chan []byte, 1)
	go func() {
		data := make([]byte, 3)
		_, err := io.ReadFull(reader, data)
		if err != nil {
			read <- nil
			return
		}
		read <- data
	}()
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := writeConfigRequest(ctx, writer, []byte("abc"), func() { reader.Close() }); err != nil {
		t.Fatal("nonpollable request pipe rejected")
	}
	if string(<-read) != "abc" {
		t.Fatal("request frame changed")
	}
}

func TestConfigRequestBlockedWriteCancellation(t *testing.T) {
	reader, writer := io.Pipe()
	defer reader.Close()
	defer writer.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	stopped := false
	if err := writeConfigRequest(ctx, writer, []byte("abc"), func() { stopped = true; reader.Close() }); err == nil || !stopped {
		t.Fatal("blocked write did not cancel its process")
	}
}
