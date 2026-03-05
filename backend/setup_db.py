import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

db_url = os.getenv("DATABASE_URL")

conn = psycopg2.connect(db_url)
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS prices (
        id bigint generated always as identity primary key,
        symbol text not null,
        price numeric not null,
        created_at timestamptz default now()
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS symbols (
        id bigint generated always as identity primary key,
        symbol text not null unique,
        created_at timestamptz default now()
    );
""")

cur.execute("""
    INSERT INTO symbols (symbol) VALUES ('AAPL'), ('GOOGL'), ('MSFT'), ('TSLA')
    ON CONFLICT (symbol) DO NOTHING;
""")

conn.commit()
cur.close()
conn.close()

print("Tables 'prices' and 'symbols' created successfully.")
