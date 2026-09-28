package ledger

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

type API struct{ store *Store }

func NewAPI(store *Store) *API { return &API{store: store} }

func (a *API) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	p := r.URL.Path
	if p == "/health" {
		if r.Method != http.MethodGet {
			writeError(w, &APIError{Status: 405, Code: "not_found"})
			return
		}
		var version int
		if err := a.store.read.QueryRowContext(r.Context(), "PRAGMA user_version").Scan(&version); err != nil || version != 2 {
			writeError(w, &APIError{Status: 503, Code: "unavailable"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"ok": true})
		return
	}

	switch {
	case p == "/accounts" && r.Method == http.MethodPost:
		a.mutate(w, r, createAccount)
		return
	case p == "/transfers" && r.Method == http.MethodPost:
		a.mutate(w, r, postTransfer)
		return
	case p == "/batches" && r.Method == http.MethodPost:
		a.mutate(w, r, postBatch)
		return
	case p == "/holds" && r.Method == http.MethodPost:
		a.mutate(w, r, createHold)
		return
	case p == "/entries" && r.Method == http.MethodGet:
		a.getEntries(w, r)
		return
	case p == "/summary" && r.Method == http.MethodGet:
		a.getSummary(w, r)
		return
	case strings.HasPrefix(p, "/accounts/"):
		name := strings.TrimPrefix(p, "/accounts/")
		if name != "" && !strings.Contains(name, "/") {
			if r.Method != http.MethodGet {
				writeError(w, &APIError{Status: 405, Code: "not_found"})
				return
			}
			a.getAccount(w, r, name)
			return
		}
	case strings.HasPrefix(p, "/holds/"):
		parts := strings.Split(strings.TrimPrefix(p, "/holds/"), "/")
		if len(parts) == 2 && parts[0] != "" && (parts[1] == "capture" || parts[1] == "release") {
			if r.Method != http.MethodPost {
				writeError(w, &APIError{Status: 405, Code: "not_found"})
				return
			}
			if parts[1] == "capture" {
				a.mutate(w, r, func(ctx context.Context, tx *sql.Tx, tenant string, raw []byte) (int, any, error) {
					return captureHold(ctx, tx, tenant, parts[0], raw)
				})
			} else {
				a.mutate(w, r, func(ctx context.Context, tx *sql.Tx, tenant string, raw []byte) (int, any, error) {
					return releaseHold(ctx, tx, tenant, parts[0], raw)
				})
			}
			return
		}
	case strings.HasPrefix(p, "/transfers/"):
		parts := strings.Split(strings.TrimPrefix(p, "/transfers/"), "/")
		if len(parts) == 2 && parts[0] != "" && parts[1] == "reverse" {
			if r.Method != http.MethodPost {
				writeError(w, &APIError{Status: 405, Code: "not_found"})
				return
			}
			a.mutate(w, r, func(ctx context.Context, tx *sql.Tx, tenant string, raw []byte) (int, any, error) {
				return reverseTransfer(ctx, tx, tenant, parts[0], raw)
			})
			return
		}
	}
	writeError(w, missing())
}

type mutation func(context.Context, *sql.Tx, string, []byte) (int, any, error)

