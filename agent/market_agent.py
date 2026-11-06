"""
Market Intelligence Agent
Core agent with tool-calling loop that orchestrates market analysis.

This implements a simple ReAct-style agent loop:
1. Receive user query
2. LLM decides which tools to call
3. Execute tools, gather data
4. LLM generates final analysis from gathered data

In production, this would use AgentCore Runtime + LangGraph/Strands.
Here we implement a clean tool-calling loop using Bedrock's Converse API.
"""

import boto3
import json
from datetime import datetime
from typing import Optional

from agent.tools.stock_data import (
    get_stock_price,
    get_stock_history,
    get_sector_overview,
    compare_stocks,
)
from agent.tools.news_search import (
    search_financial_news,
    get_market_headlines,
    get_company_news,
)
from agent.tools.analysis import (
    generate_market_analysis,
    generate_sector_analysis,
    generate_comparison_analysis,
)
from agent.memory import (
    get_broker_profile,
    save_conversation,
    get_conversation_history,
)
from agent.logger import log_agent_run


# --- Tool Definitions for the LLM ---

TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "get_stock_price",
            "description": "Get current stock price, change, volume, and key metrics for a ticker symbol. For Indian stocks use .NS suffix (e.g., TATAMOTORS.NS, RELIANCE.NS). For Hong Kong use .HK. For London use .L.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., AAPL, NVDA, MSFT, TATAMOTORS.NS, RELIANCE.NS, 0700.HK)"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_stock_history",
            "description": "Get historical price data and summary statistics for a stock over a time period.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Stock ticker symbol"},
                        "period": {
                            "type": "string",
                            "description": "Time period: '1w', '1mo', '3mo', '6mo', '1y'",
                            "default": "1mo"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_sector_overview",
            "description": "Get overview of major stocks in a sector (technology, healthcare, energy, finance, consumer, ai, semiconductor).",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "sector": {
                            "type": "string",
                            "description": "Sector name: technology, healthcare, energy, finance, consumer, ai, semiconductor"
                        }
                    },
                    "required": ["sector"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "compare_stocks",
            "description": "Compare multiple stocks side by side with current prices and performance.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of ticker symbols to compare (max 6)"
                        }
                    },
                    "required": ["symbols"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "search_financial_news",
            "description": "Search for financial news articles on any topic, company, or market event.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (company name, topic, event)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_company_news",
            "description": "Get recent news specifically about a company using its ticker symbol.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Stock ticker symbol"
                        }
                    },
                    "required": ["symbol"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_market_headlines",
            "description": "Get top market headlines by category: top, technology, earnings, economy, crypto, commodities.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Category: top, technology, earnings, economy, crypto, commodities",
                            "default": "top"
                        }
                    },
                    "required": ["category"]
                }
            }
        }
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "get_stock_price": get_stock_price,
    "get_stock_history": get_stock_history,
    "get_sector_overview": get_sector_overview,
    "compare_stocks": compare_stocks,
    "search_financial_news": search_financial_news,
    "get_company_news": get_company_news,
    "get_market_headlines": get_market_headlines,
}


