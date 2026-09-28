package main

import "database/sql"

func migrate(db *sql.DB) error {
	for _, stmt := range []string{
		`CREATE TABLE IF NOT EXISTS events (tenant TEXT NOT NULL, event_id TEXT NOT NULL, incident_id TEXT NOT NULL, sequence INTEGER NOT NULL, kind TEXT NOT NULL, occurred_at TEXT NOT NULL, severity TEXT NOT NULL, note TEXT NOT NULL, PRIMARY KEY(tenant,event_id))`,
		`CREATE TABLE IF NOT EXISTS incidents (tenant TEXT NOT NULL, incident_id TEXT NOT NULL, status TEXT NOT NULL, severity TEXT NOT NULL, latest_at TEXT NOT NULL, note TEXT NOT NULL, PRIMARY KEY(tenant,incident_id))`,
	} {
		if _, err := db.Exec(stmt); err != nil { return err }
	}
	return nil
}