func (a *API) mutate(w http.ResponseWriter, r *http.Request, apply mutation) {
	tenant := r.Header.Get("X-Tenant")
	key := r.Header.Get("Idempotency-Key")
	if !validName(tenant) || !keyPattern.MatchString(key) {
		writeError(w, invalid())
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	raw, err := io.ReadAll(r.Body)
	if err != nil {
		writeError(w, invalid())
		return
	}
	canonical, err := canonicalBody(raw)
	if err != nil {
		writeError(w, invalid())
		return
	}
	tx, err := a.store.write.BeginTx(r.Context(), nil)
	if err != nil {
		writeInternal(w)
		return
	}
	defer tx.Rollback()
	var oldPath, oldBody string
	var oldStatus int
	var oldResult []byte
	err = tx.QueryRowContext(r.Context(), `SELECT path,body,status,result FROM idempotency WHERE tenant=? AND key=?`, tenant, key).
		Scan(&oldPath, &oldBody, &oldStatus, &oldResult)
	if err == nil {
		_ = tx.Rollback()
		if oldPath != r.URL.Path || oldBody != canonical {
			writeError(w, conflict("idempotency_conflict"))
			return
		}
		writeRawJSON(w, oldStatus, oldResult)
		return
	}
	if !errors.Is(err, sql.ErrNoRows) {
		writeInternal(w)
		return
	}
	status, value, applyErr := apply(r.Context(), tx, tenant, raw)
	if applyErr != nil {
		var apiErr *APIError
		if errors.As(applyErr, &apiErr) {
			writeError(w, apiErr)
		} else {
			writeInternal(w)
		}
		return
	}
	result, err := json.Marshal(value)
	if err != nil {
		writeInternal(w)
		return
	}
	if _, err := tx.ExecContext(r.Context(), `INSERT INTO idempotency(tenant,key,path,body,status,result) VALUES(?,?,?,?,?,?)`,
		tenant, key, r.URL.Path, canonical, status, result); err != nil {
		writeInternal(w)
		return
	}
	if err := tx.Commit(); err != nil {
		writeInternal(w)
		return
	}
	writeRawJSON(w, status, result)
}

func (a *API) tenant(r *http.Request) (string, *APIError) {
	tenant := r.Header.Get("X-Tenant")
	if !validName(tenant) {
		return "", invalid()
	}
	return tenant, nil
}

func (a *API) getAccount(w http.ResponseWriter, r *http.Request, name string) {
	tenant, apiErr := a.tenant(r)
	if apiErr != nil {
		writeError(w, apiErr)
		return
	}
	if !validName(name) {
		writeError(w, invalid())
		return
	}
	acct, err := loadAccount(r.Context(), a.store.read, tenant, name)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			writeError(w, missing())
		} else {
			writeInternal(w)
		}
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"account": acct})
}

func parseQuery(raw string, allowed map[string]bool) (url.Values, bool) {
	values, err := url.ParseQuery(raw)
	if err != nil {
		return nil, false
	}
	for key, list := range values {
		if !allowed[key] || len(list) != 1 {
			return nil, false
		}
	}
	return values, true
}

func nonnegativeQuery(values url.Values, name string, fallback int64) (int64, bool) {
	list, exists := values[name]
	if !exists {
		return fallback, true
	}
	if list[0] == "" {
		return 0, false
	}
	for _, c := range list[0] {
		if c < '0' || c > '9' {
			return 0, false
		}
	}
	value, err := strconv.ParseInt(list[0], 10, 64)
	return value, err == nil
}

