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
    _build_prompt,
    _build_traced_figures,
    _generate_fallback_narrative,
    _format_rupees,
)


@pytest.fixture
def sample_reconciliation():
    return ReconciliationReport(
        clinic_id="CLN-KNP-014",
        date="2026-07-27",
        total_billed_paise=326000,
        total_collected_paise=317200,
        outstanding_paise=8800,
        total_refunds_paise=0,
        total_visits=18,
        refund_count=0,
        pending_visits=3,
        payment_mode_breakdown=[
            PaymentModeBreakdown(mode="cash", billed_paise=129000, collected_paise=127000, outstanding_paise=2000),
            PaymentModeBreakdown(mode="card", billed_paise=107000, collected_paise=79700, outstanding_paise=27300),
            PaymentModeBreakdown(mode="upi", billed_paise=90000, collected_paise=110500, outstanding_paise=-20500),
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
        assert "3,260" in billed_fig.display_value


class TestFallbackNarrative:
    def test_contains_key_figures(self, sample_reconciliation, sample_analytics):
        narrative = _generate_fallback_narrative(sample_reconciliation, sample_analytics)
        assert "₹3,260" in narrative  # total billed
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


class TestPromptConstruction:
    def test_prompt_contains_grounding_rules(self, sample_reconciliation, sample_analytics):
        prompt = _build_prompt(sample_reconciliation, sample_analytics)
        assert "ONLY the figures" in prompt
        assert "Do NOT invent" in prompt
        assert "cost price" in prompt.lower()

    def test_prompt_contains_figures(self, sample_reconciliation, sample_analytics):
        prompt = _build_prompt(sample_reconciliation, sample_analytics)
        assert "₹3,260" in prompt
        assert "18 visits" in prompt
