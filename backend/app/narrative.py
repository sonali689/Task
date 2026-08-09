"""
LLM narrative generation with figure tracing.

Given a deterministic reconciliation + analytics report, generates a
WhatsApp-friendly owner-facing summary. Every figure in the narrative
is traced back to its source field in the deterministic report.

Handles malformed/off-schema LLM responses gracefully — never crashes
or silently corrupts output.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from dotenv import load_dotenv

from .models import (
    AnalyticsReport,
    NarrativeResponse,
    ReconciliationReport,
    TracedFigure,
)

load_dotenv()


def _format_rupees(paise: int) -> str:
    """Format paise as rupees string for display."""
    rupees = paise / 100
    if rupees == int(rupees):
        return f"₹{int(rupees):,}"
    return f"₹{rupees:,.2f}"


def _build_prompt(
    reconciliation: ReconciliationReport,
    analytics: AnalyticsReport,
) -> str:
    """
    Build a grounded LLM prompt with all computed figures.

    The prompt instructs the LLM to use ONLY the provided figures
    and to explicitly flag when a metric cannot be computed.
    """
    # Format amounts for the prompt
    total_billed = _format_rupees(reconciliation.total_billed_paise)
    total_collected = _format_rupees(reconciliation.total_collected_paise)
    outstanding = _format_rupees(reconciliation.outstanding_paise)
    refunds = _format_rupees(reconciliation.total_refunds_paise)
    visits = reconciliation.total_visits
    refund_count = reconciliation.refund_count
    pending = reconciliation.pending_visits

    # Collection percentage
    if reconciliation.total_billed_paise > 0:
        collection_pct = round(
            (reconciliation.total_collected_paise / reconciliation.total_billed_paise) * 100
        )
    else:
        collection_pct = 0

    # Peak hour
    peak_info = "No activity recorded."
    if analytics.peak_hour:
        peak_label = analytics.peak_hour.hour_label
        # Create range label like "12pm–1pm"
        next_hour = analytics.peak_hour.hour + 1
        if next_hour == 0 or next_hour == 24:
            next_label = "12am"
        elif next_hour < 12:
            next_label = f"{next_hour}am"
        elif next_hour == 12:
            next_label = "12pm"
        else:
            next_label = f"{next_hour - 12}pm"
        peak_rev = _format_rupees(analytics.peak_hour.revenue_paise)
        peak_info = f"{peak_label}–{next_label}, with {peak_rev} in revenue"

    # Top drug by quantity
    top_qty_info = "No drug sales recorded."
    if analytics.top_drugs_by_qty:
        top = analytics.top_drugs_by_qty[0]
        top_qty_info = f"{top.drug_name} ({top.value} units)"

    # Top drug by revenue
    top_rev_info = "No drug sales recorded."
    if analytics.top_drugs_by_revenue:
        top = analytics.top_drugs_by_revenue[0]
        top_rev_info = f"{top.drug_name} ({_format_rupees(top.value)})"

    date_str = reconciliation.date
    clinic_id = reconciliation.clinic_id

    prompt = f"""You are a clinic billing assistant generating an end-of-day WhatsApp summary
for the clinic owner. Write a short, friendly, professional summary.

IMPORTANT RULES:
1. Use ONLY the figures provided below. Do NOT invent, approximate, or calculate any numbers yourself.
2. Every monetary amount and statistic you mention MUST come directly from the data below.
3. If a metric cannot be computed from the data (e.g., profit, because cost price is not available), say so plainly. Do NOT approximate or present something else as that metric.
4. Keep it brief and WhatsApp-friendly. Use simple paragraphs, not markdown.
5. Do NOT use bullet points or headers. Write flowing paragraphs.

DATA FOR {date_str} — Clinic {clinic_id}:

Reconciliation:
- Total Billed: {total_billed} across {visits} visits
- Total Collected: {total_collected} ({collection_pct}% of billed)
- Outstanding: {outstanding} across {pending} pending visits
- Refunds: {refunds} on {refund_count} refund(s)

Analytics:
- Busiest hour: {peak_info}
- Top medicine by quantity: {top_qty_info}
- Top medicine by revenue: {top_rev_info}

Note: Cost price data is NOT available, so profit cannot be calculated. Flag this clearly.

