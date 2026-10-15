//go:build !darwin && !linux

package compat

import "github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"

func systemTempDirectory() string          { return "" }
func existingOAuth(string) ([]byte, error) { return nil, failure(diagnostics.Unsupported) }
