// Package registration isolates external host registration from file transactions.
package registration

import "context"

type State struct {
	Root       string            `json:"root"`
	Registered bool              `json:"registered"`
	Installed  bool              `json:"installed"`
	Enabled    bool              `json:"enabled"`
	Version    string            `json:"version,omitempty"`
	Data       map[string]string `json:"data,omitempty"`
}

// Adapter only touches the exact managed identity, and never grants hook trust.
type Adapter interface {
	Inspect(context.Context, string) (State, error)
	Replace(context.Context, State, State) error
	Verify(context.Context, State) error
}
type Change struct {
	Host   string `json:"host"`
	Before State  `json:"before"`
	After  State  `json:"after"`
}
