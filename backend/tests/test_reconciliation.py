"""
Tests for the deterministic reconciliation logic.

Covers: happy-path day (Jul 27), refund-only day (Jul 25),
empty day (Jul 26), payment mode breakdown, and discount handling.
"""

import json
import pytest
from pathlib import Path

from app.models import BillingRecord
from app.reconciliation import (
    compute_reconciliation,
    compute_line_items_total_paise,
    compute_net_billed_paise,
)
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

    Figures below are independently recomputed from the raw JSON (gross
    line-item total minus discount_paise minus amount_paid_paise), not
    just re-derived from whatever the code currently outputs.
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

    def test_gross_line_items_total(self, records):
        """
        Gross sum of all line_items (qty * unit_price_paise), BEFORE
        discount. This is what compute_line_items_total_paise returns —
        it is not the reconciliation "billed" figure.
        Total = 326000 paise = ₹3,260
        """
        gross = sum(compute_line_items_total_paise(r) for r in records)
        assert gross == 326000

    def test_total_discounts(self, report):
        """
        Sum of discount_paise across the 18 valid, non-refund visits.
        V002:1000, V003:1000, V006:500, V007:1000, V009:500, V011:1000,
        V012:500, V013:500, V017:1000 = 7000 paise = ₹70
        """
        assert report.total_discounts_paise == 7000

    def test_total_billed_is_net_of_discount(self, report):
        """
        total_billed = gross line_items total - discounts, for non-refund
        visits. This is the amount actually invoiced to patients.
        326000 - 7000 = 319000 paise = ₹3,190
        """
        assert report.total_billed_paise == 319000

    def test_total_collected(self, report):
        """
        Sum of amount_paid_paise for non-refund visits.
        Total = 317200 paise = ₹3,172
        """
        assert report.total_collected_paise == 317200

    def test_outstanding_excludes_discount(self, report):
        """
        Outstanding = net billed - collected. A discount must never show
        up here — only genuine unpaid amounts (V-004, V-011, V-016 each
        have a real gap beyond their discount).
        319000 - 317200 = 1800 paise = ₹18
        """
        assert report.outstanding_paise == report.total_billed_paise - report.total_collected_paise
        assert report.outstanding_paise == 1800  # ₹18, NOT ₹88

    def test_pending_visits_excludes_discount_only_rows(self, report):
        """
        Only visits with a genuine shortfall beyond their discount count
        as pending — a row where amount_paid == line_total - discount is
        fully paid, not pending. V-004, V-011, V-016 are the real ones.
        """
        assert report.pending_visits == 3  # NOT 11

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
        Cash sales, net of discount: V001 (6000, 6000 paid),
        V005 (12000, 12000), V011 (56000-1000=55000, 54500),
        V013 (30000-500=29500, 29500), V015 (25000, 25000)
        Billed (net): 6000+12000+55000+29500+25000 = 127500
        Collected: 6000+12000+54500+29500+25000 = 127000
        Outstanding: 500
        """
        cash = next(b for b in report.payment_mode_breakdown if b.mode.value == "cash")
        assert cash.billed_paise == 127500
        assert cash.collected_paise == 127000
        assert cash.outstanding_paise == 500

    def test_card_breakdown(self, report):
        card = next(b for b in report.payment_mode_breakdown if b.mode.value == "card")
        assert card.billed_paise == 83500
        assert card.collected_paise == 82700
        assert card.outstanding_paise == 800

    def test_upi_breakdown(self, report):
        upi = next(b for b in report.payment_mode_breakdown if b.mode.value == "upi")
        assert upi.billed_paise == 108000
        assert upi.collected_paise == 107500
        assert upi.outstanding_paise == 500


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

    def test_zero_discounts(self, report):
        """No sales → zero discounts."""
        assert report.total_discounts_paise == 0

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
        assert report.total_discounts_paise == 0
        assert report.outstanding_paise == 0
        assert report.total_refunds_paise == 0
        assert report.total_visits == 0
        assert report.refund_count == 0


class TestLineItemsTotal:
    """Tests for compute_line_items_total_paise (gross) and
    compute_net_billed_paise (gross minus discount) helpers."""

    def test_single_item_gross(self):
        record = _load_valid_records("billing_log_2026-07-27.json")[0]
        # V-001: 3 * 2000 = 6000, no discount
        assert compute_line_items_total_paise(record) == 6000
        assert compute_net_billed_paise(record) == 6000

    def test_multiple_items_gross(self):
        records = _load_valid_records("billing_log_2026-07-27.json")
        # V-004 (index 3): 3*12000 + 2*6000 + 1*4000 = 52000, no discount
        v004 = [r for r in records if r.visit_id == "V-20260727-004"][0]
        assert compute_line_items_total_paise(v004) == 52000
        assert compute_net_billed_paise(v004) == 52000

    def test_net_billed_subtracts_discount(self):
        records = _load_valid_records("billing_log_2026-07-27.json")
        # V-002: 1*4000 = 4000 gross, discount 1000 -> net billed 3000,
        # which exactly equals amount_paid (3000) — fully paid, not pending.
        v002 = [r for r in records if r.visit_id == "V-20260727-002"][0]
        assert compute_line_items_total_paise(v002) == 4000
        assert compute_net_billed_paise(v002) == 3000
        assert v002.amount_paid_paise == 3000