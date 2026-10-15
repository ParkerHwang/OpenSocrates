// Package hosts describes distribution capabilities independently of runtime adapters.
package hosts

import (
	"runtime"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
)

type ID string
type Scope string
type Platform string

const (
	Codex         ID       = "codex"
	Claude        ID       = "claude"
	Antigravity   ID       = "antigravity"
	ClaudeAccount ID       = "claude-chat"
	Global        Scope    = "global"
	Workspace     Scope    = "workspace"
	Export        Scope    = "export"
	MacARM64      Platform = "darwin-arm64"
	WindowsX64    Platform = "windows-amd64"
	WindowsARM64  Platform = "windows-arm64"
)

type Profile struct {
	ID                 ID
	Platforms          []Platform
	Scopes             []Scope
	Commands           []string
	RuntimeAdapter     bool
	ContentOnly        bool
	ScheduledUpdates   bool
	TrustApproval      bool
	ActivationBoundary string
}

// Additional scheduled profiles require their own native activation qualification.
var profiles = []Profile{
	{Codex, []Platform{MacARM64, WindowsX64, WindowsARM64}, []Scope{Global}, []string{"install", "adopt", "update", "remove", "status", "diagnose"}, true, false, true, true, "fresh_session_or_host_reload"},
	{Claude, []Platform{MacARM64}, []Scope{Global}, []string{"install", "adopt", "update", "remove", "enable", "disable", "status", "diagnose"}, true, false, false, true, "fresh_session_or_host_reload"},
	{Antigravity, []Platform{MacARM64, WindowsX64, WindowsARM64}, []Scope{Global, Workspace}, []string{"install", "adopt", "update", "remove", "enable", "disable", "status", "diagnose"}, false, true, false, false, "fresh_session_or_host_reload"},
	{ClaudeAccount, []Platform{MacARM64, WindowsX64, WindowsARM64}, []Scope{Export}, []string{"verify", "export"}, false, true, false, false, "separate_account_upload_and_activation"},
}

func Get(id ID) (Profile, error) {
	for _, p := range profiles {
		if p.ID == id {
			p.Platforms = append([]Platform(nil), p.Platforms...)
			p.Scopes = append([]Scope(nil), p.Scopes...)
			p.Commands = append([]string(nil), p.Commands...)
			return p, nil
		}
	}
	return Profile{}, diagnostics.New(diagnostics.Unsupported, "distribution_profile")
}

// DistributionTarget preserves the released x64 asset spelling while Go and
// update metadata continue to use the native amd64 architecture identity.
func DistributionTarget(goos, goarch string) string {
	if goos == "windows" && goarch == "amd64" {
		return "windows-x64"
	}
	return goos + "-" + goarch
}
func ParseDistributionTarget(target string) (goos, goarch string, ok bool) {
	switch target {
	case "darwin-arm64":
		return "darwin", "arm64", true
	case "windows-x64":
		return "windows", "amd64", true
	case "windows-arm64":
		return "windows", "arm64", true
	default:
		return "", "", false
	}
}
func NativePlatformSupported(goos, goarch string) bool {
	_, _, ok := ParseDistributionTarget(DistributionTarget(goos, goarch))
	return ok
}

func CurrentPlatform() Platform { return Platform(runtime.GOOS + "-" + runtime.GOARCH) }

func (p Profile) Supports(platform Platform, scope Scope, command string) bool {
	foundPlatform, foundScope, foundCommand := false, false, false
	for _, v := range p.Platforms {
		foundPlatform = foundPlatform || v == platform
	}
	for _, v := range p.Scopes {
		foundScope = foundScope || v == scope
	}
	for _, v := range p.Commands {
		foundCommand = foundCommand || v == command
	}
	return foundPlatform && foundScope && foundCommand
}

// Expand preserves the legacy Codex-only meaning of --host all.
func Expand(value string) ([]ID, error) {
	if value == "all" {
		return []ID{Codex}, nil
	}
	p, err := Get(ID(value))
	if err != nil {
		return nil, err
	}
	return []ID{p.ID}, nil
}

// LegacyRuntimeAdapters is the closed retained selector registry. Native Claude
// entry and content transports do not implicitly become legacy selector adapters.
func LegacyRuntimeAdapters() []ID { return []ID{Codex} }
