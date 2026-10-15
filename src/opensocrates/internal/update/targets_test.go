package update

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"path/filepath"
	"testing"
	"time"
)

func TestClosedNativeMetadataTargets(t *testing.T) {
	for _, row := range []struct{ os, arch, target string }{{"darwin", "arm64", "stable/darwin-arm64/opensocrates.archive"}, {"windows", "amd64", "stable/windows-amd64/opensocrates.archive"}, {"windows", "arm64", "stable/windows-arm64/opensocrates.archive"}} {
		target, e := MetadataTarget(row.os, row.arch)
		if e != nil || target != row.target {
			t.Fatal("signed native target differs")
		}
		goos, arch, ok := metadataPlatform(target)
		if !ok || goos != row.os || arch != row.arch {
			t.Fatal("metadata target identity differs")
		}
	}
	for _, pair := range [][2]string{{"windows", "386"}, {"darwin", "amd64"}, {"linux", "arm64"}} {
		if _, e := MetadataTarget(pair[0], pair[1]); e == nil {
			t.Fatal("unagreed metadata platform accepted")
		}
	}
	if _, _, ok := metadataPlatform("stable/windows-x64/opensocrates.archive"); ok {
		t.Fatal("asset alias changed retained signed amd64 target")
	}
}
func TestARM64UpdatePlatformOptInBoundary(t *testing.T) {
	dir, e := platform.MkdirTemp(t.TempDir(), "arm-policy-")
	if e != nil {
		t.Fatal(e)
	}
	engine := Engine{StateDir: dir, OS: "windows", Arch: "arm64", Version: "1.6.0"}
	receipt, e := engine.Run(context.Background(), true, false)
	if e != nil || receipt.Result != "disabled" {
		t.Fatal("ARM64 default scheduled policy is not disabled")
	}
	policy, e := engine.Policy()
	if e != nil || policy.Enabled {
		t.Fatal("ARM64 enabled updates without opt-in")
	}
}
func TestARM64CompatibilityRejectsX64SignedRelease(t *testing.T) {
	r := Release{Schema: "opensocrates.release/1.0.0", Version: "1.6.1", ContentRevision: "frozen", Channel: "stable", OS: "windows", Arch: "arm64", MinimumManager: "1.6.0", DataSchema: 1, Profiles: []string{"codex"}, PackagePath: "v1.6.1/arm64.zip"}
	if action, e := Compatible(r, "1.6.0", "windows", "arm64", true); e != nil || action != "apply" {
		t.Fatal("compatible ARM64 release rejected")
	}
	r.Arch = "amd64"
	if _, e := Compatible(r, "1.6.0", "windows", "arm64", true); e == nil {
		t.Fatal("x64 release delivered to ARM64 runtime")
	}
}
func TestARM64SignedTargetBinding(t *testing.T) {
	now := time.Now().UTC()
	root, signers := fixtureRoot(t)
	r := Release{Schema: "opensocrates.release/1.0.0", Version: "1.6.1", ContentRevision: "frozen", Channel: "stable", OS: "windows", Arch: "arm64", MinimumManager: "1.6.0", DataSchema: 1, Profiles: []string{"codex"}, PackagePath: "v1.6.1/arm64.zip"}
	archive := []byte("authenticated ARM64 archive")
	signed, e := SignRelease(SigningInputs{Root: root, Signers: signers, TargetsVersion: 1, SnapshotVersion: 1, TimestampVersion: 1, ExpiresTargets: now.Add(time.Hour), ExpiresSnapshot: now.Add(time.Hour), ExpiresTimestamp: now.Add(time.Hour), Targets: map[string]SignedArchive{"stable/windows-arm64/opensocrates.archive": {Release: r, Data: archive}}}, now)
	if e != nil {
		t.Fatal(e)
	}
	repo := armRepositoryFixture(root, signed, archive)
	dir, e := platform.MkdirTemp(t.TempDir(), "arm-trust-")
	if e != nil {
		t.Fatal(e)
	}
	candidate, e := repo.Fetch(context.Background(), filepath.Join(dir, "trust"), "stable/windows-arm64/opensocrates.archive")
	if e != nil || candidate.Release.Arch != "arm64" {
		t.Fatal("signed ARM64 metadata not selected")
	}
	// A valid signature cannot change the platform identity named by the target.
	r.Arch = "amd64"
	signed, e = SignRelease(SigningInputs{Root: root, Signers: signers, TargetsVersion: 1, SnapshotVersion: 1, TimestampVersion: 1, ExpiresTargets: now.Add(time.Hour), ExpiresSnapshot: now.Add(time.Hour), ExpiresTimestamp: now.Add(time.Hour), Targets: map[string]SignedArchive{"stable/windows-arm64/opensocrates.archive": {Release: r, Data: archive}}}, now)
	if e != nil {
		t.Fatal(e)
	}
	repo = armRepositoryFixture(root, signed, archive)
	dir, e = platform.MkdirTemp(t.TempDir(), "arm-mismatch-")
	if e != nil {
		t.Fatal(e)
	}
	if _, e = repo.Fetch(context.Background(), filepath.Join(dir, "trust"), "stable/windows-arm64/opensocrates.archive"); e == nil {
		t.Fatal("signed mismatched target platform accepted")
	}
}

func armRepositoryFixture(root []byte, out map[string][]byte, archive []byte) Repository {
	files := map[string][]byte{}
	for name, b := range out {
		files["https://metadata.example/"+name] = b
	}
	files["https://metadata.example/1.targets.json"] = out["targets.json"]
	files["https://metadata.example/1.snapshot.json"] = out["snapshot.json"]
	files["https://assets.example/v1.6.1/arm64.zip"] = archive
	return Repository{BootstrapRoot: root, MetadataURL: "https://metadata.example/", TargetsURL: "https://assets.example/", Fetcher: &memoryFetcher{files}}
}
