package ledger

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"reflect"
	"regexp"
	"strconv"
	"strings"
)

const maxValue int64 = 9_000_000_000_000_000

var identifierPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,40}$`)
var keyPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{1,80}$`)

type APIError struct {
	Status int
	Code   string
}

func (e *APIError) Error() string { return e.Code }

func invalid() *APIError             { return &APIError{Status: 400, Code: "invalid"} }
func missing() *APIError             { return &APIError{Status: 404, Code: "not_found"} }
func conflict(code string) *APIError { return &APIError{Status: 409, Code: code} }

type OptionalInt struct {
	Set   bool
	Value int64
}

func (n *OptionalInt) UnmarshalJSON(data []byte) error {
	n.Set = true
	if bytes.Equal(data, []byte("null")) {
		return errors.New("null is not an integer")
	}
	v, err := strconv.ParseInt(string(data), 10, 64)
	if err != nil {
		return err
	}
	n.Value = v
	return nil
}

func (n OptionalInt) ValidVersion() bool { return !n.Set || n.Value > 0 }

func validName(s string) bool { return identifierPattern.MatchString(s) }

func decodeBody(raw []byte, target any) error {
	shapeDecoder := json.NewDecoder(bytes.NewReader(raw))
	shapeDecoder.UseNumber()
	var shape any
	if err := shapeDecoder.Decode(&shape); err != nil {
		return err
	}
	if err := validateExactShape(shape, reflect.TypeOf(target)); err != nil {
		return err
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(target); err != nil {
		return err
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		if err == nil {
			return errors.New("multiple JSON values")
		}
		return err
	}
	return nil
}

var jsonUnmarshalerType = reflect.TypeOf((*json.Unmarshaler)(nil)).Elem()

func validateExactShape(value any, target reflect.Type) error {
	if target == nil {
		return nil
	}
	if target.Kind() == reflect.Pointer {
		target = target.Elem()
	}
	if reflect.PointerTo(target).Implements(jsonUnmarshalerType) {
		return nil
	}
	switch target.Kind() {
	case reflect.Struct:
		object, ok := value.(map[string]any)
		if !ok {
			return nil // the ordinary decoder reports the type mismatch
		}
		fields := make(map[string]reflect.Type, target.NumField())
		for i := 0; i < target.NumField(); i++ {
			field := target.Field(i)
			if field.PkgPath != "" {
				continue
			}
			name := field.Name
			if tag := field.Tag.Get("json"); tag != "" {
				name = strings.Split(tag, ",")[0]
				if name == "-" {
					continue
				}
			}
			fields[name] = field.Type
		}
		for key, child := range object {
			childType, ok := fields[key]
			if !ok {
				return errors.New("unknown or incorrectly cased field")
			}
			if err := validateExactShape(child, childType); err != nil {
				return err
			}
		}
	case reflect.Slice, reflect.Array:
		items, ok := value.([]any)
		if !ok {
			return nil
		}
		for _, child := range items {
			if err := validateExactShape(child, target.Elem()); err != nil {
				return err
			}
		}
	}
	return nil
}

func canonicalBody(raw []byte) (string, error) {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var value any
	if err := dec.Decode(&value); err != nil {
		return "", err
	}
	if _, ok := value.(map[string]any); !ok {
		return "", errors.New("body must be an object")
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		if err == nil {
			return "", errors.New("multiple JSON values")
		}
		return "", err
	}
	b, err := json.Marshal(value)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

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
	Seq         int64  `json:"seq"`
	Account     string `json:"account"`
	Kind        string `json:"kind"`
	Balance     int64  `json:"balance_delta"`
	Reserved    int64  `json:"reserved_delta"`
	OperationID string `json:"operation_id"`
	LegacyID    *int64 `json:"legacy_id,omitempty"`
}

type HistoricalAccount struct {
	Name      string `json:"name"`
	Balance   int64  `json:"balance"`
	Reserved  int64  `json:"reserved"`
	Available int64  `json:"available"`
}

type SummaryTotals struct {
	Balance   int64 `json:"balance"`
	Reserved  int64 `json:"reserved"`
	Available int64 `json:"available"`
}

func account(name string, balance, reserved, version int64) Account {
	return Account{Name: name, Balance: balance, Reserved: reserved, Available: balance - reserved, Version: version}
}

func validAmount(n OptionalInt) bool { return n.Set && n.Value >= 1 && n.Value <= 1_000_000_000 }

func checkOptionalVersions(values ...OptionalInt) bool {
	for _, v := range values {
		if !v.ValidVersion() {
			return false
		}
	}
	return true
}
