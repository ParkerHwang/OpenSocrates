// Package platform registers the common pinned SQLite driver. It supplies no queue logic.
package platform

import _ "modernc.org/sqlite"

const SQLiteDriver = "sqlite"
