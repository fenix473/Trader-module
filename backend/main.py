import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from pydantic import BaseModel
from db import supabase, get_latest_news, get_ma_crossover, get_all_ma_crossovers, get_rsi_divergence
from tasks import fetch_and_store, fetch_single, fetch_news, is_market_open, compute_ma_crossover_for_symbol, compute_ma_crossover_all, compute_rsi_divergence_for_symbol, compute_rsi_divergence_all
from data_enrichment_module import enrich_pending


class SymbolIn(BaseModel):
    symbol: str

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(fetch_and_store, "interval", minutes=1)
    scheduler.add_job(fetch_news, "interval", minutes=5)
    scheduler.add_job(enrich_pending, "interval", minutes=10, max_instances=1)
    scheduler.add_job(compute_ma_crossover_all, "cron", hour=18, minute=0, timezone="America/New_York")
    scheduler.add_job(compute_rsi_divergence_all, "cron", hour=18, minute=5, timezone="America/New_York")
    scheduler.start()
    await fetch_and_store()
    await fetch_news()
    asyncio.create_task(enrich_pending())  # start enrichment backlog immediately
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://trader-module-frontend.vercel.app", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/market/status")
async def market_status():
    return {"open": is_market_open()}


@app.get("/prices")
async def get_prices():
    res = supabase.table("prices").select("*").order("created_at", desc=True).limit(100).execute()
    return res.data


@app.get("/symbols")
async def get_symbols():
    res = supabase.table("symbols").select("*").order("created_at").execute()
    return res.data


@app.post("/symbols", status_code=201)
async def add_symbol(body: SymbolIn, background_tasks: BackgroundTasks):
    symbol = body.symbol.upper().strip()
    existing = supabase.table("symbols").select("id").eq("symbol", symbol).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail=f"{symbol} already exists")
    res = supabase.table("symbols").insert({"symbol": symbol}).execute()
    background_tasks.add_task(fetch_single, symbol)
    return res.data[0]


@app.get("/prices/latest")
async def get_latest_prices():
    symbols_res = supabase.table("symbols").select("symbol").execute()
    symbols = [row["symbol"] for row in symbols_res.data]
    rows = []
    for symbol in symbols:
        res = (
            supabase.table("prices")
            .select("*")
            .eq("symbol", symbol)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            rows.append(res.data[0])
    return rows


@app.get("/prices/{symbol}")
async def get_price(symbol: str, limit: int = 10, offset: int = 0, date: str = None):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    query = (
        supabase.table("prices")
        .select("*")
        .eq("symbol", symbol.upper())
        .order("created_at", desc=True)
    )
    if date:
        et = ZoneInfo("America/New_York")
        start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=et)
        end = start + timedelta(days=1)
        query = query.gte("created_at", start.isoformat()).lt("created_at", end.isoformat()).limit(500)
    else:
        query = query.range(offset, offset + limit - 1)
    res = query.execute()
    return res.data


@app.get("/news/latest")
async def get_latest_news_route():
    return await get_latest_news()


@app.get("/signals/ma-crossover")
async def get_all_ma_crossover_signals():
    return get_all_ma_crossovers()


@app.get("/signals/ma-crossover/{symbol}")
async def get_ma_crossover_signal(symbol: str):
    row = get_ma_crossover(symbol.upper())
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No signal computed for {symbol.upper()}. Trigger a manual run or wait for the nightly task.",
        )
    return row


@app.post("/signals/ma-crossover/{symbol}/refresh", status_code=202)
async def refresh_ma_crossover(symbol: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(compute_ma_crossover_for_symbol, symbol.upper())
    return {"status": "accepted", "symbol": symbol.upper()}


class RsiDivergenceTriggerIn(BaseModel):
    symbol: str
    timeframe: str = "1d"


@app.get("/signals/rsi-divergence")
async def get_rsi_divergence_signal(symbol: str, timeframe: str = "1d", limit: int = 30):
    rows = get_rsi_divergence(symbol.upper(), timeframe, limit)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No RSI divergence signal for {symbol.upper()}. Trigger a manual run or wait for the nightly task.",
        )
    return rows


@app.post("/signals/rsi-divergence/trigger", status_code=202)
async def trigger_rsi_divergence(body: RsiDivergenceTriggerIn, background_tasks: BackgroundTasks):
    background_tasks.add_task(compute_rsi_divergence_for_symbol, body.symbol.upper(), body.timeframe)
    return {"status": "queued", "symbol": body.symbol.upper(), "timeframe": body.timeframe}