func (a *API) getEntries(w http.ResponseWriter, r *http.Request) {
	tenant, apiErr := a.tenant(r)
	if apiErr != nil {
		writeError(w, apiErr)
		return
	}
	q, ok := parseQuery(r.URL.RawQuery, map[string]bool{"after": true, "limit": true, "snapshot": true})
	if !ok {
		writeError(w, invalid())
		return
	}
	after, ok := nonnegativeQuery(q, "after", 0)
	if !ok {
		writeError(w, invalid())
		return
	}
	limit64, ok := nonnegativeQuery(q, "limit", 50)
	if !ok || limit64 < 1 || limit64 > 100 {
		writeError(w, invalid())
		return
	}
	tx, err := a.store.read.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
	if err != nil {
		writeInternal(w)
		return
	}
	defer tx.Rollback()
	maxSeq, err := maxSequence(r.Context(), tx, tenant)
	if err != nil {
		writeInternal(w)
		return
	}
	snapshot, ok := nonnegativeQuery(q, "snapshot", maxSeq)
	if !ok || snapshot > maxSeq || after > snapshot {
		writeError(w, invalid())
		return
	}
	rows, err := tx.QueryContext(r.Context(), `SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id
		FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, tenant, after, snapshot, limit64)
	if err != nil {
		writeInternal(w)
		return
	}
	entries := make([]Entry, 0)
	for rows.Next() {
		var entry Entry
		var legacyID sql.NullInt64
		if err := rows.Scan(&entry.Seq, &entry.Account, &entry.Kind, &entry.Balance, &entry.Reserved, &entry.OperationID, &legacyID); err != nil {
			rows.Close()
			writeInternal(w)
			return
		}
		if legacyID.Valid {
			value := legacyID.Int64
			entry.LegacyID = &value
		}
		entries = append(entries, entry)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		writeInternal(w)
		return
	}
	if err := rows.Close(); err != nil {
		writeInternal(w)
		return
	}
	nextAfter := after
	if len(entries) > 0 {
		nextAfter = entries[len(entries)-1].Seq
	}
	var hasMore int
	if err := tx.QueryRowContext(r.Context(), `SELECT EXISTS(SELECT 1 FROM entries WHERE tenant=? AND seq>? AND seq<=?)`, tenant, nextAfter, snapshot).Scan(&hasMore); err != nil {
		writeInternal(w)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"entries": entries, "snapshot": snapshot, "next_after": nextAfter, "has_more": hasMore != 0,
	})
}

func (a *API) getSummary(w http.ResponseWriter, r *http.Request) {
	tenant, apiErr := a.tenant(r)
	if apiErr != nil {
		writeError(w, apiErr)
		return
	}
	q, ok := parseQuery(r.URL.RawQuery, map[string]bool{"snapshot": true})
	if !ok {
		writeError(w, invalid())
		return
	}
	tx, err := a.store.read.BeginTx(r.Context(), &sql.TxOptions{ReadOnly: true})
	if err != nil {
		writeInternal(w)
		return
	}
	defer tx.Rollback()
	maxSeq, err := maxSequence(r.Context(), tx, tenant)
	if err != nil {
		writeInternal(w)
		return
	}
	snapshot, ok := nonnegativeQuery(q, "snapshot", maxSeq)
	if !ok || snapshot > maxSeq {
		writeError(w, invalid())
		return
	}
	accounts := make([]HistoricalAccount, 0)
	rows, err := tx.QueryContext(r.Context(), `SELECT account,SUM(balance_delta),SUM(reserved_delta)
		FROM entries WHERE tenant=? AND seq<=? GROUP BY account
		HAVING SUM(CASE WHEN kind='opening' THEN 1 ELSE 0 END)>0 ORDER BY account`, tenant, snapshot)
	if err != nil {
		writeInternal(w)
		return
	}
	totals := SummaryTotals{}
	for rows.Next() {
		var item HistoricalAccount
		if err := rows.Scan(&item.Name, &item.Balance, &item.Reserved); err != nil {
			rows.Close()
			writeInternal(w)
			return
		}
		item.Available = item.Balance - item.Reserved
		accounts = append(accounts, item)
		totals.Balance += item.Balance
		totals.Reserved += item.Reserved
		totals.Available += item.Available
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		writeInternal(w)
		return
	}
	if err := rows.Close(); err != nil {
		writeInternal(w)
		return
	}
	var entryCount int64
	if err := tx.QueryRowContext(r.Context(), `SELECT COUNT(*) FROM entries WHERE tenant=? AND seq<=?`, tenant, snapshot).Scan(&entryCount); err != nil {
		writeInternal(w)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"snapshot": snapshot, "accounts": accounts, "totals": totals, "entry_count": entryCount,
	})
}

func maxSequence(ctx context.Context, q interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}, tenant string) (int64, error) {
	var max sql.NullInt64
	if err := q.QueryRowContext(ctx, `SELECT MAX(seq) FROM entries WHERE tenant=?`, tenant).Scan(&max); err != nil {
		return 0, err
	}
	if !max.Valid {
		return 0, nil
	}
	return max.Int64, nil
}

func writeError(w http.ResponseWriter, apiErr *APIError) {
	if apiErr == nil {
		apiErr = invalid()
	}
	writeJSON(w, apiErr.Status, map[string]any{"error": map[string]any{"code": apiErr.Code}})
}

func writeInternal(w http.ResponseWriter) {
	writeJSON(w, http.StatusInternalServerError, map[string]any{"error": map[string]any{"code": "internal"}})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	b, err := json.Marshal(value)
	if err != nil {
		writeInternal(w)
		return
	}
	writeRawJSON(w, status, b)
}

func writeRawJSON(w http.ResponseWriter, status int, value []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = io.Copy(w, bytes.NewReader(value))
}
