"""
News Search Tool
Fetches financial news using free APIs (RSS feeds + web scraping).
Falls back to yfinance news when external sources are unavailable.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional
import json
import re


# --- RSS Feed Sources ---

FINANCIAL_RSS_FEEDS = {
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "google_finance": "https://news.google.com/rss/search?q={query}+stock+market&hl=en-US&gl=US&ceid=US:en",
    "cnbc": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
}


def search_financial_news(query: str, max_results: int = 8) -> dict:
    """
    Search for financial news related to a query (company, sector, topic).
    
    Args:
        query: Search term (e.g., 'NVIDIA', 'AI stocks', 'oil prices')
        max_results: Maximum number of articles to return
    
    Returns:
        Dictionary with news articles and metadata
    """
    articles = []
    
    # Strategy 1: Google News RSS (most reliable for custom queries)
    google_articles = _fetch_google_news(query, max_results)
    articles.extend(google_articles)
    
    # Strategy 2: yfinance news for specific tickers
    if _looks_like_ticker(query):
        yf_articles = _fetch_yfinance_news(query)
        articles.extend(yf_articles)
    
    # Deduplicate by title similarity (Fix #5: use word-set overlap instead of prefix match)
    def _title_fingerprint(title: str) -> frozenset:
        """Create a word-set fingerprint for fuzzy dedup."""
        words = set(title.lower().split())
        # Remove common filler words for better matching
        stopwords = {"the", "a", "an", "is", "are", "was", "in", "on", "at", "to", "for", "of", "and", "or", "by"}
        return frozenset(words - stopwords)
    
    seen_fingerprints = []
    unique_articles = []
    for article in articles:
        fp = _title_fingerprint(article["title"])
        # Check if this title is too similar to any already seen (>60% word overlap)
        is_duplicate = False
        for seen_fp in seen_fingerprints:
            if len(fp) > 0 and len(seen_fp) > 0:
                overlap = len(fp & seen_fp) / min(len(fp), len(seen_fp))
                if overlap > 0.6:
                    is_duplicate = True
                    break
        if not is_duplicate:
            seen_fingerprints.append(fp)
            unique_articles.append(article)
    
    unique_articles = unique_articles[:max_results]
    
    return {
        "query": query,
        "articles": unique_articles,
        "count": len(unique_articles),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": list(set(a.get("source", "Unknown") for a in unique_articles)),
    }


def get_market_headlines(category: str = "top") -> dict:
    """
    Get top market headlines.
    
    Args:
        category: 'top', 'technology', 'earnings', 'economy'
    
    Returns:
        Dictionary with headline articles
    """
    query_map = {
        "top": "stock market today",
        "technology": "technology stocks market",
        "earnings": "earnings report quarterly results",
        "economy": "economy GDP inflation interest rates",
        "crypto": "cryptocurrency bitcoin ethereum",
        "commodities": "oil gold commodities prices",
    }
    
    search_query = query_map.get(category.lower(), f"{category} stock market")
    return search_financial_news(search_query, max_results=10)


def get_company_news(symbol: str) -> dict:
    """
    Get news specifically about a company.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Company-specific news articles
    """
    # Try yfinance first for ticker-specific news
    articles = _fetch_yfinance_news(symbol)
    
    # Supplement with Google News
    google_articles = _fetch_google_news(f"{symbol} stock", max_results=5)
    articles.extend(google_articles)
    
    # Deduplicate using word-set overlap
    seen_fingerprints = []
    unique = []
    for a in articles:
        words = set(a["title"][:60].lower().split())
        is_dup = False
        for seen in seen_fingerprints:
            if len(words) > 0 and len(seen) > 0:
                overlap = len(words & seen) / min(len(words), len(seen))
                if overlap > 0.6:
                    is_dup = True
                    break
        if not is_dup:
            seen_fingerprints.append(words)
            unique.append(a)
    
    return {
        "symbol": symbol.upper(),
        "articles": unique[:8],
        "count": len(unique[:8]),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# --- Internal Helper Functions ---

def _fetch_google_news(query: str, max_results: int = 8) -> list:
    """Fetch news from Google News RSS feed."""
    articles = []
    try:
        url = f"https://news.google.com/rss/search?q={query}+stock+market&hl=en-US&gl=US&ceid=US:en"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall(".//item")
            
            for item in items[:max_results]:
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                source = item.find("source")
                
                articles.append({
                    "title": title.text if title is not None else "No title",
                    "url": link.text if link is not None else "",
                    "published": pub_date.text if pub_date is not None else "",
                    "source": source.text if source is not None else "Google News",
                    "relevance": "high",
                })
    except Exception as e:
        # Silently fail — we have fallback sources
        pass
    
    return articles


def _fetch_yfinance_news(symbol: str) -> list:
    """Fetch news from yfinance for a specific ticker."""
    articles = []
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if news:
            for item in news[:5]:
                # Bug #4 fix: handle both old and new yfinance news format
                title = item.get("title", item.get("headline", "No title"))
                url = item.get("link", item.get("url", ""))
                publisher = item.get("publisher", item.get("source", "Yahoo Finance"))
                
                # Handle different timestamp field names
                pub_time = item.get("providerPublishTime", item.get("publishedAt", 0))
                if isinstance(pub_time, int) and pub_time > 0:
                    published = datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M")
                elif isinstance(pub_time, str):
                    published = pub_time[:16]
                else:
                    published = ""
                
                articles.append({
                    "title": title,
                    "url": url,
                    "published": published,
                    "source": publisher,
                    "relevance": "high",
                })
    except Exception:
        pass
    
    return articles


def _looks_like_ticker(query: str) -> bool:
    """Check if query looks like a stock ticker symbol."""
    clean = query.strip().upper()
    return len(clean) <= 5 and clean.isalpha()
