"""
Charts Tool
Generates interactive Plotly charts for stock data visualization.
"""

import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime


def create_stock_chart(symbol: str, period: str = "3mo") -> go.Figure:
    """
    Create an interactive candlestick chart with volume for a stock.
    
    Args:
        symbol: Stock ticker symbol
        period: Time period ('1mo', '3mo', '6mo', '1y', '2y')
    
    Returns:
        Plotly Figure object
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)
    
    if hist.empty:
        # Return empty figure with message
        fig = go.Figure()
        fig.add_annotation(text=f"No data available for {symbol}", x=0.5, y=0.5,
                          xref="paper", yref="paper", showarrow=False, font=dict(size=16))
        return fig
    
    # Create subplot with candlestick + volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"{symbol} Price", "Volume"),
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=hist.index,
            open=hist["Open"],
            high=hist["High"],
            low=hist["Low"],
            close=hist["Close"],
            name="Price",
            increasing_line_color="#00D4AA",
            decreasing_line_color="#FF4757",
        ),
        row=1, col=1,
    )
    
    # Add moving averages
    if len(hist) >= 20:
        ma20 = hist["Close"].rolling(window=20).mean()
        fig.add_trace(
            go.Scatter(x=hist.index, y=ma20, name="MA 20",
                      line=dict(color="#FFA502", width=1)),
            row=1, col=1,
        )
    
    if len(hist) >= 50:
        ma50 = hist["Close"].rolling(window=50).mean()
        fig.add_trace(
            go.Scatter(x=hist.index, y=ma50, name="MA 50",
                      line=dict(color="#7B68EE", width=1)),
            row=1, col=1,
        )
    
    # Volume bars (colored by price direction)
    colors = ["#00D4AA" if hist["Close"].iloc[i] >= hist["Open"].iloc[i]
              else "#FF4757" for i in range(len(hist))]
    
    fig.add_trace(
        go.Bar(x=hist.index, y=hist["Volume"], name="Volume",
               marker_color=colors, opacity=0.6),
        row=2, col=1,
    )
    
    # Style
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        showlegend=True,
        legend=dict(x=0, y=1, bgcolor="rgba(0,0,0,0)"),
        height=500,
        margin=dict(l=50, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
    )
    
    fig.update_xaxes(gridcolor="#1A1F2E")
    fig.update_yaxes(gridcolor="#1A1F2E")
    
    return fig


def create_comparison_chart(symbols: list, period: str = "3mo") -> go.Figure:
    """
    Create a normalized comparison chart for multiple stocks.
    Shows percentage change from start of period.
    
    Args:
        symbols: List of ticker symbols
        period: Time period
    
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    colors = ["#00D4AA", "#FFA502", "#7B68EE", "#FF4757", "#00BFFF", "#FF69B4"]
    
    for i, symbol in enumerate(symbols[:6]):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if not hist.empty:
                # Normalize to percentage change from first day
                normalized = ((hist["Close"] / hist["Close"].iloc[0]) - 1) * 100
                
                fig.add_trace(
                    go.Scatter(
                        x=hist.index,
                        y=normalized,
                        name=symbol,
                        line=dict(color=colors[i % len(colors)], width=2),
                    )
                )
        except Exception:
            continue
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="#444", opacity=0.5)
    
    fig.update_layout(
        title="Relative Performance (% Change)",
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        yaxis_title="% Change",
        height=400,
        margin=dict(l=50, r=20, t=50, b=20),
        legend=dict(x=0, y=1, bgcolor="rgba(0,0,0,0)"),
    )
    
    fig.update_xaxes(gridcolor="#1A1F2E")
    fig.update_yaxes(gridcolor="#1A1F2E")
    
    return fig


def create_sector_bar_chart(sector_data: dict) -> go.Figure:
    """
    Create a horizontal bar chart showing sector stock performance.
    
    Args:
        sector_data: Output from get_sector_overview()
    
    Returns:
        Plotly Figure object
    """
    if "error" in sector_data or not sector_data.get("stocks"):
        fig = go.Figure()
        fig.add_annotation(text="No sector data available", x=0.5, y=0.5,
                          xref="paper", yref="paper", showarrow=False)
        return fig
    
    stocks = sector_data["stocks"]
    symbols = [s["symbol"] for s in stocks]
    changes = [s["change_pct"] for s in stocks]
    colors = ["#00D4AA" if c >= 0 else "#FF4757" for c in changes]
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Bar(
            x=changes,
            y=symbols,
            orientation="h",
            marker_color=colors,
            text=[f"{c:+.2f}%" for c in changes],
            textposition="outside",
            textfont=dict(color="#FAFAFA"),
        )
    )
    
    fig.add_vline(x=0, line_color="#444", line_dash="dash", opacity=0.5)
    
    fig.update_layout(
        title=f"{sector_data.get('sector', 'Sector')} — Today's Performance",
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA"),
        xaxis_title="% Change",
        height=300,
        margin=dict(l=60, r=80, t=50, b=30),
        showlegend=False,
    )
    
    fig.update_xaxes(gridcolor="#1A1F2E")
    fig.update_yaxes(gridcolor="#1A1F2E")
    
    return fig
