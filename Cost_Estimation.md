# Cost Estimation — Market Intelligence Agent

## Development (Current State — Local)

| Resource | Cost | Notes |
|----------|------|-------|
| Amazon Bedrock (Nova Lite) | ~$0.001/query | Input: $0.06/1M tokens, Output: $0.24/1M tokens |
| yfinance | Free | Yahoo Finance public API |
| Google News RSS | Free | Public RSS feed |
| Streamlit | Free | Local development server |
| **Total (Dev)** | **< $1/month** | Assuming ~500 queries/month during development |

---

## Production Deployment — Light Usage

Scenario: 5 users, ~50 queries/day, deployed on ECS Fargate

| Resource | Monthly Cost | Notes |
|----------|-------------|-------|
| Amazon Bedrock (Nova Lite) | ~$2.00 | 1,500 queries × ~800 tokens avg |
| ECS Fargate (512 CPU, 1GB) | ~$22.00 | Always-on, 1 task |
| ECR Storage | ~$0.10 | Container image ~500MB |
| CloudWatch Logs | ~$0.50 | Log ingestion |
| NAT Gateway (if VPC) | ~$32.00 | Optional — not needed if public subnet |
| **Total (Light)** | **~$25-55/month** | |

---

## Production Deployment — Moderate Usage

Scenario: 20 users, ~200 queries/day, with auto-scaling

| Resource | Monthly Cost | Notes |
|----------|-------------|-------|
| Amazon Bedrock (Nova Pro) | ~$30.00 | 6,000 queries × ~1,500 tokens avg |
| ECS Fargate (1 vCPU, 2GB) | ~$45.00 | Auto-scaling 1-3 tasks |
| Application Load Balancer | ~$16.00 | Fixed + LCU charges |
| ECR Storage | ~$0.10 | |
| CloudWatch Logs + Alarms | ~$3.00 | |
| S3 (report storage) | ~$0.50 | If PDF reports are stored |
| **Total (Moderate)** | **~$95-120/month** | |

---

## Production — AgentCore Deployment (Future)

Scenario: Full AgentCore with memory, gateway, evaluators

| Resource | Monthly Cost | Notes |
|----------|-------------|-------|
| AgentCore Runtime | TBD | Per-invocation pricing (preview) |
| AgentCore Memory | TBD | Per-read/write (preview) |
| AgentCore Gateway | TBD | Per-request (preview) |
| Bedrock (Claude Sonnet) | ~$150.00 | 6,000 queries, better analysis |
| Lambda (5 evaluators) | ~$1.00 | Minimal invocations |
| CloudWatch | ~$5.00 | Spans + evaluation results |
| **Total (AgentCore)** | **~$200-300/month** | Estimate based on preview pricing |

---

## Cost Comparison: Models

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Quality | Speed |
|-------|----------------------|------------------------|---------|-------|
| Nova Lite | $0.06 | $0.24 | Good | Fast |
| Nova Pro | $0.80 | $3.20 | Better | Medium |
| Claude 3 Haiku | $0.25 | $1.25 | Good | Fast |
| Claude 3.5 Sonnet | $3.00 | $15.00 | Best | Slower |

**Recommendation:** Nova Lite for development and demos. Nova Pro for production. Claude Sonnet only for complex multi-step analysis.

---

## Cost per Query Breakdown

| Component | Nova Lite | Nova Pro | Claude Sonnet |
|-----------|-----------|----------|---------------|
| Input tokens (~500) | $0.00003 | $0.0004 | $0.0015 |
| Output tokens (~800) | $0.0002 | $0.0026 | $0.012 |
| Tool calls (2-3 avg) | Free (yfinance) | Free | Free |
| **Total per query** | **~$0.001** | **~$0.003** | **~$0.014** |

---

## Cost Optimization Strategies

1. **Use Nova Lite for tool routing, Nova Pro only for final analysis** — reduces cost by ~60%
2. **Cache stock data** — 5-minute cache for repeated queries on same ticker
3. **Limit tool calls** — max 3-5 per query (already implemented)
4. **Batch sector queries** — one yfinance call for multiple tickers
5. **Off-peak scaling** — scale ECS to 0 at night for non-24/7 use cases
