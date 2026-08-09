"""
Tests for the narrative generation module.

Covers: figure tracing, fallback narrative, prompt construction.
"""

import pytest
from app.models import (
    AnalyticsReport,
    DrugRanking,
    HourlyRevenue,
    PaymentModeBreakdown,
    ReconciliationReport,
)
from app.narrative import (
    _build_grounding_values,
    _build_prompt,
    _build_traced_figures,
    _find_ungrounded_numbers,
    _generate_fallback_narrative,
    _format_rupees,
)


@pytest.fixture
def sample_reconciliation():
    # Figures match the actual Jul 27 sample data run through the fixed
    # reconciliation.py: total_billed is net of discount, so outstanding
    # is ₹18 (1800 paise) and pending_visits is 3 — see test_reconciliation.py.
    return ReconciliationReport(
        clinic_id="CLN-KNP-014",
        date="2026-07-27",
        total_billed_paise=319000,
        total_collected_paise=317200,
        total_discounts_paise=7000,
        outstanding_paise=1800,
        total_refunds_paise=0,
        total_visits=18,
        refund_count=0,
        pending_visits=3,
        payment_mode_breakdown=[
            PaymentModeBreakdown(mode="cash", billed_paise=127500, collected_paise=127000, outstanding_paise=500),
            PaymentModeBreakdown(mode="card", billed_paise=83500, collected_paise=82700, outstanding_paise=800),
            PaymentModeBreakdown(mode="upi", billed_paise=108000, collected_paise=107500, outstanding_paise=500),
        ],
        validation_errors=[],
    )


@pytest.fixture
def sample_analytics():
    return AnalyticsReport(
        clinic_id="CLN-KNP-014",
        date="2026-07-27",
        revenue_by_hour=[
            HourlyRevenue(hour=9, hour_label="9am", revenue_paise=9000),
            HourlyRevenue(hour=10, hour_label="10am", revenue_paise=56500),
            HourlyRevenue(hour=11, hour_label="11am", revenue_paise=33500),
            HourlyRevenue(hour=12, hour_label="12pm", revenue_paise=9500),
            HourlyRevenue(hour=13, hour_label="1pm", revenue_paise=75500),
        ],
        peak_hour=HourlyRevenue(hour=13, hour_label="1pm", revenue_paise=75500),
        top_drugs_by_qty=[
            DrugRanking(rank=1, drug_name="OMEPRAZOLE", value=18, display_value="18 units"),
            DrugRanking(rank=2, drug_name="PARACETAMOL", value=11, display_value="11 units"),
        ],
        top_drugs_by_revenue=[
            DrugRanking(rank=1, drug_name="ATORVASTATIN", value=120000, display_value="₹1,200"),
            DrugRanking(rank=2, drug_name="AMOXICILLIN", value=66000, display_value="₹660"),
        ],
    )


class TestFormatRupees:
    def test_whole_rupees(self):
        assert _format_rupees(100000) == "₹1,000"

    def test_paise(self):
        assert _format_rupees(0) == "₹0"

    def test_large_amount(self):
        assert _format_rupees(4285000) == "₹42,850"


class TestTracedFigures:
    def test_all_key_figures_traced(self, sample_reconciliation, sample_analytics):
        figures = _build_traced_figures(sample_reconciliation, sample_analytics)

        # Should have: total_billed, total_collected, outstanding, refunds,
        # peak_hour, top_drug_by_qty, top_drug_by_revenue = 7 figures
        assert len(figures) == 7

        source_fields = {f.source_field for f in figures}
        assert "total_billed" in source_fields
        assert "total_collected" in source_fields
        assert "outstanding" in source_fields
        assert "refunds" in source_fields
        assert "revenue_by_hour[max]" in source_fields
        assert "top_drug_by_qty" in source_fields
        assert "top_drug_by_revenue" in source_fields

    def test_figure_values_match_report(self, sample_reconciliation, sample_analytics):
        figures = _build_traced_figures(sample_reconciliation, sample_analytics)
        billed_fig = next(f for f in figures if f.source_field == "total_billed")
        assert "3,190" in billed_fig.display_value


class TestFallbackNarrative:
    def test_contains_key_figures(self, sample_reconciliation, sample_analytics):
        narrative = _generate_fallback_narrative(sample_reconciliation, sample_analytics)
        assert "₹3,190" in narrative  # total billed (net of discount)
        assert "18" in narrative  # visit count
        assert "cost data" in narrative.lower()  # profit disclaimer

    def test_mentions_peak_hour(self, sample_reconciliation, sample_analytics):
        narrative = _generate_fallback_narrative(sample_reconciliation, sample_analytics)
        assert "1pm" in narrative

    def test_empty_day_narrative(self):
        empty_recon = ReconciliationReport(
            clinic_id="CLN-KNP-014",
            date="2026-07-26",
            total_billed_paise=0,
            total_collected_paise=0,
            total_discounts_paise=0,
            outstanding_paise=0,
            total_refunds_paise=0,
            total_visits=0,
            refund_count=0,
            pending_visits=0,
            payment_mode_breakdown=[],
            validation_errors=[],
        )
        empty_analytics = AnalyticsReport(
            clinic_id="CLN-KNP-014",
            date="2026-07-26",
            revenue_by_hour=[],
            peak_hour=None,
            top_drugs_by_qty=[],
            top_drugs_by_revenue=[],
        )
        narrative = _generate_fallback_narrative(empty_recon, empty_analytics)
        assert "₹0" in narrative
        assert "0 visits" in narrative


class TestGroundingVerification:
    """
    Tests for the actual number-extraction grounding check — the part that
    verifies what the LLM wrote, not just what the prompt asked for.
    """

    def test_narrative_using_only_given_figures_passes(self, sample_reconciliation, sample_analytics):
        allowed = _build_grounding_values(sample_reconciliation, sample_analytics)
        narrative = (
            "Good evening! ₹3,190 billed across 18 visits, ₹3,172 collected (99%). "
            "₹18 is still outstanding across 3 visits. Busiest hour: 1pm–2pm with "
            "₹755 in revenue. Top mover: OMEPRAZOLE (18 units)."
        )
        assert _find_ungrounded_numbers(narrative, allowed) == []

    def test_narrative_with_invented_number_is_flagged(self, sample_reconciliation, sample_analytics):
        allowed = _build_grounding_values(sample_reconciliation, sample_analytics)
        narrative = (
            "Good evening! ₹3,190 billed across 18 visits, with an estimated "
            "profit margin of 42%, which is a number nobody gave the model."
        )
        ungrounded = _find_ungrounded_numbers(narrative, allowed)
        assert "42" in ungrounded

    def test_generic_connector_numbers_are_not_flagged(self, sample_reconciliation, sample_analytics):
        allowed = _build_grounding_values(sample_reconciliation, sample_analytics)
        narrative = "There was 1 refund and 0 issues today."
        assert _find_ungrounded_numbers(narrative, allowed) == []


class TestPromptConstruction:
    def test_prompt_contains_grounding_rules(self, sample_reconciliation, sample_analytics):
        prompt = _build_prompt(sample_reconciliation, sample_analytics)
        assert "ONLY the figures" in prompt
        assert "Do NOT invent" in prompt
        assert "cost price" in prompt.lower()

    def test_prompt_contains_figures(self, sample_reconciliation, sample_analytics):
        prompt = _build_prompt(sample_reconciliation, sample_analytics)
        assert "₹3,190" in prompt
        assert "18 visits" in prompt