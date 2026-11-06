# Market Intelligence Agent

An AI-powered financial analysis copilot that autonomously searches live market data, analyses stocks, fetches news, and answers complex investment questions in natural language.

Built during my internship at **Quadra Systems** (AWS Partner) as a learning prototype demonstrating agentic AI using Amazon Bedrock's ReAct pattern. It is a portfolio/prototype project, not a production system.

---

## How It Works

The agent uses the **ReAct (Reason + Act)** pattern — the LLM reads your question, decides which tools to call, calls them autonomously, reads the results, and reasons toward a final answer. You never have to specify which tool to use.

```
User asks: "Compare AAPL and MSFT and summarise the latest news"
        ↓
Amazon Bedrock (Nova Lite) reasons about the query
        ↓
Autonomously calls: compare_stocks → get_company_news (x2)
        ↓
Synthesises results into a natural language response
        ↓
Streamed back to Streamlit UI with tool-use badges
```

---

## Features

### AI Chat
- Natural language queries about any stock, sector, or market topic
- Live market snapshot (4 tickers with 5-min cache)
- Tool-use badges showing exactly which tools the agent invoked
- PDF download of any response
- Quick action buttons (e.g. "Analyse top gainers", "Show sector overview")
- Broker profile personalisation — risk tolerance and investment style injected into system prompt
- Multi-turn memory — last 6 messages kept as context

### Charts
- Plotly candlestick chart with MA20 / MA50 overlays and volume
- Normalised comparison chart (% change across multiple tickers)
- Sector performance bar chart (7 sectors, 6 stocks each)

### Portfolio Tracker
- Watchlist with add / remove
- Real-time P&L and daily change per holding

### Observability Dashboard
- Total runs, success rate, average latency
- Tool usage frequency breakdown
- Recent agent run log — one JSONL record per run (query, tools used, latency, success); it does not trace each intermediate reasoning step

---

## Agent Tools (7 total)

| Tool | Description |
|------|-------------|
| `get_stock_price` | Live price, PE ratio, market cap, 52-week range |
| `get_stock_history` | Historical returns, volatility, average volume |
| `get_sector_overview` | 7 sectors × 6 stocks each (parallel fetch) |
| `compare_stocks` | Side-by-side comparison of up to 6 tickers |
| `search_financial_news` | Google News RSS + yfinance news |
| `get_company_news` | Ticker-specific news feed |
| `get_market_headlines` | Top / tech / earnings / crypto / commodities headlines |

---

## Architecture

| Layer | Technology |
|-------|-----------|
| UI | Streamlit (4 tabs, dark theme) |
| LLM | Amazon Bedrock Converse API (Nova Lite / Nova Pro / Claude) |
| Agent pattern | ReAct (tool_use protocol) |
| Market data | yfinance (real-time) |
| News | Google News RSS + yfinance |
| Memory | Local JSON (broker profiles + conversation history) |
| PDF reports | fpdf2 (custom MarketReportPDF class) |
| Observability | JSONL run logging (one record per run) |
| Deployment | Runs locally or via Docker; ECS Fargate steps documented (not deployed to production) |

---

## Project Structure

```
market-intelligence-agent/
├── streamlit_app.py              # Main UI — 4 tabs
├── agent/
│   ├── market_agent.py           # Core ReAct agent loop (Bedrock Converse API)
│   ├── memory.py                 # Broker profiles + conversation history
│   ├── logger.py                 # JSONL observability logger
│   └── tools/
│       ├── stock_data.py         # get_stock_price, get_stock_history
│       ├── analysis.py           # get_sector_overview, compare_stocks
│       ├── news_search.py        # search_financial_news, get_market_headlines
│       ├── charts.py             # Plotly chart builders
│       ├── portfolio.py          # Watchlist + P&L tracking
│       └── report.py             # PDF report generation
├── test_agent.py                 # Test script (~38 assertions; partial tool coverage)
├── Dockerfile                    # python:3.11-slim + healthcheck
├── requirements.txt
├── DEPLOY_INSTRUCTIONS.md        # Local / Docker / ECS Fargate guide
├── DEMO_SCRIPT.md                # 5–7 min recording walkthrough
└── Cost_Estimation.md
```

---

## How to Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/kaustubhkalpathy/market-intelligence-agent.git
cd market-intelligence-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set AWS credentials (needed for Bedrock)
set AWS_ACCESS_KEY_ID=your_key
set AWS_SECRET_ACCESS_KEY=your_secret
set AWS_DEFAULT_REGION=us-east-1

# 4. Run the app
streamlit run streamlit_app.py
```

Opens at **http://localhost:8501**

---

## Run with Docker

```bash
docker build -t market-intelligence-agent .
docker run -p 8501:8501 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_DEFAULT_REGION=us-east-1 \
  market-intelligence-agent
```

---

## Cost

| Scenario | Monthly estimate |
|----------|-----------------|
| Development (light usage) | ~$1 |
| Production on ECS Fargate | ~$25–50 |
| Per query (Nova Lite) | ~$0.001 |

---

## Testing

```bash
pip install pytest
pytest test_agent.py -v
```

A test script with ~38 assertions across stock data tools, news tools, memory CRUD, and the agent loop (agent-loop tests require AWS credentials). Not all tools are fully covered — this is a sanity-check suite, not exhaustive contract testing.

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Amazon Bedrock](https://img.shields.io/badge/AWS-Bedrock-232F3E?logo=amazon-aws)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-red?logo=streamlit)
![Plotly](https://img.shields.io/badge/Plotly-Charts-3F4F75?logo=plotly)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?logo=docker)
![yfinance](https://img.shields.io/badge/yfinance-Market%20Data-purple)

---

## Internship Context

Built at **Quadra Systems** (AWS Partner) — June 2026
Mentor: Anna | Tools: Kiro IDE, AWS Console

This project demonstrates agentic AI engineering: LLM reasoning → autonomous tool calling → real-time data → natural language synthesis.
