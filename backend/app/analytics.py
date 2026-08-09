"""
Deterministic analytics logic.

Computes revenue-by-hour, top medicines by quantity, and top medicines
by revenue. This module NEVER calls an LLM — it is ground truth.
All monetary values are integer paise.
"""

from __future__ import annotations

from collections import defaultdict

from .models import (
    AnalyticsReport,
    BillingRecord,
    DrugRanking,
    HourlyRevenue,
)


def _hour_label(hour: int) -> str:
    """Convert 24-hour int to display label: 0→'12am', 9→'9am', 13→'1pm'."""
    if hour == 0:
        return "12am"
    elif hour < 12:
        return f"{hour}am"
    elif hour == 12:
        return "12pm"
    else:
        return f"{hour - 12}pm"


def _format_rupees(paise: int) -> str:
    """Format paise as ₹ rupees with comma grouping (Indian style)."""
    rupees = paise / 100
    if rupees == int(rupees):
        # Indian comma formatting for whole numbers
        return f"₹{int(rupees):,}"
    return f"₹{rupees:,.2f}"


def compute_analytics(
    records: list[BillingRecord],
    clinic_id: str,
    date: str,
) -> AnalyticsReport:
    """
    Compute analytics from validated billing records.

    Only non-refund records are included in analytics.
    Revenue by hour uses amount_paid_paise (what was actually collected).
    Drug rankings use line_items data (qty and qty*unit_price).
    """
    sales = [r for r in records if not r.is_refund]

    # ── Revenue by hour ────────────────────────────────────────────────────
    hourly: dict[int, int] = defaultdict(int)
    for r in sales:
        hour = r.timestamp.hour
        hourly[hour] += r.amount_paid_paise

    # Build hourly list for all hours that had activity
    all_hours = sorted(hourly.keys()) if hourly else []
    # Fill in the range from min to max hour to show gaps
    if all_hours:
        hour_range = range(all_hours[0], all_hours[-1] + 1)
    else:
        hour_range = range(0)

    revenue_by_hour = [
        HourlyRevenue(
            hour=h,
            hour_label=_hour_label(h),
            revenue_paise=hourly.get(h, 0),
        )
        for h in hour_range
    ]

    # Peak hour
    peak_hour = None
    if revenue_by_hour:
        peak_hour = max(revenue_by_hour, key=lambda h: h.revenue_paise)

    # ── Top medicines by quantity ──────────────────────────────────────────
    drug_qty: dict[str, int] = defaultdict(int)
    drug_rev: dict[str, int] = defaultdict(int)

    for r in sales:
        for item in r.line_items:
            drug_qty[item.drug_name] += item.qty
            drug_rev[item.drug_name] += item.qty * item.unit_price_paise

    # Sort descending, build ranked lists
    sorted_by_qty = sorted(drug_qty.items(), key=lambda x: x[1], reverse=True)
    sorted_by_rev = sorted(drug_rev.items(), key=lambda x: x[1], reverse=True)

    top_drugs_by_qty = [
        DrugRanking(
            rank=i + 1,
            drug_name=name,
            value=qty,
            display_value=f"{qty} units",
        )
        for i, (name, qty) in enumerate(sorted_by_qty)
    ]

    top_drugs_by_revenue = [
        DrugRanking(
            rank=i + 1,
            drug_name=name,
            value=rev,
            display_value=_format_rupees(rev),
        )
        for i, (name, rev) in enumerate(sorted_by_rev)
    ]

    return AnalyticsReport(
        clinic_id=clinic_id,
        date=date,
        revenue_by_hour=revenue_by_hour,
        peak_hour=peak_hour,
        top_drugs_by_qty=top_drugs_by_qty,
        top_drugs_by_revenue=top_drugs_by_revenue,
    )
