"""
Stock Data Tool
Fetches real-time stock prices, historical data, and key metrics using yfinance.
Includes retry logic for rate limiting and transient failures.
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional
import time
import signal
import threading


def _retry(func, max_retries=2, delay=1.0, timeout=15):
    """Retry wrapper for yfinance calls with timeout and rate-limit handling."""
    for attempt in range(max_retries + 1):
        try:
            # Run with a timeout using threading
            result = [None]
            error = [None]
            
            def target():
                try:
                    result[0] = func()
                except Exception as e:
                    error[0] = e
            
            thread = threading.Thread(target=target)
            thread.start()
            thread.join(timeout=timeout)
            
            if thread.is_alive():
                # Timed out
                raise TimeoutError(f"Operation timed out after {timeout}s")
            
            if error[0]:
                raise error[0]
            
            return result[0]
        except Exception as e:
            if attempt < max_retries:
                time.sleep(delay * (attempt + 1))
            else:
                raise e


def get_stock_price(symbol: str) -> dict:
    """
    Get current stock price and key metrics for a given ticker symbol.
    
    Args:
        symbol: Stock ticker (e.g., 'AAPL', 'NVDA', 'TATAMOTORS.NS', 'RELIANCE.NS')
    
    Returns:
        Dictionary with price, change, volume, and key metrics
    """
    if not symbol or len(symbol.strip()) > 20:
        return {"error": f"Invalid symbol: '{symbol}'. Must be a valid ticker symbol (letters, digits, dots allowed)."}
    
    # Clean the symbol — allow alphanumeric + dots (for exchange suffixes like .NS, .HK, .L)
    clean = symbol.strip().upper()
    if not all(c.isalpha() or c.isdigit() or c == '.' for c in clean):
        return {"error": f"Invalid symbol format: '{symbol}'. Only letters, numbers, and dots (for exchange suffix like .NS) are allowed."}
    
    symbol = clean
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Retry-wrapped history fetch
        hist = _retry(lambda: ticker.history(period="5d"))
        if hist is None or hist.empty:
            return {"error": f"Yahoo Finance has no data for symbol '{symbol}'. This stock may have been renamed, delisted, or is not covered by Yahoo Finance. The Charts tab in this app also uses Yahoo Finance — so this ticker won't work there either."}
        
        # Get info (may fail for some tickers — handle gracefully)
        try:
            info = ticker.info
        except Exception:
            info = {}
        
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
        
        return {
            "symbol": symbol.upper(),
            "current_price": round(current_price, 2),
            "previous_close": round(prev_close, 2),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "volume": int(hist['Volume'].iloc[-1]),
            "market_cap": info.get("marketCap", "N/A"),
            "pe_ratio": info.get("trailingPE", "N/A"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "company_name": info.get("shortName", symbol.upper()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        return {"error": f"Failed to fetch data from Yahoo Finance for '{symbol}': {str(e)}"}


def get_stock_history(symbol: str, period: str = "1mo") -> dict:
    """
    Get historical price data for a stock.
    
    Args:
        symbol: Stock ticker
        period: Time period - '1w', '1mo', '3mo', '6mo', '1y'
    
    Returns:
        Dictionary with historical prices and summary stats
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty:
            return {"error": f"Yahoo Finance has no historical data for '{symbol}'. This ticker may not exist or may have been delisted."}
        
        # Calculate summary statistics
        prices = hist['Close'].tolist()
        return {
            "symbol": symbol.upper(),
            "period": period,
            "data_points": len(prices),
            "start_price": round(prices[0], 2),
            "end_price": round(prices[-1], 2),
            "high": round(max(prices), 2),
            "low": round(min(prices), 2),
            "avg_price": round(sum(prices) / len(prices), 2),
            "total_return_pct": round(((prices[-1] - prices[0]) / prices[0]) * 100, 2),
            "volatility": round(hist['Close'].pct_change().std() * 100, 2),
            "avg_volume": int(hist['Volume'].mean()),
        }
    except Exception as e:
        return {"error": f"Failed to fetch history from Yahoo Finance for '{symbol}': {str(e)}"}


def get_sector_overview(sector: str) -> dict:
    """
    Get overview of major stocks in a sector.
    
    Args:
        sector: Sector name (e.g., 'Technology', 'Healthcare', 'Energy')
    
    Returns:
        Dictionary with sector stocks and their performance
    """
    # Major stocks by sector
    sector_tickers = {
        "technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN"],
        "healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY"],
        "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC"],
        "finance": ["JPM", "BAC", "GS", "MS", "WFC", "C"],
        "consumer": ["WMT", "PG", "KO", "PEP", "COST", "HD"],
        "ai": ["NVDA", "MSFT", "GOOGL", "META", "AMD", "SMCI"],
        "semiconductor": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM"],
    }
    
    sector_key = sector.lower().strip()
    # Try fuzzy match
    matched_key = None
    for key in sector_tickers:
        if key in sector_key or sector_key in key:
            matched_key = key
            break
    
    if not matched_key:
        return {
            "error": f"Sector '{sector}' not recognized. Available: {list(sector_tickers.keys())}"
        }
    
    tickers = sector_tickers[matched_key]
    results = []
    
    # Fix #4: Parallel fetching for better performance
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def _fetch_ticker_data(sym):
        """Fetch data for a single ticker (runs in thread)."""
        try:
            ticker = yf.Ticker(sym)
            hist = _retry(lambda t=ticker: t.history(period="5d"))
            if hist is not None and not hist.empty:
                price = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else price
                change_pct = ((price - prev) / prev) * 100
                try:
                    name = ticker.info.get("shortName", sym)
                except Exception:
                    name = sym
                return {
                    "symbol": sym,
                    "price": round(price, 2),
                    "change_pct": round(change_pct, 2),
                    "name": name,
                }
        except Exception:
            pass
        return None
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_fetch_ticker_data, sym): sym for sym in tickers}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    # Sort by original ticker order
    ticker_order = {sym: i for i, sym in enumerate(tickers)}
    results.sort(key=lambda x: ticker_order.get(x["symbol"], 99))
    
    return {
        "sector": matched_key.title(),
        "stocks": results,
        "count": len(results),
        "avg_change_pct": round(
            sum(s["change_pct"] for s in results) / len(results), 2
        ) if results else 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def compare_stocks(symbols: list) -> dict:
    """
    Compare multiple stocks side by side.
    
    Args:
        symbols: List of ticker symbols to compare
    
    Returns:
        Comparison data for all symbols
    """
    results = []
    for sym in symbols[:6]:  # Max 6 stocks
        data = get_stock_price(sym.strip())
        if "error" not in data:
            results.append(data)
    
    return {
        "comparison": results,
        "count": len(results),
        "best_performer": max(results, key=lambda x: x["change_percent"])["symbol"] if results else None,
        "worst_performer": min(results, key=lambda x: x["change_percent"])["symbol"] if results else None,
    }
