"""Typed errors and stable error codes for the foundation contracts."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_VALUE = "invalid_value"
    UNKNOWN_FIELD = "unknown_field"
    UNKNOWN_ENUM = "unknown_enum"
    MISSING_FIELD = "missing_field"
    INVALID_IDENTIFIER = "invalid_identifier"
    INVALID_SCHEMA = "invalid_schema"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_URL = "invalid_url"
    INVALID_JSON = "invalid_json"
    SERIALIZATION_ERROR = "serialization_error"
    UNSUPPORTED = "unsupported"


class OpenSocratesError(Exception):
    """Base class for errors safe to map at a process boundary."""

    code: ErrorCode = ErrorCode.INVALID_VALUE

    def __init__(self, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.path = path


class ValidationError(OpenSocratesError):
    """A contract value is malformed or violates a cross-field invariant."""


class UnknownFieldError(ValidationError):
    """A closed object contained a field outside its contract."""

    code = ErrorCode.UNKNOWN_FIELD


class MissingFieldError(ValidationError):
    """A required contract field was omitted."""

    code = ErrorCode.MISSING_FIELD


class UnknownEnumValueError(ValidationError):
    """A closed enum received an unrecognized value."""

    code = ErrorCode.UNKNOWN_ENUM


class IdentifierError(ValidationError):
    """An identifier does not have the required shape or timestamp."""

    code = ErrorCode.INVALID_IDENTIFIER


class SerializationError(OpenSocratesError):
    """Canonical JSON serialization/deserialization failed."""

    code = ErrorCode.SERIALIZATION_ERROR


class SchemaGenerationError(OpenSocratesError):
    """A schema manifest or generated projection is inconsistent."""

    code = ErrorCode.INVALID_SCHEMA
