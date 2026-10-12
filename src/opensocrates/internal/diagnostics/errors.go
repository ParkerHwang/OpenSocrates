package diagnostics

import (
	"errors"
	"fmt"
)

type Code string

const (
	Verification         Code = "verification"
	Network              Code = "network"
	Permission           Code = "permission"
	Locked               Code = "locked"
	HostUnavailable      Code = "host_unavailable"
	ProtocolIncompatible Code = "protocol_incompatible"
	Activation           Code = "activation"
	RollbackIncomplete   Code = "rollback_incomplete"
	Unsupported          Code = "unsupported"
)

// Error never contains private source errors or user content.
type Error struct {
	Code  Code   `json:"error_code"`
	Stage string `json:"stage"`
}

func (e *Error) Error() string          { return fmt.Sprintf("%s: %s", e.Stage, e.Code) }
func New(code Code, stage string) error { return &Error{Code: code, Stage: stage} }

// CodeOf deliberately avoids classification by wording or exposing a source error.
func CodeOf(err error) Code {
	var typed *Error
	if errors.As(err, &typed) {
		return typed.Code
	}
	return Verification
}
