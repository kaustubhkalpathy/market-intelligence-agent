"""
Analysis Tool
Uses Amazon Bedrock (Claude/Nova) to generate market analysis and investment recommendations.
"""

import boto3
import json
from typing import Optional
from datetime import datetime


def get_bedrock_client(region: str = "us-east-1"):
    """Get Bedrock Runtime client."""
    return boto3.client("bedrock-runtime", region_name=region)


def generate_market_analysis(
    stock_data: dict,
    news_data: dict,
    broker_profile: Optional[dict] = None,
    model_id: str = "amazon.nova-lite-v1:0",
    region: str = "us-east-1",
) -> str:
    """
    Generate an AI-powered market analysis using Bedrock.
    
    Args:
        stock_data: Stock price and metrics data
        news_data: Relevant news articles
        broker_profile: Optional broker/user profile for personalization
        model_id: Bedrock model to use
        region: AWS region
    
    Returns:
        Generated analysis text
    """
    # Build the analysis prompt
    prompt = _build_analysis_prompt(stock_data, news_data, broker_profile)
    
    try:
        client = get_bedrock_client(region)
        
        # Use Converse API (works with Claude, Nova, etc.)
        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            system=[
                {
                    "text": _get_system_prompt(broker_profile)
                }
            ],
            inferenceConfig={
                "maxTokens": 2048,
                "temperature": 0.3,
            },
        )
        
        # Extract response text
        output = response["output"]["message"]["content"][0]["text"]
        return output
        
    except Exception as e:
        return f"⚠️ Analysis generation failed: {str(e)}\n\nPlease check your AWS credentials and Bedrock model access."


def generate_sector_analysis(
    sector_data: dict,
    news_data: dict,
    broker_profile: Optional[dict] = None,
    model_id: str = "amazon.nova-lite-v1:0",
    region: str = "us-east-1",
) -> str:
    """Generate AI analysis for a sector overview."""
    
    prompt = f"""Analyze the following sector data and provide investment insights:

## Sector Data
{json.dumps(sector_data, indent=2, default=str)}

## Recent News
{json.dumps(news_data.get('articles', [])[:5], indent=2, default=str)}

Provide:
1. Sector performance summary
2. Key drivers (why is the sector moving this way)
3. Top picks with rationale
4. Risk factors to watch
5. Short-term outlook (1-4 weeks)
"""
    
    try:
        client = get_bedrock_client(region)
        
        response = client.converse(
            modelId=model_id,
            messages=[
                {"role": "user", "content": [{"text": prompt}]}
            ],
            system=[{"text": _get_system_prompt(broker_profile)}],
            inferenceConfig={"maxTokens": 2048, "temperature": 0.3},
        )
        
        return response["output"]["message"]["content"][0]["text"]
        
    except Exception as e:
        return f"⚠️ Sector analysis failed: {str(e)}"


def generate_comparison_analysis(
    comparison_data: dict,
    broker_profile: Optional[dict] = None,
    model_id: str = "amazon.nova-lite-v1:0",
    region: str = "us-east-1",
) -> str:
    """Generate AI comparison analysis for multiple stocks."""
    
    prompt = f"""Compare the following stocks and provide investment recommendations:

## Stock Comparison Data
{json.dumps(comparison_data, indent=2, default=str)}

Provide:
1. Side-by-side comparison summary
2. Relative valuation assessment
3. Recommended allocation (if investing across these)
4. Which stock to buy/hold/avoid and why
5. Key catalysts for each
"""
    
    try:
        client = get_bedrock_client(region)
        
        response = client.converse(
            modelId=model_id,
            messages=[
                {"role": "user", "content": [{"text": prompt}]}
            ],
            system=[{"text": _get_system_prompt(broker_profile)}],
            inferenceConfig={"maxTokens": 2048, "temperature": 0.3},
        )
        
        return response["output"]["message"]["content"][0]["text"]
        
    except Exception as e:
        return f"⚠️ Comparison analysis failed: {str(e)}"


def _build_analysis_prompt(stock_data: dict, news_data: dict, broker_profile: Optional[dict]) -> str:
    """Build the analysis prompt from data."""
    
    prompt_parts = ["Analyze the following market data and provide actionable insights:\n"]
    
    # Add stock data
    if stock_data and "error" not in stock_data:
        prompt_parts.append(f"## Stock Data\n{json.dumps(stock_data, indent=2, default=str)}\n")
    
    # Add news
    if news_data and news_data.get("articles"):
        articles_summary = []
        for a in news_data["articles"][:6]:
            articles_summary.append(f"- {a['title']} ({a.get('source', 'Unknown')})")
        prompt_parts.append(f"## Recent News Headlines\n" + "\n".join(articles_summary) + "\n")
    
    # Add personalization context
    if broker_profile:
        prompt_parts.append(f"""
## Broker Profile (Tailor response accordingly)
- Risk Tolerance: {broker_profile.get('risk_tolerance', 'moderate')}
- Investment Style: {broker_profile.get('investment_style', 'balanced')}
- Sector Interests: {broker_profile.get('sector_interests', 'general')}
- Client Focus: {broker_profile.get('client_demographics', 'general investors')}
""")
    
    prompt_parts.append("""
Provide:
1. **Market Summary** — What's happening with this stock/sector right now
2. **Key Drivers** — Why it's moving (earnings, news, macro factors)
3. **Technical Outlook** — Support/resistance levels, trend direction
4. **Risk Assessment** — Key risks to watch
5. **Recommendation** — Buy/Hold/Sell with rationale and time horizon
""")
    
    return "\n".join(prompt_parts)


def _get_system_prompt(broker_profile: Optional[dict] = None) -> str:
    """Get the system prompt for the analysis LLM."""
    
    base_prompt = """You are an expert financial analyst and market intelligence advisor. 
You provide clear, actionable market analysis based on real-time data.

Guidelines:
- Be concise but thorough — focus on what matters
- Use specific numbers and data points from the provided information
- Clearly state your confidence level in recommendations
- Highlight both opportunities AND risks
- Use markdown formatting for readability
- Never fabricate data — only reference what's provided
- If data is insufficient, say so and suggest what additional info would help
"""
    
    if broker_profile:
        style = broker_profile.get("investment_style", "balanced")
        risk = broker_profile.get("risk_tolerance", "moderate")
        base_prompt += f"""
Personalization:
- This broker has a {risk} risk tolerance and prefers {style} strategies.
- Tailor language and recommendations accordingly.
- Focus on sectors they care about: {broker_profile.get('sector_interests', 'general')}
"""
    
    return base_prompt
