package platform

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
)

const maxRequestBytes = 1 << 20

type errorEnvelope struct {
	Error struct {
		Code string `json:"code"`
	} `json:"error"`
}

func writeError(w http.ResponseWriter, appErr *apiError) {
	if appErr == nil {
		appErr = internal()
	}
	var payload errorEnvelope
	payload.Error.Code = appErr.code
	writeJSON(w, appErr.status, payload)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	body, err := json.Marshal(value)
	if err != nil {
		writeError(w, internal())
		return
	}
	writeRawJSON(w, status, body)
}

func writeRawJSON(w http.ResponseWriter, status int, body []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func (s *Service) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	if path == "/health" {
		if r.Method != http.MethodGet {
			writeError(w, notFound())
			return
		}
		if err := s.db.PingContext(r.Context()); err != nil {
			log.Printf("health database check: %v", err)
			writeError(w, internal())
			return
		}
		writeJSON(w, http.StatusOK, struct {
			OK bool `json:"ok"`
		}{true})
		return
	}

	kind, arg := resolveRoute(r.Method, path)
	if kind == "" {
		writeError(w, notFound())
		return
	}
	tenant, appErr := requestTenant(r)
	if appErr != nil {
		writeError(w, appErr)
		return
	}

	switch kind {
	case "create_account":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		var req struct {
			Name    string `json:"name"`
			Opening *int64 `json:"opening"`
		}
		canonical, appErr := decodeRequest(r, &req)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		if !validName(req.Name) || req.Opening == nil || *req.Opening < 0 || *req.Opening > 1_000_000_000 {
			writeError(w, invalid())
			return
		}
		key, appErr := idempotencyKey(r)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		status, body, writeErr, err := s.createAccount(r.Context(), tenant, key, r.Method+" "+path, canonical, req.Name, *req.Opening)
		sendMutation(w, status, body, writeErr, err)
	case "get_account":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		if !validName(arg) {
			writeError(w, invalid())
			return
		}
		var balance, reserved, version int64
		err := s.db.QueryRowContext(r.Context(), `SELECT balance,reserved,version FROM accounts WHERE tenant=? AND name=?`, tenant, arg).Scan(&balance, &reserved, &version)
		if err == sql.ErrNoRows {
			writeError(w, notFound())
			return
		}
		if err != nil {
			log.Printf("read account: %v", err)
			writeError(w, internal())
			return
		}
		writeJSON(w, http.StatusOK, struct {
			Account account `json:"account"`
		}{makeAccount(arg, balance, reserved, version)})
	case "transfer":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		var req transferRequest
		canonical, appErr := decodeRequest(r, &req)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		if appErr = req.validate(); appErr != nil {
			writeError(w, appErr)
			return
		}
		key, appErr := idempotencyKey(r)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		status, body, writeErr, err := s.transfer(r.Context(), tenant, key, r.Method+" "+path, canonical, req)
		sendMutation(w, status, body, writeErr, err)
	case "batch":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		var req struct {
			Transfers []transferRequest `json:"transfers"`
		}
		canonical, appErr := decodeRequest(r, &req)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		if req.Transfers == nil || len(req.Transfers) < 1 || len(req.Transfers) > 20 {
			writeError(w, invalid())
			return
		}
		for _, transfer := range req.Transfers {
			if appErr = transfer.validate(); appErr != nil {
				writeError(w, appErr)
				return
			}
		}
		key, appErr := idempotencyKey(r)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		status, body, writeErr, err := s.batch(r.Context(), tenant, key, r.Method+" "+path, canonical, req.Transfers)
		sendMutation(w, status, body, writeErr, err)
	case "create_hold":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		var req struct {
			Account string          `json:"account"`
			Amount  int64           `json:"amount"`
			Version OptionalVersion `json:"version"`
		}
		canonical, appErr := decodeRequest(r, &req)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		if !validName(req.Account) || validateAccountAmount(req.Amount) != nil {
			writeError(w, invalid())
			return
		}
		key, appErr := idempotencyKey(r)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		status, body, writeErr, err := s.createHold(r.Context(), tenant, key, r.Method+" "+path, canonical, req.Account, req.Amount, req.Version)
		sendMutation(w, status, body, writeErr, err)
	case "release_hold":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		var req struct {
			Version OptionalVersion `json:"version"`
		}
		canonical, appErr := decodeRequest(r, &req)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		key, appErr := idempotencyKey(r)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		status, body, writeErr, err := s.releaseHold(r.Context(), tenant, key, r.Method+" "+path, canonical, arg, req.Version)
		sendMutation(w, status, body, writeErr, err)
	case "capture_hold":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		var req struct {
			To          string          `json:"to"`
			FromVersion OptionalVersion `json:"from_version"`
			ToVersion   OptionalVersion `json:"to_version"`
		}
		canonical, appErr := decodeRequest(r, &req)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		if !validName(req.To) {
			writeError(w, invalid())
			return
		}
		key, appErr := idempotencyKey(r)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		status, body, writeErr, err := s.captureHold(r.Context(), tenant, key, r.Method+" "+path, canonical, arg, req.To, req.FromVersion, req.ToVersion)
		sendMutation(w, status, body, writeErr, err)
	case "reverse_transfer":
		if hasQuery(r) {
			writeError(w, invalid())
			return
		}
		var req struct {
			FromVersion OptionalVersion `json:"from_version"`
			ToVersion   OptionalVersion `json:"to_version"`
		}
		canonical, appErr := decodeRequest(r, &req)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		key, appErr := idempotencyKey(r)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		status, body, writeErr, err := s.reverseTransfer(r.Context(), tenant, key, r.Method+" "+path, canonical, arg, req.FromVersion, req.ToVersion)
		sendMutation(w, status, body, writeErr, err)
	case "entries":
		query, appErr := parseEntriesQuery(r.URL.RawQuery)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		result, appErr, err := s.entries(r.Context(), tenant, query)
		if err != nil {
			log.Printf("read entries: %v", err)
			writeError(w, internal())
			return
		}
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		writeJSON(w, http.StatusOK, result)
	case "summary":
		snapshot, appErr := parseSummaryQuery(r.URL.RawQuery)
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		result, appErr, err := s.summary(r.Context(), tenant, snapshot)
		if err != nil {
			log.Printf("read summary: %v", err)
			writeError(w, internal())
			return
		}
		if appErr != nil {
			writeError(w, appErr)
			return
		}
		writeJSON(w, http.StatusOK, result)
	default:
		writeError(w, notFound())
	}
}

