package update

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/theupdateframework/go-tuf/v2/metadata"
	"github.com/theupdateframework/go-tuf/v2/metadata/config"
	"github.com/theupdateframework/go-tuf/v2/metadata/fetcher"
	"github.com/theupdateframework/go-tuf/v2/metadata/updater"
	"os"
	"path/filepath"
	"strings"
)

const trustSchema = "opensocrates.tuf-trust/1.0.0"

type trustState struct {
	Schema string                     `json:"schema"`
	Roles  map[string]json.RawMessage `json:"roles"`
}
type Repository struct {
	BootstrapRoot           []byte
	MetadataURL, TargetsURL string
	AllowedHosts            []string
	Fetcher                 fetcher.Fetcher
}

// Fetch authenticates all metadata against installer-provided trust, persists
// accepted monotonic trust before returning an executable target, and checks
// target length and every signed hash. Runtime rollback never reverts trust.
func (r Repository) Fetch(ctx context.Context, stateDir, target string) (Candidate, error) {
	var none Candidate
	if !validTarget(target) {
		return none, closed(diagnostics.Verification, "target")
	}
	anchor, e := metadata.Root().FromBytes(r.BootstrapRoot)
	if e != nil || anchor.Signed.Version < 1 {
		return none, closed(diagnostics.HostUnavailable, "trust_root")
	}
	if e = anchor.VerifyDelegate(metadata.ROOT, anchor); e != nil {
		return none, closed(diagnostics.Verification, "trust_root")
	}
	if e = platform.Mkdir(stateDir); e != nil {
		return none, e
	}
	lock, e := platform.Lock(filepath.Join(stateDir, "trust.lock"))
	if e != nil {
		return none, e
	}
	defer lock.Close()
	envelope := filepath.Join(stateDir, "trust.json")
	persisted := trustState{Schema: trustSchema, Roles: map[string]json.RawMessage{"root": r.BootstrapRoot}}
	b, e := platform.ReadFile(envelope, 12<<20)
	if e == nil {
		if strict(b, &persisted) != nil || persisted.Schema != trustSchema || len(persisted.Roles["root"]) == 0 {
			return none, closed(diagnostics.Verification, "trust_state")
		}
	} else if _, err := os.Lstat(envelope); !os.IsNotExist(err) {
		return none, e
	}
	root, e := metadata.Root().FromBytes(persisted.Roles["root"])
	if e != nil || root.Signed.Version < anchor.Signed.Version {
		return none, closed(diagnostics.Verification, "trust_state")
	}
	// Cache is disposable; trusted role bytes live only in the atomic envelope.
	scratch, e := os.MkdirTemp(stateDir, "tuf-")
	if e != nil {
		return none, closed(diagnostics.Permission, "trust_state")
	}
	defer os.RemoveAll(scratch)
	for role, data := range persisted.Roles {
		if !validRole(role) {
			return none, closed(diagnostics.Verification, "trust_state")
		}
		if e = platform.AtomicWrite(filepath.Join(scratch, role+".json"), data, 0600); e != nil {
			return none, e
		}
	}
	cfg, e := config.New(r.MetadataURL, persisted.Roles["root"])
	if e != nil {
		return none, closed(diagnostics.Verification, "repository")
	}
	cfg.LocalMetadataDir = scratch
	cfg.LocalTargetsDir = filepath.Join(scratch, "targets")
	cfg.RemoteTargetsURL = r.TargetsURL
	cfg.PrefixTargetsWithHash = false // Immutable GitHub Release asset names; signed hashes still mandatory.
	cfg.MaxRootRotations = 32
	cfg.MaxDelegations = 8
	cfg.RootMaxLength = 512 << 10
	cfg.TimestampMaxLength = 16 << 10
	cfg.SnapshotMaxLength = 2 << 20
	cfg.TargetsMaxLength = 5 << 20
	cfg.Fetcher = &Transport{Context: ctx, AllowedHosts: r.AllowedHosts}
	if r.Fetcher != nil {
		cfg.Fetcher = r.Fetcher
	} // Injected transport is for offline tests; production factory never sets it.
	u, e := updater.New(cfg)
	if e != nil {
		return none, closed(diagnostics.Verification, "trust_root")
	}
	e = u.Refresh()
	// Persist even the accepted portion of a failed refresh. In particular root
	// key rotation must survive failed timestamp/target downloads and power loss.
	persist := func() error {
		trusted := u.GetTrustedMetadataSet()
		if trusted.Root != nil {
			data, err := trusted.Root.ToBytes(false)
			if err != nil {
				return err
			}
			persisted.Roles["root"] = data
		}
		if trusted.Timestamp != nil {
			data, err := trusted.Timestamp.ToBytes(false)
			if err != nil {
				return err
			}
			persisted.Roles["timestamp"] = data
		}
		if trusted.Snapshot != nil {
			data, err := trusted.Snapshot.ToBytes(false)
			if err != nil {
				return err
			}
			persisted.Roles["snapshot"] = data
		}
		for name, m := range trusted.Targets {
			if !validRole(name) {
				return closed(diagnostics.Verification, "trust_state")
			}
			data, err := m.ToBytes(false)
			if err != nil {
				return err
			}
			persisted.Roles[name] = data
		}
		data, err := json.Marshal(persisted)
		if err != nil {
			return err
		}
		return platform.AtomicWrite(envelope, append(data, '\n'), 0600)
	}
	if err := persist(); err != nil {
		return none, closed(diagnostics.Permission, "trust_persist")
	}
	if e != nil {
		var network *metadata.ErrDownloadHTTP
		if errors.As(e, &network) {
			return none, closed(diagnostics.Network, "metadata")
		}
		var d *diagnostics.Error
		if errors.As(e, &d) {
			return none, d
		}
		return none, closed(diagnostics.Verification, "metadata")
	}
	info, e := u.GetTargetInfo(target)
	if e != nil {
		return none, closed(diagnostics.Verification, "target")
	}
	if e = persist(); e != nil {
		return none, closed(diagnostics.Permission, "trust_persist")
	}
	if info.Custom == nil || info.Length <= 0 || info.Length > MaxArchiveSize || len(info.Hashes["sha256"]) != 32 {
		return none, closed(diagnostics.Verification, "target")
	}
	var rel Release
	if strict(*info.Custom, &rel) != nil || rel.Schema != "opensocrates.release/1.0.0" || !validTarget(rel.PackagePath) {
		return none, closed(diagnostics.Verification, "release")
	}
	// Disable library target persistence: write through protected native API.
	cfg.DisableLocalCache = true
	info.Path = rel.PackagePath
	_, data, e := u.DownloadTarget(info, "", "")
	if e != nil {
		return none, closed(diagnostics.Verification, "target_download")
	}
	archive := filepath.Join(stateDir, "candidate-"+hex.EncodeToString(info.Hashes["sha256"])+".archive")
	if !safeID(rel.OS) || !safeID(rel.Arch) {
		return none, closed(diagnostics.Verification, "release")
	}
	if existing, err := platform.ReadFile(archive, MaxArchiveSize); err == nil {
		if info.VerifyLengthHashes(existing) != nil {
			return none, closed(diagnostics.Verification, "candidate_modified")
		}
	} else {
		if _, stat := os.Lstat(archive); !os.IsNotExist(stat) {
			return none, err
		}
		if e = platform.AtomicWrite(archive, data, 0600); e != nil {
			return none, e
		}
	}
	return Candidate{Release: rel, Archive: archive}, nil
}
func validRole(s string) bool { return safeID(s) && len(s) <= 128 }
func safeID(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '-' || c == '_') {
			return false
		}
	}
	return true
}
func validTarget(s string) bool {
	if s == "" || strings.HasPrefix(s, "/") || strings.ContainsAny(s, "\\\x00?#:") {
		return false
	}
	for _, p := range strings.Split(s, "/") {
		if p == "" || p == "." || p == ".." {
			return false
		}
	}
	return true
}
