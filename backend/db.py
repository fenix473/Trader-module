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