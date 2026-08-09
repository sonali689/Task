# SwasthiQ — EOD Billing & Analytics Agent

A Python REST API + React frontend that ingests clinic billing logs and produces:
1. **Deterministic EOD Reconciliation** — total billed, collected, outstanding, refunds (split by payment mode)
2. **Analytics** — revenue by hour, top medicines by quantity and revenue
3. **AI Narrative Summary** — LLM-generated WhatsApp-friendly summary with every figure traced back to the deterministic report

## Architecture

```
┌─────────────┐     JSON upload     ┌──────────────────────────┐
│   React UI  │ ◄──────────────────► │    FastAPI Backend        │
│  (Vite)     │     REST API         │                          │
│             │                      │  ┌────────────────────┐  │
│  Screen 1:  │  GET /reconciliation │  │  Validator          │  │
│  Reconcile  │ ◄───────────────────►│  │  (Pydantic schemas) │  │
│             │                      │  └────────────────────┘  │
│  Screen 2:  │  GET /analytics      │  ┌────────────────────┐  │
│  Analytics  │ ◄───────────────────►│  │  Reconciliation     │  │
│             │                      │  │  (deterministic)    │  │
│  Screen 3:  │  POST /narrative     │  └────────────────────┘  │
│  Narrative  │ ◄───────────────────►│  ┌────────────────────┐  │
│             │                      │  │  Analytics          │  │
└─────────────┘                      │  │  (deterministic)    │  │
                                     │  └────────────────────┘  │
                                     │  ┌────────────────────┐  │
                                     │  │  Narrative          │  │
                                     │  │  (LLM + tracing)   │  │
                                     │  └────────────────────┘  │
                                     │  ┌────────────────────┐  │
                                     │  │  SQLite Storage     │  │
                                     │  └────────────────────┘  │
                                     └──────────────────────────┘
```

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLite
- **Frontend**: React 18, Vite, Recharts, React Router v6
- **LLM**: Google Gemini (default), OpenAI, or Anthropic (configurable)
- **Tests**: pytest (58 tests covering all 3 dataset days + edge cases)

---

## REST API Contracts

### `POST /api/billing/upload`
Upload a billing log JSON file.

**Request**: `multipart/form-data` with `file` field (JSON file)

**Response** (`200 OK`):
```json
{
  "message": "File uploaded successfully. 18 records processed.",
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "valid_records": 18,
  "rejected_records": 1,
  "validation_errors": [
    {
      "row_index": 18,
      "visit_id": "V-20260727-019",
      "field": "payment_mode",
      "message": "Row 18 (visit V-20260727-019): field 'payment_mode' — Field required."
    }
  ]
}
```

**Error** (`400`): Invalid JSON format  
**Error** (`422`): All rows malformed

---

### `GET /api/billing/{clinic_id}/{date}/reconciliation`
Get the deterministic reconciliation report.

**Response** (`200 OK`):
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "total_billed_paise": 326000,
  "total_collected_paise": 317200,
  "outstanding_paise": 8800,
  "total_refunds_paise": 0,
  "total_visits": 18,
  "refund_count": 0,
  "pending_visits": 3,
  "payment_mode_breakdown": [
    { "mode": "cash", "billed_paise": 129000, "collected_paise": 127000, "outstanding_paise": 2000 },
    { "mode": "card", "billed_paise": 107000, "collected_paise": 79700, "outstanding_paise": 27300 },
    { "mode": "upi", "billed_paise": 90000, "collected_paise": 110500, "outstanding_paise": -20500 }
  ],
  "validation_errors": []
}
```

---

### `GET /api/billing/{clinic_id}/{date}/analytics`
Get the deterministic analytics report.

**Response** (`200 OK`):
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "revenue_by_hour": [
    { "hour": 9, "hour_label": "9am", "revenue_paise": 9000 },
    { "hour": 10, "hour_label": "10am", "revenue_paise": 56500 }
  ],
  "peak_hour": { "hour": 13, "hour_label": "1pm", "revenue_paise": 75500 },
  "top_drugs_by_qty": [
    { "rank": 1, "drug_name": "OMEPRAZOLE", "value": 18, "display_value": "18 units" }
  ],
  "top_drugs_by_revenue": [
    { "rank": 1, "drug_name": "ATORVASTATIN", "value": 120000, "display_value": "₹1,200" }
  ]
}
```

