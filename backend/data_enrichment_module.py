import asyncio
import json
from openai import OpenAI
from db import get_next_pending_article, supabase
from config import OPENROUTER_API_KEY

_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

FREE_MODELS = [
    "openrouter/hunter-alpha",
    "openrouter/healer-alpha",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

SLEEP_BETWEEN_ARTICLES = 10  # seconds — stay under 8 req/min rate limit

PROMPT = (
    "Read the following article and return a JSON object with:\n"
    "- \"summary\": 2-3 sentence summary\n"
    "- \"tags\": list of stock ticker symbols mentioned (e.g. [\"AAPL\", \"MSFT\"]) — empty list if none\n"
    "Return only the JSON, no explanation.\n\n"
)


async def enrich_pending():
    while True:
        article = get_next_pending_article()
        if not article:
            print("No pending articles to enrich.")
            return

        full_text = (article.get("full_text") or "").strip()
        if not full_text:
            print(f"No full_text for {article['url']} — marking failed")
            supabase.table("news_articles").update(
                {"enrichment_status": "failed"}
            ).eq("id", article["id"]).execute()
            continue

        print(f"Enriching: {article['title'][:60]}")

        response = None
        for model in FREE_MODELS:
            try:
                response = _client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": PROMPT + full_text}],
                    max_tokens=512,
                )
                print(f"  model: {model}")
                break
            except Exception as e:
                print(f"  {model} failed: {e}, trying next...")

        if response is None:
            print(f"All models failed for {article['url']} — marking error")
            supabase.table("news_articles").update(
                {"enrichment_status": "error"}
            ).eq("id", article["id"]).execute()
            continue

        raw = response.choices[0].message.content or ""
        start = raw.find('{')
        end = raw.rfind('}')

        if start == -1 or end == -1:
            print(f"No JSON in response for {article['url']} — model said: {raw[:200]!r}")
            supabase.table("news_articles").update(
                {"enrichment_status": "failed"}
            ).eq("id", article["id"]).execute()
            continue

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

        await asyncio.sleep(SLEEP_BETWEEN_ARTICLES)