package platform

import (
	"path/filepath"
	"testing"
)

func TestPinnedDriverCanCreateSQLite(t *testing.T) {
	db, err := Open(filepath.Join(t.TempDir(), "generic.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var version string
	if err := db.QueryRow("SELECT sqlite_version()").Scan(&version); err != nil {
		t.Fatal(err)
	}
	if version == "" {
		t.Fatal("empty SQLite version")
	}
}
