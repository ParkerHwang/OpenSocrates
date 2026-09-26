package ledger

import (
	"bytes"
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"regexp"
	"strconv"
	"strings"
)

var (
	tenantPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
	keyPattern    = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)
)

type Account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}

type Transfer struct {
	ID       string `json:"id"`
	From     string `json:"from"`
	To       string `json:"to"`
	Amount   int64  `json:"amount"`
	Reversed bool   `json:"reversed"`
	LegacyID *int64 `json:"legacy_id,omitempty"`
}

type Hold struct {
	ID      string `json:"id"`
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	State   string `json:"state"`
}

type Entry struct {
	Seq           int64  `json:"seq"`
	Account       string `json:"account"`
	Kind          string `json:"kind"`
	BalanceDelta  int64  `json:"balance_delta"`
	ReservedDelta int64  `json:"reserved_delta"`
	OperationID   string `json:"operation_id"`
	LegacyID      *int64 `json:"legacy_id,omitempty"`
}

type apiError struct {
	status int
	code   string
}

func apiErr(status int, code string) *apiError { return &apiError{status: status, code: code} }

var (
	errInvalid  = apiErr(400, "invalid")
	errMissing  = apiErr(404, "not_found")
	errExists   = apiErr(409, "exists")
	errVersion  = apiErr(409, "version_conflict")
	errFunds    = apiErr(409, "insufficient")
	errIdem     = apiErr(409, "idempotency_conflict")
	errTerminal = apiErr(409, "terminal")
)

type transferRequest struct {
	From        string `json:"from"`
	To          string `json:"to"`
	Amount      int64  `json:"amount"`
	FromVersion *int64 `json:"from_version,omitempty"`
	ToVersion   *int64 `json:"to_version,omitempty"`
}

type createAccountRequest struct {
	Name    string `json:"name"`
	Opening int64  `json:"opening"`
}

type batchRequest struct {
	Transfers []transferRequest `json:"transfers"`
}

type holdRequest struct {
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	Version *int64 `json:"version,omitempty"`
}

type captureRequest struct {
	To          string `json:"to"`
	FromVersion *int64 `json:"from_version,omitempty"`
	ToVersion   *int64 `json:"to_version,omitempty"`
}

type releaseRequest struct {
	Version *int64 `json:"version,omitempty"`
}

type reverseRequest struct {
	FromVersion *int64 `json:"from_version,omitempty"`
	ToVersion   *int64 `json:"to_version,omitempty"`
}

func readObject(r io.Reader) (map[string]json.RawMessage, error) {
	b, err := io.ReadAll(io.LimitReader(r, 1<<20+1))
	if err != nil || len(b) == 0 || len(b) > 1<<20 {
		return nil, errors.New("invalid body")
	}
	dec := json.NewDecoder(bytes.NewReader(b))
	tok, err := dec.Token()
	if err != nil || tok != json.Delim('{') {
		return nil, errors.New("body must be an object")
	}
	fields := make(map[string]json.RawMessage)
	for dec.More() {
		tok, err = dec.Token()
		if err != nil {
			return nil, err
		}
		name, ok := tok.(string)
		if !ok {
			return nil, errors.New("invalid field")
		}
		if _, exists := fields[name]; exists {
			return nil, errors.New("duplicate field")
		}
		var raw json.RawMessage
		if err := dec.Decode(&raw); err != nil {
			return nil, err
		}
		fields[name] = raw
	}
	if _, err := dec.Token(); err != nil {
		return nil, err
	}
	var trailing any
	if err := dec.Decode(&trailing); err != io.EOF {
		return nil, errors.New("trailing json")
	}
	return fields, nil
}

func checkFields(fields map[string]json.RawMessage, allowed, required []string) error {
	allow := make(map[string]bool, len(allowed))
	for _, key := range allowed {
		allow[key] = true
	}
	for key := range fields {
		if !allow[key] {
			return fmt.Errorf("unknown field %q", key)
		}
	}
	for _, key := range required {
		if _, ok := fields[key]; !ok {
			return fmt.Errorf("missing field %q", key)
		}
	}
	return nil
}

func fieldString(fields map[string]json.RawMessage, name string) (string, error) {
	raw, ok := fields[name]
	if !ok {
		return "", fmt.Errorf("missing field %q", name)
	}
	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 || trimmed[0] != '"' {
		return "", fmt.Errorf("field %q must be a string", name)
	}
	var value string
	if err := json.Unmarshal(raw, &value); err != nil {
		return "", err
	}
	return value, nil
}

func fieldInt(fields map[string]json.RawMessage, name string) (int64, error) {
	raw, ok := fields[name]
	if !ok {
		return 0, fmt.Errorf("missing field %q", name)
	}
	return parseJSONInt(raw)
}

