import asyncio
import httpx
import feedparser
import trafilatura
import anthropic
import json
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo
from config import FINNHUB_API_KEY, ANTHROPIC_API_KEY
from db import supabase

_anthropic = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_NEWS_RSS = "https://finance.yahoo.com/news/rssindex"

_EASTERN = ZoneInfo("America/New_York")
_MARKET_OPEN  = time(9, 30)
_MARKET_CLOSE = time(16, 0)
_PRE_OPEN     = time(4, 0)
_POST_CLOSE   = time(20, 0)

_last_news_fetch: Optional[datetime] = None


def is_market_open() -> bool:
    now = datetime.now(_EASTERN)
    if now.weekday() >= 5:
        return False
    return _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


def _news_interval_minutes() -> int:
    """Return how many minutes must pass before fetching news again."""
    now = datetime.now(_EASTERN)
    t = now.time()
    if now.weekday() >= 5:
        return 60
    if _MARKET_OPEN <= t <= _MARKET_CLOSE:
        return 5
    if _PRE_OPEN <= t < _MARKET_OPEN or _MARKET_CLOSE < t <= _POST_CLOSE:
        return 30
    return 60


async def fetch_single(symbol: str):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}",
                timeout=10.0
            )
            if res.status_code != 200 or not res.text.strip():
                print(f"Skipping {symbol}: HTTP {res.status_code}, empty body")
                return
            data = res.json()
            if "c" not in data or data["c"] == 0:
                print(f"Skipping {symbol}: unexpected response {data}")
                return
            supabase.table("prices").insert({"symbol": symbol, "price": data["c"]}).execute()
            print(f"Fetched price for {symbol}")
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")


async def fetch_and_store():
    if not is_market_open():
        print("Market closed, skipping fetch")
        return
    symbols_res = supabase.table("symbols").select("symbol").execute()
    symbols = [row["symbol"] for row in symbols_res.data]
    async with httpx.AsyncClient() as client:
        for symbol in symbols:
            try:
                res = await client.get(
                    f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}",
                    timeout=10.0
                )
                if res.status_code != 200 or not res.text.strip():
                    print(f"Skipping {symbol}: HTTP {res.status_code}, empty body")
                    continue
                data = res.json()
                if "c" not in data or data["c"] == 0:
                    print(f"Skipping {symbol}: unexpected response {data}")
                    continue
                supabase.table("prices").insert({
                    "symbol": symbol,
                    "price": data["c"],
                }).execute()
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
            await asyncio.sleep(1)
    print(f"Fetched and stored prices for {symbols}")


async def fetch_news():
    global _last_news_fetch
    interval = _news_interval_minutes()
    if _last_news_fetch is not None:
        elapsed = (datetime.now(_EASTERN) - _last_news_fetch).total_seconds() / 60
        if elapsed < interval:
            print(f"News: {elapsed:.1f}m elapsed, waiting until {interval}m — skipping")
            return
    _last_news_fetch = datetime.now(_EASTERN)

    feed = feedparser.parse(_NEWS_RSS)
    entries = feed.entries[:20]  # cap per run

    for entry in entries:
        url = entry.get("link", "")
        if not url:
            continue

        # skip if already stored
        existing = supabase.table("news_articles").select("id").eq("url", url).execute()
        if existing.data:
            continue

        title = entry.get("title", "")
        published_at = None
        if entry.get("published_parsed"):
            published_at = datetime(*entry.published_parsed[:6]).isoformat()

        # scrape full text
        downloaded = trafilatura.fetch_url(url)
        full_text = trafilatura.extract(downloaded) if downloaded else None

        if not full_text:
            print(f"Could not extract text from {url}, skipping")
            continue

        # haiku: summary + tags, retry up to 3 times
        summary = ""
        tags = []
        for attempt in range(3):
            try:
                response = _anthropic.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=512,
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Article title: {title}\n\n"
                            f"Article text:\n{full_text[:4000]}\n\n"
                            "Return a JSON object with two keys:\n"
                            "- \"summary\": 2-3 sentence summary of the article\n"
                            "- \"tags\": list of stock ticker symbols mentioned (e.g. [\"AAPL\", \"MSFT\"])\n"
                            "Return only the JSON, no explanation."
                        )
                    }]
                )
                block = response.content[0]
                text = block.text if isinstance(block, anthropic.types.TextBlock) else "{}"
                text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                result = json.loads(text)
                summary = result.get("summary", "").strip()
                tags = result.get("tags", [])
                if summary and tags:
                    break
                print(f"Haiku attempt {attempt + 1}: missing {'summary' if not summary else 'tags'} for {url}")
            except Exception as e:
                print(f"Haiku attempt {attempt + 1} error for {url}: {e}")

        if not summary or not tags:
            print(f"Haiku failed after 3 attempts for {url}, storing ERROR")
            summary = "ERROR"
            tags = []

        supabase.table("news_articles").insert({
            "url": url,
            "title": title,
            "published_at": published_at,
            "full_text": full_text,
            "summary": summary,
            "tags": tags,
        }).execute()
        print(f"Stored article: {title[:60]}")
