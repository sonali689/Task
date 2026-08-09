"""
Tests for the input validator.

Covers: malformed rows, missing fields, invalid types, edge cases.
"""

import pytest
from app.validator import parse_billing_json, validate_billing_log


class TestParseJson:
    """Tests for JSON parsing."""

    def test_valid_json_array(self):
        data, err = parse_billing_json(b'[{"key": "value"}]')
        assert err is None
        assert isinstance(data, list)

    def test_empty_array(self):
        data, err = parse_billing_json(b"[]")
        assert err is None
        assert data == []

    def test_invalid_json(self):
        data, err = parse_billing_json(b"{invalid json")
        assert data is None
        assert "Invalid JSON" in err

    def test_trailing_comma(self):
        data, err = parse_billing_json(b'[{"a": 1},]')
        assert data is None
        assert "Invalid JSON" in err


class TestValidateBillingLog:
    """Tests for billing log validation."""

    VALID_RECORD = {
        "clinic_id": "CLN-KNP-014",
        "visit_id": "V-001",
        "timestamp": "2026-07-27T10:00:00Z",
        "doctor_id": "DOC-014-01",
        "line_items": [
            {"drug_name": "PARACETAMOL", "qty": 3, "unit_price_paise": 2000}
        ],
        "payment_mode": "cash",
        "amount_paid_paise": 6000,
        "discount_paise": 0,
        "is_refund": False,
    }

    def test_valid_record(self):
        result = validate_billing_log([self.VALID_RECORD])
        assert result.valid_count == 1
        assert result.error_count == 0

    def test_missing_payment_mode(self):
        """Edge case from dataset: V-20260727-019 has no payment_mode."""
        row = {**self.VALID_RECORD, "visit_id": "V-019"}
        del row["payment_mode"]
        result = validate_billing_log([row])
        assert result.valid_count == 0
        assert result.error_count >= 1
        assert any("payment_mode" in e.field for e in result.errors)

    def test_invalid_payment_mode(self):
        row = {**self.VALID_RECORD, "payment_mode": "bitcoin"}
        result = validate_billing_log([row])
        assert result.valid_count == 0
        assert result.error_count >= 1

    def test_empty_line_items(self):
        row = {**self.VALID_RECORD, "line_items": []}
        result = validate_billing_log([row])
        assert result.valid_count == 0
        assert result.error_count >= 1

    def test_negative_qty(self):
        row = {
            **self.VALID_RECORD,
            "line_items": [
                {"drug_name": "X", "qty": -1, "unit_price_paise": 100}
            ],
        }
        result = validate_billing_log([row])
        assert result.valid_count == 0
        assert result.error_count >= 1

    def test_refund_with_positive_amount(self):
        """Refund row should have negative amount_paid_paise."""
        row = {
            **self.VALID_RECORD,
            "is_refund": True,
            "amount_paid_paise": 5000,
        }
        result = validate_billing_log([row])
        assert result.valid_count == 0
        assert result.error_count >= 1

    def test_non_list_input(self):
        result = validate_billing_log({"key": "value"})
        assert result.valid_count == 0
        assert result.error_count == 1
        assert "JSON array" in result.errors[0].message

    def test_non_dict_row(self):
        result = validate_billing_log(["not a dict", 42])
        assert result.valid_count == 0
        assert result.error_count == 2

    def test_mixed_valid_and_invalid(self):
        """Should accept valid rows and reject invalid ones separately."""
        invalid_row = {**self.VALID_RECORD, "visit_id": "V-BAD"}
        del invalid_row["payment_mode"]
        result = validate_billing_log([self.VALID_RECORD, invalid_row])
        assert result.valid_count == 1
        assert result.error_count >= 1
        assert result.total_rows == 2

    def test_empty_array_input(self):
        result = validate_billing_log([])
        assert result.valid_count == 0
        assert result.error_count == 0
        assert result.total_rows == 0
