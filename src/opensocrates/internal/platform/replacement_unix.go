//go:build !windows

package platform

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
)

func waitOwnedProcess(ctx context.Context, pid int, target string) error {
	return diagnostics.New(diagnostics.Unsupported, "windows_replacement")
}
