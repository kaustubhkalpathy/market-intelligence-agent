# Demo Script — Market Intelligence Agent

Use this when recording your demo video or presenting live.
Total time: ~5-7 minutes.

---

## Setup (before recording)

1. Open terminal in `Use_Case_2_Market_Intelligence_Agent/`
2. Run: `python -m streamlit run streamlit_app.py`
3. Wait for app to load at http://localhost:8501
4. Make sure browser is in dark mode / full screen

---

## Demo Flow

### Part 1: Introduction (30 sec)

*Say:* "This is a Market Intelligence Agent — an AI-powered financial copilot that autonomously gathers real-time market data and generates personalized analysis using Amazon Bedrock."

*Show:* The main app screen — header, market snapshot, chat interface.

---

### Part 2: Set Up Broker Profile (1 min)

*Do:*
1. Open sidebar → Edit Profile
2. Fill in:
   - Name: Kaustubh
   - Company: Quadra Systems
   - Role: Investment Advisor
   - Risk Tolerance: drag to "high"
   - Investment Style: growth
   - Sector Interests: AI, semiconductors, technology
   - Client Demographics: tech professionals
3. Click "Save Profile"

*Say:* "The agent personalizes its analysis based on the broker's profile — risk tolerance, investment style, and sector interests are injected into the system prompt."

---

### Part 3: Single Stock Query (1.5 min)

*Type in chat:* "What's happening with NVIDIA stock today?"

*Wait for response, then say:*
- "Notice the agent autonomously decided to call `get_stock_price` and `get_company_news`"
- "It fetched real-time data from Yahoo Finance and recent news from Google"
- "The analysis is tailored to my high-risk growth profile"

*Show:* Expand "Technical Details" — show metadata (model, tools used, elapsed time)

---

### Part 4: Sector Analysis (1 min)

*Type:* "Give me a technology sector overview"

*Say:* "Here the agent calls `get_sector_overview` which fetches live data for 6 major tech stocks, then generates a sector analysis."

---

### Part 5: Multi-Stock Comparison (1 min)

*Type:* "Compare NVDA, AMD, and INTC — which should I buy for my growth clients?"

*Say:* "The agent calls `compare_stocks` to get side-by-side data, then generates a recommendation tailored to my growth-focused clients."

---

### Part 6: Interactive Charts (1 min)

*Do:*
1. Expand "Interactive Stock Charts" section
2. Show NVDA candlestick chart (3mo)
3. Change comparison to "NVDA, AMD, INTC, MSFT"
4. Show sector bar chart for "ai"

*Say:* "The dashboard also includes interactive Plotly charts — candlestick with moving averages, normalized comparisons, and sector performance views."

---

### Part 7: Architecture Summary (30 sec)

*Say:* "Under the hood, this uses a ReAct agent pattern. The LLM autonomously decides which tools to call — I don't hardcode the logic. It uses Bedrock's Converse API with tool_use protocol, the same pattern used in AWS AgentCore production deployments. The architecture is containerized and ready for deployment on ECS Fargate or AgentCore Runtime."

---

### Part 8: Test Suite (30 sec, optional)

*Switch to terminal, run:* `python test_agent.py`

*Say:* "I also built an automated test suite — 38 tests covering the tools, memory system, and full agent loop. All passing."

---

## Key Talking Points (if asked questions)

| Question | Answer |
|----------|--------|
| "How does it decide what tools to call?" | "The LLM reads tool descriptions and picks the most relevant ones. I don't hardcode the logic." |
| "Why not just use ChatGPT with plugins?" | "This runs on our own AWS infrastructure with Bedrock, no data leaves our account, and it's customizable." |
| "Can it scale?" | "Yes — it's containerized with a Dockerfile and deploy instructions for ECS Fargate. Production would use AgentCore." |
| "What's the cost?" | "About $0.001 per query with Nova Lite. Under $10/month for light usage." |
| "How is this different from Use Case 1?" | "Use Case 1 is a traditional ML pipeline (train → deploy → predict). Use Case 2 is agentic AI — the LLM acts autonomously with tools." |