func parseJSONInt(raw json.RawMessage) (int64, error) {
	trimmed := strings.TrimSpace(string(raw))
	if trimmed == "" {
		return 0, errors.New("empty integer")
	}
	return strconv.ParseInt(trimmed, 10, 64)
}

func optionalInt(fields map[string]json.RawMessage, name string) (*int64, error) {
	raw, ok := fields[name]
	if !ok {
		return nil, nil
	}
	value, err := parseJSONInt(raw)
	if err != nil || value < 1 {
		return nil, fmt.Errorf("invalid version %q", name)
	}
	return &value, nil
}

func parseTransferRequest(raw json.RawMessage) (transferRequest, error) {
	fields, err := readObject(bytes.NewReader(raw))
	if err != nil {
		return transferRequest{}, err
	}
	if err := checkFields(fields, []string{"from", "to", "amount", "from_version", "to_version"}, []string{"from", "to", "amount"}); err != nil {
		return transferRequest{}, err
	}
	from, err := fieldString(fields, "from")
	if err != nil {
		return transferRequest{}, err
	}
	if !identifierPattern.MatchString(from) {
		return transferRequest{}, errors.New("invalid source name")
	}
	to, err := fieldString(fields, "to")
	if err != nil {
		return transferRequest{}, err
	}
	if !identifierPattern.MatchString(to) {
		return transferRequest{}, errors.New("invalid destination name")
	}
	amount, err := fieldInt(fields, "amount")
	if err != nil || amount < 1 || amount > 1_000_000_000 {
		return transferRequest{}, errors.New("invalid amount")
	}
	fv, err := optionalInt(fields, "from_version")
	if err != nil {
		return transferRequest{}, err
	}
	tv, err := optionalInt(fields, "to_version")
	if err != nil {
		return transferRequest{}, err
	}
	return transferRequest{From: from, To: to, Amount: amount, FromVersion: fv, ToVersion: tv}, nil
}

func parseCreateAccount(r io.Reader) (createAccountRequest, []byte, error) {
	fields, err := readObject(r)
	if err != nil || checkFields(fields, []string{"name", "opening"}, []string{"name", "opening"}) != nil {
		return createAccountRequest{}, nil, errors.New("invalid account body")
	}
	name, err := fieldString(fields, "name")
	if err != nil || !identifierPattern.MatchString(name) {
		return createAccountRequest{}, nil, errors.New("invalid account name")
	}
	opening, err := fieldInt(fields, "opening")
	if err != nil || opening < 0 || opening > 1_000_000_000 {
		return createAccountRequest{}, nil, errors.New("invalid opening")
	}
	req := createAccountRequest{Name: name, Opening: opening}
	canonical, err := json.Marshal(req)
	return req, canonical, err
}

func parseTransferBody(r io.Reader) (transferRequest, []byte, error) {
	fields, err := readObject(r)
	if err != nil {
		return transferRequest{}, nil, err
	}
	raw, err := json.Marshal(fields)
	if err != nil {
		return transferRequest{}, nil, err
	}
	req, err := parseTransferRequest(raw)
	if err != nil {
		return transferRequest{}, nil, err
	}
	canonical, err := json.Marshal(req)
	return req, canonical, err
}

func parseBatch(r io.Reader) (batchRequest, []byte, error) {
	fields, err := readObject(r)
	if err != nil || checkFields(fields, []string{"transfers"}, []string{"transfers"}) != nil {
		return batchRequest{}, nil, errors.New("invalid batch body")
	}
	var rawTransfers []json.RawMessage
	if err := json.Unmarshal(fields["transfers"], &rawTransfers); err != nil || rawTransfers == nil || len(rawTransfers) < 1 || len(rawTransfers) > 20 {
		return batchRequest{}, nil, errors.New("invalid batch transfers")
	}
	req := batchRequest{Transfers: make([]transferRequest, 0, len(rawTransfers))}
	for _, raw := range rawTransfers {
		tr, err := parseTransferRequest(raw)
		if err != nil {
			return batchRequest{}, nil, err
		}
		req.Transfers = append(req.Transfers, tr)
	}
	canonical, err := json.Marshal(req)
	return req, canonical, err
}

func parseHold(r io.Reader) (holdRequest, []byte, error) {
	fields, err := readObject(r)
	if err != nil || checkFields(fields, []string{"account", "amount", "version"}, []string{"account", "amount"}) != nil {
		return holdRequest{}, nil, errors.New("invalid hold body")
	}
	account, err := fieldString(fields, "account")
	if err != nil || !identifierPattern.MatchString(account) {
		return holdRequest{}, nil, errors.New("invalid account name")
	}
	amount, err := fieldInt(fields, "amount")
	if err != nil || amount < 1 || amount > 1_000_000_000 {
		return holdRequest{}, nil, errors.New("invalid amount")
	}
	version, err := optionalInt(fields, "version")
	if err != nil {
		return holdRequest{}, nil, err
	}
	req := holdRequest{Account: account, Amount: amount, Version: version}
	canonical, err := json.Marshal(req)
	return req, canonical, err
}

