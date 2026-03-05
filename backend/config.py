import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SYMBOLS = ["AAPL", "GOOGL", "MSFT", "TSLA"]