func resolveRoute(method, path string) (string, string) {
	switch {
	case path == "/accounts" && method == http.MethodPost:
		return "create_account", ""
	case path == "/transfers" && method == http.MethodPost:
		return "transfer", ""
	case path == "/batches" && method == http.MethodPost:
		return "batch", ""
	case path == "/holds" && method == http.MethodPost:
		return "create_hold", ""
	case path == "/entries" && method == http.MethodGet:
		return "entries", ""
	case path == "/summary" && method == http.MethodGet:
		return "summary", ""
	}
	parts := strings.Split(path, "/")
	if len(parts) == 3 && parts[0] == "" && parts[1] == "accounts" && parts[2] != "" && method == http.MethodGet {
		return "get_account", parts[2]
	}
	if len(parts) == 4 && parts[0] == "" && parts[1] == "holds" && parts[2] != "" && method == http.MethodPost {
		if parts[3] == "capture" {
			return "capture_hold", parts[2]
		}
		if parts[3] == "release" {
			return "release_hold", parts[2]
		}
	}
	if len(parts) == 4 && parts[0] == "" && parts[1] == "transfers" && parts[2] != "" && parts[3] == "reverse" && method == http.MethodPost {
		return "reverse_transfer", parts[2]
	}
	return "", ""
}

func requestTenant(r *http.Request) (string, *apiError) {
	values := r.Header.Values("X-Tenant")
	if len(values) != 1 || !validName(values[0]) {
		return "", invalid()
	}
	return values[0], nil
}

func idempotencyKey(r *http.Request) (string, *apiError) {
	values := r.Header.Values("Idempotency-Key")
	if len(values) != 1 || !idempotencyPattern.MatchString(values[0]) {
		return "", invalid()
	}
	return values[0], nil
}

func hasQuery(r *http.Request) bool { return r.URL.RawQuery != "" }

func sendMutation(w http.ResponseWriter, status int, body []byte, appErr *apiError, err error) {
	if err != nil {
		log.Printf("write transaction: %v", err)
		writeError(w, internal())
		return
	}
	if appErr != nil {
		writeError(w, appErr)
		return
	}
	writeRawJSON(w, status, body)
}

