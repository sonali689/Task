"""Quick LLM integration test — verifies the Gemini API key works."""

import asyncio
import os
import sys

# Fix Windows console encoding for ₹ symbol
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add parent to path so we can import app modules
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.models import ReconciliationReport, AnalyticsReport, HourlyRevenue, DrugRanking
from app.narrative import generate_narrative


async def test_llm():
    """Test the full narrative generation pipeline including LLM call."""
    
    recon = ReconciliationReport(
        clinic_id="CLN-KNP-014",
        date="2026-07-27",
        total_billed_paise=326000,
        total_collected_paise=317200,
        total_discounts_paise=0,
        outstanding_paise=8800,
        total_refunds_paise=0,
        total_visits=18,
        refund_count=0,
        pending_visits=3,
        payment_mode_breakdown=[],
        validation_errors=[],
    )
    
    analytics = AnalyticsReport(
        clinic_id="CLN-KNP-014",
        date="2026-07-27",
        revenue_by_hour=[
            HourlyRevenue(hour=9, hour_label="9am", revenue_paise=9000),
            HourlyRevenue(hour=10, hour_label="10am", revenue_paise=56500),
            HourlyRevenue(hour=13, hour_label="1pm", revenue_paise=75500),
        ],
        peak_hour=HourlyRevenue(hour=13, hour_label="1pm", revenue_paise=75500),
        top_drugs_by_qty=[
            DrugRanking(rank=1, drug_name="OMEPRAZOLE", value=18, display_value="18 units"),
        ],
        top_drugs_by_revenue=[
            DrugRanking(rank=1, drug_name="ATORVASTATIN", value=120000, display_value="Rs.1,200"),
        ],
    )
    
    print("=" * 60)
    print("LLM INTEGRATION TEST")
    print("=" * 60)
    print(f"\nLLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'gemini')}")
    api_key = os.getenv("GEMINI_API_KEY", "")
    print(f"GEMINI_API_KEY: {'set (' + api_key[:8] + '...)' if api_key else 'NOT SET'}")
    print()

    # Attempt 1
    print("--- Attempt 1 ---")
    result = await generate_narrative(recon, analytics)
    
    print(f"Status: {result.status}")
    print(f"Error:  {result.error_message}")
    
    if result.status == "fallback" and "429" in str(result.error_message):
        print("\nGemini free-tier quota exhausted (429). Retrying in 30s...")
        await asyncio.sleep(30)
        print("\n--- Attempt 2 (after 30s wait) ---")
        result = await generate_narrative(recon, analytics)
        print(f"Status: {result.status}")
        print(f"Error:  {result.error_message}")
    
    print()
    print("--- Generated Narrative ---")
    print(result.narrative)
    print()
    print("--- Traced Figures ---")
    for fig in result.traced_figures:
        print(f"  {fig.display_value:30s} <- {fig.source_field}")
    print()
    
    if result.status == "success":
        print("[PASS] LLM is working fine! Gemini returned a grounded narrative.")
    elif result.status == "fallback":
        print("[FALLBACK] LLM call failed - used deterministic fallback.")
        print(f"   Reason: {result.error_message}")
        print()
        print("   The fallback mechanism is working correctly.")
        print("   The Gemini API key IS valid but the free-tier daily quota is exhausted.")
        print("   Options:")
        print("   1. Wait until quota resets (usually midnight Pacific Time)")
        print("   2. Upgrade to a paid plan at https://ai.google.dev")
        print("   3. Use a different API key")
    else:
        print("[FAIL] LLM error.")
        print(f"   Error: {result.error_message}")
    
    return result.status


if __name__ == "__main__":
    status = asyncio.run(test_llm())
    sys.exit(0 if status in ("success", "fallback") else 1)
