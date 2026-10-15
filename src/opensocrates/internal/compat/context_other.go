//go:build !darwin && !linux

package compat

import "os"

// This is the pre-existing legacy POSIX context boundary, not a restriction on
// the native decision path or other Windows integrations.
func contextAvailable() bool                                      { return false }
func openExactContext(string, bool) (*os.File, error)             { return nil, os.ErrPermission }
func openBeneathContext(string, []string, bool) (*os.File, error) { return nil, os.ErrPermission }