---

### `POST /api/billing/{clinic_id}/{date}/narrative`
Generate LLM narrative summary with figure tracing.

**Response** (`200 OK`):
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "narrative": "Good evening! Here's today's summary...",
  "traced_figures": [
    { "display_value": "₹3,260", "source_field": "total_billed", "source_label": "total_billed" },
    { "display_value": "₹3,172", "source_field": "total_collected", "source_label": "total_collected" }
  ],
  "status": "success",
  "error_message": null
}
```

---

### `GET /api/billing/dates`
List all uploaded clinic+date combinations.

### `GET /api/health`
Health check endpoint.

---

## Data Consistency Design

### How the pipeline ensures data consistency:

1. **Validation Layer** (`validator.py`): Every row is validated against the `BillingRecord` Pydantic schema before entering the pipeline. Malformed rows (e.g., missing `payment_mode`, invalid `amount_paid_paise` sign) are **rejected with actionable errors** — they never reach the computation layer.

2. **Integer Paise Throughout**: All monetary values are stored and computed as integer paise (1 rupee = 100 paise). This eliminates floating-point precision errors. Conversion to rupees happens **only** at the display/frontend layer.

3. **Deterministic Layer** (`reconciliation.py`, `analytics.py`): These modules **never call an LLM**. They are pure functions that compute totals, breakdowns, and rankings from validated records. They are the ground truth.

4. **Atomic Storage** (`database.py`): Uploads are transactional — if a re-upload occurs for the same clinic+date, the old data and cached reports are atomically replaced. SQLite WAL mode ensures consistency.

5. **LLM Grounding** (`narrative.py`): The LLM prompt provides **only pre-computed figures** as input and instructs the model to use nothing else. The `traced_figures` array maps every number in the narrative back to its deterministic source field. If the LLM fails or returns garbage, a deterministic fallback narrative is used instead.

6. **Idempotent Re-computation**: Uploading the same file twice produces identical results. Reports are cached in SQLite after the first computation.

---

## Edge Cases Handled

| Edge Case | File | Handling |
|---|---|---|
| All refunds, no sales | `billing_log_2026-07-25.json` | Zero billed/collected, correct refund total |
| Empty day (no records) | `billing_log_2026-07-26.json` | All-zero report, no crash |
| Missing `payment_mode` | `billing_log_2026-07-27.json` (V-019) | Row rejected with actionable error |
| Drug name typo ("PARACETMOL") | `billing_log_2026-07-27.json` (V-009) | Accepted as-is (valid schema-wise) |
| `amount_paid ≠ line items total` | `billing_log_2026-07-27.json` (V-016) | Accepted — `amount_paid` is what was collected |

---

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # Set your LLM API key
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

---

## Project Structure

```
/backend
├── app/
│   ├── main.py              # FastAPI endpoints
│   ├── models.py            # Pydantic schemas
│   ├── validator.py         # Input validation
│   ├── reconciliation.py    # Deterministic reconciliation
│   ├── analytics.py         # Deterministic analytics
│   ├── narrative.py         # LLM narrative + figure tracing
│   └── database.py          # SQLite storage
├── tests/
│   ├── test_validator.py
│   ├── test_reconciliation.py
│   ├── test_analytics.py
│   └── test_narrative.py
├── requirements.txt
└── .env.example

/frontend
├── src/
│   ├── App.jsx              # Main app shell + routing
│   ├── main.jsx             # Entry point
│   ├── index.css            # Complete design system
│   ├── api/client.js        # Backend API client
│   ├── components/
│   │   ├── Sidebar.jsx      # Persistent navigation
│   │   ├── StatCard.jsx     # Reusable stat card
│   │   └── PaymentTable.jsx # Payment mode breakdown
│   └── pages/
│       ├── Upload.jsx       # File upload page
│       ├── Reconciliation.jsx  # Screen 1
│       ├── Analytics.jsx       # Screen 2
│       └── Narrative.jsx       # Screen 3
├── package.json
└── vite.config.js
```