func decodeRequest(r *http.Request, target any) (string, *apiError) {
	reader := io.LimitReader(r.Body, maxRequestBytes+1)
	body, err := io.ReadAll(reader)
	if err != nil || len(body) == 0 || len(body) > maxRequestBytes {
		return "", invalid()
	}
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.UseNumber()
	value, err := decodeJSONValue(decoder)
	if err != nil {
		return "", invalid()
	}
	if _, ok := value.(map[string]any); !ok {
		return "", invalid()
	}
	if _, err := decoder.Token(); err != io.EOF {
		return "", invalid()
	}
	normalized, err := normalizeNumbers(value)
	if err != nil {
		return "", invalid()
	}
	canonicalBytes, err := json.Marshal(normalized)
	if err != nil {
		return "", invalid()
	}
	strict := json.NewDecoder(bytes.NewReader(body))
	strict.DisallowUnknownFields()
	if err := strict.Decode(target); err != nil {
		return "", invalid()
	}
	var extra any
	if err := strict.Decode(&extra); err != io.EOF {
		return "", invalid()
	}
	return string(canonicalBytes), nil
}

func decodeJSONValue(decoder *json.Decoder) (any, error) {
	token, err := decoder.Token()
	if err != nil {
		return nil, err
	}
	delim, isDelim := token.(json.Delim)
	if !isDelim {
		return token, nil
	}
	switch delim {
	case '{':
		object := make(map[string]any)
		for decoder.More() {
			keyToken, err := decoder.Token()
			if err != nil {
				return nil, err
			}
			key, ok := keyToken.(string)
			if !ok {
				return nil, errInvalidJSON
			}
			if _, exists := object[key]; exists {
				return nil, errDuplicateJSONKey
			}
			value, err := decodeJSONValue(decoder)
			if err != nil {
				return nil, err
			}
			object[key] = value
		}
		end, err := decoder.Token()
		if err != nil || end != json.Delim('}') {
			return nil, errInvalidJSON
		}
		return object, nil
	case '[':
		array := make([]any, 0)
		for decoder.More() {
			value, err := decodeJSONValue(decoder)
			if err != nil {
				return nil, err
			}
			array = append(array, value)
		}
		end, err := decoder.Token()
		if err != nil || end != json.Delim(']') {
			return nil, errInvalidJSON
		}
		return array, nil
	default:
		return nil, errInvalidJSON
	}
}

type simpleError string

func (e simpleError) Error() string { return string(e) }

var errInvalidJSON error = simpleError("invalid JSON structure")
var errDuplicateJSONKey error = simpleError("duplicate JSON field")

func normalizeNumbers(value any) (any, error) {
	switch typed := value.(type) {
	case json.Number:
		n, err := strconv.ParseInt(typed.String(), 10, 64)
		if err != nil {
			return nil, err
		}
		return n, nil
	case []any:
		out := make([]any, 0, len(typed))
		for _, item := range typed {
			normalized, err := normalizeNumbers(item)
			if err != nil {
				return nil, err
			}
			out = append(out, normalized)
		}
		return out, nil
	case map[string]any:
		out := make(map[string]any, len(typed))
		for key, item := range typed {
			normalized, err := normalizeNumbers(item)
			if err != nil {
				return nil, err
			}
			out[key] = normalized
		}
		return out, nil
	default:
		return value, nil
	}
}

type entriesQuery struct {
	after    int64
	limit    int64
	snapshot *int64
}

func parseEntriesQuery(raw string) (entriesQuery, *apiError) {
	query := entriesQuery{limit: 50}
	values, err := url.ParseQuery(raw)
	if err != nil {
		return query, invalid()
	}
	for key, items := range values {
		if len(items) != 1 {
			return query, invalid()
		}
		switch key {
		case "after":
			query.after, err = parseQueryInt(items[0])
			if err != nil || query.after < 0 {
				return query, invalid()
			}
		case "limit":
			query.limit, err = parseQueryInt(items[0])
			if err != nil || query.limit < 1 || query.limit > 100 {
				return query, invalid()
			}
		case "snapshot":
			snapshot, parseErr := parseQueryInt(items[0])
			if parseErr != nil || snapshot < 0 {
				return query, invalid()
			}
			query.snapshot = &snapshot
		default:
			return query, invalid()
		}
	}
	return query, nil
}

func parseSummaryQuery(raw string) (*int64, *apiError) {
	values, err := url.ParseQuery(raw)
	if err != nil {
		return nil, invalid()
	}
	for key, items := range values {
		if key != "snapshot" || len(items) != 1 {
			return nil, invalid()
		}
		snapshot, err := parseQueryInt(items[0])
		if err != nil || snapshot < 0 {
			return nil, invalid()
		}
		return &snapshot, nil
	}
	return nil, nil
}

func parseQueryInt(value string) (int64, error) {
	if value == "" {
		return 0, strconv.ErrSyntax
	}
	for _, ch := range value {
		if ch < '0' || ch > '9' {
			return 0, strconv.ErrSyntax
		}
	}
	return strconv.ParseInt(value, 10, 64)
}
