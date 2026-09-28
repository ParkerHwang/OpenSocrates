package platform

import (
	"database/sql"
	"testing"
)

func TestPinnedDriverAvailable(t *testing.T) {
	db, err := sql.Open(SQLiteDriver, ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var n int
	if err := db.QueryRow("SELECT 1").Scan(&n); err != nil || n != 1 {
		t.Fatalf("driver query: value=%d error=%v", n, err)
	}
}