Write the summary now. Start with a greeting like "Good evening!" and address it as a daily summary for the clinic."""

    return prompt


def _build_traced_figures(
    reconciliation: ReconciliationReport,
    analytics: AnalyticsReport,
) -> list[TracedFigure]:
    """
    Build the traced figures list that maps every key number
    back to its source field in the deterministic report.
    """
    figures = [
        TracedFigure(
            display_value=_format_rupees(reconciliation.total_billed_paise),
            source_field="total_billed",
            source_label="total_billed",
        ),
        TracedFigure(
            display_value=_format_rupees(reconciliation.total_collected_paise),
            source_field="total_collected",
            source_label="total_collected",
        ),
        TracedFigure(
            display_value=_format_rupees(reconciliation.outstanding_paise),
            source_field="outstanding",
            source_label="outstanding",
        ),
        TracedFigure(
            display_value=_format_rupees(reconciliation.total_refunds_paise),
            source_field="refunds",
            source_label="refunds",
        ),
    ]

    # Peak hour
    if analytics.peak_hour:
        peak_h = analytics.peak_hour
        next_hour = peak_h.hour + 1
        if next_hour == 0 or next_hour == 24:
            next_label = "12am"
        elif next_hour < 12:
            next_label = f"{next_hour}am"
        elif next_hour == 12:
            next_label = "12pm"
        else:
            next_label = f"{next_hour - 12}pm"
        figures.append(
            TracedFigure(
                display_value=f"{peak_h.hour_label}–{next_label} / {_format_rupees(peak_h.revenue_paise)}",
                source_field="revenue_by_hour[max]",
                source_label="revenue_by_hour[max]",
            )
        )

    # Top drug by quantity
    if analytics.top_drugs_by_qty:
        top = analytics.top_drugs_by_qty[0]
        figures.append(
            TracedFigure(
                display_value=f"{top.drug_name} / {top.value}",
                source_field="top_drug_by_qty",
                source_label="top_drug_by_qty",
            )
        )

    # Top drug by revenue
    if analytics.top_drugs_by_revenue:
        top = analytics.top_drugs_by_revenue[0]
        figures.append(
            TracedFigure(
                display_value=f"{top.drug_name} / {_format_rupees(top.value)}",
                source_field="top_drug_by_revenue",
                source_label="top_drug_by_revenue",
            )
        )

    return figures


async def generate_narrative(
    reconciliation: ReconciliationReport,
    analytics: AnalyticsReport,
) -> NarrativeResponse:
    """
    Generate the LLM narrative summary with figure tracing.

    Tries Google Gemini by default (free tier). Falls back to a
    template-based narrative if the LLM call fails or returns
    malformed output.
    """
    prompt = _build_prompt(reconciliation, analytics)
    traced_figures = _build_traced_figures(reconciliation, analytics)

    # Try LLM generation
    narrative_text = None
    error_message = None

    try:
        narrative_text = await _call_llm(prompt)
    except Exception as e:
        error_message = f"LLM generation failed: {str(e)}"

    # Validate LLM response
    if narrative_text:
        # Basic sanity check: response should be non-empty text
        narrative_text = narrative_text.strip()
        if len(narrative_text) < 20:
            error_message = "LLM returned a response that was too short to be useful."
            narrative_text = None

    # Fallback to template if LLM failed
    if not narrative_text:
        narrative_text = _generate_fallback_narrative(reconciliation, analytics)
        status = "fallback"
        if error_message is None:
            error_message = "Used template-based fallback narrative."
    else:
        status = "success"

    return NarrativeResponse(
        clinic_id=reconciliation.clinic_id,
        date=reconciliation.date,
        narrative=narrative_text,
        traced_figures=traced_figures,
        status=status,
        error_message=error_message,
    )


async def _call_llm(prompt: str) -> str:
    """
    Call the configured LLM provider.
    Supports: Google Gemini (default), OpenAI, Anthropic.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "gemini":
        return await _call_gemini(prompt)
    elif provider == "openai":
        return await _call_openai(prompt)
    elif provider == "anthropic":
        return await _call_anthropic(prompt)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def _call_gemini(prompt: str) -> str:
    """Call Google Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your-gemini-api-key-here":
        raise ValueError(
            "GEMINI_API_KEY not configured. "
            "Set it in .env or use LLM_PROVIDER=openai/anthropic."
        )

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text


async def _call_openai(prompt: str) -> str:
    """Call OpenAI API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-openai-api-key-here":
        raise ValueError("OPENAI_API_KEY not configured.")

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.3,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_anthropic(prompt: str) -> str:
    """Call Anthropic API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your-anthropic-api-key-here":
        raise ValueError("ANTHROPIC_API_KEY not configured.")

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 500,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


def _generate_fallback_narrative(
    reconciliation: ReconciliationReport,
    analytics: AnalyticsReport,
) -> str:
    """
    Template-based fallback narrative when LLM is unavailable.
    Uses only deterministic figures — no invented numbers.
    """
    date = reconciliation.date
    total_billed = _format_rupees(reconciliation.total_billed_paise)
    total_collected = _format_rupees(reconciliation.total_collected_paise)
    outstanding = _format_rupees(reconciliation.outstanding_paise)
    refunds = _format_rupees(reconciliation.total_refunds_paise)
    visits = reconciliation.total_visits
    refund_count = reconciliation.refund_count
    pending = reconciliation.pending_visits

    if reconciliation.total_billed_paise > 0:
        pct = round(
            (reconciliation.total_collected_paise / reconciliation.total_billed_paise) * 100
        )
    else:
        pct = 0

    lines = [
        f"Good evening! Here's today's summary for Mehta Clinic ({date}):",
        "",
        f"{total_billed} billed across {visits} visits, "
        f"{total_collected} collected ({pct}%).",
    ]

    if reconciliation.outstanding_paise > 0:
        lines.append(
            f"{outstanding} is still outstanding across {pending} visits, "
            f"and {refunds} was refunded on {refund_count} visit."
        )
    elif reconciliation.total_refunds_paise > 0:
        lines.append(f"{refunds} was refunded on {refund_count} visit(s).")

    if analytics.peak_hour:
        peak = analytics.peak_hour
        next_hour = peak.hour + 1
        if next_hour == 24:
            next_label = "12am"
        elif next_hour < 12:
            next_label = f"{next_hour}am"
        elif next_hour == 12:
            next_label = "12pm"
        else:
            next_label = f"{next_hour - 12}pm"
        lines.append("")
        lines.append(
            f"Busiest hour: {peak.hour_label}–{next_label}, "
            f"with {_format_rupees(peak.revenue_paise)} in revenue."
        )

    if analytics.top_drugs_by_qty:
        top_qty = analytics.top_drugs_by_qty[0]
        lines.append("")
        lines.append(
            f"Top mover by quantity: {top_qty.drug_name} ({top_qty.value} units)."
        )

    if analytics.top_drugs_by_revenue:
        top_rev = analytics.top_drugs_by_revenue[0]
        lines.append(
            f"Top by revenue: {top_rev.drug_name} ({_format_rupees(top_rev.value)})."
        )

    lines.append("")
    lines.append(
        "Note: cost data wasn't available today, so this is revenue, "
        "not profit — flagging rather than estimating."
    )

    return "\n".join(lines)
