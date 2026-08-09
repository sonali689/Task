# SwasthiQ — EOD Billing & Analytics Agent

A full-stack application that ingests daily clinic billing logs and produces:
1. **Deterministic EOD Reconciliation** — total billed, collected, outstanding, refunds (split by payment mode)
2. **Analytics Dashboard** — revenue by hour-of-day, top medicines by quantity and revenue
3. **AI Narrative Summary** — LLM-generated WhatsApp-friendly summary where every figure is traced back to its source in the deterministic report

> Built for the SwasthiQ hiring assignment — Kaagazy Technologies Private Limited.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLite (WAL mode) |
| **Frontend** | React 18, Vite, Recharts, React Router v6 |
| **LLM** | Google Gemini 1.5 Flash (default), OpenAI, or Anthropic (configurable) |
| **Tests** | pytest — 58 tests covering all 3 dataset days + edge cases |

---

## Architecture

```
┌─────────────────┐     JSON upload     ┌──────────────────────────────────────┐
│   React UI      │ ◄──────────────────►│         FastAPI Backend              │
│   (Vite)        │     REST API        │                                      │
│                 │                     │  ┌──────────────┐  ┌──────────────┐  │
│  Upload Page    │  POST /upload       │  │  Validator    │  │  SQLite      │  │
│                 │ ───────────────────►│  │  (Pydantic)   │  │  Storage     │  │
│  Screen 1:      │  GET /reconciliation│  └──────┬───────┘  └──────────────┘  │
│  Reconciliation │ ◄──────────────────►│         ▼                            │
│                 │                     │  ┌──────────────┐  ┌──────────────┐  │
│  Screen 2:      │  GET /analytics     │  │ Reconciliation│  │  Analytics   │  │
│  Analytics      │ ◄──────────────────►│  │ (deterministic)│ │ (deterministic)│
│                 │                     │  └──────────────┘  └──────────────┘  │
│  Screen 3:      │  POST /narrative    │  ┌──────────────────────────────────┐│
│  Narrative      │ ◄──────────────────►│  │  Narrative (LLM + figure tracing)││
│                 │                     │  └──────────────────────────────────┘│
└─────────────────┘                     └──────────────────────────────────────┘
```

**Data flow**: Upload → Validate → Store → Compute (reconciliation + analytics) → Cache → Serve via API → Render in React UI → LLM narrative generated on demand from cached deterministic data.

---

## REST API Contracts

### 1. `POST /api/billing/upload`

Upload a clinic's daily billing log JSON file.

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

**Error Responses**:
- `400` — Invalid JSON (parse error with line/column info)
- `422` — All rows malformed (returns all errors)

---

### 2. `GET /api/billing/{clinic_id}/{date}/reconciliation`

Returns the deterministic EOD reconciliation report. All values in integer **paise** (1 rupee = 100 paise).

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
    { "mode": "upi",  "billed_paise": 90000,  "collected_paise": 110500, "outstanding_paise": -20500 }
  ],
  "validation_errors": []
}
```

**Reconciliation definitions**:
- **Total Billed** = Σ (qty × unit_price_paise) across all line_items, for non-refund visits only
- **Total Collected** = Σ amount_paid_paise for non-refund visits only
- **Outstanding** = Total Billed − Total Collected
- **Refunds** = Σ |amount_paid_paise| for refund rows (always displayed as positive)
- **Pending Visits** = count of non-refund visits where amount_paid < billed

---

### 3. `GET /api/billing/{clinic_id}/{date}/analytics`

Returns the deterministic analytics report. Only non-refund records are included.

**Response** (`200 OK`):
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "revenue_by_hour": [
    { "hour": 9,  "hour_label": "9am",  "revenue_paise": 9000 },
    { "hour": 10, "hour_label": "10am", "revenue_paise": 56500 },
    { "hour": 11, "hour_label": "11am", "revenue_paise": 33500 },
    { "hour": 12, "hour_label": "12pm", "revenue_paise": 9500 },
    { "hour": 13, "hour_label": "1pm",  "revenue_paise": 75500 }
  ],
  "peak_hour": { "hour": 13, "hour_label": "1pm", "revenue_paise": 75500 },
  "top_drugs_by_qty": [
    { "rank": 1, "drug_name": "OMEPRAZOLE",  "value": 18, "display_value": "18 units" },
    { "rank": 2, "drug_name": "PARACETAMOL", "value": 11, "display_value": "11 units" }
  ],
  "top_drugs_by_revenue": [
    { "rank": 1, "drug_name": "ATORVASTATIN", "value": 120000, "display_value": "₹1,200" },
    { "rank": 2, "drug_name": "AMOXICILLIN",  "value": 66000,  "display_value": "₹660" }
  ]
}
```

