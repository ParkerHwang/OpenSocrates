package devtools

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"testing"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

func TestMacReleaseRelativePackagePathReachesCodeVerifier(t *testing.T) {
	if runtime.GOOS != "darwin" {
		t.Skip("requires native Apple code-signing tools")
	}
	self, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(self)
	if err != nil {
		t.Fatal(err)
	}
	root := filepath.Join(t.TempDir(), "private")
	if err = platform.Mkdir(root); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "bare-cli")
	if err = platform.AtomicWrite(path, data, 0755); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if _, err = platform.Run(ctx, "/usr/bin/codesign", []string{"--force", "--sign", "-", path}, platform.RunOptions{OutputLimit: 64 << 10}); err != nil {
		t.Fatal("could not prepare ad-hoc Mach-O fixture")
	}
	t.Chdir(root)
	for _, candidate := range []string{path, "bare-cli"} {
		err = verifyMacReleaseSignature(candidate)
		var typed *diagnostics.Error
		if !errors.As(err, &typed) || typed.Code != diagnostics.Verification || typed.Stage != "native_trust" {
			t.Fatalf("owned ad-hoc path did not reach the native signature verifier: %v", err)
		}
	}
	link := "bare-cli-link"
	if err = os.Symlink("bare-cli", link); err != nil {
		t.Fatal(err)
	}
	for _, candidate := range []string{link, "./bare-cli", "unused/../bare-cli", "../private/bare-cli", root + "/../private/bare-cli"} {
		err = verifyMacReleaseSignature(candidate)
		var typed *diagnostics.Error
		if !errors.As(err, &typed) || typed.Code != diagnostics.Permission || typed.Stage != "filesystem" {
			t.Fatalf("symlink or lexical alias bypassed the filesystem guard: %v", err)
		}
	}
}

func TestNativeReleaseAuthenticatesBothExecutablesBeforeExecution(t *testing.T) {
	for _, target := range []string{"darwin-arm64", "windows-x64", "windows-arm64"} {
		for _, failed := range []string{"manager", "helper", ""} {
			t.Run(target+"/"+failed, func(t *testing.T) {
				var calls []string
				rejected := errors.New("signature rejected")
				verify := func(role, wantPath string) func(string, string) error {
					return func(path, gotTarget string) error {
						if path != wantPath || gotTarget != target {
							t.Fatal("incorrect executable or target authenticated")
						}
						calls = append(calls, role)
						if failed == role {
							return rejected
						}
						return nil
					}
				}
				marker := filepath.Join(t.TempDir(), "candidate-executed")
				commands := nativeReleaseCommands{
					verifyManager: verify("manager", "manager-path"),
					verifyHelper:  verify("helper", "helper-path"),
					version: func(path string) ([]byte, error) {
						if path != "manager-path" {
							t.Fatal("incorrect executable invoked")
						}
						calls = append(calls, "version")
						return []byte("OpenSocrates 1.6.0"), os.WriteFile(marker, []byte("executed"), 0600)
					},
				}
				err := checkNativeReleaseExecutables("manager-path", "helper-path", target, "1.6.0", commands)
				want := []string{"manager", "helper", "version"}
				if failed != "" {
					if !errors.Is(err, rejected) {
						t.Fatalf("signature failure lost: %v", err)
					}
					if _, err := os.Stat(marker); !os.IsNotExist(err) {
						t.Fatal("candidate ran before both signatures were authenticated")
					}
					want = []string{"manager", "helper"}
					if failed == "manager" {
						want = []string{"manager"}
					}
				} else if err != nil {
					t.Fatal(err)
				} else if _, err := os.Stat(marker); err != nil {
					t.Fatal("authenticated candidate was not executed")
				}
				if !reflect.DeepEqual(calls, want) {
					t.Fatalf("incorrect authentication/execution ordering: %v", calls)
				}
			})
		}
	}
}

func TestNativeReleaseRejectsVersionFailureAfterAuthentication(t *testing.T) {
	for _, result := range []struct {
		output string
		err    error
	}{{"OpenSocrates 1.5.0", nil}, {"OpenSocrates 1.6.0", errors.New("execution failed")}} {
		commands := nativeReleaseCommands{
			verifyManager: func(string, string) error { return nil },
			verifyHelper:  func(string, string) error { return nil },
			version:       func(string) ([]byte, error) { return []byte(result.output), result.err },
		}
		if err := checkNativeReleaseExecutables("manager", "helper", "darwin-arm64", "1.6.0", commands); err == nil {
			t.Fatal("invalid native version execution accepted")
		}
	}
}

func TestMacReleaseManagerAndHelperRejectUnsignedCode(t *testing.T) {
	if runtime.GOOS != "darwin" {
		t.Skip("requires native Apple code-signing tools")
	}
	root := filepath.Join(t.TempDir(), "private")
	if err := platform.Mkdir(root); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "unsigned")
	if err := platform.AtomicWrite(path, []byte("unsigned code"), 0755); err != nil {
		t.Fatal(err)
	}
	// Environment values may not supply or relax the embedded publisher policy.
	t.Setenv("OPENSOCRATES_DARWIN_TEAM_ID", "ABCDEFGHIJ")
	if err := verifyMacReleaseSignature(path); err == nil {
		t.Fatal("manager release gate accepted unsigned code")
	}
	if err := verifyHelperSignature(path, "darwin-arm64"); err == nil || err.Error() != "production helper signature required" {
		t.Fatalf("helper release gate did not fail closed: %v", err)
	}
	link := path + "-link"
	if err := os.Symlink(path, link); err != nil {
		t.Fatal(err)
	}
	if err := verifyMacReleaseSignature(link); err == nil {
		t.Fatal("release gate accepted an unowned indirection")
	}
}
