package update

import (
	"crypto/sha256"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/sigstore/sigstore/pkg/signature"
	"github.com/theupdateframework/go-tuf/v2/metadata"
	"time"
)

// SigningInputs contains public release metadata plus external signing handles.
// The caller obtains credentials from its release environment. No private key
// bytes are serialized to metadata, bundles, receipts, or repository state.
type SigningInputs struct {
	Root                                              []byte
	TargetsVersion, SnapshotVersion, TimestampVersion int64
	ExpiresTargets, ExpiresSnapshot, ExpiresTimestamp time.Time
	Targets                                           map[string]SignedArchive
	Signers                                           map[string][]signature.Signer
}
type SignedArchive struct {
	Release Release
	Data    []byte
}

// ValidateProductionRoot is the production gate. Empty preparation trust,
// unsigned roots, expired roots and shared offline/online key identities fail.
func ValidateProductionRoot(data []byte, now time.Time) error {
	root, e := metadata.Root().FromBytes(data)
	if e != nil {
		return closed(diagnostics.Verification, "production_root")
	}
	if root.Signed.Version < 1 || !root.Signed.Expires.After(now.Add(30*24*time.Hour)) || !root.Signed.ConsistentSnapshot {
		return closed(diagnostics.Verification, "production_root")
	}
	if root.VerifyDelegate(metadata.ROOT, root) != nil {
		return closed(diagnostics.Verification, "production_root")
	}
	rootRole := root.Signed.Roles[metadata.ROOT]
	if rootRole == nil || rootRole.Threshold < 2 {
		return closed(diagnostics.Verification, "production_root")
	}
	offline := map[string]bool{}
	for _, id := range rootRole.KeyIDs {
		offline[id] = true
	}
	for _, name := range []string{metadata.TARGETS, metadata.SNAPSHOT, metadata.TIMESTAMP} {
		role := root.Signed.Roles[name]
		if role == nil || role.Threshold < 1 || len(role.KeyIDs) < role.Threshold {
			return closed(diagnostics.Verification, "production_root")
		}
		for _, id := range role.KeyIDs {
			if offline[id] || root.Signed.Keys[id] == nil {
				return closed(diagnostics.Verification, "production_root")
			}
		}
	}
	return nil
}

// SignRelease builds the complete signed TUF top-level set. Versions must be
// allocated by the release owner above the previous published versions. The
// caller publishes consistent versioned snapshot/targets names atomically.
func SignRelease(in SigningInputs, now time.Time) (map[string][]byte, error) {
	if ValidateProductionRoot(in.Root, now) != nil {
		return nil, closed(diagnostics.Verification, "production_root")
	}
	if in.TargetsVersion < 1 || in.SnapshotVersion < 1 || in.TimestampVersion < 1 || len(in.Targets) == 0 {
		return nil, closed(diagnostics.Verification, "signing")
	}
	for _, expiry := range []time.Time{in.ExpiresTargets, in.ExpiresSnapshot, in.ExpiresTimestamp} {
		if !expiry.After(now) || expiry.After(now.Add(366*24*time.Hour)) {
			return nil, closed(diagnostics.Verification, "signing_expiry")
		}
	}
	root, _ := metadata.Root().FromBytes(in.Root)
	targets := metadata.Targets(in.ExpiresTargets)
	targets.Signed.Version = in.TargetsVersion
	for name, a := range in.Targets {
		if !validTarget(name) || !validTarget(a.Release.PackagePath) || len(a.Data) == 0 || int64(len(a.Data)) > MaxArchiveSize {
			return nil, closed(diagnostics.Verification, "signing_target")
		}
		if a.Release.Schema != "opensocrates.release/1.0.0" || a.Release.Channel != "stable" {
			return nil, closed(diagnostics.Verification, "signing_target")
		}
		custom, e := json.Marshal(a.Release)
		if e != nil {
			return nil, closed(diagnostics.Verification, "signing_target")
		}
		file, e := metadata.TargetFile().FromBytes(name, a.Data, "sha256")
		if e != nil {
			return nil, closed(diagnostics.Verification, "signing_target")
		}
		raw := json.RawMessage(custom)
		file.Custom = &raw
		targets.Signed.Targets[name] = file
	}
	for _, s := range in.Signers[metadata.TARGETS] {
		if _, e := targets.Sign(s); e != nil {
			return nil, closed(diagnostics.Verification, "signing")
		}
	}
	if root.VerifyDelegate(metadata.TARGETS, targets) != nil {
		return nil, closed(diagnostics.Verification, "signing_threshold")
	}
	targetData, e := targets.ToBytes(false)
	if e != nil {
		return nil, e
	}
	snapshot := metadata.Snapshot(in.ExpiresSnapshot)
	snapshot.Signed.Version = in.SnapshotVersion
	snapshot.Signed.Meta["targets.json"] = metaFile(in.TargetsVersion, targetData)
	for _, s := range in.Signers[metadata.SNAPSHOT] {
		if _, e := snapshot.Sign(s); e != nil {
			return nil, closed(diagnostics.Verification, "signing")
		}
	}
	if root.VerifyDelegate(metadata.SNAPSHOT, snapshot) != nil {
		return nil, closed(diagnostics.Verification, "signing_threshold")
	}
	snapshotData, e := snapshot.ToBytes(false)
	if e != nil {
		return nil, e
	}
	timestamp := metadata.Timestamp(in.ExpiresTimestamp)
	timestamp.Signed.Version = in.TimestampVersion
	timestamp.Signed.Meta["snapshot.json"] = metaFile(in.SnapshotVersion, snapshotData)
	for _, s := range in.Signers[metadata.TIMESTAMP] {
		if _, e := timestamp.Sign(s); e != nil {
			return nil, closed(diagnostics.Verification, "signing")
		}
	}
	if root.VerifyDelegate(metadata.TIMESTAMP, timestamp) != nil {
		return nil, closed(diagnostics.Verification, "signing_threshold")
	}
	timestampData, e := timestamp.ToBytes(false)
	if e != nil {
		return nil, e
	}
	return map[string][]byte{"root.json": in.Root, "targets.json": targetData, "snapshot.json": snapshotData, "timestamp.json": timestampData}, nil
}
func metaFile(v int64, b []byte) *metadata.MetaFiles {
	h := sha256.Sum256(b)
	return &metadata.MetaFiles{Version: v, Length: int64(len(b)), Hashes: metadata.Hashes{"sha256": h[:]}}
}

// VerifyRootRotation requires both old and new root thresholds and exactly one
// version increment. Release signing can use it before publishing N+1.root.json.
func VerifyRootRotation(before, after []byte) error {
	old, e := metadata.Root().FromBytes(before)
	if e != nil {
		return closed(diagnostics.Verification, "root_rotation")
	}
	next, e := metadata.Root().FromBytes(after)
	if e != nil || next.Signed.Version != old.Signed.Version+1 {
		return closed(diagnostics.Verification, "root_rotation")
	}
	if old.VerifyDelegate(metadata.ROOT, next) != nil || next.VerifyDelegate(metadata.ROOT, next) != nil {
		return closed(diagnostics.Verification, "root_rotation")
	}
	return nil
}
