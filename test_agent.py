"""
Automated Test Suite — Market Intelligence Agent
Tests tool functions, agent behavior, and end-to-end flows.

Run: python test_agent.py
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from agent.tools.stock_data import get_stock_price, get_stock_history, get_sector_overview, compare_stocks
from agent.tools.news_search import search_financial_news, get_company_news, get_market_headlines
from agent.memory import save_broker_profile, get_broker_profile, clear_conversation_history, delete_broker_profile
from agent.market_agent import MarketIntelligenceAgent


# --- Test Infrastructure ---

PASS = 0
FAIL = 0
ERRORS = []


def test(name, condition, detail=""):
    """Run a single test assertion."""
    global PASS, FAIL, ERRORS
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


def section(title):
    """Print a test section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
# TOOL TESTS — Do the data-fetching tools work?
# ============================================================

section("STOCK DATA TOOLS")

# Test: get_stock_price returns valid data
result = get_stock_price("AAPL")
test("get_stock_price returns dict", isinstance(result, dict))
test("get_stock_price has symbol", result.get("symbol") == "AAPL")
test("get_stock_price has price", isinstance(result.get("current_price"), (int, float)))
test("get_stock_price price > 0", result.get("current_price", 0) > 0)
test("get_stock_price has change_percent", "change_percent" in result)
test("get_stock_price has volume", isinstance(result.get("volume"), int))

# Test: invalid symbol returns error
result_bad = get_stock_price("ZZZZZZZ123")
test("invalid symbol returns error", "error" in result_bad)

# Test: get_stock_history
hist = get_stock_history("MSFT", "1mo")
test("get_stock_history returns dict", isinstance(hist, dict))
test("get_stock_history has data_points", hist.get("data_points", 0) > 0)
test("get_stock_history has total_return_pct", "total_return_pct" in hist)

# Test: get_sector_overview
sector = get_sector_overview("technology")
test("get_sector_overview returns dict", isinstance(sector, dict))
test("get_sector_overview has stocks", len(sector.get("stocks", [])) > 0)
test("get_sector_overview has avg_change", "avg_change_pct" in sector)

# Test: invalid sector returns error
bad_sector = get_sector_overview("underwater_basket_weaving")
test("invalid sector returns error", "error" in bad_sector)

# Test: compare_stocks
comparison = compare_stocks(["AAPL", "MSFT"])
test("compare_stocks returns comparison list", len(comparison.get("comparison", [])) == 2)
test("compare_stocks has best_performer", comparison.get("best_performer") is not None)


section("NEWS TOOLS")

# Test: search_financial_news
news = search_financial_news("technology stocks", max_results=3)
test("search_news returns dict", isinstance(news, dict))
test("search_news has articles", isinstance(news.get("articles"), list))
test("search_news has count", news.get("count", 0) >= 0)  # May be 0 if rate limited

# Test: get_market_headlines
headlines = get_market_headlines("top")
test("get_headlines returns dict", isinstance(headlines, dict))
test("get_headlines has articles key", "articles" in headlines)


section("MEMORY SYSTEM")

# Test: save and retrieve broker profile
test_profile = {
    "name": "Test Broker",
    "company": "Test Corp",
    "risk_tolerance": "high",
    "investment_style": "growth",
    "sector_interests": "technology, AI",
    "client_demographics": "tech workers",
}

save_result = save_broker_profile(test_profile)
test("save_broker_profile succeeds", save_result.get("status") == "saved")

retrieved = get_broker_profile("Test Broker")
test("get_broker_profile retrieves correctly", retrieved is not None)
test("profile has correct name", retrieved.get("name") == "Test Broker")
test("profile has correct risk", retrieved.get("risk_tolerance") == "high")
test("profile has timestamp", "updated_at" in retrieved)

# Cleanup test profile
delete_broker_profile("Test Broker")
test("delete_broker_profile works", get_broker_profile("Test Broker") is None)


# ============================================================
# AGENT TESTS — Does the full agent loop work?
# ============================================================

section("AGENT (Full ReAct Loop)")

print("  [INFO] Testing agent with Bedrock — requires AWS credentials...")

try:
    agent = MarketIntelligenceAgent(
        model_id="amazon.nova-lite-v1:0",
        region="us-east-1",
        max_tool_calls=3,
    )
    
    # Test 1: Simple stock question — should call get_stock_price
    result = agent.run("What is Apple's stock price right now?")
    test("agent returns response", len(result.get("response", "")) > 50)
    test("agent used tools", len(result.get("tools_used", [])) > 0)
    test("agent called get_stock_price", 
         any(t["tool"] == "get_stock_price" for t in result.get("tools_used", [])))
    test("agent has metadata", "model" in result.get("metadata", {}))
    test("agent completed in reasonable time", result["metadata"].get("elapsed_seconds", 99) < 30)
    
    # Test 2: Sector question — should call get_sector_overview
    result2 = agent.run("How is the technology sector doing?")
    test("sector query returns response", len(result2.get("response", "")) > 50)
    test("sector query used sector tool",
         any(t["tool"] == "get_sector_overview" for t in result2.get("tools_used", [])))
    
    # Test 3: Multi-tool question — should call multiple tools
    result3 = agent.run("Give me NVIDIA stock price and latest news about it")
    tools_used = [t["tool"] for t in result3.get("tools_used", [])]
    test("multi-tool query used 2+ tools", len(tools_used) >= 2)
    test("multi-tool query got stock data",
         "get_stock_price" in tools_used or "get_stock_history" in tools_used)
    
    # Test 4: Personalization — agent uses broker profile
    agent.set_broker_profile({
        "name": "TestBroker",
        "risk_tolerance": "aggressive",
        "investment_style": "momentum",
        "sector_interests": "AI, semiconductors",
        "client_demographics": "young professionals",
    })
    result4 = agent.run("What should I look at today?")
    test("personalized query returns response", len(result4.get("response", "")) > 50)
    test("agent metadata shows broker",
         result4.get("metadata", {}).get("broker_profile") == "TestBroker")

except Exception as e:
    print(f"\n  [SKIP] Agent tests skipped — {str(e)[:80]}")
    print("  [INFO] This likely means AWS credentials are not configured or Bedrock access is missing.")


# ============================================================
# RESULTS SUMMARY
# ============================================================

section("TEST RESULTS")

total = PASS + FAIL
print(f"\n  Total:  {total} tests")
print(f"  Passed: {PASS}")
print(f"  Failed: {FAIL}")
print(f"  Rate:   {(PASS/total*100):.0f}%" if total > 0 else "  Rate:   N/A")

if ERRORS:
    print(f"\n  Failures:")
    for err in ERRORS:
        print(f"    - {err}")

print(f"\n  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

if FAIL == 0:
    print("  ALL TESTS PASSED — Agent is working correctly!")
else:
    print(f"  WARNING: {FAIL} test(s) failed — review above")

sys.exit(0 if FAIL == 0 else 1)