**Analytics definitions**:
- **Revenue by Hour** = Σ amount_paid_paise grouped by hour of timestamp (non-refund only)
- **Peak Hour** = the hour bucket with the highest revenue
- **Top Drugs by Quantity** = ranked by Σ qty across all line_items (non-refund only)
- **Top Drugs by Revenue** = ranked by Σ (qty × unit_price_paise) across all line_items (non-refund only)

---

### 4. `POST /api/billing/{clinic_id}/{date}/narrative`

Generate an LLM narrative summary from the deterministic report. Every figure is traced.

**Response** (`200 OK`):
```json
{
  "clinic_id": "CLN-KNP-014",
  "date": "2026-07-27",
  "narrative": "Good evening! Here's today's summary for Mehta Clinic (2026-07-27):\n\n₹3,260 billed across 18 visits, ₹3,172 collected (97%).\n₹88 is still outstanding across 3 visits...",
  "traced_figures": [
    { "display_value": "₹3,260",       "source_field": "total_billed",       "source_label": "total_billed" },
    { "display_value": "₹3,172",       "source_field": "total_collected",    "source_label": "total_collected" },
    { "display_value": "₹88",          "source_field": "outstanding",        "source_label": "outstanding" },
    { "display_value": "₹0",           "source_field": "refunds",            "source_label": "refunds" },
    { "display_value": "1pm–2pm / ₹755", "source_field": "revenue_by_hour[max]", "source_label": "revenue_by_hour[max]" },
    { "display_value": "OMEPRAZOLE / 18",     "source_field": "top_drug_by_qty",     "source_label": "top_drug_by_qty" },
    { "display_value": "ATORVASTATIN / ₹1,200", "source_field": "top_drug_by_revenue", "source_label": "top_drug_by_revenue" }
  ],
  "status": "success",
  "error_message": null
}
```

`status` can be `"success"` (LLM worked), `"fallback"` (used deterministic template), or `"error"`.

---

### 5. `GET /api/billing/dates`

List all uploaded clinic+date combinations.

### 6. `GET /api/health`

Health check endpoint.

---

## Data Consistency Design

The pipeline is designed so that **no LLM-generated content can corrupt the numbers**. Here's how:

### 1. Strict Input Validation (`validator.py`)

Every row is validated against a Pydantic `BillingRecord` schema before it enters the computation layer. Validation rules include:

- Required fields: `clinic_id`, `visit_id`, `timestamp`, `doctor_id`, `line_items`, `payment_mode`, `amount_paid_paise`
- `payment_mode` must be one of: `cash`, `card`, `upi`
- `line_items` must be non-empty; each item needs `drug_name` (non-empty), `qty` (> 0), `unit_price_paise` (≥ 0)
- **Sign convention enforced**: refund rows must have negative `amount_paid_paise`; non-refund rows must have non-negative
- Malformed rows are **skipped with actionable per-field errors** — they never reach the computation layer. Valid rows in the same file are still processed.

### 2. Integer Paise Throughout

All monetary values are stored, transmitted, and computed as **integer paise** (1 rupee = 100 paise). This completely eliminates floating-point precision errors that plague `float`-based currency. Conversion to rupees for display happens **only** at the frontend layer (`formatRupees()` in `client.js`) and in display-only string fields.

### 3. Deterministic Computation Layer (`reconciliation.py`, `analytics.py`)

These modules are **pure functions** that take validated records and return computed reports. They:
- **Never call an LLM** — they are the ground truth
- Use only simple arithmetic: sums, counts, max, sorting
- Are the single source of truth for all figures shown in the UI

### 4. Atomic Storage (`database.py`)

- Uploads are transactional — if a re-upload occurs for the same clinic+date, the old data, cached reconciliation, and cached analytics are **atomically replaced** within a single SQLite transaction
- SQLite WAL mode ensures readers don't block writers
- Pre-computed reports are cached in `reconciliation_cache` and `analytics_cache` tables for instant retrieval

### 5. LLM Grounding (`narrative.py`)

The LLM never sees raw billing data. Instead:
- The prompt provides **only pre-computed figures** from the deterministic report
- The prompt explicitly instructs: *"Use ONLY the figures provided. Do NOT invent, approximate, or calculate."*
- The `traced_figures` array maps every key number back to its source field (e.g., `"₹3,260"` → `total_billed`)
- If the LLM is unavailable or returns garbage (< 20 chars), a **deterministic template-based fallback** is used automatically
- The narrative page shows traced figures alongside the text for manual verification

### 6. Idempotent Re-computation

Uploading the same file twice produces **identical results**. The pipeline is deterministic: same input → same validation → same reconciliation → same analytics → same cached reports.

---

## Edge Cases in the Sample Dataset