class MarketIntelligenceAgent:
    """
    Agentic AI that autonomously gathers market data and generates analysis.
    
    Uses a ReAct loop:
    - Reason: LLM decides what data to gather
    - Act: Execute tools to get real-time data
    - Observe: Feed results back to LLM
    - Respond: Generate final personalized analysis
    """
    
    def __init__(
        self,
        model_id: str = "amazon.nova-pro-v1:0",
        region: str = "us-east-1",
        max_tool_calls: int = 8,
    ):
        self.model_id = model_id
        self.region = region
        self.max_tool_calls = max_tool_calls
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.broker_profile = get_broker_profile()
        self.tool_calls_made = []
        self.conversation_history = []  # Stores previous turns for multi-turn context
    
    def set_broker_profile(self, profile: dict):
        """Set the active broker profile for personalization."""
        self.broker_profile = profile
    
    def run(self, user_message: str) -> dict:
        """
        Run the agent on a user message.
        
        Args:
            user_message: The user's question or request
        
        Returns:
            Dictionary with:
                - response: The final analysis text
                - tools_used: List of tools called
                - data_gathered: Raw data from tools
                - metadata: Timing and model info
        """
        start_time = datetime.now()
        self.tool_calls_made = []
        data_gathered = {}
        
        # Build conversation messages — include history for multi-turn context
        messages = []
        
        # Add last 3 turns of conversation history (to keep token usage manageable)
        for turn in self.conversation_history[-6:]:  # Last 6 messages = 3 turns (user+assistant)
            messages.append(turn)
        
        # Add current user message
        messages.append(
            {"role": "user", "content": [{"text": user_message}]}
        )
        
        # System prompt
        system_prompt = self._get_agent_system_prompt()
        
        # Agent loop — let the LLM decide tools to call
        iteration = 0
        while iteration < self.max_tool_calls:
            iteration += 1
            
            try:
                response = self.client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    system=[{"text": system_prompt}],
                    toolConfig={"tools": TOOL_DEFINITIONS},
                    inferenceConfig={"maxTokens": 4096, "temperature": 0.2},
                )
            except Exception as e:
                error_msg = str(e)
                # Friendly error messages for common issues
                if "credentials" in error_msg.lower() or "security token" in error_msg.lower():
                    friendly = "🔐 **AWS credentials not configured.** Please set up your AWS CLI credentials with Bedrock access to use this agent."
                elif "AccessDeniedException" in error_msg or "not authorized" in error_msg.lower():
                    friendly = "🚫 **Model access denied.** Your AWS account may not have Amazon Bedrock model access enabled in this region. Enable it in the AWS Bedrock console."
                elif "ThrottlingException" in error_msg or "rate" in error_msg.lower():
                    friendly = "⏳ **Rate limited.** Too many requests — please wait a moment and try again."
                elif "ValidationException" in error_msg:
                    friendly = "⚠️ **Request too large.** Try a shorter question or clear the chat history to reduce context size."
                else:
                    friendly = f"⚠️ **Something went wrong.** The AI service returned an error. Please try again.\n\n<details><summary>Technical details</summary>\n\n`{error_msg}`\n</details>"
                
                log_agent_run(user_message, "", self.tool_calls_made, {"error": error_msg},
                             broker_name=self.broker_profile.get("name") if self.broker_profile else None,
                             error=error_msg)
                return {
                    "response": friendly,
                    "tools_used": self.tool_calls_made,
                    "data_gathered": data_gathered,
                    "metadata": {"error": error_msg},
                }
            
            # Check stop reason
            stop_reason = response.get("stopReason", "")
            output_message = response["output"]["message"]
            
            # If the model wants to use tools
            if stop_reason == "tool_use":
                # Add assistant message to conversation
                messages.append(output_message)
                
                # Process each tool use block
                tool_results = []
                for block in output_message["content"]:
                    if "toolUse" in block:
                        tool_use = block["toolUse"]
                        tool_name = tool_use["name"]
                        tool_input = tool_use["input"]
                        tool_use_id = tool_use["toolUseId"]
                        
                        # Execute the tool
                        result = self._execute_tool(tool_name, tool_input)
                        data_gathered[tool_name] = result
                        self.tool_calls_made.append({
                            "tool": tool_name,
                            "input": tool_input,
                            "success": "error" not in result if isinstance(result, dict) else True,
                        })
                        
                        tool_results.append({
                            "toolResult": {
                                "toolUseId": tool_use_id,
                                "content": [{"json": result}],
                            }
                        })
                
                # Add tool results back to conversation
                messages.append({"role": "user", "content": tool_results})
            
            else:
                # Model is done — extract final response
                final_text = ""
                for block in output_message["content"]:
                    if "text" in block:
                        final_text += block["text"]
                
                # Clean up thinking tags (some models expose internal reasoning)
                import re
                final_text = re.sub(r'<thinking>.*?</thinking>\s*', '', final_text, flags=re.DOTALL)
                final_text = final_text.strip()
                
                # Save to conversation history (for multi-turn context)
                self.conversation_history.append(
                    {"role": "user", "content": [{"text": user_message}]}
                )
                self.conversation_history.append(
                    {"role": "assistant", "content": [{"text": final_text}]}
                )
                
                # Save to file-based conversation history
                save_conversation("user", user_message)
                save_conversation("assistant", final_text, {
                    "tools_used": [t["tool"] for t in self.tool_calls_made]
                })
                
                elapsed = (datetime.now() - start_time).total_seconds()
                
                metadata = {
                    "model": self.model_id,
                    "region": self.region,
                    "iterations": iteration,
                    "elapsed_seconds": round(elapsed, 2),
                    "broker_profile": self.broker_profile.get("name") if self.broker_profile else None,
                }
                
                # Log the run
                log_agent_run(user_message, final_text, self.tool_calls_made, metadata,
                             broker_name=self.broker_profile.get("name") if self.broker_profile else None)
                
                return {
                    "response": final_text,
                    "tools_used": self.tool_calls_made,
                    "data_gathered": data_gathered,
                    "metadata": metadata,
                }
        
        # Exceeded max iterations
        return {
            "response": "⚠️ Agent reached maximum tool call limit. Partial data was gathered.",
            "tools_used": self.tool_calls_made,
            "data_gathered": data_gathered,
            "metadata": {"max_iterations_reached": True},
        }
    
    def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool by name with given inputs."""
        func = TOOL_FUNCTIONS.get(tool_name)
        if not func:
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            result = func(**tool_input)
            return result
        except Exception as e:
            return {"error": f"Tool '{tool_name}' failed: {str(e)}"}
    
    def _get_agent_system_prompt(self) -> str:
        """Build the agent's system prompt."""
        
        prompt = """You are a Market Intelligence Agent — an AI-powered financial analyst that helps 
investment professionals make informed decisions.

Your capabilities:
- Fetch real-time stock prices and metrics (get_stock_price, get_stock_history)
- Analyze entire sectors (get_sector_overview)
- Compare multiple stocks (compare_stocks)
- Search financial news (search_financial_news, get_company_news, get_market_headlines)

Workflow:
1. Analyze the user's question to determine what data you need
2. Call the appropriate tools to gather real-time data
3. Synthesize the data into clear, actionable analysis
4. Provide specific recommendations with rationale

Rules:
- ALWAYS use tools to get real data before answering — never make up prices or news
- Call multiple tools if needed (e.g., stock price + news for a complete picture)
- Be specific — cite actual numbers from the data
- Format your final response with clear sections using markdown
- If the user asks about a specific stock, ALWAYS get its current price first
- If asked about a sector, use get_sector_overview
- For market updates, use get_market_headlines
- NEVER ask the user for a ticker symbol — figure it out yourself:
  - If they mention a company name, try the obvious ticker (e.g., "Apple" → AAPL, "Tesla" → TSLA)
  - For Indian stocks, add .NS suffix (e.g., "Tata Motors" → TATAMOTORS.NS, "Reliance" → RELIANCE.NS, "SBI" → SBIN.NS, "Infosys" → INFY.NS, "HDFC Bank" → HDFCBANK.NS)
  - For Hong Kong stocks, add .HK suffix (e.g., "Tencent" → 0700.HK)
  - For London stocks, add .L suffix (e.g., "BP" → BP.L)
  - IMPORTANT: When someone asks about a stock, ALWAYS try get_stock_price FIRST with your best guess at the ticker. Do NOT use search_financial_news to look up tickers — it won't help. Just try get_stock_price directly. If it fails, try one more variation, then give up.
  - If the stock doesn't exist or returns an error after 2 attempts, say clearly: "I couldn't find market data for [company name]. This company may not be publicly traded on major exchanges, or the ticker symbol may be different." Then STOP — do NOT ask the user for more information or a different symbol.
- NEVER give generic responses like "please provide more details" or "could you provide a different symbol" or "I can help with that" — always ACT first by calling tools, then state your findings. If you can't find something, say so and move on.
- NEVER recommend the user to visit other websites like moneycontrol.com or bseindia.com — YOU are the tool, provide the data yourself or say you can't find it.
- If a tool returns an error, try ONE alternative ticker format, then report what happened honestly — don't loop endlessly
- CRITICAL: NEVER show data for a DIFFERENT company than what the user asked about. If the user asks about "Tata" and you can only find "Reliance", that is NOT an answer. Say "I couldn't find data for Tata companies on Yahoo Finance" — do NOT substitute a different company's data.

Limitations you MUST be aware of and communicate to users when relevant:
- Your stock data comes from Yahoo Finance (via yfinance). You can ONLY show data for stocks that exist in Yahoo Finance's database.
- Some stocks may have been restructured, renamed, or delisted — their old tickers won't work even if you know them from your training data.
- Indian stocks need .NS (NSE) or .BO (BSE) suffix. Not all Indian stocks are available on Yahoo Finance.
- If a tool returns "No data found" or "possibly delisted", tell the user clearly: "This stock is not available in my data source (Yahoo Finance). It may have been renamed, delisted, or is not covered."
- You CANNOT execute trades, access portfolio accounts, predict future prices, or provide guaranteed returns.
- Your news comes from Google News RSS and Yahoo Finance news — it may not include every article from every source.
- The Charts tab in this app uses the same data source (Yahoo Finance) — if a ticker doesn't work in chat, it won't work in Charts either.
- When suggesting tickers to users, add a note: "If this doesn't show data, the ticker may have changed on Yahoo Finance."
"""
        
        if self.broker_profile:
            prompt += f"""
Active Broker Profile:
- Name: {self.broker_profile.get('name', 'Unknown')}
- Risk Tolerance: {self.broker_profile.get('risk_tolerance', 'moderate')}
- Investment Style: {self.broker_profile.get('investment_style', 'balanced')}
- Sector Interests: {self.broker_profile.get('sector_interests', 'general')}
- Client Demographics: {self.broker_profile.get('client_demographics', 'general')}

Tailor your analysis to this broker's style and risk appetite.
"""
        
        return prompt
