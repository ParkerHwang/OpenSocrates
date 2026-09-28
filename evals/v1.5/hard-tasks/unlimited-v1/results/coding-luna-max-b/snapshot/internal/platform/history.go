package platform

import (
	"context"
	"database/sql"
	"math/big"
	"sort"
)

type ledgerEntry struct {
	Seq           int64  `json:"seq"`
	Account       string `json:"account"`
	Kind          string `json:"kind"`
	BalanceDelta  int64  `json:"balance_delta"`
	ReservedDelta int64  `json:"reserved_delta"`
	OperationID   string `json:"operation_id"`
	LegacyID      *int64 `json:"legacy_id,omitempty"`
}

type entriesResult struct {
	Entries   []ledgerEntry `json:"entries"`
	Snapshot  int64         `json:"snapshot"`
	NextAfter int64         `json:"next_after"`
	HasMore   bool          `json:"has_more"`
}

type summaryAccount struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
}

type exactInteger struct{ value *big.Int }

func (n exactInteger) MarshalJSON() ([]byte, error) { return []byte(n.value.String()), nil }

type summaryTotals struct {
	Balance   exactInteger `json:"balance"`
	Reserved  exactInteger `json:"reserved"`
	Available exactInteger `json:"available"`
}

type summaryResult struct {
	Snapshot   int64            `json:"snapshot"`
	Accounts   []summaryAccount `json:"accounts"`
	Totals     summaryTotals    `json:"totals"`
	EntryCount int64            `json:"entry_count"`
}

func (s *Service) entries(ctx context.Context, tenant string, query entriesQuery) (entriesResult, *apiError, error) {
	var result entriesResult
	appErr, err := s.readTransaction(ctx, func(conn *sql.Conn) *apiError {
		maxSeq, err := currentSnapshot(ctx, conn, tenant)
		if err != nil {
			return internal()
		}
		snapshot := maxSeq
		if query.snapshot != nil {
			snapshot = *query.snapshot
		}
		if snapshot < 0 || snapshot > maxSeq || query.after < 0 || query.after > snapshot {
			return invalid()
		}
		result = entriesResult{Entries: make([]ledgerEntry, 0), Snapshot: snapshot, NextAfter: query.after}
		rows, err := conn.QueryContext(ctx, `SELECT seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id FROM entries WHERE tenant=? AND seq>? AND seq<=? ORDER BY seq LIMIT ?`, tenant, query.after, snapshot, query.limit+1)
		if err != nil {
			return internal()
		}
		defer rows.Close()
		fetched := int64(0)
		for rows.Next() {
			fetched++
			var entry ledgerEntry
			var legacy sql.NullInt64
			if err := rows.Scan(&entry.Seq, &entry.Account, &entry.Kind, &entry.BalanceDelta, &entry.ReservedDelta, &entry.OperationID, &legacy); err != nil {
				return internal()
			}
			if legacy.Valid {
				value := legacy.Int64
				entry.LegacyID = &value
			}
			if int64(len(result.Entries)) < query.limit {
				result.Entries = append(result.Entries, entry)
			}
		}
		if err := rows.Err(); err != nil {
			return internal()
		}
		result.HasMore = fetched > query.limit
		if len(result.Entries) > 0 {
			result.NextAfter = result.Entries[len(result.Entries)-1].Seq
		}
		return nil
	})
	return result, appErr, err
}

func (s *Service) summary(ctx context.Context, tenant string, requested *int64) (summaryResult, *apiError, error) {
	var result summaryResult
	appErr, err := s.readTransaction(ctx, func(conn *sql.Conn) *apiError {
		maxSeq, err := currentSnapshot(ctx, conn, tenant)
		if err != nil {
			return internal()
		}
		snapshot := maxSeq
		if requested != nil {
			snapshot = *requested
		}
		if snapshot < 0 || snapshot > maxSeq {
			return invalid()
		}
		result = summaryResult{
			Snapshot: snapshot,
			Accounts: make([]summaryAccount, 0),
			Totals: summaryTotals{
				Balance:   exactInteger{value: new(big.Int)},
				Reserved:  exactInteger{value: new(big.Int)},
				Available: exactInteger{value: new(big.Int)},
			},
		}
		rows, err := conn.QueryContext(ctx, `SELECT account,kind,balance_delta,reserved_delta FROM entries WHERE tenant=? AND seq<=? ORDER BY seq`, tenant, snapshot)
		if err != nil {
			return internal()
		}
		type accountTotals struct {
			balance  big.Int
			reserved big.Int
			opened   bool
		}
		totalsByName := make(map[string]*accountTotals)
		for rows.Next() {
			var name, kind string
			var balanceDelta, reservedDelta int64
			if err := rows.Scan(&name, &kind, &balanceDelta, &reservedDelta); err != nil {
				rows.Close()
				return internal()
			}
			sums := totalsByName[name]
			if sums == nil {
				sums = new(accountTotals)
				totalsByName[name] = sums
			}
			if kind == "opening" {
				sums.opened = true
			}
			sums.balance.Add(&sums.balance, big.NewInt(balanceDelta))
			sums.reserved.Add(&sums.reserved, big.NewInt(reservedDelta))
		}
		if err := rows.Err(); err != nil {
			rows.Close()
			return internal()
		}
		if err := rows.Close(); err != nil {
			return internal()
		}
		names := make([]string, 0, len(totalsByName))
		for name, sums := range totalsByName {
			if sums.opened {
				names = append(names, name)
			}
		}
		sort.Strings(names)
		for _, name := range names {
			sums := totalsByName[name]
			if !sums.balance.IsInt64() || !sums.reserved.IsInt64() {
				return internal()
			}
			balance, reserved := sums.balance.Int64(), sums.reserved.Int64()
			if balance < 0 || balance > maxBalance || reserved < 0 || reserved > balance {
				return internal()
			}
			a := summaryAccount{Name: name, Balance: balance, Reserved: reserved, Available: balance - reserved}
			result.Accounts = append(result.Accounts, a)
			result.Totals.Balance.value.Add(result.Totals.Balance.value, big.NewInt(a.Balance))
			result.Totals.Reserved.value.Add(result.Totals.Reserved.value, big.NewInt(a.Reserved))
			result.Totals.Available.value.Add(result.Totals.Available.value, big.NewInt(a.Available))
		}
		if err := conn.QueryRowContext(ctx, `SELECT count(*) FROM entries WHERE tenant=? AND seq<=?`, tenant, snapshot).Scan(&result.EntryCount); err != nil {
			return internal()
		}
		return nil
	})
	return result, appErr, err
}

func currentSnapshot(ctx context.Context, conn *sql.Conn, tenant string) (int64, error) {
	var maxSeq int64
	err := conn.QueryRowContext(ctx, `SELECT COALESCE(MAX(seq),0) FROM entries WHERE tenant=?`, tenant).Scan(&maxSeq)
	return maxSeq, err
}

func (s *Service) readTransaction(ctx context.Context, read func(*sql.Conn) *apiError) (*apiError, error) {
	conn, err := s.db.Conn(ctx)
	if err != nil {
		return nil, err
	}
	defer conn.Close()
	if _, err := conn.ExecContext(ctx, `BEGIN DEFERRED`); err != nil {
		return nil, err
	}
	defer func() { _, _ = conn.ExecContext(context.Background(), `ROLLBACK`) }()
	appErr := read(conn)
	if appErr != nil {
		return appErr, nil
	}
	if _, err := conn.ExecContext(ctx, `COMMIT`); err != nil {
		return nil, err
	}
	return nil, nil
}
