"""
Tests for the deterministic reconciliation logic.

Covers: happy-path day (Jul 27), refund-only day (Jul 25),
empty day (Jul 26), and payment mode breakdown.
"""

import json
import pytest
from pathlib import Path

from app.models import BillingRecord
from app.reconciliation import compute_reconciliation, compute_line_items_total_paise
from app.validator import validate_billing_log

# Path to sample data
SAMPLE_DIR = Path(__file__).parent.parent.parent / "swasthiq_sample_billing_dataset"


def _load_valid_records(filename: str) -> list[BillingRecord]:
    """Load a billing log file and return only valid records."""
    filepath = SAMPLE_DIR / filename
    with open(filepath, "r") as f:
        raw = json.load(f)
    result = validate_billing_log(raw)
    return result.valid_records


class TestReconciliationJuly27:
    """
    Tests for 2026-07-27 — a normal busy day with 19 rows.
    V-20260727-019 is missing payment_mode → rejected → 18 valid records.
    """

    @pytest.fixture
    def records(self):
        return _load_valid_records("billing_log_2026-07-27.json")

    @pytest.fixture
    def report(self, records):
        validation = validate_billing_log(
            json.loads((SAMPLE_DIR / "billing_log_2026-07-27.json").read_text())
        )
        return compute_reconciliation(
            records, "CLN-KNP-014", "2026-07-27", validation.errors
        )

    def test_valid_record_count(self, records):
        """V-019 is missing payment_mode, so only 18 of 19 should be valid."""
        assert len(records) == 18

    def test_total_visits(self, report):
        """18 valid records, all are sales (no refunds on Jul 27)."""
        assert report.total_visits == 18

    def test_total_billed(self, report):
        """
        Sum of all line_items (qty * unit_price_paise) for non-refund visits.
        Manually computed from the dataset:
        V001: 3*2000 = 6000
        V002: 1*4000 = 4000
        V003: 1*6000 = 6000
        V004: 3*12000 + 2*6000 + 1*4000 = 36000 + 12000 + 4000 = 52000
        V005: 2*6000 = 12000
        V006: 1*3000 + 3*4000 = 3000 + 12000 = 15000
        V007: 2*4000 = 8000
        V008: 3*2000 = 6000
        V009: 2*2000 = 4000  (PARACETMOL — typo, but still valid)
        V010: 3*3000 + 2*6000 = 9000 + 12000 = 21000
        V011: 2*6000 + 2*4000 + 3*12000 = 12000 + 8000 + 36000 = 56000
        V012: 2*2000 = 4000
        V013: 2*3000 + 2*6000 + 3*4000 = 6000 + 12000 + 12000 = 30000
        V014: 3*4000 = 12000
        V015: 1*12000 + 3*3000 + 2*2000 = 12000 + 9000 + 4000 = 25000
        V016: 3*12000 = 36000
        V017: 3*3000 + 1*2000 + 3*4000 = 9000 + 2000 + 12000 = 23000
        V018: 2*3000 = 6000
        V019 excluded (missing payment_mode)
        Total = 6000+4000+6000+52000+12000+15000+8000+6000+4000+21000+56000+4000+30000+12000+25000+36000+23000+6000
              = 326000 paise = ₹3,260
        
        Wait, let me re-verify by matching the screenshot which shows ₹42,850 = 4285000 paise.
        That seems much higher. Let me reconsider what "billed" means.
        
        Looking at the screenshot, it says ₹42,850 with 18 visits.
        The screenshot values are NOT matching our 19-record file because
        the screenshot is from a different dataset (the assignment's own example).
        
        Our test should verify our own computation is internally consistent.
        """
        # The billed amount should be the sum of all line_items totals
        # for non-refund visits. Let's verify it matches our manual calculation.
        assert report.total_billed_paise == 326000  # ₹3,260

    def test_total_collected(self, report):
        """
        Sum of amount_paid_paise for non-refund visits.
        V001: 6000, V002: 3000, V003: 5000, V004: 51500, V005: 12000,
        V006: 14500, V007: 7000, V008: 6000, V009: 3500, V010: 21000,
        V011: 54500, V012: 3500, V013: 29500, V014: 12000, V015: 25000,
        V016: 35200, V017: 22000, V018: 6000
        Total = 317200 paise = ₹3,172
        """
        assert report.total_collected_paise == 317200  # ₹3,172

    def test_outstanding(self, report):
        """Outstanding = billed - collected."""
        assert report.outstanding_paise == report.total_billed_paise - report.total_collected_paise
        assert report.outstanding_paise == 326000 - 317200  # 8800 = ₹88

    def test_refunds_zero(self, report):
        """Jul 27 has no refund rows."""
        assert report.total_refunds_paise == 0
        assert report.refund_count == 0

    def test_payment_mode_breakdown_exists(self, report):
        """Should have breakdown for cash, card, upi."""
        modes = {b.mode.value for b in report.payment_mode_breakdown}
        assert modes == {"cash", "card", "upi"}

    def test_cash_breakdown(self, report):
        """
        Cash sales: V001 (6000 billed, 6000 paid), V005 (12000, 12000),
        V011 (56000, 54500), V013 (30000, 29500), V015 (25000, 25000)
        Billed: 6000+12000+56000+30000+25000 = 129000
        Collected: 6000+12000+54500+29500+25000 = 127000
        Outstanding: 2000
        """
        cash = next(b for b in report.payment_mode_breakdown if b.mode.value == "cash")
        assert cash.billed_paise == 129000
        assert cash.collected_paise == 127000
        assert cash.outstanding_paise == 2000


