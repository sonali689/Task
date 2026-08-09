"""
Pydantic models for billing data validation and API response schemas.

All monetary values are stored and transmitted as integer paise (1 rupee = 100 paise).
Conversion to rupees is done only at the display/frontend layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ── Enums ──────────────────────────────────────────────────────────────────────

class PaymentMode(str, Enum):
    """Accepted payment modes."""
    cash = "cash"
    card = "card"
    upi = "upi"


# ── Input Schemas ──────────────────────────────────────────────────────────────

class LineItem(BaseModel):
    """A single drug/item in a visit's bill."""
    drug_name: str = Field(..., min_length=1)
    qty: int = Field(..., gt=0)
    unit_price_paise: int = Field(..., ge=0)


class BillingRecord(BaseModel):
    """A single visit/transaction record from the daily billing log."""
    clinic_id: str = Field(..., min_length=1)
    visit_id: str = Field(..., min_length=1)
    timestamp: datetime
    doctor_id: str = Field(..., min_length=1)
    line_items: list[LineItem] = Field(..., min_length=1)
    payment_mode: PaymentMode
    amount_paid_paise: int
    discount_paise: int = Field(default=0, ge=0)
    is_refund: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_refund_sign(self):
        """Refund rows should have negative amount_paid_paise."""
        if self.is_refund and self.amount_paid_paise > 0:
            raise ValueError(
                f"is_refund is true but amount_paid_paise is positive "
                f"({self.amount_paid_paise}). Refund amounts should be negative."
            )
        if not self.is_refund and self.amount_paid_paise < 0:
            raise ValueError(
                f"is_refund is false but amount_paid_paise is negative "
                f"({self.amount_paid_paise}). Non-refund amounts should be "
                f"non-negative."
            )
        return self


# ── Validation Result ──────────────────────────────────────────────────────────

class RowValidationError(BaseModel):
    """A specific, actionable error for a malformed row."""
    row_index: int
    visit_id: Optional[str] = None
    field: str
    message: str


class ValidationResult(BaseModel):
    """Result of parsing and validating a billing log."""
    valid_records: list[BillingRecord]
    errors: list[RowValidationError]
    total_rows: int
    valid_count: int
    error_count: int


# ── Reconciliation Response ────────────────────────────────────────────────────

class PaymentModeBreakdown(BaseModel):
    """Reconciliation figures for a single payment mode."""
    mode: PaymentMode
    billed_paise: int
    collected_paise: int
    outstanding_paise: int


class ReconciliationReport(BaseModel):
    """End-of-day reconciliation report — all values in paise."""
    clinic_id: str
    date: str
    total_billed_paise: int
    total_collected_paise: int
    outstanding_paise: int
    total_refunds_paise: int
    total_visits: int
    refund_count: int
    pending_visits: int  # visits where amount_paid < billed
    payment_mode_breakdown: list[PaymentModeBreakdown]
    validation_errors: list[RowValidationError]


# ── Analytics Response ─────────────────────────────────────────────────────────

class HourlyRevenue(BaseModel):
    """Revenue for a single hour bucket."""
    hour: int  # 0-23
    hour_label: str  # e.g. "9am", "12pm"
    revenue_paise: int


class DrugRanking(BaseModel):
    """A drug's ranking entry."""
    rank: int
    drug_name: str
    value: int  # qty for quantity ranking, paise for revenue ranking
    display_value: str  # e.g. "142 units" or "₹6,480"


class AnalyticsReport(BaseModel):
    """Analytics report — revenue by hour, top drugs by qty and revenue."""
    clinic_id: str
    date: str
    revenue_by_hour: list[HourlyRevenue]
    peak_hour: Optional[HourlyRevenue] = None
    top_drugs_by_qty: list[DrugRanking]
    top_drugs_by_revenue: list[DrugRanking]


# ── Narrative Response ─────────────────────────────────────────────────────────

class TracedFigure(BaseModel):
    """A figure in the narrative mapped back to its source in the report."""
    display_value: str  # e.g. "₹42,850"
    source_field: str   # e.g. "total_billed"
    source_label: str   # e.g. "total_billed" (human-readable label for UI)


class NarrativeResponse(BaseModel):
    """LLM-generated narrative with figure tracing for grounding verification."""
    clinic_id: str
    date: str
    narrative: str
    traced_figures: list[TracedFigure]
    status: str = "success"  # "success" or "error"
    error_message: Optional[str] = None


# ── API Response Wrappers ──────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response from uploading a billing log."""
    message: str
    clinic_id: str
    date: str
    valid_records: int
    rejected_records: int
    validation_errors: list[RowValidationError]


class AvailableDate(BaseModel):
    """An available date for a clinic."""
    clinic_id: str
    date: str
    record_count: int
