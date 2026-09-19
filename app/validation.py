"""JSON Schema (Draft 2020-12) gating for final merge results.

A merge order may carry an optional ``result_schema``. The schema itself is
validated against the Draft 2020-12 meta-schema when the order is created;
an invalid schema rejects the request with HTTP 422 before any record is
written. The final result document is only ever validated once all
conflicts are resolved — working documents still carrying conflict
placeholders are never checked.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

_META_VALIDATOR = Draft202012Validator(Draft202012Validator.META_SCHEMA)


class InvalidResultSchema(Exception):
    """The supplied result_schema is not itself a valid Draft 2020-12 schema."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("result_schema is not a valid JSON Schema (Draft 2020-12)")


class ResultValidationFailed(Exception):
    """A candidate final result violates the merge order's result_schema."""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("result document does not satisfy result_schema")


def _pointer(parts: list[Any]) -> str:
    """Render deque/tuple path parts as an RFC 6901 JSON Pointer."""
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _error_item(err: SchemaError | ValidationError) -> dict:
    return {
        "instance_path": _pointer(list(err.absolute_path)),
        "schema_path": _pointer(list(err.absolute_schema_path)),
        "message": err.message,
    }


def compile_schema(schema: Any) -> Draft202012Validator:
    """Validate ``schema`` against the Draft 2020-12 meta-schema.

    Returns a ready-to-use validator. Raises InvalidResultSchema (HTTP 422),
    listing every meta-validation error, when the schema itself is invalid.
    """
    meta_errors = sorted(
        _META_VALIDATOR.iter_errors(schema),
        key=lambda e: (
            _pointer(list(e.absolute_path)),
            _pointer(list(e.absolute_schema_path)),
        ),
    )
    if meta_errors:
        raise InvalidResultSchema([_error_item(e) for e in meta_errors])
    return Draft202012Validator(schema)


def validate_result(validator: Draft202012Validator, document: Any) -> None:
    """Validate a candidate final result, listing every violation.

    Raises ResultValidationFailed (HTTP 422) with all errors sorted
    deterministically by (instance_path, schema_path).
    """
    errors = sorted(
        validator.iter_errors(document),
        key=lambda e: (
            _pointer(list(e.absolute_path)),
            _pointer(list(e.absolute_schema_path)),
        ),
    )
    if errors:
        raise ResultValidationFailed([_error_item(e) for e in errors])
