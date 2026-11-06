# Architecture Diagram — Market Intelligence Agent

## How to Create the Diagram

Use draw.io (https://app.diagrams.net) or Excalidraw. Match the dark theme style from Use Case 1.

---

## Diagram Layout (Top to Bottom)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STREAMLIT UI (PORT 8501)                        │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   Chat   │  │   Charts     │  │   Profile    │  │ Quick Actions │  │
│  │Interface │  │  (Plotly)    │  │   Editor     │  │   Buttons     │  │
│  └─────┬────┘  └──────────────┘  └──────────────┘  └───────────────┘  │
└────────┼────────────────────────────────────────────────────────────────┘
         │
         │ user_message
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    MARKET INTELLIGENCE AGENT                            │
│                    (agent/market_agent.py)                              │
│                                                                         │
│    ┌───────────────────────────────────────────────────────┐           │
│    │              ReAct Loop (max 5 iterations)            │           │
│    │                                                       │           │
│    │  ┌─────────┐     ┌──────────┐     ┌──────────────┐  │           │
│    │  │ REASON  │────▶│   ACT    │────▶│   OBSERVE    │  │           │
│    │  │(LLM     │     │(Execute  │     │(Feed result  │  │           │
│    │  │ decides │◀────│ tool)    │     │ back to LLM) │──┘           │
│    │  │ tools)  │     └──────────┘     └──────────────┘              │
│    │  └─────────┘                                                     │
│    └───────────────────────────────────────────────────────┘           │
│                                                                         │
└────────┬─────────────────┬─────────────────────────┬────────────────────┘
         │                 │                         │
         ▼                 ▼                         ▼
┌────────────────┐ ┌───────────────┐ ┌──────────────────────────┐
│  AMAZON        │ │  DATA TOOLS   │ │  LOCAL MEMORY            │
│  BEDROCK       │ │               │ │  (.memory/)              │
│                │ │ ┌───────────┐ │ │                          │
│ ┌────────────┐ │ │ │  yfinance │ │ │  ┌────────────────────┐ │
│ │ Nova Lite  │ │ │ │  (Yahoo   │ │ │  │broker_profiles.json│ │
│ │ / Nova Pro │ │ │ │  Finance) │ │ │  └────────────────────┘ │
│ │ / Claude   │ │ │ └───────────┘ │ │                          │
│ └────────────┘ │ │               │ │  ┌────────────────────┐ │
│                │ │ ┌───────────┐ │ │  │conversation_history│ │
│  Converse API  │ │ │  Google   │ │ │  │        .json       │ │
│  (tool_use)    │ │ │  News RSS │ │ │  └────────────────────┘ │
│                │ │ └───────────┘ │ │                          │
└────────────────┘ └───────────────┘ └──────────────────────────┘
         │
         │ Bedrock API Call
         ▼
┌────────────────────────────────────────────┐
│            AWS CLOUD (us-east-1)           │
│                                            │
│  Amazon Bedrock                            │
│  ├── Model: amazon.nova-lite-v1:0          │
│  ├── API: Converse (tool_use protocol)     │
│  └── Cost: ~$0.001 / query                 │
│                                            │
└────────────────────────────────────────────┘
```

---

## Data Flow (Numbered Steps)

```
1. User types question in Streamlit chat
2. MarketIntelligenceAgent.run() is called
3. Agent sends message + tool definitions to Bedrock
4. Bedrock LLM decides: "I need to call get_stock_price"
5. Agent executes get_stock_price() → yfinance → Yahoo Finance API
6. Real-time data returned to agent
7. Agent sends tool result back to Bedrock
8. Bedrock LLM decides: "I also need news" → calls get_company_news()
9. Agent executes → Google News RSS → parsed articles
10. Agent sends news back to Bedrock
11. Bedrock LLM has enough data → generates final analysis text
12. Agent returns response to Streamlit
13. Streamlit renders markdown + shows tool badges
```

---

## Component Details

### Streamlit UI Layer
| Component | Purpose |
|-----------|---------|
| Chat Interface | Main interaction — user types, agent responds |
| Interactive Charts (Plotly) | Candlestick, comparison, sector bar charts |
| Broker Profile Editor | Set risk tolerance, investment style |
| Quick Actions | One-click buttons for common queries |
| Market Snapshot | 4 live tickers at the top |

### Agent Layer
| Component | File | Purpose |
|-----------|------|---------|
| ReAct Loop | market_agent.py | Orchestrates LLM + tools in a loop |
| Tool Definitions | market_agent.py | JSON schemas for Bedrock tool_use |
| Tool Executor | market_agent.py | Maps tool names → Python functions |
| System Prompt | market_agent.py | Instructions + broker personalization |

### Tools Layer
| Tool | File | Data Source | API Key? |
|------|------|-------------|----------|
| get_stock_price | stock_data.py | Yahoo Finance (yfinance) | No |
| get_stock_history | stock_data.py | Yahoo Finance | No |
| get_sector_overview | stock_data.py | Yahoo Finance | No |
| compare_stocks | stock_data.py | Yahoo Finance | No |
| search_financial_news | news_search.py | Google News RSS | No |
| get_company_news | news_search.py | yfinance news | No |
| get_market_headlines | news_search.py | Google News RSS | No |

### Memory Layer
| Store | File | Format |
|-------|------|--------|
| Broker Profiles | .memory/broker_profiles.json | JSON (name, risk, style, interests) |
| Conversation History | .memory/conversation_history.json | JSON (role, content, timestamp) |

---

## Production Upgrade Path

```
LOCAL (Current)                    →    AWS PRODUCTION (Future)
─────────────────                       ──────────────────────
Streamlit (localhost)              →    Streamlit Cloud / ECS Fargate
Python ReAct loop                  →    AgentCore Runtime (container)
Local JSON memory                  →    AgentCore Memory (managed)
Direct Bedrock calls               →    AgentCore Gateway (auth + rate limit)
No monitoring                      →    AgentCore Evaluators (5 Lambda fns)
No testing                         →    AgentCore A/B Testing + Optimization
yfinance                           →    Playwright browser automation
Google News RSS                    →    Bloomberg/Reuters via browser
```

---

## Color Scheme for Diagram

- Background: #0E1117 (dark)
- Primary accent: #00D4AA (teal/green)
- Secondary: #FFA502 (orange)
- Error/negative: #FF4757 (red)
- Text: #FAFAFA (white)
- Card borders: #2A3040
