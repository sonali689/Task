"""
Deterministic EOD reconciliation logic.

Computes total billed, total collected, outstanding, and refunds —
each split by payment mode. This module NEVER calls an LLM.
All values are integer paise throughout.
"""

from __future__ import annotations

from collections import defaultdict

from .models import (
    BillingRecord,
    PaymentMode,
    PaymentModeBreakdown,
    ReconciliationReport,
    RowValidationError,
)


def compute_line_items_total_paise(record: BillingRecord) -> int:
    """
    Sum of (qty × unit_price_paise) across all line items in a record.
    This is the GROSS amount on the bill, before any discount.
    """
    return sum(item.qty * item.unit_price_paise for item in record.line_items)


def compute_net_billed_paise(record: BillingRecord) -> int:
    """
    The amount the patient was actually billed for this visit: gross
    line-item total minus any discount applied.

    A discount is money the clinic chose not to charge — it was never
    owed, so it must never be counted as "outstanding". Everything
    downstream (total_billed, outstanding, pending_visits) uses this net
    figure, not the gross line-item total.
    """
    return compute_line_items_total_paise(record) - record.discount_paise


def compute_reconciliation(
    records: list[BillingRecord],
    clinic_id: str,
    date: str,
    validation_errors: list[RowValidationError] | None = None,
) -> ReconciliationReport:
    """
    Compute the end-of-day reconciliation report from validated billing records.

    Definitions:
    - Total Billed: sum of (line_items total − discount) for non-refund
      visits — i.e. the amount actually invoiced to the patient.
    - Total Collected: sum of amount_paid_paise for non-refund visits
    - Outstanding: Total Billed − Total Collected (overall and per mode).
      A discount is never part of this — it was never owed in the first
      place, so it can't be "outstanding".
    - Total Discounts: sum of discount_paise for non-refund visits — kept
      as its own figure so discounts are visible, not just quietly
      absorbed into the billed number.
    - Refunds: sum of abs(amount_paid_paise) for refund rows
    """
    if validation_errors is None:
        validation_errors = []

    # Separate refunds from sales
    sales = [r for r in records if not r.is_refund]
    refunds = [r for r in records if r.is_refund]

    # ── Overall totals ─────────────────────────────────────────────────────
    total_billed = sum(compute_net_billed_paise(r) for r in sales)
    total_collected = sum(r.amount_paid_paise for r in sales)
    total_discounts = sum(r.discount_paise for r in sales)
    outstanding = total_billed - total_collected
    total_refunds = sum(abs(r.amount_paid_paise) for r in refunds)

    # Count visits where amount_paid < net billed — a genuine partial
    # payment, not just a discount that was already netted out above.
    pending_visits = sum(
        1 for r in sales
        if r.amount_paid_paise < compute_net_billed_paise(r)
    )

    # ── Per payment-mode breakdown ─────────────────────────────────────────
    mode_billed: dict[PaymentMode, int] = defaultdict(int)
    mode_collected: dict[PaymentMode, int] = defaultdict(int)

    for r in sales:
        mode_billed[r.payment_mode] += compute_net_billed_paise(r)
        mode_collected[r.payment_mode] += r.amount_paid_paise

    breakdown = []
    for mode in PaymentMode:
        billed = mode_billed.get(mode, 0)
        collected = mode_collected.get(mode, 0)
        breakdown.append(
            PaymentModeBreakdown(
                mode=mode,
                billed_paise=billed,
                collected_paise=collected,
                outstanding_paise=billed - collected,
            )
        )

    return ReconciliationReport(
        clinic_id=clinic_id,
        date=date,
        total_billed_paise=total_billed,
        total_collected_paise=total_collected,
        total_discounts_paise=total_discounts,
        outstanding_paise=outstanding,
        total_refunds_paise=total_refunds,
        total_visits=len(sales),
        refund_count=len(refunds),
        pending_visits=pending_visits,
        payment_mode_breakdown=breakdown,
        validation_errors=validation_errors,
    )