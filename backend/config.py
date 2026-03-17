import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "TSLA"]
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MA_CROSSOVER_LOOKBACK_DAYS = 220       # market days (need ≥200 for SMA-200)
RSI_DIVERGENCE_LOOKBACK_DAYS = 95      # market days (need ≥90 for divergence lookback)

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "https://fenix473.app.n8n.cloud/webhook/ba0d1190-ed2b-4f6a-829c-141cec7b7f74",
)

