package update

import (
	"bytes"
	"crypto"
	"crypto/ed25519"
	"crypto/x509"
	"encoding/pem"
	"flag"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update/trustconfig"
	"github.com/sigstore/sigstore/pkg/signature"
	"github.com/theupdateframework/go-tuf/v2/metadata"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type keyPaths []string

func (k *keyPaths) String() string     { return "external signing key files" }
func (k *keyPaths) Set(s string) error { *k = append(*k, s); return nil }

// MetadataCommand is release preparation only. It does not publish or tag.
// Private PEM files remain external and are never copied into the output.
func MetadataCommand(args []string) error {
	fs := flag.NewFlagSet("metadata-sign", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	rootPath := fs.String("root", "", "approved signed public root")
	mac := fs.String("macos-archive", "", "macOS archive")
	win := fs.String("windows-archive", "", "Windows archive")
	ver := fs.String("version", "", "product version")
	rev := fs.String("content-revision", "", "frozen content revision")
	out := fs.String("output", "dist", "public metadata output")
	site := fs.String("site-output", "", "metadata publication preparation output")
	previous := fs.String("previous-metadata", "", "authenticated prior publication metadata directory")
	initial := fs.Bool("initial-repository", false, "explicit first production repository initialization")
	tv := fs.Int64("targets-version", 0, "monotonic published version")
	sv := fs.Int64("snapshot-version", 0, "monotonic published version")
	tsv := fs.Int64("timestamp-version", 0, "monotonic published version")
	var tk, sk, tsk keyPaths
	fs.Var(&tk, "targets-key", "external PKCS8 private PEM")
	fs.Var(&sk, "snapshot-key", "external PKCS8 private PEM")
	fs.Var(&tsk, "timestamp-key", "external PKCS8 private PEM")
	if fs.Parse(args) != nil || fs.NArg() != 0 || *rootPath == "" || *mac == "" || *win == "" || *rev == "" {
		return closed(diagnostics.Verification, "signing_arguments")
	}
	if _, ok := version(*ver); !ok {
		return closed(diagnostics.Verification, "signing_arguments")
	}
	*ver = strings.TrimPrefix(*ver, "v")
	now := time.Now().UTC()
	root, e := readReleaseInput(*rootPath, 512<<10)
	if e != nil {
		return e
	}
	// The release builder must use the exact checked-in anchor compiled into
	// installers. A random CLI argument cannot establish installer trust.
	built, e := readReleaseInput("config/update/root.json", 512<<10)
	if e != nil || !bytes.Equal(bytes.TrimSpace(built), bytes.TrimSpace(root)) || !bytes.Equal(bytes.TrimSpace(trustconfig.Root()), bytes.TrimSpace(root)) {
		return closed(diagnostics.Verification, "installer_root_mismatch")
	}
	in := SigningInputs{Root: root, TargetsVersion: *tv, SnapshotVersion: *sv, TimestampVersion: *tsv, ExpiresTargets: now.Add(90 * 24 * time.Hour), ExpiresSnapshot: now.Add(7 * 24 * time.Hour), ExpiresTimestamp: now.Add(48 * time.Hour), Targets: map[string]SignedArchive{}, Signers: map[string][]signature.Signer{}}
	for _, k := range []struct {
		role  string
		paths keyPaths
	}{{metadata.TARGETS, tk}, {metadata.SNAPSHOT, sk}, {metadata.TIMESTAMP, tsk}} {
		for _, p := range k.paths {
			s, err := loadSigningKey(p)
			if err != nil {
				return err
			}
			in.Signers[k.role] = append(in.Signers[k.role], s)
		}
	}
	for _, a := range []struct{ os, arch, path string }{{"darwin", "arm64", *mac}, {"windows", "amd64", *win}} {
		b, err := readReleaseInput(a.path, MaxArchiveSize)
		if err != nil {
			return err
		}
		rel := Release{Schema: "opensocrates.release/1.0.0", Version: *ver, ContentRevision: *rev, Channel: "stable", OS: a.os, Arch: a.arch, MinimumManager: "1.6.0", DataSchema: 1, MigrationVersion: 0, Profiles: []string{"codex"}, PackagePath: "v" + *ver + "/" + filepath.Base(a.path)}
		in.Targets["stable/"+a.os+"-"+a.arch+"/opensocrates.archive"] = SignedArchive{Release: rel, Data: b}
	}
	if *initial {
		if *tv != 1 || *sv != 1 || *tsv != 1 {
			return closed(diagnostics.Verification, "signing_versions")
		}
	} else {
		if *previous == "" {
			return closed(diagnostics.Verification, "previous_metadata_required")
		}
		if err := VerifyPreviousPublication(root, *previous, *tv, *sv, *tsv); err != nil {
			return err
		}
	}
	signed, e := SignRelease(in, now)
	if e != nil {
		return e
	}
	if *previous != "" {
		history, err := os.ReadDir(*previous)
		if err == nil {
			for _, file := range history {
				if file.IsDir() {
					continue
				}
				name := file.Name()
				if strings.HasSuffix(name, ".root.json") {
					n := strings.TrimSuffix(name, ".root.json")
					if _, err = strconv.ParseInt(n, 10, 64); err != nil {
						return closed(diagnostics.Verification, "root_history")
					}
					b, err := readReleaseInput(filepath.Join(*previous, name), 512<<10)
					if err != nil {
						return err
					}
					historyRoot, err := metadata.Root().FromBytes(b)
					if err != nil || historyRoot.Signed.Version < 1 || strconv.FormatInt(historyRoot.Signed.Version, 10) != n || historyRoot.VerifyDelegate(metadata.ROOT, historyRoot) != nil {
						return closed(diagnostics.Verification, "root_history")
					}
					approved, _ := metadata.Root().FromBytes(root)
					if historyRoot.Signed.Version > approved.Signed.Version {
						return closed(diagnostics.Verification, "root_history")
					}
					signed[name] = b
				}
			}
		}
	}
	dirs := []string{*out}
	if *site != "" {
		dirs = append(dirs, *site)
	}
	r, _ := metadata.Root().FromBytes(root)
	for _, dir := range dirs {
		if e = os.MkdirAll(dir, 0755); e != nil {
			return closed(diagnostics.Permission, "signing_output")
		}
		for name, b := range signed {
			if e = os.WriteFile(filepath.Join(dir, name), b, 0644); e != nil {
				return closed(diagnostics.Permission, "signing_output")
			}
		}
		for name, b := range map[string][]byte{strconv.FormatInt(*tv, 10) + ".targets.json": signed["targets.json"], strconv.FormatInt(*sv, 10) + ".snapshot.json": signed["snapshot.json"], strconv.FormatInt(r.Signed.Version, 10) + ".root.json": root} {
			if e = os.WriteFile(filepath.Join(dir, name), b, 0644); e != nil {
				return closed(diagnostics.Permission, "signing_output")
			}
		}
	}
	return nil
}
func RootRotationCommand(args []string) error {
	fs := flag.NewFlagSet("metadata-root-rotate", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	before := fs.String("root", "", "previous signed root")
	after := fs.String("next-root", "", "next root signed by both thresholds")
	out := fs.String("output", "dist", "public output")
	if fs.Parse(args) != nil || fs.NArg() != 0 || *before == "" || *after == "" {
		return closed(diagnostics.Verification, "root_rotation")
	}
	old, e := readReleaseInput(*before, 512<<10)
	if e != nil {
		return e
	}
	next, e := readReleaseInput(*after, 512<<10)
	if e != nil {
		return e
	}
	if VerifyRootRotation(old, next) != nil || ValidateProductionRoot(next, time.Now().UTC()) != nil {
		return closed(diagnostics.Verification, "root_rotation")
	}
	r, _ := metadata.Root().FromBytes(next)
	if os.MkdirAll(*out, 0755) != nil {
		return closed(diagnostics.Permission, "signing_output")
	}
	if os.WriteFile(filepath.Join(*out, strconv.FormatInt(r.Signed.Version, 10)+".root.json"), next, 0644) != nil {
		return closed(diagnostics.Permission, "signing_output")
	}
	return nil
}
func readReleaseInput(path string, max int64) ([]byte, error) {
	f, e := os.Open(path)
	if e != nil {
		return nil, closed(diagnostics.Verification, "signing_input")
	}
	defer f.Close()
	b, e := io.ReadAll(io.LimitReader(f, max+1))
	if e != nil || int64(len(b)) > max {
		return nil, closed(diagnostics.Verification, "signing_input")
	}
	return b, nil
}
func loadSigningKey(path string) (signature.Signer, error) {
	b, e := readReleaseInput(path, 64<<10)
	if e != nil {
		return nil, e
	}
	block, rest := pem.Decode(b)
	if block == nil || len(bytes.TrimSpace(rest)) != 0 {
		return nil, closed(diagnostics.Verification, "signing_key")
	}
	key, e := x509.ParsePKCS8PrivateKey(block.Bytes)
	if e != nil {
		return nil, closed(diagnostics.Verification, "signing_key")
	}
	hash := crypto.SHA256
	if _, ok := key.(ed25519.PrivateKey); ok {
		hash = crypto.Hash(0)
	}
	signer, e := signature.LoadSigner(key, hash)
	if e != nil {
		return nil, closed(diagnostics.Verification, "signing_key")
	}
	return signer, nil
}

// VerifyPreviousPublication requires all previous role signatures and parent
// bindings before allocating strictly higher versions. Release operators retain
// this public metadata in protected release state; never infer from filenames.
func VerifyPreviousPublication(rootData []byte, dir string, tv, sv, tsv int64) error {
	root, e := metadata.Root().FromBytes(rootData)
	if e != nil {
		return closed(diagnostics.Verification, "previous_metadata")
	}
	targetData, e := readReleaseInput(filepath.Join(dir, "targets.json"), 5<<20)
	if e != nil {
		return e
	}
	snapshotData, e := readReleaseInput(filepath.Join(dir, "snapshot.json"), 2<<20)
	if e != nil {
		return e
	}
	timestampData, e := readReleaseInput(filepath.Join(dir, "timestamp.json"), 16<<10)
	if e != nil {
		return e
	}
	target, e := metadata.Targets().FromBytes(targetData)
	if e != nil || root.VerifyDelegate(metadata.TARGETS, target) != nil {
		return closed(diagnostics.Verification, "previous_metadata")
	}
	snapshot, e := metadata.Snapshot().FromBytes(snapshotData)
	if e != nil || root.VerifyDelegate(metadata.SNAPSHOT, snapshot) != nil {
		return closed(diagnostics.Verification, "previous_metadata")
	}
	timestamp, e := metadata.Timestamp().FromBytes(timestampData)
	if e != nil || root.VerifyDelegate(metadata.TIMESTAMP, timestamp) != nil {
		return closed(diagnostics.Verification, "previous_metadata")
	}
	tm := snapshot.Signed.Meta["targets.json"]
	sm := timestamp.Signed.Meta["snapshot.json"]
	if tm == nil || sm == nil || tm.Version != target.Signed.Version || sm.Version != snapshot.Signed.Version || tm.VerifyLengthHashes(targetData) != nil || sm.VerifyLengthHashes(snapshotData) != nil || tv <= target.Signed.Version || sv <= snapshot.Signed.Version || tsv <= timestamp.Signed.Version {
		return closed(diagnostics.Verification, "signing_versions")
	}
	return nil
}
