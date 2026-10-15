package devtools

import (
	"bytes"
	"fmt"
	"path/filepath"
)

// GenerateTrustConfig embeds exact public canonical input bytes. In particular,
// it never invents publisher IDs or treats an unapproved root as production.
func GenerateTrustConfig(root string) error {
	for _, name := range []string{"root.json", "identities.json"} {
		data, e := regularRead(root, "config/update/"+name)
		if e != nil {
			return e
		}
		if _, e = ReadObject(filepath.Join(root, "config/update", name)); e != nil {
			return e
		}
		if e = writeData(filepath.Join(root, "src/opensocrates/internal/update/trustconfig", name), data, 0644); e != nil {
			return e
		}
		actual, e := regularRead(root, "src/opensocrates/internal/update/trustconfig/"+name)
		if e != nil || !bytes.Equal(data, actual) {
			return fmt.Errorf("embedded trust copy differs from canonical input")
		}
	}
	return nil
}