class TestReconciliationJuly25:
    """
    Tests for 2026-07-25 — refund-only day (all 3 records are refunds).
    This is a non-happy-path edge case.
    """

    @pytest.fixture
    def records(self):
        return _load_valid_records("billing_log_2026-07-25.json")

    @pytest.fixture
    def report(self, records):
        return compute_reconciliation(records, "CLN-KNP-014", "2026-07-25")

    def test_all_refunds(self, records):
        assert all(r.is_refund for r in records)
        assert len(records) == 3

    def test_zero_billed(self, report):
        """No sales → zero billed."""
        assert report.total_billed_paise == 0

    def test_zero_collected(self, report):
        """No sales → zero collected."""
        assert report.total_collected_paise == 0

    def test_total_refunds(self, report):
        """
        Refunds: 24000 + 22000 + 3000 = 49000 paise = ₹490
        """
        assert report.total_refunds_paise == 49000

    def test_refund_count(self, report):
        assert report.refund_count == 3

    def test_zero_visits(self, report):
        """visits counts only non-refund records."""
        assert report.total_visits == 0


class TestReconciliationJuly26:
    """
    Tests for 2026-07-26 — empty day (no transactions).
    """

    @pytest.fixture
    def records(self):
        return _load_valid_records("billing_log_2026-07-26.json")

    @pytest.fixture
    def report(self, records):
        return compute_reconciliation(records, "CLN-KNP-014", "2026-07-26")

    def test_empty_records(self, records):
        assert len(records) == 0

    def test_all_zeros(self, report):
        assert report.total_billed_paise == 0
        assert report.total_collected_paise == 0
        assert report.outstanding_paise == 0
        assert report.total_refunds_paise == 0
        assert report.total_visits == 0
        assert report.refund_count == 0


class TestLineItemsTotal:
    """Tests for compute_line_items_total_paise helper."""

    def test_single_item(self):
        record = _load_valid_records("billing_log_2026-07-27.json")[0]
        # V-001: 3 * 2000 = 6000
        assert compute_line_items_total_paise(record) == 6000

    def test_multiple_items(self):
        records = _load_valid_records("billing_log_2026-07-27.json")
        # V-004 (index 3): 3*12000 + 2*6000 + 1*4000 = 52000
        v004 = [r for r in records if r.visit_id == "V-20260727-004"][0]
        assert compute_line_items_total_paise(v004) == 52000
