"""
Market Intelligence Agent — Streamlit UI
An AI-powered financial analysis copilot with real-time market data,
interactive charts, portfolio tracking, and personalized insights.

Run: python -m streamlit run streamlit_app.py
"""

import streamlit as st
import json
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from agent.market_agent import MarketIntelligenceAgent
from agent.memory import (
    save_broker_profile,
    get_broker_profile,
    list_broker_profiles,
    clear_conversation_history,
)
from agent.tools.stock_data import get_stock_price, get_sector_overview
from agent.tools.charts import create_stock_chart, create_comparison_chart, create_sector_bar_chart
from agent.tools.portfolio import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    get_portfolio_performance,
    clear_watchlist,
)
from agent.logger import get_run_stats, get_recent_runs
from agent.tools.report import generate_pdf_report


# --- Page Configuration (MUST be first Streamlit command) ---
st.set_page_config(
    page_title="Market Intelligence Agent | Quadra Systems",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Cached Data Fetchers (Bug #1 + #6 fix: avoid blocking page load) ---

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_market_snapshot():
    """Fetch market snapshot data with caching to avoid blocking page load."""
    snapshot = {}
    for ticker in ["NVDA", "AAPL", "MSFT", "GOOGL"]:
        try:
            data = get_stock_price(ticker)
            snapshot[ticker] = data
        except Exception:
            snapshot[ticker] = {"error": "unavailable"}
    # Check if US market is currently open (Mon-Fri, 9:30 AM - 4:00 PM ET)
    from datetime import timezone
    import pytz
    try:
        et = pytz.timezone("US/Eastern")
        now_et = datetime.now(et)
        market_open = (now_et.weekday() < 5 and 
                      now_et.hour >= 9 and now_et.hour < 16 and
                      not (now_et.hour == 9 and now_et.minute < 30))
        snapshot["_market_open"] = market_open
        snapshot["_last_updated"] = datetime.now().strftime("%H:%M")
    except Exception:
        snapshot["_market_open"] = None
        snapshot["_last_updated"] = datetime.now().strftime("%H:%M")
    return snapshot


@st.cache_data(ttl=120)  # Cache for 2 minutes
def get_cached_portfolio_performance():
    """Fetch portfolio performance with caching to avoid repeated yfinance calls."""
    return get_portfolio_performance()

# --- Custom CSS ---
st.markdown("""
<style>
    /* Global */
    .block-container { padding-top: 2rem; }
    
    /* Bigger text everywhere */
    .stMarkdown p, .stMarkdown li { font-size: 1.05rem; line-height: 1.7; }
    
    /* Hide anchor link icons on headings */
    [data-testid="StyledLinkIconContainer"],
    .stMarkdown a[href^="#"] {
        display: none !important;
    }
    
    /* Header */
    .app-header { text-align: center; padding: 1rem 0 0.5rem 0; }
    .app-title { font-size: 2.8rem; font-weight: 800; color: #00D4AA; margin: 0; }
    .app-subtitle { font-size: 1.15rem; color: #777; margin-top: 0.3rem; }
    
    /* Tool badges */
    .tool-badge {
        display: inline-block;
        background: #0D2818;
        color: #00D4AA;
        padding: 5px 14px;
        border-radius: 16px;
        font-size: 0.88rem;
        margin-right: 6px;
        margin-top: 8px;
        border: 1px solid #00D4AA44;
        font-weight: 500;
    }
    
    /* Status colors */
    .status-positive { color: #00D4AA; font-weight: 600; }
    .status-negative { color: #FF4757; font-weight: 600; }
    
    /* Bigger metrics */
    [data-testid="stMetricValue"] { font-size: 2rem !important; }
    [data-testid="stMetricLabel"] { font-size: 1.05rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.95rem !important; }
    
    /* Bigger tabs */
    .stTabs [data-baseweb="tab"] { font-size: 1.05rem; padding: 12px 24px; }
    
    /* Sidebar */
    [data-testid="stSidebar"] .stMarkdown h3 { font-size: 1.3rem; }
    [data-testid="stSidebar"] .stButton button { font-size: 1rem; padding: 0.65rem 1rem; }
    
    /* Chat input */
    .stChatInput textarea { font-size: 1.1rem; }
    
    /* Footer */
    .app-footer { text-align: center; color: #555; font-size: 0.9rem; padding: 2rem 0 1rem 0; border-top: 1px solid #2A3040; margin-top: 2rem; }
</style>
""", unsafe_allow_html=True)


# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "broker_profile" not in st.session_state:
    st.session_state.broker_profile = get_broker_profile()
if "agent_instance" not in st.session_state:
    st.session_state.agent_instance = None


# --- Sidebar ---
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.caption("Configure AI model and AWS region")
    
    with st.expander("Model & Region", expanded=False):
        region = st.selectbox("AWS Region", ["us-east-1", "us-west-2"], index=0,
                              help="AWS region where Bedrock models are accessed. us-east-1 has the most model availability.")
        model_id = st.selectbox(
            "Bedrock Model",
            ["amazon.nova-pro-v1:0", "amazon.nova-lite-v1:0"],
            index=0,
            help="Nova Pro = better analysis quality & instruction following (~$0.003/query). Nova Lite = faster & cheaper but less accurate on complex questions (~$0.001/query).",
        )
    
    st.markdown("---")
    st.markdown("### 👤 Broker Profile")
    st.caption("Your investment preferences — the AI tailors analysis to match your style")
    
    with st.expander("Edit Profile", expanded=st.session_state.broker_profile is None):
        broker_name = st.text_input("Name", value=(st.session_state.broker_profile or {}).get("name", ""),
                                    help="Your name or alias. Used for personalization and PDF reports.")
        broker_company = st.text_input("Company", value=(st.session_state.broker_profile or {}).get("company", ""),
                                       help="Your firm or company name. Optional — for report branding.")
        
        risk_options = ["low", "moderate", "high", "aggressive"]
        current_risk = (st.session_state.broker_profile or {}).get("risk_tolerance", "moderate")
        risk_tolerance = st.select_slider("Risk Tolerance", options=risk_options, value=current_risk,
                                          help="How much risk are you comfortable with? Low = safe dividends. Aggressive = high-growth, volatile stocks.")
        
        style_options = ["value", "growth", "dividend", "momentum", "balanced"]
        current_style = (st.session_state.broker_profile or {}).get("investment_style", "balanced")
        investment_style = st.selectbox("Investment Style", style_options, index=style_options.index(current_style),
                                        help="Value = underpriced stocks. Growth = fast-growing companies. Dividend = steady income. Momentum = riding trends. Balanced = mix of all.")
        
        sector_interests = st.text_input(
            "Sector Interests",
            value=(st.session_state.broker_profile or {}).get("sector_interests", ""),
            placeholder="AI, semiconductors, energy",
            help="Comma-separated sectors you care about. The agent will focus its analysis on these areas.",
        )
        
        if st.button("💾 Save Profile", use_container_width=True, help="Save your profile to personalize all AI analysis to your investment style"):
            if broker_name:
                profile = {"name": broker_name, "company": broker_company,
                           "risk_tolerance": risk_tolerance, "investment_style": investment_style,
                           "sector_interests": sector_interests}
                save_broker_profile(profile)
                st.session_state.broker_profile = profile
                st.success(f"✓ Saved for {broker_name}")
            else:
                st.warning("Enter a name")
    
    if st.session_state.broker_profile:
        p = st.session_state.broker_profile
        st.caption(f"**Active:** {p.get('name', '?')} • {p.get('investment_style', '?')} • {p.get('risk_tolerance', '?')} risk")
    
    st.markdown("---")
    st.markdown("### 🚀 Quick Queries")
    st.caption("One-click common questions — the agent will fetch live data and analyze")
    if st.button("📰 Today's Headlines", use_container_width=True, help="Ask the AI agent for today's top market news headlines"):
        st.session_state.quick_action = "What are today's top market headlines?"
    if st.button("🧠 AI Sector Analysis", use_container_width=True, help="Get a detailed analysis of AI/tech sector stocks with recommendations"):
        st.session_state.quick_action = "Give me a detailed AI sector analysis with top picks"
    if st.button("⚡ NVDA + AMD + INTC", use_container_width=True, help="Compare NVIDIA, AMD, and Intel side-by-side — which is the best buy?"):
        st.session_state.quick_action = "Compare NVDA, AMD, and INTC — which is the best buy right now?"
    if st.button("🌍 Market Overview", use_container_width=True, help="Get a broad overview of all major market sectors"):
        st.session_state.quick_action = "Give me a broad market overview across all major sectors"
    
    st.markdown("---")
    if st.button("🗑️ Clear Chat", use_container_width=True, help="Delete all chat messages and reset the agent's conversation memory"):
        st.session_state.messages = []
        st.session_state.agent_instance = None
        clear_conversation_history()
        st.rerun()
    
    st.markdown("---")
    st.caption("⚠️ Not financial advice. AI analysis may contain errors. Always verify with professional sources.")


# --- HEADER ---
st.markdown("""
<div class="app-header">
    <div class="app-title">📈 Market Intelligence Agent</div>
    <div class="app-subtitle">Agentic AI • Real-Time Market Data • Personalized Investment Analysis • Powered by Amazon Bedrock</div>
</div>
""", unsafe_allow_html=True)

st.markdown("")  # spacing

# --- Tabs ---
tab_chat, tab_charts, tab_portfolio, tab_stats = st.tabs([
    "💬  AI Chat", "📊  Charts", "💼  Portfolio", "📋  Stats"
])


# ============================================================
# TAB 1: AI CHAT
# ============================================================
with tab_chat:
    # Market snapshot (Bug #1 fix: cached, non-blocking)
    snapshot = get_market_snapshot()
    
    # Market status indicator
    market_open = snapshot.get("_market_open")
    last_updated = snapshot.get("_last_updated", "")
    if market_open is True:
        st.caption(f"🟢 US Market Open · Updated {last_updated}")
    elif market_open is False:
        st.caption(f"🔴 US Market Closed · Showing last close · Updated {last_updated}")
    
    col1, col2, col3, col4 = st.columns(4)
    for col, ticker in zip([col1, col2, col3, col4], ["NVDA", "AAPL", "MSFT", "GOOGL"]):
        with col:
            data = snapshot.get(ticker, {})
            if data and "error" not in data:
                st.metric(label=ticker, value=f"${data['current_price']:,.2f}",
                          delta=f"{data['change_percent']:+.2f}%")
            else:
                st.metric(label=ticker, value="—")
    
    st.markdown("")  # spacing
    
    # Onboarding — show welcome section when no messages exist
    if not st.session_state.messages:
        st.markdown("""
<div style="background: linear-gradient(135deg, #0D2818 0%, #1A2238 100%); border: 1px solid #00D4AA33; 
    border-radius: 16px; padding: 28px 32px; margin-bottom: 24px;">
    <h3 style="color: #00D4AA; margin: 0 0 12px 0; font-size: 1.5rem;">Welcome to your AI Market Analyst</h3>
    <p style="color: #AAA; font-size: 1.05rem; line-height: 1.7; margin: 0 0 16px 0;">
        I autonomously gather real-time market data and generate personalized investment insights. 
        Ask me anything about stocks, sectors, or market trends — I'll fetch live data and analyze it for you.
    </p>
    <p style="color: #777; font-size: 0.95rem; margin: 0 0 8px 0;"><strong style="color: #CCC;">Try asking:</strong></p>
    <ul style="color: #999; font-size: 0.95rem; line-height: 2; margin: 0; padding-left: 20px;">
        <li>"How is NVIDIA doing today?"</li>
        <li>"Compare AAPL, MSFT, and GOOGL — which should I buy?"</li>
        <li>"Give me an AI sector overview with top picks"</li>
        <li>"What are today's top market headlines?"</li>
        <li>"Analyze Tesla's performance over the last 3 months"</li>
    </ul>
    <p style="color: #555; font-size: 0.82rem; margin: 16px 0 0 0; font-style: italic;">
        💡 Set up your broker profile in the sidebar for personalized recommendations tailored to your risk appetite.
    </p>
</div>
        """, unsafe_allow_html=True)
    
    # Chat messages
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("tools_used"):
                tools_html = " ".join(f'<span class="tool-badge">🔧 {t["tool"]}</span>' for t in message["tools_used"])
                st.markdown(tools_html, unsafe_allow_html=True)
            if message["role"] == "assistant" and message.get("metadata"):
                col_details, col_pdf = st.columns([3, 1])
                with col_details:
                    with st.expander("📋 Technical Details"):
                        st.json(message["metadata"])
                with col_pdf:
                    # Bug #7 fix: only generate PDF on button click, not on every render
                    pdf_key = f"pdf_{idx}"
                    if pdf_key not in st.session_state:
                        st.session_state[pdf_key] = None
                    if st.button("📄 Generate PDF", key=f"gen_pdf_{idx}"):
                        try:
                            pdf_bytes = generate_pdf_report(
                                query=st.session_state.messages[idx-1]["content"] if idx > 0 else "",
                                response=message["content"],
                                tools_used=message.get("tools_used", []),
                                metadata=message.get("metadata", {}),
                                broker_name=(st.session_state.broker_profile or {}).get("name"),
                            )
                            st.session_state[pdf_key] = pdf_bytes
                        except Exception:
                            st.caption("PDF generation failed")
                    if st.session_state.get(pdf_key):
                        st.download_button(
                            "⬇️ Download",
                            data=st.session_state[pdf_key],
                            file_name=f"market_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{idx}",
                        )
    
    # Handle quick action
    if "quick_action" in st.session_state:
        prompt = st.session_state.pop("quick_action")
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("🔍 Gathering market intelligence..."):
                # Bug #2 fix: preserve conversation history when model changes
                # Only transfer text-based messages (not tool_use format) to avoid format conflicts
                old_history = None
                if st.session_state.agent_instance is not None and st.session_state.agent_instance.model_id != model_id:
                    old_history = [msg for msg in st.session_state.agent_instance.conversation_history 
                                   if msg.get("role") in ("user", "assistant") and 
                                   isinstance(msg.get("content"), list) and 
                                   len(msg["content"]) > 0 and "text" in msg["content"][0]]
                if st.session_state.agent_instance is None or st.session_state.agent_instance.model_id != model_id:
                    st.session_state.agent_instance = MarketIntelligenceAgent(model_id=model_id, region=region)
                    if old_history:
                        st.session_state.agent_instance.conversation_history = old_history
                agent = st.session_state.agent_instance
                if st.session_state.broker_profile:
                    agent.set_broker_profile(st.session_state.broker_profile)
                result = agent.run(prompt)
            st.markdown(result["response"])
            if result["tools_used"]:
                tools_html = " ".join(f'<span class="tool-badge">🔧 {t["tool"]}</span>' for t in result["tools_used"])
                st.markdown(tools_html, unsafe_allow_html=True)
            with st.expander("📋 Technical Details"):
                st.json(result["metadata"])
        st.session_state.messages.append({
            "role": "assistant", "content": result["response"],
            "tools_used": result["tools_used"], "metadata": result["metadata"],
        })
        st.rerun()
    
    # Chat input
    if prompt := st.chat_input("Ask about stocks, sectors, market news..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("🔍 Gathering market intelligence..."):
                # Bug #2 fix: preserve conversation history when model changes
                old_history = None
                if st.session_state.agent_instance is not None and st.session_state.agent_instance.model_id != model_id:
                    old_history = [msg for msg in st.session_state.agent_instance.conversation_history 
                                   if msg.get("role") in ("user", "assistant") and 
                                   isinstance(msg.get("content"), list) and 
                                   len(msg["content"]) > 0 and "text" in msg["content"][0]]
                if st.session_state.agent_instance is None or st.session_state.agent_instance.model_id != model_id:
                    st.session_state.agent_instance = MarketIntelligenceAgent(model_id=model_id, region=region)
                    if old_history:
                        st.session_state.agent_instance.conversation_history = old_history
                agent = st.session_state.agent_instance
                if st.session_state.broker_profile:
                    agent.set_broker_profile(st.session_state.broker_profile)
                result = agent.run(prompt)
            st.markdown(result["response"])
            if result["tools_used"]:
                tools_html = " ".join(f'<span class="tool-badge">🔧 {t["tool"]}</span>' for t in result["tools_used"])
                st.markdown(tools_html, unsafe_allow_html=True)
            with st.expander("📋 Technical Details"):
                st.json(result["metadata"])
        st.session_state.messages.append({
            "role": "assistant", "content": result["response"],
            "tools_used": result["tools_used"], "metadata": result["metadata"],
        })
        st.rerun()


# ============================================================
# TAB 2: CHARTS
# ============================================================
with tab_charts:
    st.markdown("#### 📊 Interactive Stock Charts")
    st.markdown("")
    
    chart_col1, chart_col2 = st.columns([3, 1])
    
    with chart_col2:
        st.markdown("**Stock Chart**")
        chart_symbol_raw = st.text_input("Ticker Symbol", value="NVDA", key="chart_sym",
                                         help="Enter a stock ticker symbol (e.g., NVDA, AAPL, TSLA, TATASTEEL.NS, RELIANCE.NS).").strip().upper()
        # Validate: allow letters, digits, and dots (for .NS, .HK, .L suffixes)
        chart_symbol = chart_symbol_raw if (len(chart_symbol_raw) >= 1 and len(chart_symbol_raw) <= 20 and all(c.isalpha() or c.isdigit() or c == '.' for c in chart_symbol_raw)) else "NVDA"
        if chart_symbol != chart_symbol_raw and chart_symbol_raw:
            st.caption("⚠️ Invalid ticker — showing NVDA")
        chart_period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=1, key="chart_per",
                                    help="How far back to show price history. 1mo = 1 month, 1y = 1 year, etc.")
        
        st.markdown("")
        st.markdown("**Compare Stocks**")
        compare_input = st.text_input("Tickers (comma-separated)", value="NVDA, MSFT, AMD, GOOGL", key="cmp",
                                      help="Enter 2-6 ticker symbols separated by commas to see their relative performance on one chart.")
        
        st.markdown("")
        st.markdown("**Sector Performance**")
        sector_choice = st.selectbox("Sector", ["ai", "technology", "semiconductor", "healthcare", "energy", "finance"], index=0, key="sec_chart",
                                     help="View today's performance of major stocks in this sector as a bar chart.")
    
    with chart_col1:
        try:
            fig = create_stock_chart(chart_symbol, chart_period)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.info(f"Enter a valid ticker symbol. Error: {e}")
    
    # Comparison
    st.markdown("")
    compare_symbols = [s.strip().upper() for s in compare_input.split(",") if s.strip()]
    if len(compare_symbols) >= 2:
        try:
            comp_fig = create_comparison_chart(compare_symbols, chart_period)
            st.plotly_chart(comp_fig, use_container_width=True)
        except Exception as e:
            st.info(f"Comparison unavailable: {e}")
    
    # Sector
    try:
        sector_data = get_sector_overview(sector_choice)
        if "error" not in sector_data:
            sector_fig = create_sector_bar_chart(sector_data)
            st.plotly_chart(sector_fig, use_container_width=True)
    except Exception:
        pass


# ============================================================
# TAB 3: PORTFOLIO
# ============================================================
with tab_portfolio:
    st.markdown("#### 💼 Portfolio Watchlist")
    st.caption("Track your stocks with real-time prices and profit/loss calculations.")
    st.markdown("")
    
    # Add stock form
    add_col1, add_col2, add_col3, add_col4 = st.columns([2, 1.5, 1.5, 1])
    with add_col1:
        new_symbol = st.text_input("Ticker", placeholder="e.g. NVDA", key="add_sym", label_visibility="collapsed",
                                   help="Stock ticker symbol to add to your watchlist (e.g., NVDA, AAPL, TSLA).")
    with add_col2:
        new_shares = st.number_input("Shares", min_value=0.0, value=0.0, step=1.0, key="add_shares",
                                     help="Number of shares you own. Enter 0 to just watch without tracking P&L.")
    with add_col3:
        new_price = st.number_input("Avg Buy Price ($)", min_value=0.0, value=0.0, step=1.0, key="add_price",
                                    help="Your average purchase price per share. Used to calculate profit/loss. Enter 0 if just watching.")
    with add_col4:
        st.markdown("")  # alignment spacer
        if st.button("➕ Add", use_container_width=True, key="add_btn"):
            if new_symbol.strip():
                # Validate ticker exists before adding
                clean_sym = new_symbol.strip().upper()
                if not all(c.isalpha() or c == '.' for c in clean_sym):
                    st.error("Invalid ticker symbol")
                else:
                    add_to_watchlist(clean_sym, new_shares, new_price)
                    get_cached_portfolio_performance.clear()
                    st.rerun()
            else:
                st.warning("Enter a ticker symbol")
    
    st.markdown("---")
    
    # Portfolio performance (Bug #6 fix: cached to avoid repeated yfinance calls)
    perf = get_cached_portfolio_performance()
    
    if perf.get("error"):
        st.info("👆 Add stocks above to start tracking your portfolio.")
        st.markdown("")
        st.markdown("**Quick start — add a sample portfolio:**")
        qc1, qc2, qc3 = st.columns(3)
        with qc1:
            if st.button("NVDA (10 @ $200)", use_container_width=True):
                add_to_watchlist("NVDA", 10, 200)
                get_cached_portfolio_performance.clear()
                st.rerun()
        with qc2:
            if st.button("AAPL (20 @ $180)", use_container_width=True):
                add_to_watchlist("AAPL", 20, 180)
                get_cached_portfolio_performance.clear()
                st.rerun()
        with qc3:
            if st.button("MSFT (15 @ $350)", use_container_width=True):
                add_to_watchlist("MSFT", 15, 350)
                get_cached_portfolio_performance.clear()
                st.rerun()
    else:
        # Summary row
        summary = perf.get("summary", {})
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.metric("💰 Invested", f"${summary.get('total_invested', 0):,.0f}")
        with sc2:
            st.metric("📈 Current Value", f"${summary.get('total_current_value', 0):,.0f}")
        with sc3:
            gl = summary.get('total_gain_loss', 0)
            gl_pct = summary.get('total_gain_loss_pct', 0)
            st.metric("📊 Total P&L", f"${gl:+,.0f}", delta=f"{gl_pct:+.1f}%")
        with sc4:
            daily = summary.get('daily_change', 0)
            st.metric("📅 Today's Change", f"${daily:+,.0f}")
        
        st.markdown("---")
        
        # Stock rows
        for stock in perf.get("stocks", []):
            if "error" in stock:
                continue
            cols = st.columns([1.5, 1.5, 2, 2, 0.5])
            with cols[0]:
                st.markdown(f"**{stock['symbol']}**")
                st.caption(f"${stock['current_price']:,.2f}")
            with cols[1]:
                chg = stock.get('daily_change_pct', 0)
                color = "status-positive" if chg >= 0 else "status-negative"
                st.markdown(f'<span class="{color}">{chg:+.2f}% today</span>', unsafe_allow_html=True)
            with cols[2]:
                if stock.get('shares', 0) > 0:
                    st.markdown(f"{stock['shares']:.0f} shares @ ${stock.get('buy_price', 0):.0f}")
                else:
                    st.caption("Watching only")
            with cols[3]:
                if stock.get('gain_loss') is not None:
                    gl = stock['gain_loss']
                    gl_pct = stock.get('gain_loss_pct', 0)
                    color = "status-positive" if gl >= 0 else "status-negative"
                    st.markdown(f'<span class="{color}">${gl:+,.0f} ({gl_pct:+.1f}%)</span>', unsafe_allow_html=True)
            with cols[4]:
                if st.button("✕", key=f"rm_{stock['symbol']}"):
                    remove_from_watchlist(stock['symbol'])
                    get_cached_portfolio_performance.clear()  # Clear cache on change
                    st.rerun()
        
        st.markdown("---")
        if st.button("🗑️ Clear All"):
            clear_watchlist()
            get_cached_portfolio_performance.clear()  # Clear cache on change
            st.rerun()


# ============================================================
# TAB 4: STATS
# ============================================================
with tab_stats:
    st.markdown("#### 📋 Agent Observability Dashboard")
    st.caption("Every AI query is logged — tracks performance, tool usage, and reliability.")
    st.markdown("")
    
    stats = get_run_stats()
    
    if stats.get("total_runs", 0) == 0:
        st.info("No agent runs logged yet. Use the AI Chat tab to generate activity data.")
    else:
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.metric("Total Runs", stats["total_runs"])
        with sc2:
            st.metric("Success Rate", f"{stats.get('success_rate_pct', 0)}%")
        with sc3:
            st.metric("Avg Latency", f"{stats.get('avg_latency_seconds', 0):.1f}s")
        with sc4:
            st.metric("Avg Tools/Query", f"{stats.get('avg_tools_per_run', 0):.1f}")
        
        st.markdown("---")
        
        col_t, col_m = st.columns(2)
        with col_t:
            st.markdown("**🔧 Tool Usage Frequency**")
            for tool, count in stats.get("tool_usage", {}).items():
                st.markdown(f"- `{tool}` — {count} calls")
        with col_m:
            st.markdown("**🤖 Models Used**")
            for model, count in stats.get("models_used", {}).items():
                short_name = model.split(":")[0] if ":" in model else model
                st.markdown(f"- `{short_name}` — {count} runs")
        
        st.markdown("---")
        st.markdown("**📜 Recent Runs**")
        recent = get_recent_runs(5)
        for run in reversed(recent):
            ts = run.get("timestamp", "")[:16].replace("T", " ")
            query = run.get("query", "")[:50]
            tools = ", ".join(run.get("tools_used", []))
            elapsed = run.get("elapsed_seconds", 0)
            icon = "✅" if run.get("success") else "❌"
            st.markdown(f"{icon} **{ts}** — _{query}..._ → `{tools}` ({elapsed:.1f}s)")


# --- Footer with Disclaimer ---
st.markdown("""
<div class="app-footer">
    <p style="margin-bottom: 8px;">Market Intelligence Agent v2.0 • Built with Amazon Bedrock + yfinance • Quadra Systems 2026</p>
    <p style="font-size: 0.75rem; color: #444; max-width: 700px; margin: 0 auto; line-height: 1.6;">
        <strong>Disclaimer:</strong> This tool is for informational and educational purposes only. It does not constitute 
        financial advice, investment recommendations, or solicitation to buy or sell securities. AI-generated analysis 
        may contain inaccuracies. Always consult a qualified financial advisor before making investment decisions. 
        Past performance does not guarantee future results.
    </p>
</div>
""", unsafe_allow_html=True)
