import asyncio
import httpx
from datetime import datetime, time
from zoneinfo import ZoneInfo
from config import FINNHUB_API_KEY
from db import supabase

_EASTERN = ZoneInfo("America/New_York")
_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)


def is_market_open() -> bool:
    now = datetime.now(_EASTERN)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


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
