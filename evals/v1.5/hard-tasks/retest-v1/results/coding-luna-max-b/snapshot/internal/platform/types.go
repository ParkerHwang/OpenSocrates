package platform

import (
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
)

var namePattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var idempotencyPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

func validName(s string) bool { return namePattern.MatchString(s) }

type apiError struct {
	status int
	code   string
}

func invalid() *apiError             { return &apiError{status: 400, code: "invalid"} }
func notFound() *apiError            { return &apiError{status: 404, code: "not_found"} }
func conflict(code string) *apiError { return &apiError{status: 409, code: code} }
func internal() *apiError            { return &apiError{status: 500, code: "internal"} }

type OptionalVersion struct {
	Present bool
	Value   int64
}

func (v *OptionalVersion) UnmarshalJSON(data []byte) error {
	v.Present = true
	if string(data) == "null" {
		return errors.New("version cannot be null")
	}
	if err := json.Unmarshal(data, &v.Value); err != nil {
		return err
	}
	if v.Value <= 0 {
		return errors.New("version must be positive")
	}
	return nil
}

func checkVersion(got int64, want OptionalVersion) *apiError {
	if want.Present && got != want.Value {
		return conflict("version_conflict")
	}
	return nil
}

type account struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
	Version   int64  `json:"version"`
}

func makeAccount(name string, balance, reserved, version int64) account {
	return account{Name: name, Balance: balance, Reserved: reserved, Available: balance - reserved, Version: version}
}

type transferObject struct {
	ID       string `json:"id"`
	From     string `json:"from"`
	To       string `json:"to"`
	Amount   int64  `json:"amount"`
	Reversed bool   `json:"reversed"`
}

type holdObject struct {
	ID      string `json:"id"`
	Account string `json:"account"`
	Amount  int64  `json:"amount"`
	State   string `json:"state"`
}

type transferRequest struct {
	From        string          `json:"from"`
	To          string          `json:"to"`
	Amount      int64           `json:"amount"`
	FromVersion OptionalVersion `json:"from_version"`
	ToVersion   OptionalVersion `json:"to_version"`
}

func (t transferRequest) validate() *apiError {
	if !validName(t.From) || !validName(t.To) || t.From == t.To || t.Amount < 1 || t.Amount > 1_000_000_000 {
		return invalid()
	}
	return nil
}

func validateAccountAmount(amount int64) *apiError {
	if amount < 1 || amount > 1_000_000_000 {
		return invalid()
	}
	return nil
}

func requireName(name string) *apiError {
	if !validName(name) {
		return invalid()
	}
	return nil
}

func requestError(err error) *apiError {
	if err == nil {
		return nil
	}
	return invalid()
}

func internalMessage(err error) string {
	if err == nil {
		return ""
	}
	return fmt.Sprintf("internal database error: %v", err)
}
