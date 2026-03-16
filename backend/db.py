from typing import Optional
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


async def get_latest_news(limit=None):
    query = (
        supabase.table("news_articles")
        .select("id, tags, published_at, summary, title, url, enrichment_status")
        .order("published_at", desc=True)
    )
    if limit:
        query = query.limit(limit)
    res = query.execute()
    return res.data


def get_next_pending_article():
    res = (
        supabase.table("news_articles")
        .select("id, url, title, published_at, full_text")
        .eq("enrichment_status", "pending")
        .order("published_at", desc=True)  # DESC — newest first (LIFO)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def upsert_ma_crossover(symbol: str, signal: dict) -> None:
    from datetime import date
    row = {
        "symbol": symbol,
        "computed_date": str(date.today()),
        "sma_50": signal["sma_50"],
        "sma_200": signal["sma_200"],
        "golden_cross_active": signal["golden_cross_active"],
        "crossover_date": str(signal["crossover_date"]) if signal["crossover_date"] else None,
        "days_since_cross": signal["days_since_cross"],
        "ma_spread_pct": signal["ma_spread_pct"],
        "trend_strength": signal["trend_strength"],
    }
    supabase.table("ma_crossover_signals").upsert(row, on_conflict="symbol,computed_date").execute()


def get_ma_crossover(symbol: str) -> Optional[dict]:
    res = (
        supabase.table("ma_crossover_signals")
        .select("*")
        .eq("symbol", symbol)
        .order("computed_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_all_ma_crossovers() -> list[dict]:
    res = (
        supabase.table("ma_crossover_signals")
        .select("*")
        .order("computed_at", desc=True)
        .execute()
    )
    seen, rows = set(), []
    for row in res.data:
        if row["symbol"] not in seen:
            seen.add(row["symbol"])
            rows.append(row)
    return rows