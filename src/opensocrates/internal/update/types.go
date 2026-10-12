// Package update owns opt-in native update trust and policy. It is never called
// by hooks. Host mutation is delegated to the shared lifecycle transaction engine.
package update

import (
	"context"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"time"
)

const Interval = 24 * time.Hour
const LoginDelay = 5 * time.Minute
const MaxArchiveSize int64 = 256 << 20
const Owner = "opensocrates-native"
const StateSchema = "opensocrates.native-update/1.0.0"

type Policy struct {
	Schema           string    `json:"schema"`
	Enabled          bool      `json:"enabled"`
	Channel          string    `json:"channel"`
	Owner            string    `json:"owner"`
	Hosts            []string  `json:"hosts"`
	LastCheck        time.Time `json:"last_check,omitempty"`
	NextCheck        time.Time `json:"next_check,omitempty"`
	AvailableVersion string    `json:"available_version,omitempty"`
}

// Release is authenticated target custom metadata, not an unauthenticated feed.
type Release struct {
	Schema           string   `json:"schema"`
	Version          string   `json:"version"`
	ContentRevision  string   `json:"content_revision"`
	Channel          string   `json:"channel"`
	OS               string   `json:"os"`
	Arch             string   `json:"arch"`
	MinimumManager   string   `json:"minimum_manager"`
	DataSchema       int      `json:"data_schema"`
	MigrationVersion int      `json:"migration_version"`
	Profiles         []string `json:"profiles"`
	PackagePath      string   `json:"package_path"`
}
type Candidate struct {
	Release Release
	Archive string
}
type ApplyResult struct {
	Pending bool
	Version string
}
type Apply func(context.Context, Candidate) (ApplyResult, error)
type Receipt struct {
	Schema        string           `json:"schema"`
	Version       string           `json:"version,omitempty"`
	CheckedAt     time.Time        `json:"checked_at"`
	Host          string           `json:"host"`
	Scope         string           `json:"scope"`
	Phase         string           `json:"phase"`
	Result        string           `json:"result"`
	ErrorCategory diagnostics.Code `json:"error_category,omitempty"`
}

func closed(code diagnostics.Code, stage string) error { return diagnostics.New(code, stage) }
func strict(data []byte, target any) error {
	var fields map[string]json.RawMessage
	if json.Unmarshal(data, &fields) != nil {
		return closed(diagnostics.Verification, "metadata")
	}
	d := json.NewDecoder(bytesReader(data))
	d.DisallowUnknownFields()
	if d.Decode(target) != nil {
		return closed(diagnostics.Verification, "metadata")
	}
	return nil
}
