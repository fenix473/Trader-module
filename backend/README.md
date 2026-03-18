# Trader Module — Backend

A production-grade FastAPI backend powering real-time stock monitoring, AI-enriched financial news, technical signal computation, and on-demand AI analysis workflows — all running autonomously through a multi-service async architecture.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Database Setup](#database-setup)
  - [Running the Server](#running-the-server)
- [API Reference](#api-reference)
  - [Market Status](#market-status)
  - [Symbols](#symbols)
  - [Prices](#prices)
  - [News](#news)
  - [Signals — Moving Average Crossover](#signals--moving-average-crossover)
  - [Signals — RSI Divergence](#signals--rsi-divergence)
  - [AI Analysis](#ai-analysis)
- [Background Tasks](#background-tasks)
- [Signal Algorithms](#signal-algorithms)
  - [Moving Average Crossover](#moving-average-crossover)
  - [RSI Divergence](#rsi-divergence)
- [External Integrations](#external-integrations)
- [Database Schema](#database-schema)
- [Deployment](#deployment)

---

## Overview

The backend serves as the data engine for the Trader Module platform. On startup it launches a set of background jobs that continuously:

1. **Fetch real-time stock quotes** from Finnhub every minute during market hours.
2. **Pull financial news** from Yahoo Finance RSS, at adaptive frequencies based on market hours.
3. **Enrich news articles** with AI-generated summaries and ticker tags via OpenRouter free models.
4. **Compute nightly technical signals** — Moving Average crossovers and RSI divergences — using historical data from Yahoo Finance.
5. **Trigger AI analysis workflows** through N8N webhooks on demand.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     FastAPI App                      │
│                      main.py                         │
│                                                      │
│  REST API Endpoints ──────────────────────────────┐  │
│  Background Scheduler (APScheduler) ──────────────┤  │
│    ├─ fetch_and_store()   every 1 min              │  │
│    ├─ fetch_news()        every 5–60 min           │  │
│    ├─ enrich_pending()    every 10 min             │  │
│    ├─ compute_ma_crossover_all()  nightly 18:00 ET │  │
│    └─ compute_rsi_divergence_all() nightly 18:05 ET│  │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
    Supabase        Finnhub       OpenRouter
   (Postgres)    (Live quotes)  (AI enrichment)
                                      │
                               Yahoo Finance RSS
                               Yahoo Finance OHLC
                                      │
                                 N8N Webhook
                              (AI analysis reports)
```

---

## Project Structure

```
backend/
├── main.py                      # FastAPI app, all routes, lifespan management
├── config.py                    # Environment variable loading and constants
├── db.py                        # All database query functions
├── tasks.py                     # Background task functions (price fetch, news, signals)
├── data_enrichment_module.py    # AI news enrichment pipeline
├── setup_db.py                  # One-time database table creation script
├── requirements.txt             # Python dependencies
├── .env                         # API keys (not committed)
└── signals/
    ├── registry.py              # Extensible signal registration system
    ├── ma_crossover.py          # SMA-50/SMA-200 crossover computation
    └── rsi_divergence.py        # RSI divergence detection algorithm
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI Server | [Uvicorn](https://www.uvicorn.org/) |
| Database | [Supabase](https://supabase.com/) (PostgreSQL) |
| Task Scheduling | [APScheduler](https://apscheduler.readthedocs.io/) |
| HTTP Client | [HTTPX](https://www.python-httpx.org/) (async) |
| Stock Quotes | [Finnhub API](https://finnhub.io/) |
| Historical Data | [yfinance](https://github.com/ranaroussi/yfinance) |
| News Feed | Yahoo Finance RSS via [feedparser](https://feedparser.readthedocs.io/) |
| Article Extraction | [trafilatura](https://trafilatura.readthedocs.io/) |
| AI Enrichment | [OpenRouter API](https://openrouter.ai/) (via openai SDK) |
| Analysis Workflows | [N8N](https://n8n.io/) webhooks |
| Data Processing | pandas, numpy |

---

## Getting Started

### Prerequisites

- Python 3.10+
- A [Supabase](https://supabase.com/) project
- A [Finnhub](https://finnhub.io/) API key (free tier works)
- An [OpenRouter](https://openrouter.ai/) API key (free tier works)
- An [N8N](https://n8n.io/) instance with the analysis webhook configured

### Installation

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Stock quotes
FINNHUB_API_KEY=your_finnhub_api_key

# Database
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

# AI enrichment
OPENROUTER_API_KEY=sk-or-v1-...

# Claude API (optional, if used directly)
ANTHROPIC_API_KEY=sk-ant-api03-...

# N8N analysis workflow
N8N_WEBHOOK_URL=https://your-n8n-instance/webhook/your-webhook-id
```

### Database Setup

Run the setup script once to create all required tables in Supabase:

```bash
python setup_db.py
```

### Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

## API Reference

All endpoints return JSON. Timestamps are in ISO 8601 format (UTC).

### Market Status

#### `GET /market/status`

Returns whether the US stock market is currently open.

```json
{ "open": true }
```

---

### Symbols

#### `GET /symbols`

Returns all tracked stock symbols.

#### `POST /symbols`

Add a new symbol to track. Immediately triggers a price fetch for that symbol.

**Body:**
```json
{ "symbol": "NVDA" }
```

---

### Prices

#### `GET /prices`

Returns the last 100 price entries across all tracked symbols.

#### `GET /prices/latest`

Returns the most recent price for each tracked symbol.

#### `GET /prices/{symbol}`

Returns price history for a specific symbol.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 10 | Number of results to return |
| `offset` | int | 0 | Pagination offset |
| `date` | string | — | Filter by date (`YYYY-MM-DD`), returns all prices for that day in ET |

---

### News

#### `GET /news/latest`

Returns the latest news articles with AI-generated summaries, ticker tags, and enrichment status.

---

### Signals — Moving Average Crossover

Compares the 50-day and 200-day Simple Moving Averages to identify golden cross / death cross conditions.

#### `GET /signals/ma-crossover`

Returns the latest MA crossover signal for all tracked symbols.

#### `GET /signals/ma-crossover/{symbol}`

Returns the latest MA crossover signal for a specific symbol.

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sma_50` | float | Current 50-day SMA |
| `sma_200` | float | Current 200-day SMA |
| `golden_cross_active` | bool | True if SMA-50 > SMA-200 |
| `crossover_date` | date | Date of the most recent crossover |
| `days_since_cross` | int | Trading days elapsed since crossover |
| `ma_spread_pct` | float | `(SMA50 - SMA200) / SMA200 * 100` |
| `trend_strength` | string | `"strong"`, `"weakening"`, or `"flat"` |

#### `POST /signals/ma-crossover/{symbol}/refresh`

Manually trigger MA crossover recomputation for a symbol. Returns `202 Accepted`.

---

### Signals — RSI Divergence

Detects bullish and bearish divergences between price action and the 14-period RSI.

#### `GET /signals/rsi-divergence`

Returns RSI divergence signals.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | — | Filter by symbol |
| `timeframe` | string | `"1d"` | Timeframe (`"1d"`, etc.) |
| `limit` | int | 30 | Number of results to return |

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `divergence_type` | string | `"bullish"`, `"bearish"`, `"hidden_bullish"`, `"hidden_bearish"`, `"none"` |
| `confidence` | string | `"high"`, `"medium"`, `"low"` |
| `bars_ago` | int | How many bars ago the divergence occurred |
| `price_pivot_value` | float | Price at the pivot point |
| `rsi_pivot_value` | float | RSI value at the pivot point |
| `raw_payload` | object | Detailed swing analysis metadata |

#### `POST /signals/rsi-divergence/trigger`

Manually trigger RSI divergence computation. Returns `202 Accepted`.

**Body:**
```json
{ "symbol": "AAPL", "timeframe": "1d" }
```

---

### AI Analysis

Integration with an N8N workflow that generates AI-powered market analysis reports.

#### `POST /analysis/request`

Trigger an AI analysis workflow for a symbol via the N8N webhook. Returns `202 Accepted`.

**Body:**
```json
{ "symbol": "AAPL" }
```

**Flow:** Sets `should_analyze=true` on the symbol → calls N8N webhook → resets flag.

#### `GET /analysis/status/{symbol}`

Check whether an analysis is pending for a symbol.

```json
{ "pending": false }
```

#### `POST /analysis/complete/{symbol}`

Mark an analysis as complete (called by N8N after it writes the report).

#### `GET /analysis/latest`

Returns the latest 200 analysis reports, deduplicated by symbol.

#### `GET /analysis/latest/{symbol}`

Returns the most recent analysis report for a specific symbol.

#### `GET /analysis/reports`

Returns paginated analysis reports.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 10 | Number of results |
| `offset` | int | 0 | Pagination offset |
| `symbol` | string | — | Filter by symbol |

#### `GET /analysis/history/{symbol}`

Returns the last 30 analysis reports for a symbol.

---

## Background Tasks

All tasks are scheduled on app startup via APScheduler.

| Task | Schedule | Description |
|------|----------|-------------|
| `fetch_and_store` | Every 1 min | Fetch live quotes from Finnhub for all tracked symbols (market hours only) |
| `fetch_news` | Adaptive | Pull Yahoo Finance RSS. Every 5 min during market hours, every 30 min pre/post-market, every 60 min otherwise |
| `enrich_pending` | Every 10 min | AI-enrich pending news articles via OpenRouter |
| `compute_ma_crossover_all` | Daily @ 18:00 ET | Recompute MA crossover signals for all symbols |
| `compute_rsi_divergence_all` | Daily @ 18:05 ET | Recompute RSI divergence signals for all symbols |

---

## Signal Algorithms

### Moving Average Crossover

**Lookback:** 220 market days (from yfinance)
**Requires:** ≥ 200 data points

1. Compute SMA-50 and SMA-200 on daily close prices.
2. Scan backwards to find the most recent bar where the sign of `(SMA50 − SMA200)` changed — this is the crossover date.
3. Compute spread: `(SMA50 − SMA200) / SMA200 × 100`.
4. Classify trend strength:
   - **`strong`** — spread > 3%
   - **`weakening`** — spread between 1–3% and narrowing vs. previous bar
   - **`flat`** — spread ≤ 1%
5. Set `golden_cross_active = true` when SMA-50 > SMA-200.

### RSI Divergence

**Lookback:** 95 market days (from yfinance)
**RSI Period:** 14 (Wilder's smoothing via pandas EWM)
**Swing window:** 5 bars

1. Identify swing lows (local minima within ±5 bars) and swing highs (local maxima).
2. Compare the two most recent swing lows for **bullish divergence**:
   - **Bullish:** Price lower low + RSI higher low
   - **Hidden bullish:** Price higher low + RSI lower low
3. Compare the two most recent swing highs for **bearish divergence**:
   - **Bearish:** Price higher high + RSI lower high
   - **Hidden bearish:** Price lower high + RSI higher high
4. Score confidence by |ΔRSI|:
   - **`high`** — Δ RSI > 5
   - **`medium`** — Δ RSI > 2
   - **`low`** — Δ RSI ≤ 2
5. Return the highest-confidence, most-recent divergence found.

---

## External Integrations

### Finnhub

- **Endpoint:** `https://finnhub.io/api/v1/quote`
- **Used for:** Real-time stock quotes (current price, open, high, low)
- **Note:** 1-second delay added between symbols in batch fetches to respect rate limits.

### Yahoo Finance RSS

- **Feed:** `https://finance.yahoo.com/news/rssindex`
- **Used for:** Financial news headlines and article URLs
- **Parsing:** feedparser + trafilatura for full-text extraction

### OpenRouter (AI News Enrichment)

- **Base URL:** `https://openrouter.ai/api/v1` (via openai SDK)
- **Models used (rotated):** Free-tier models from OpenRouter
- **Purpose:** Generate 2–3 sentence article summaries and extract relevant ticker symbols
- **Rate limit:** 10-second sleep between requests (~6 req/min)

### N8N Webhook

- **Trigger:** `POST /analysis/request`
- **Payload:** `{"symbol": "AAPL"}`
- **Expected response:** `{"message": "..."}`
- **N8N writes** the resulting analysis report directly to the `analysis_reports` Supabase table.

---

## Database Schema

### `symbols`
| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK, auto-increment |
| symbol | text | Unique |
| created_at | timestamptz | |
| should_analyze | boolean | N8N trigger flag |

### `prices`
| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK, auto-increment |
| symbol | text | |
| price | numeric | |
| created_at | timestamptz | Default: now() |

### `news_articles`
| Column | Type | Notes |
|--------|------|-------|
| id | uuid / bigint | PK |
| url | text | Unique |
| title | text | |
| published_at | timestamptz | |
| full_text | text | |
| summary | text | AI-generated |
| tags | text[] | Ticker symbols |
| enrichment_status | text | `pending`, `enriched`, `failed`, `error` |

### `ma_crossover_signals`
| Column | Type | Notes |
|--------|------|-------|
| symbol | text | |
| computed_date | date | Unique with symbol |
| sma_50 | numeric | |
| sma_200 | numeric | |
| golden_cross_active | boolean | |
| crossover_date | date | |
| days_since_cross | int | |
| ma_spread_pct | numeric | |
| trend_strength | text | `strong`, `weakening`, `flat` |
| computed_at | timestamptz | |

### `rsi_divergence_signals`
| Column | Type | Notes |
|--------|------|-------|
| symbol | text | |
| timeframe | text | e.g. `"1d"` |
| computed_at | timestamptz | |
| divergence_type | text | `bullish`, `bearish`, `hidden_bullish`, `hidden_bearish`, `none` |
| confidence | text | `high`, `medium`, `low` |
| bars_ago | int | |
| price_pivot_value | numeric | |
| rsi_pivot_value | numeric | |
| rsi_period | int | Default: 14 |
| raw_payload | jsonb | Full swing analysis detail |

### `analysis_reports`
| Column | Type | Notes |
|--------|------|-------|
| symbol | text | |
| generated_at | timestamptz | |
| ... | ... | Additional fields written by N8N |

---

## Deployment

The backend is designed to run as a single long-lived process. It self-manages all background scheduling internally — no external cron or worker queue required.

- **CORS** is locked to the production frontend (`https://trader-module-frontend.vercel.app`) and `localhost:3000` for local development.
- **Database access** is handled exclusively server-side via the Supabase service role, keeping all credentials off the client.
- **Environment variables** are managed via `.env` (excluded from version control).