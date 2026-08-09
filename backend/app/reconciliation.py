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
    """Sum of (qty × unit_price_paise) across all line items in a record."""
    return sum(item.qty * item.unit_price_paise for item in record.line_items)


def compute_reconciliation(
    records: list[BillingRecord],
    clinic_id: str,
    date: str,
    validation_errors: list[RowValidationError] | None = None,
) -> ReconciliationReport:
    """
    Compute the end-of-day reconciliation report from validated billing records.

    Definitions:
    - Total Billed: sum of line_items totals for non-refund visits
    - Total Collected: sum of amount_paid_paise for non-refund visits
    - Outstanding: Total Billed - Total Collected (overall and per mode)
    - Refunds: sum of abs(amount_paid_paise) for refund rows
    """
    if validation_errors is None:
        validation_errors = []

    # Separate refunds from sales
    sales = [r for r in records if not r.is_refund]
    refunds = [r for r in records if r.is_refund]

    # ── Overall totals ─────────────────────────────────────────────────────
    total_billed = sum(compute_line_items_total_paise(r) for r in sales)
    total_collected = sum(r.amount_paid_paise for r in sales)
    outstanding = total_billed - total_collected
    total_refunds = sum(abs(r.amount_paid_paise) for r in refunds)

    # Count visits where amount_paid < billed (pending/partial payment)
    pending_visits = sum(
        1 for r in sales
        if r.amount_paid_paise < compute_line_items_total_paise(r)
    )

    # ── Per payment-mode breakdown ─────────────────────────────────────────
    mode_billed: dict[PaymentMode, int] = defaultdict(int)
    mode_collected: dict[PaymentMode, int] = defaultdict(int)

    for r in sales:
        mode_billed[r.payment_mode] += compute_line_items_total_paise(r)
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
        outstanding_paise=outstanding,
        total_refunds_paise=total_refunds,
        total_visits=len(sales),
        refund_count=len(refunds),
        pending_visits=pending_visits,
        payment_mode_breakdown=breakdown,
        validation_errors=validation_errors,
    )
