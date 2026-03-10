import asyncio
import json
import anthropic
from db import get_next_pending_article, supabase
from config import ANTHROPIC_API_KEY

_anthropic = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def enrich_pending():
    while True:
        article = get_next_pending_article()
        if not article:
            print("No pending articles to enrich.")
            return

        print(f"Enriching: {article['title'][:60]}")
        try:
            response = _anthropic.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                tools=[{"type": "web_fetch_20260209", "name": "web_fetch"}],
                messages=[{
                    "role": "user",
                    "content": (
                        f"Fetch this article URL and return a JSON object with:\n"
                        f"- \"summary\": 2-3 sentence summary of the article\n"
                        f"- \"tags\": list of stock ticker symbols mentioned (e.g. [\"AAPL\", \"MSFT\"]) — empty list if none\n"
                        f"URL: {article['url']}\n"
                        f"Return only the JSON, no explanation."
                    )
                }]
            )
            text_blocks = [b for b in response.content if b.type == "text"]
            if not text_blocks:
                print(f"No content returned for {article['url']} — marking failed")
                supabase.table("news_articles").update(
                    {"enrichment_status": "failed"}
                ).eq("id", article["id"]).execute()
            else:
                raw = text_blocks[-1].text
                start = raw.find('{')
                end = raw.rfind('}')
                if start == -1 or end == -1:
                    print(f"No JSON in response for {article['url']} — Claude said: {raw[:200]!r}")
                    supabase.table("news_articles").update(
                        {"enrichment_status": "failed"}
                    ).eq("id", article["id"]).execute()
                else:
                    try:
                        result = json.loads(raw[start:end + 1])
                        summary = result.get("summary", "").strip()
                        tags = result.get("tags", [])

                        if not summary:
                            print(f"Empty summary for {article['url']} — marking failed")
                            supabase.table("news_articles").update(
                                {"enrichment_status": "failed"}
                            ).eq("id", article["id"]).execute()
                        else:
                            supabase.table("news_articles").update({
                                "summary": summary,
                                "tags": tags,
                                "enrichment_status": "enriched",
                            }).eq("id", article["id"]).execute()
                            print(f"Enriched: {article['title'][:60]}")

                    except json.JSONDecodeError as e:
                        print(f"JSON parse error for {article['url']}: {e} — marking error")
                        supabase.table("news_articles").update(
                            {"enrichment_status": "error"}
                        ).eq("id", article["id"]).execute()

        except Exception as e:
            print(f"Error enriching {article['url']}: {e} — marking error")
            supabase.table("news_articles").update(
                {"enrichment_status": "error"}
            ).eq("id", article["id"]).execute()

        print("Cooling down 90s...")
        await asyncio.sleep(90)
