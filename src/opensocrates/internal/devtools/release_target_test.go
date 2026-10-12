package devtools

import (
	"context"
	"debug/pe"
	"encoding/binary"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"
)

func TestNativeReleaseTargetMatrix(t *testing.T) {
	for _, row := range []struct{ target, goos, arch, suffix string }{{"darwin-arm64", "darwin", "arm64", ""}, {"windows-x64", "windows", "amd64", ".exe"}, {"windows-arm64", "windows", "arm64", ".exe"}} {
		goos, arch, suffix, err := nativeBuildTarget(row.target)
		if err != nil || goos != row.goos || arch != row.arch || suffix != row.suffix {
			t.Fatalf("incorrect native target mapping %s", row.target)
		}
		if err = requireNativeExecution(row.target, row.goos, row.arch); err != nil {
			t.Fatal(err)
		}
	}
	for _, target := range []string{"windows-amd64", "windows-386", "darwin-amd64", "linux-arm64", "windows-arm64ec", "all"} {
		if _, _, _, err := nativeBuildTarget(target); err == nil {
			t.Fatal("unexpected new target", target)
		}
	}
	if requireNativeExecution("windows-arm64", "windows", "amd64") == nil || requireNativeExecution("windows-arm64", "darwin", "arm64") == nil || requireNativeExecution("windows-x64", "windows", "arm64") == nil {
		t.Fatal("cross execution counted as native qualification")
	}
}

func TestNativeWindowsGoAndPEIdentity(t *testing.T) {
	source := filepath.Join(t.TempDir(), "main.go")
	if err := os.WriteFile(source, []byte("package main\nfunc main(){}\n"), 0644); err != nil {
		t.Fatal(err)
	}
	for _, row := range []struct {
		target, arch string
		machine      uint16
	}{{"windows-x64", "amd64", pe.IMAGE_FILE_MACHINE_AMD64}, {"windows-arm64", "arm64", pe.IMAGE_FILE_MACHINE_ARM64}} {
		t.Run(row.target, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "native.exe")
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
			defer cancel()
			command := exec.CommandContext(ctx, "go", "build", "-trimpath", "-o", path, source)
			command.Env = append(os.Environ(), "GOOS=windows", "GOARCH="+row.arch, "CGO_ENABLED=0")
			if output, err := command.CombinedOutput(); err != nil {
				t.Fatalf("native PE fixture build: %v %s", err, output)
			}
			if err := verifyGoBinary(path, row.target); err != nil {
				t.Fatal(err)
			}
			other := "windows-x64"
			if row.target == other {
				other = "windows-arm64"
			}
			if verifyGoBinary(path, other) == nil {
				t.Fatal("wrong architecture Go binary accepted")
			}
			// Keep the real Go build metadata unchanged while swapping COFF Machine.
			bytes, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			offset := int(binary.LittleEndian.Uint32(bytes[0x3c:0x40]))
			wrong := uint16(pe.IMAGE_FILE_MACHINE_AMD64)
			if wrong == row.machine {
				wrong = pe.IMAGE_FILE_MACHINE_ARM64
			}
			binary.LittleEndian.PutUint16(bytes[offset+4:offset+6], wrong)
			mutated := filepath.Join(t.TempDir(), "wrong-machine.exe")
			if err = os.WriteFile(mutated, bytes, 0644); err != nil {
				t.Fatal(err)
			}
			if verifyNativePE(mutated, row.target) == nil || verifyGoBinary(mutated, row.target) == nil {
				t.Fatal("forged PE machine accepted despite Go metadata")
			}
		})
	}
}
