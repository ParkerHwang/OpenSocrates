// Package trustconfig embeds generated copies of the canonical public trust
// data in config/update. The Go generator verifies exact byte equivalence.
package trustconfig

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"errors"
)

//go:embed root.json
var root []byte

//go:embed identities.json
var identities []byte

type Identity struct {
	MetadataURL              string `json:"metadata_url"`
	TargetsURL               string `json:"targets_url"`
	DarwinTeamID             string `json:"darwin_team_id"`
	WindowsCertificateSHA256 string `json:"windows_certificate_sha256"`
}

// Root returns a copy so callers cannot change the compiled trust anchor.
func Root() []byte { return append([]byte(nil), root...) }

func Load() (Identity, error) {
	var value Identity
	decoder := json.NewDecoder(bytes.NewReader(identities))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&value) != nil || value.MetadataURL == "" || value.TargetsURL == "" {
		return Identity{}, errors.New("embedded update identities unavailable")
	}
	return value, nil
}
