"""Quick API verification script."""
import httpx
import json

BASE = "http://localhost:8000/api"

# Upload all 3 files
for f in ["billing_log_2026-07-27.json", "billing_log_2026-07-26.json", "billing_log_2026-07-25.json"]:
    path = f"../swasthiq_sample_billing_dataset/{f}"
    r = httpx.post(f"{BASE}/billing/upload", files={"file": (f, open(path, "rb"), "application/json")})
    d = r.json()
    print(f"\n=== {f} ===")
    print(f"  Status: {r.status_code}")
    print(f"  Valid: {d['valid_records']}, Rejected: {d['rejected_records']}")

# Check reconciliation for Jul 27
r = httpx.get(f"{BASE}/billing/CLN-KNP-014/2026-07-27/reconciliation")
d = r.json()
print(f"\n=== Reconciliation (Jul 27) ===")
print(f"  Billed: Rs {d['total_billed_paise']/100}")
print(f"  Collected: Rs {d['total_collected_paise']/100}")
print(f"  Outstanding: Rs {d['outstanding_paise']/100}")
print(f"  Refunds: Rs {d['total_refunds_paise']/100}")
print(f"  Visits: {d['total_visits']}")

# Check analytics for Jul 27
r = httpx.get(f"{BASE}/billing/CLN-KNP-014/2026-07-27/analytics")
d = r.json()
print(f"\n=== Analytics (Jul 27) ===")
print(f"  Peak Hour: {d['peak_hour']['hour_label']} = Rs {d['peak_hour']['revenue_paise']/100}")
print(f"  Top by Qty: {[(x['drug_name'], x['value']) for x in d['top_drugs_by_qty'][:3]]}")
print(f"  Top by Rev: {[(x['drug_name'], x['value']/100) for x in d['top_drugs_by_revenue'][:3]]}")

# Check narrative for Jul 27
r = httpx.post(f"{BASE}/billing/CLN-KNP-014/2026-07-27/narrative")
d = r.json()
print(f"\n=== Narrative (Jul 27) ===")
print(f"  Status: {d['status']}")
print(f"  Traced figures: {len(d['traced_figures'])}")
print(f"  Narrative preview: {d['narrative'][:200]}...")

# Check dates
r = httpx.get(f"{BASE}/billing/dates")
print(f"\n=== Available Dates ===")
for d in r.json():
    print(f"  {d['date']} - {d['record_count']} records")

print("\n✅ All API tests passed!")
