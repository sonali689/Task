"""
Input validation for billing log JSON files.

Parses raw JSON, validates each row against the BillingRecord schema,
and returns (valid_records, errors) — never crashes on malformed data.
Each error includes the row index, visit_id (if available), the failing
field, and an actionable human-readable message.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .models import BillingRecord, RowValidationError, ValidationResult


def validate_billing_log(raw_data: Any) -> ValidationResult:
    """
    Validate a parsed JSON billing log (expected: list of dicts).

    Returns a ValidationResult with valid records and per-row errors.
    Malformed rows are skipped with specific, actionable errors —
    never a generic 500.
    """
    # Handle non-list input
    if not isinstance(raw_data, list):
        return ValidationResult(
            valid_records=[],
            errors=[
                RowValidationError(
                    row_index=0,
                    visit_id=None,
                    field="root",
                    message=(
                        f"Expected a JSON array of billing records, "
                        f"got {type(raw_data).__name__}. "
                        f"Wrap your records in [ ... ]."
                    ),
                )
            ],
            total_rows=0,
            valid_count=0,
            error_count=1,
        )

    valid_records: list[BillingRecord] = []
    errors: list[RowValidationError] = []

    for idx, row in enumerate(raw_data):
        # Handle non-dict rows
        if not isinstance(row, dict):
            errors.append(
                RowValidationError(
                    row_index=idx,
                    visit_id=None,
                    field="root",
                    message=(
                        f"Row {idx}: expected a JSON object, "
                        f"got {type(row).__name__}."
                    ),
                )
            )
            continue

        visit_id = row.get("visit_id", f"unknown (row {idx})")

        try:
            record = BillingRecord(**row)
            valid_records.append(record)
        except ValidationError as e:
            for err in e.errors():
                # Build a human-readable field path
                field_path = " → ".join(str(loc) for loc in err["loc"])
                errors.append(
                    RowValidationError(
                        row_index=idx,
                        visit_id=visit_id,
                        field=field_path,
                        message=(
                            f"Row {idx} (visit {visit_id}): "
                            f"field '{field_path}' — {err['msg']}."
                        ),
                    )
                )

    return ValidationResult(
        valid_records=valid_records,
        errors=errors,
        total_rows=len(raw_data),
        valid_count=len(valid_records),
        error_count=len(errors),
    )


def parse_billing_json(raw_json: str | bytes) -> tuple[Any, str | None]:
    """
    Parse raw JSON string/bytes into Python objects.

    Returns (parsed_data, error_message).
    error_message is None on success.
    """
    try:
        data = json.loads(raw_json)
        return data, None
    except json.JSONDecodeError as e:
        return None, (
            f"Invalid JSON: {e.msg} at line {e.lineno}, column {e.colno}. "
            f"Check for trailing commas, unquoted keys, or encoding issues."
        )
