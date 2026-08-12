"""
Finnhub-backed tools for real-time market data.

These are plain Python functions with type hints and docstrings — passed
directly to Gemini's `tools=[...]` parameter, the SDK reads the signature
and docstring to build the function-calling schema automatically. Gemini
decides on its own whether a question needs one of these (e.g. "what's
AAPL trading at right now") versus just answering from filing context.

Free tier: 60 calls/minute, no credit card required.
Get a key at https://finnhub.io/register
"""
import datetime
import os

import requests
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
BASE_URL = "https://finnhub.io/api/v1"


def get_stock_price(ticker: str) -> dict:
    """Get the latest real-time price for a US-listed stock ticker.

    Use this whenever the user asks about a current, live, or "right now"
    stock price — not historical figures from a filing, which come from
    the filing context instead.

    Args:
        ticker: The stock ticker symbol, e.g. "AAPL" or "MSFT".

    Returns:
        A dict with current price, change, percent change, day high/low/open,
        and previous close — or an "error" key if the ticker wasn't found.
    """
    if not FINNHUB_API_KEY:
        return {"error": "FINNHUB_API_KEY is not set"}

    resp = requests.get(
        f"{BASE_URL}/quote",
        params={"symbol": ticker.upper(), "token": FINNHUB_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("c"):
        return {"error": f"No price data found for ticker '{ticker}'"}

    return {
        "ticker": ticker.upper(),
        "current_price": data.get("c"),
        "change": data.get("d"),
        "percent_change": data.get("dp"),
        "day_high": data.get("h"),
        "day_low": data.get("l"),
        "open": data.get("o"),
        "previous_close": data.get("pc"),
    }


def get_company_news(ticker: str, days: int = 7) -> list:
    """Get recent news headlines for a company.

    Use this when the user asks about recent news, developments, or
    breaking events for a company — not content already covered in the
    ingested filing.

    Args:
        ticker: The stock ticker symbol, e.g. "AAPL" or "MSFT".
        days: How many days back to search for news. Defaults to 7.

    Returns:
        A list of up to 5 recent news items, each with headline, summary,
        source, and date.
    """
    if not FINNHUB_API_KEY:
        return [{"error": "FINNHUB_API_KEY is not set"}]

    today = datetime.date.today()
    from_date = today - datetime.timedelta(days=days)

    resp = requests.get(
        f"{BASE_URL}/company-news",
        params={
            "symbol": ticker.upper(),
            "from": from_date.isoformat(),
            "to": today.isoformat(),
            "token": FINNHUB_API_KEY,
        },
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json()[:5]

    return [
        {
            "headline": item.get("headline"),
            "summary": item.get("summary"),
            "source": item.get("source"),
            "date": (
                datetime.datetime.fromtimestamp(item["datetime"]).strftime("%Y-%m-%d")
                if item.get("datetime")
                else None
            ),
        }
        for item in items
    ]