The assignment includes intentional edge cases. Here's each one and how it's handled:

| # | Edge Case | File | Record | How It's Handled |
|---|---|---|---|---|
| 1 | **Empty day** — no transactions | `billing_log_2026-07-26.json` | `[]` | All-zero report created, no crash, no division-by-zero |
| 2 | **Refund-only day** — no sales | `billing_log_2026-07-25.json` | All 3 records | `total_billed = 0`, `total_collected = 0`, correct `refunds = ₹490`, analytics shows no data |
| 3 | **Missing required field** (`payment_mode`) | `billing_log_2026-07-27.json` | V-019 | Row rejected with `"field 'payment_mode' — Field required."`, other 18 rows processed normally |
| 4 | **Drug name typo** ("PARACETMOL") | `billing_log_2026-07-27.json` | V-009 | Accepted as-is — valid schema-wise. Appears as separate drug in rankings. System ingests what it receives; fuzzy matching would risk silent data corruption |
| 5 | **Amount paid ≠ line items total** | `billing_log_2026-07-27.json` | V-004, V-016, etc. | Both tracked independently: `billed` = line_items sum, `collected` = amount_paid. Difference captured as `outstanding`. Reflects real-world discounts, negotiation, partial payments |
| 6 | **Negative amounts on refunds** | `billing_log_2026-07-25.json` | All records | Validator enforces: `is_refund=true` ⟹ `amount_paid_paise < 0`. Reconciliation uses `abs()` for display. A refund with positive amount is **rejected** |
| 7 | **Discounts applied** | `billing_log_2026-07-27.json` | V-002, V-003, V-006, etc. | `discount_paise` is stored for audit but doesn't enter reconciliation formula — `outstanding = billed - collected` naturally captures the gap |

---

## Quick Start

### Backend

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env    # Then set your GEMINI_API_KEY
python -m uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The React app will open at `http://localhost:5173`. It proxies API requests to the backend via Vite's dev server.

### Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

All 58 tests should pass:
- `test_validator.py` — 10 tests (JSON parsing, schema validation, error cases)
- `test_reconciliation.py` — 14 tests (Jul 27 busy day, Jul 25 refund-only, Jul 26 empty)
- `test_analytics.py` — 16 tests (revenue by hour, drug rankings, edge cases)
- `test_narrative.py` — 10 tests (figure tracing, fallback narrative, prompt construction)

---

## Project Structure

```
/backend
├── app/
│   ├── main.py              # FastAPI endpoints (upload, reconciliation, analytics, narrative)
│   ├── models.py            # Pydantic schemas — all monetary values in integer paise
│   ├── validator.py         # Input validation — row-level errors, never crashes
│   ├── reconciliation.py    # Deterministic reconciliation — never calls LLM
│   ├── analytics.py         # Deterministic analytics — never calls LLM
│   ├── narrative.py         # LLM narrative + figure tracing + fallback
│   └── database.py          # SQLite storage — atomic upserts, WAL mode
├── tests/
│   ├── test_validator.py
│   ├── test_reconciliation.py
│   ├── test_analytics.py
│   └── test_narrative.py
├── requirements.txt
└── .env.example

/frontend
├── src/
│   ├── App.jsx              # Main app shell + routing + date selection
│   ├── main.jsx             # Entry point
│   ├── index.css            # Complete design system
│   ├── api/client.js        # Backend API client + formatRupees()
│   ├── components/
│   │   ├── Sidebar.jsx      # Persistent navigation sidebar
│   │   ├── StatCard.jsx     # Reusable stat card component
│   │   └── PaymentTable.jsx # Payment mode breakdown table
│   └── pages/
│       ├── Upload.jsx       # File upload with drag-and-drop
│       ├── Reconciliation.jsx  # Screen 1: EOD Reconciliation
│       ├── Analytics.jsx       # Screen 2: Revenue & Drug Analytics
│       └── Narrative.jsx       # Screen 3: AI Summary + Traced Figures
├── package.json
└── vite.config.js

/swasthiq_sample_billing_dataset
├── billing_log_2026-07-25.json  # Edge case: refund-only day
├── billing_log_2026-07-26.json  # Edge case: empty day
├── billing_log_2026-07-27.json  # Normal day + missing field + drug typo
└── README.md
```

---

## LLM Configuration

The narrative endpoint supports three LLM providers. Set `LLM_PROVIDER` in `.env`:

| Provider | Env Var | Default Model |
|---|---|---|
| Google Gemini *(default)* | `GEMINI_API_KEY` | `gemini-1.5-flash` |
| OpenAI | `OPENAI_API_KEY` | `gpt-3.5-turbo` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-haiku` |

If no API key is configured, the system uses a **deterministic template-based fallback** that produces the same narrative from the same data every time.