func parseCapture(r io.Reader) (captureRequest, []byte, error) {
	fields, err := readObject(r)
	if err != nil || checkFields(fields, []string{"to", "from_version", "to_version"}, []string{"to"}) != nil {
		return captureRequest{}, nil, errors.New("invalid capture body")
	}
	to, err := fieldString(fields, "to")
	if err != nil || !identifierPattern.MatchString(to) {
		return captureRequest{}, nil, errors.New("invalid destination")
	}
	fv, err := optionalInt(fields, "from_version")
	if err != nil {
		return captureRequest{}, nil, err
	}
	tv, err := optionalInt(fields, "to_version")
	if err != nil {
		return captureRequest{}, nil, err
	}
	req := captureRequest{To: to, FromVersion: fv, ToVersion: tv}
	canonical, err := json.Marshal(req)
	return req, canonical, err
}

func parseRelease(r io.Reader) (releaseRequest, []byte, error) {
	fields, err := readObject(r)
	if err != nil || checkFields(fields, []string{"version"}, nil) != nil {
		return releaseRequest{}, nil, errors.New("invalid release body")
	}
	version, err := optionalInt(fields, "version")
	if err != nil {
		return releaseRequest{}, nil, err
	}
	req := releaseRequest{Version: version}
	canonical, err := json.Marshal(req)
	return req, canonical, err
}

func parseReverse(r io.Reader) (reverseRequest, []byte, error) {
	fields, err := readObject(r)
	if err != nil || checkFields(fields, []string{"from_version", "to_version"}, nil) != nil {
		return reverseRequest{}, nil, errors.New("invalid reverse body")
	}
	fv, err := optionalInt(fields, "from_version")
	if err != nil {
		return reverseRequest{}, nil, err
	}
	tv, err := optionalInt(fields, "to_version")
	if err != nil {
		return reverseRequest{}, nil, err
	}
	req := reverseRequest{FromVersion: fv, ToVersion: tv}
	canonical, err := json.Marshal(req)
	return req, canonical, err
}

type sqlExecQuerier interface {
	ExecContext(context.Context, string, ...any) (sql.Result, error)
	QueryRowContext(context.Context, string, ...any) *sql.Row
}

type entryWriter struct {
	tenant string
	seq    int64
}

func newEntryWriter(ctx context.Context, q sqlExecQuerier, tenant string) (*entryWriter, error) {
	w := &entryWriter{tenant: tenant}
	err := q.QueryRowContext(ctx, `SELECT seq FROM tenant_sequences WHERE tenant=?`, tenant).Scan(&w.seq)
	if errors.Is(err, sql.ErrNoRows) {
		return w, nil
	}
	if err != nil {
		return nil, err
	}
	return w, nil
}

func (w *entryWriter) append(ctx context.Context, q sqlExecQuerier, account, kind string, balanceDelta, reservedDelta int64, operationID string, legacyID *int64) error {
	if w.seq == math.MaxInt64 {
		return errors.New("entry sequence exhausted")
	}
	w.seq++
	_, err := q.ExecContext(ctx, `INSERT INTO entries(tenant,seq,account,kind,balance_delta,reserved_delta,operation_id,legacy_id) VALUES(?,?,?,?,?,?,?,?)`, w.tenant, w.seq, account, kind, balanceDelta, reservedDelta, operationID, legacyID)
	return err
}

func (w *entryWriter) flush(ctx context.Context, q sqlExecQuerier) error {
	_, err := q.ExecContext(ctx, `INSERT INTO tenant_sequences(tenant,seq) VALUES(?,?) ON CONFLICT(tenant) DO UPDATE SET seq=excluded.seq`, w.tenant, w.seq)
	return err
}

func newID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic("crypto/rand unavailable: " + err.Error())
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	var out [36]byte
	hex.Encode(out[0:8], b[0:4])
	out[8] = '-'
	hex.Encode(out[9:13], b[4:6])
	out[13] = '-'
	hex.Encode(out[14:18], b[6:8])
	out[18] = '-'
	hex.Encode(out[19:23], b[8:10])
	out[23] = '-'
	hex.Encode(out[24:36], b[10:16])
	return string(out[:])
}

func newAccount(name string, balance, reserved, version int64) Account {
	return Account{Name: name, Balance: balance, Reserved: reserved, Available: balance - reserved, Version: version}
}

func checkVersion(expected *int64, actual int64) *apiError {
	if expected != nil && *expected != actual {
		return errVersion
	}
	return nil
}

func incrementVersion(version int64) (int64, bool) {
	if version == math.MaxInt64 {
		return 0, false
	}
	return version + 1, true
}

func addWithinLimit(a, b int64) (int64, bool) {
	if b < 0 || a < 0 || a > maxAccountValue-b {
		return 0, false
	}
	return a + b, true
}
