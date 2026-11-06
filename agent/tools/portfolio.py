"""
Portfolio Watchlist Tool
Manages a user's stock watchlist and calculates portfolio performance.
"""

import json
import os
from datetime import datetime
from typing import Optional
import yfinance as yf

PORTFOLIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".memory")
PORTFOLIO_FILE = os.path.join(PORTFOLIO_DIR, "portfolio.json")


def _ensure_dir():
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)


def _load_portfolio() -> dict:
    _ensure_dir()
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"stocks": [], "updated_at": None}
    return {"stocks": [], "updated_at": None}


def _save_portfolio(portfolio: dict):
    _ensure_dir()
    portfolio["updated_at"] = datetime.now().isoformat()
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


def add_to_watchlist(symbol: str, shares: float = 0, buy_price: float = 0) -> dict:
    """
    Add a stock to the watchlist.
    
    Args:
        symbol: Ticker symbol
        shares: Number of shares owned (0 = just watching)
        buy_price: Average buy price per share (0 = just watching)
    
    Returns:
        Updated watchlist status
    """
    symbol = symbol.strip().upper()
    portfolio = _load_portfolio()
    
    # Check if already exists
    for stock in portfolio["stocks"]:
        if stock["symbol"] == symbol:
            stock["shares"] = shares
            stock["buy_price"] = buy_price
            _save_portfolio(portfolio)
            return {"status": "updated", "symbol": symbol, "total_stocks": len(portfolio["stocks"])}
    
    portfolio["stocks"].append({
        "symbol": symbol,
        "shares": shares,
        "buy_price": buy_price,
        "added_at": datetime.now().isoformat(),
    })
    
    _save_portfolio(portfolio)
    return {"status": "added", "symbol": symbol, "total_stocks": len(portfolio["stocks"])}


def remove_from_watchlist(symbol: str) -> dict:
    """Remove a stock from the watchlist."""
    symbol = symbol.strip().upper()
    portfolio = _load_portfolio()
    
    original_count = len(portfolio["stocks"])
    portfolio["stocks"] = [s for s in portfolio["stocks"] if s["symbol"] != symbol]
    
    if len(portfolio["stocks"]) < original_count:
        _save_portfolio(portfolio)
        return {"status": "removed", "symbol": symbol}
    return {"status": "not_found", "symbol": symbol}


def get_watchlist() -> list:
    """Get the current watchlist symbols."""
    portfolio = _load_portfolio()
    return portfolio["stocks"]


def get_portfolio_performance() -> dict:
    """
    Calculate real-time portfolio performance.
    
    Returns:
        Dictionary with current values, gains/losses, and daily changes
    """
    portfolio = _load_portfolio()
    
    if not portfolio["stocks"]:
        return {"error": "Watchlist is empty. Add stocks first.", "stocks": []}
    
    results = []
    total_invested = 0
    total_current_value = 0
    total_daily_change = 0
    
    for stock in portfolio["stocks"]:
        symbol = stock["symbol"]
        shares = stock.get("shares", 0)
        buy_price = stock.get("buy_price", 0)
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            
            if hist.empty:
                results.append({
                    "symbol": symbol,
                    "error": "No data",
                    "shares": shares,
                })
                continue
            
            current_price = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
            daily_change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0
            
            # Calculate P&L if shares are owned
            invested = shares * buy_price
            current_value = shares * current_price
            gain_loss = current_value - invested if invested > 0 else 0
            gain_loss_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            daily_dollar_change = shares * (current_price - prev_close)
            
            total_invested += invested
            total_current_value += current_value
            total_daily_change += daily_dollar_change
            
            results.append({
                "symbol": symbol,
                "current_price": round(current_price, 2),
                "daily_change_pct": round(daily_change_pct, 2),
                "shares": shares,
                "buy_price": round(buy_price, 2) if buy_price > 0 else None,
                "current_value": round(current_value, 2) if shares > 0 else None,
                "gain_loss": round(gain_loss, 2) if invested > 0 else None,
                "gain_loss_pct": round(gain_loss_pct, 2) if buy_price > 0 else None,
                "daily_dollar_change": round(daily_dollar_change, 2) if shares > 0 else None,
            })
        except Exception as e:
            results.append({"symbol": symbol, "error": str(e), "shares": shares})
    
    total_gain_loss = total_current_value - total_invested if total_invested > 0 else 0
    total_gain_loss_pct = ((total_current_value - total_invested) / total_invested) * 100 if total_invested > 0 else 0
    
    return {
        "stocks": results,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current_value, 2),
            "total_gain_loss": round(total_gain_loss, 2),
            "total_gain_loss_pct": round(total_gain_loss_pct, 2),
            "daily_change": round(total_daily_change, 2),
            "stocks_tracked": len(results),
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def clear_watchlist():
    """Clear the entire watchlist."""
    _save_portfolio({"stocks": [], "updated_at": None})
    return {"status": "cleared"}
