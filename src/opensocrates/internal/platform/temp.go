package platform

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"
)

func temporaryName(pattern string) (string, error) {
	if !utf8.ValidString(pattern) || len(pattern) > 200 || strings.ContainsAny(pattern, "/\\\x00") {
		return "", failure()
	}
	nonce := make([]byte, 16)
	if _, e := rand.Read(nonce); e != nil {
		return "", failure()
	}
	random := hex.EncodeToString(nonce)
	if star := strings.LastIndexByte(pattern, '*'); star >= 0 {
		return pattern[:star] + random + pattern[star+1:], nil
	}
	return pattern + random, nil
}
func temporaryBase(base string) (string, error) {
	if base == "" {
		base = os.TempDir()
	}
	return cleanPath(base)
}

// MkdirTemp creates only a new private directory, with owner identity and
// permissions established at creation. Existing directories are never adopted
// or normalized. It supports the final '*' substitution of os.MkdirTemp.
func MkdirTemp(base, pattern string) (string, error) {
	base, e := temporaryBase(base)
	if e != nil {
		return "", e
	}
	for attempt := 0; attempt < 128; attempt++ {
		name, e := temporaryName(pattern)
		if e != nil {
			return "", e
		}
		path := filepath.Join(base, name)
		e = mkdirExclusive(path)
		if errors.Is(e, os.ErrExist) {
			continue
		}
		if e != nil {
			return "", e
		}
		return path, nil
	}
	return "", failure()
}

// CreateTemp creates a current-user private file through a checked parent
// handle. The returned name is the actual local path for later safe export;
// callers must close the handle and use platform operations for activation.
func CreateTemp(base, pattern string) (*os.File, error) {
	base, e := temporaryBase(base)
	if e != nil {
		return nil, e
	}
	for attempt := 0; attempt < 128; attempt++ {
		name, e := temporaryName(pattern)
		if e != nil {
			return nil, e
		}
		f, e := createExclusiveTemp(filepath.Join(base, name))
		if errors.Is(e, os.ErrExist) {
			continue
		}
		if e != nil {
			return nil, e
		}
		return f, nil
	}
	return nil, failure()
}
