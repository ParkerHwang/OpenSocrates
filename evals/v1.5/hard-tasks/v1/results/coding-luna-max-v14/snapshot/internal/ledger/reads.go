package ledger

import (
	"context"
	"database/sql"
	"encoding/json"
	"math/big"
	"net/http"
	"net/url"
	"sort"
	"strconv"
)

func parseQuery(r *http.Request, allowed ...string) (url.Values, bool) {
	values, err := url.ParseQuery(r.URL.RawQuery)
	if err != nil {
		return nil, false
	}
	allowedSet := make(map[string]bool, len(allowed))
	for _, key := range allowed {
		allowedSet[key] = true
	}
	for key, all := range values {
		if !allowedSet[key] || len(all) != 1 {
			return nil, false
		}
	}
	return values, true
}

func queryInt(values url.Values, key string, fallback int64) (int64, bool) {
	all, ok := values[key]
	if !ok {
		return fallback, true
	}
	s := all[0]
	if s == "" {
		return 0, false
	}
	for _, ch := range s {
		if ch < '0' || ch > '9' {
			return 0, false
		}
	}
	n, err := strconv.ParseInt(s, 10, 64)
	return n, err == nil
}

func maxSequence(ctx context.Context, q interface {
	QueryRowContext(context.Context, string, ...any) *sql.Row
}, tenant string) (int64, error) {
	var seq int64
	err := q.QueryRowContext(ctx, `SELECT COALESCE((SELECT seq FROM tenant_sequences WHERE tenant=?),0)`, tenant).Scan(&seq)
	return seq, err
}

func (s *Server) listEntries(w http.ResponseWriter, r *http.Request, tenant string) {
	values, ok := parseQuery(r, "after", "limit", "snapshot")
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	current, err := maxSequence(r.Context(), s.db, tenant)
	if err != nil {
		writeInternal(w)
		return
	}
	snapshot, ok := queryInt(values, "snapshot", current)
	if !ok || snapshot < 0 || snapshot > current {
		writeError(w, 400, "invalid")
		return
	}
	after, ok := queryInt(values, "after", 0)
	if !ok || after < 0 || after > snapshot {
		writeError(w, 400, "invalid")
		return
	}
	limit, ok := queryInt(values, "limit", 50)
	if !ok || limit < 1 || limit > 100 {
		writeError(w, 400, "invalid")
		return
	}
	rows, err := s.db.QueryContext(r.Context(), `SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, tenant, after, snapshot, limit+1)
	if err != nil {
		writeInternal(w)
		return
	}
	entries := make([]Entry, 0, limit)
	for rows.Next() {
		var entry Entry
		var legacyID sql.NullInt64
		if err := rows.Scan(&entry.Seq, &entry.Account, &entry.Kind, &entry.BalanceDelta, &entry.ReservedDelta, &entry.OperationID, &legacyID); err != nil {
			rows.Close()
			writeInternal(w)
			return
		}
		if legacyID.Valid {
			entry.LegacyID = &legacyID.Int64
		}
		entries = append(entries, entry)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		writeInternal(w)
		return
	}
	rows.Close()
	hasMore := int64(len(entries)) > limit
	if hasMore {
		entries = entries[:limit]
	}
	nextAfter := after
	if len(entries) != 0 {
		nextAfter = entries[len(entries)-1].Seq
	}
	writeJSON(w, 200, map[string]any{
		"entries":    entries,
		"snapshot":   snapshot,
		"next_after": nextAfter,
		"has_more":   hasMore,
	})
}

type summaryAccount struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
}

type summaryTotals struct {
	Balance   json.Number `json:"balance"`
	Reserved  json.Number `json:"reserved"`
	Available json.Number `json:"available"`
}

type summaryState struct {
	balance  *big.Int
	reserved *big.Int
}

func (s *Server) summary(w http.ResponseWriter, r *http.Request, tenant string) {
	values, ok := parseQuery(r, "snapshot")
	if !ok {
		writeError(w, 400, "invalid")
		return
	}
	current, err := maxSequence(r.Context(), s.db, tenant)
	if err != nil {
		writeInternal(w)
		return
	}
	snapshot, ok := queryInt(values, "snapshot", current)
	if !ok || snapshot < 0 || snapshot > current {
		writeError(w, 400, "invalid")
		return
	}
	rows, err := s.db.QueryContext(r.Context(), `SELECT account,balance_delta,reserved_delta FROM entries WHERE tenant=? AND seq<=? ORDER BY seq`, tenant, snapshot)
	if err != nil {
		writeInternal(w)
		return
	}
	states := make(map[string]*summaryState)
	var entryCount int64
	for rows.Next() {
		var name string
		var balanceDelta, reservedDelta int64
		if err := rows.Scan(&name, &balanceDelta, &reservedDelta); err != nil {
			rows.Close()
			writeInternal(w)
			return
		}
		state := states[name]
		if state == nil {
			state = &summaryState{balance: new(big.Int), reserved: new(big.Int)}
			states[name] = state
		}
		state.balance.Add(state.balance, big.NewInt(balanceDelta))
		state.reserved.Add(state.reserved, big.NewInt(reservedDelta))
		if entryCount == int64(^uint64(0)>>1) {
			rows.Close()
			writeInternal(w)
			return
		}
		entryCount++
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		writeInternal(w)
		return
	}
	rows.Close()

	names := make([]string, 0, len(states))
	for name := range states {
		names = append(names, name)
	}
	sort.Strings(names)
	accounts := make([]summaryAccount, 0, len(names))
	var totalBalance, totalReserved, totalAvailable big.Int
	for _, name := range names {
		state := states[name]
		available := new(big.Int).Sub(new(big.Int).Set(state.balance), state.reserved)
		if state.balance.Sign() < 0 || state.reserved.Sign() < 0 || available.Sign() < 0 || !state.balance.IsInt64() || !state.reserved.IsInt64() || !available.IsInt64() {
			writeInternal(w)
			return
		}
		balance, reserved, avail := state.balance.Int64(), state.reserved.Int64(), available.Int64()
		if balance > maxAccountValue || reserved > maxAccountValue {
			writeInternal(w)
			return
		}
		accounts = append(accounts, summaryAccount{Name: name, Balance: balance, Reserved: reserved, Available: avail})
		totalBalance.Add(&totalBalance, state.balance)
		totalReserved.Add(&totalReserved, state.reserved)
		totalAvailable.Add(&totalAvailable, available)
	}
	writeJSON(w, 200, map[string]any{
		"snapshot": snapshot,
		"accounts": accounts,
		"totals": summaryTotals{
			Balance:   json.Number(totalBalance.String()),
			Reserved:  json.Number(totalReserved.String()),
			Available: json.Number(totalAvailable.String()),
		},
		"entry_count": entryCount,
	})
}
