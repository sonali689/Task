"""
FastAPI application — EOD Billing & Analytics Agent.

Exposes REST endpoints for billing log upload, deterministic
reconciliation, analytics, and LLM narrative generation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .analytics import compute_analytics
from .database import (
    cache_analytics,
    cache_reconciliation,
    get_available_dates,
    get_cached_analytics,
    get_cached_reconciliation,
    get_db,
    init_db,
    store_records,
    store_upload,
)
from .models import (
    AnalyticsReport,
    AvailableDate,
    NarrativeResponse,
    ReconciliationReport,
    RowValidationError,
    UploadResponse,
)
from .narrative import generate_narrative
from .reconciliation import compute_reconciliation
from .validator import parse_billing_json, validate_billing_log

load_dotenv()

app = FastAPI(
    title="SwasthiQ EOD Billing & Analytics Agent",
    description="REST API for clinic billing reconciliation, analytics, and AI narrative summaries.",
    version="1.0.0",
)

# CORS — allow frontend dev server
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Initialize database on startup."""
    init_db()


# ── Upload Endpoint ────────────────────────────────────────────────────────────

@app.post("/api/billing/upload", response_model=UploadResponse)
async def upload_billing_log(file: UploadFile = File(...)):
    """
    Upload a clinic's daily billing log JSON file.

    Validates each row, stores valid records, and computes
    reconciliation + analytics immediately. Malformed rows are
    rejected with specific, actionable errors — not a generic 500.
    """
    # Read and parse JSON
    content = await file.read()
    raw_data, parse_error = parse_billing_json(content)
    if parse_error:
        raise HTTPException(status_code=400, detail=parse_error)

    # Validate all rows
    validation = validate_billing_log(raw_data)

    # Handle empty file (valid — it's just a no-activity day)
    if validation.valid_count == 0 and validation.error_count == 0:
        # Empty array — still a valid upload (no transactions that day)
        clinic_id = "CLN-KNP-014"  # Default clinic if empty
        date_str = _extract_date_from_filename(file.filename) or datetime.utcnow().strftime("%Y-%m-%d")

        with get_db() as conn:
            upload_id = store_upload(
                conn, clinic_id, date_str, content.decode("utf-8"),
                0, 0, "[]",
            )
            # Cache empty reports
            empty_recon = compute_reconciliation([], clinic_id, date_str)
            empty_analytics = compute_analytics([], clinic_id, date_str)
            cache_reconciliation(conn, clinic_id, date_str, empty_recon.model_dump_json())
            cache_analytics(conn, clinic_id, date_str, empty_analytics.model_dump_json())

        return UploadResponse(
            message="File uploaded successfully. No billing records found for this day.",
            clinic_id=clinic_id,
            date=date_str,
            valid_records=0,
            rejected_records=0,
            validation_errors=[],
        )

    if validation.valid_count == 0:
        # All rows were malformed — return errors but don't store
        raise HTTPException(
            status_code=422,
            detail={
                "message": "All rows in the billing log are malformed.",
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    # Extract clinic_id and date from the first valid record
    first = validation.valid_records[0]
    clinic_id = first.clinic_id
    date_str = first.timestamp.strftime("%Y-%m-%d")

    # Store in database
    with get_db() as conn:
        upload_id = store_upload(
            conn, clinic_id, date_str, content.decode("utf-8"),
            validation.valid_count, validation.error_count,
            json.dumps([e.model_dump() for e in validation.errors]),
        )
        store_records(conn, upload_id, validation.valid_records)

        # Compute and cache reports
        recon = compute_reconciliation(
            validation.valid_records, clinic_id, date_str,
            validation.errors,
        )
        analytics = compute_analytics(
            validation.valid_records, clinic_id, date_str,
        )
        cache_reconciliation(conn, clinic_id, date_str, recon.model_dump_json())
        cache_analytics(conn, clinic_id, date_str, analytics.model_dump_json())

    return UploadResponse(
        message=f"File uploaded successfully. {validation.valid_count} records processed.",
        clinic_id=clinic_id,
        date=date_str,
        valid_records=validation.valid_count,
        rejected_records=validation.error_count,
        validation_errors=validation.errors,
    )


# ── Reconciliation Endpoint ────────────────────────────────────────────────────

@app.get("/api/billing/{clinic_id}/{date}/reconciliation", response_model=ReconciliationReport)
async def get_reconciliation(clinic_id: str, date: str):
    """
    Get the deterministic EOD reconciliation report for a clinic on a given date.
    """
    with get_db() as conn:
        cached = get_cached_reconciliation(conn, clinic_id, date)
        if not cached:
            raise HTTPException(
                status_code=404,
                detail=f"No billing data found for clinic '{clinic_id}' on {date}. Upload a billing log first.",
            )
        return json.loads(cached)


# ── Analytics Endpoint ─────────────────────────────────────────────────────────

@app.get("/api/billing/{clinic_id}/{date}/analytics", response_model=AnalyticsReport)
async def get_analytics(clinic_id: str, date: str):
    """
    Get the deterministic analytics report for a clinic on a given date.
    """
    with get_db() as conn:
        cached = get_cached_analytics(conn, clinic_id, date)
        if not cached:
            raise HTTPException(
                status_code=404,
                detail=f"No billing data found for clinic '{clinic_id}' on {date}. Upload a billing log first.",
            )
        return json.loads(cached)


# ── Narrative Endpoint ─────────────────────────────────────────────────────────

@app.post("/api/billing/{clinic_id}/{date}/narrative", response_model=NarrativeResponse)
async def get_narrative(clinic_id: str, date: str):
    """
    Generate an LLM narrative summary from the deterministic report.

    The narrative is grounded in the reconciliation + analytics data.
    Every figure traces back to a specific report field.
    """
    with get_db() as conn:
        recon_json = get_cached_reconciliation(conn, clinic_id, date)
        analytics_json = get_cached_analytics(conn, clinic_id, date)

    if not recon_json or not analytics_json:
        raise HTTPException(
            status_code=404,
            detail=f"No billing data found for clinic '{clinic_id}' on {date}. Upload a billing log first.",
        )

    recon = ReconciliationReport.model_validate_json(recon_json)
    analytics = AnalyticsReport.model_validate_json(analytics_json)

    result = await generate_narrative(recon, analytics)
    return result


# ── Available Dates Endpoint ───────────────────────────────────────────────────

@app.get("/api/billing/dates", response_model=list[AvailableDate])
async def list_dates():
    """List all available clinic+date combinations."""
    with get_db() as conn:
        return get_available_dates(conn)


# ── Health Check ───────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "SwasthiQ EOD Billing Agent"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_date_from_filename(filename: str | None) -> str | None:
    """Try to extract a date from filename like 'billing_log_2026-07-27.json'."""
    if not filename:
        return None
    import re
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else None
