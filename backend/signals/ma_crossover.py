from datetime import date
import pandas as pd


def compute(prices: list[tuple[date, float]]) -> dict:
    if len(prices) < 200:
        raise ValueError(f"Need ≥200 closes, got {len(prices)}")

    dates, closes = zip(*prices)
    s = pd.Series(list(closes), index=list(dates))

    sma_50 = s.rolling(50).mean()
    sma_200 = s.rolling(200).mean()

    diff = sma_50 - sma_200

    # Find most recent crossover by scanning backwards
    crossover_date = None
    for i in range(len(diff) - 1, 0, -1):
        if pd.isna(diff.iloc[i]) or pd.isna(diff.iloc[i - 1]):
            continue
        if (diff.iloc[i] > 0) != (diff.iloc[i - 1] > 0):
            crossover_date = diff.index[i]
            break

    latest_spread = float(diff.iloc[-1])
    prev_spread = float(diff.iloc[-2])
    spread_pct = latest_spread / float(sma_200.iloc[-1]) * 100

    abs_pct = abs(spread_pct)
    narrowing = abs(latest_spread) < abs(prev_spread)
    if abs_pct > 3:
        trend_strength = "strong"
    elif abs_pct > 1 and narrowing:
        trend_strength = "weakening"
    else:
        trend_strength = "flat"

    return {
        "sma_50": round(float(sma_50.iloc[-1]), 4),
        "sma_200": round(float(sma_200.iloc[-1]), 4),
        "golden_cross_active": bool(diff.iloc[-1] > 0),
        "crossover_date": crossover_date,
        "days_since_cross": (date.today() - crossover_date).days if crossover_date else None,
        "ma_spread_pct": round(spread_pct, 4),
        "trend_strength": trend_strength,
    }
