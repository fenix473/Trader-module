from __future__ import annotations

import math


class InsufficientDataError(Exception):
    pass


def _is_valid(v) -> bool:
    """Return True if v is a real finite number (not None, not NaN)."""
    if v is None:
        return False
    try:
        return math.isfinite(v)
    except TypeError:
        return False


def _find_swing_lows(arr: list, window: int = 5) -> list[int]:
    """Indices where arr[i] is the minimum of the surrounding 2*window+1 bar window."""
    n = len(arr)
    indices = []
    for i in range(window, n - window):
        left_ok = all(arr[i] <= arr[j] for j in range(i - window, i))
        right_ok = all(arr[i] <= arr[j] for j in range(i + 1, i + window + 1))
        if left_ok and right_ok:
            indices.append(i)
    return indices


def _find_swing_highs(arr: list, window: int = 5) -> list[int]:
    """Indices where arr[i] is the maximum of the surrounding 2*window+1 bar window."""
    n = len(arr)
    indices = []
    for i in range(window, n - window):
        left_ok = all(arr[i] >= arr[j] for j in range(i - window, i))
        right_ok = all(arr[i] >= arr[j] for j in range(i + 1, i + window + 1))
        if left_ok and right_ok:
            indices.append(i)
    return indices


def _score_confidence(rsi_delta: float) -> str:
    if rsi_delta > 5:
        return "high"
    if rsi_delta > 2:
        return "medium"
    return "low"


def _check_low_divergence(
    lows: list, rsi_series: list, low_indices: list, n: int
) -> dict | None:
    """Return divergence dict if bullish or hidden_bullish found in swing lows, else None."""
    # Filter to indices where RSI is valid
    valid = [i for i in low_indices if _is_valid(rsi_series[i])]
    if len(valid) < 2:
        return None
    p1, p2 = valid[-1], valid[-2]
    price_p1, price_p2 = lows[p1], lows[p2]
    rsi_p1, rsi_p2 = rsi_series[p1], rsi_series[p2]
    rsi_delta = abs(rsi_p1 - rsi_p2)

    if price_p1 < price_p2 and rsi_p1 > rsi_p2:
        div_type = "bullish"
    elif price_p1 > price_p2 and rsi_p1 < rsi_p2:
        div_type = "hidden_bullish"
    else:
        return None

    return {
        "divergence_type": div_type,
        "confidence": _score_confidence(rsi_delta),
        "bars_ago": n - 1 - p1,
        "price_pivot_value": float(price_p1),
        "rsi_pivot_value": float(rsi_p1),
        "_rsi_delta": rsi_delta,
    }


def _check_high_divergence(
    highs: list, rsi_series: list, high_indices: list, n: int
) -> dict | None:
    """Return divergence dict if bearish or hidden_bearish found in swing highs, else None."""
    valid = [i for i in high_indices if _is_valid(rsi_series[i])]
    if len(valid) < 2:
        return None
    p1, p2 = valid[-1], valid[-2]
    price_p1, price_p2 = highs[p1], highs[p2]
    rsi_p1, rsi_p2 = rsi_series[p1], rsi_series[p2]
    rsi_delta = abs(rsi_p1 - rsi_p2)

    if price_p1 > price_p2 and rsi_p1 < rsi_p2:
        div_type = "bearish"
    elif price_p1 < price_p2 and rsi_p1 > rsi_p2:
        div_type = "hidden_bearish"
    else:
        return None

    return {
        "divergence_type": div_type,
        "confidence": _score_confidence(rsi_delta),
        "bars_ago": n - 1 - p1,
        "price_pivot_value": float(price_p1),
        "rsi_pivot_value": float(rsi_p1),
        "_rsi_delta": rsi_delta,
    }


def compute_rsi_divergence(
    closes: list,
    highs: list,
    lows: list,
    rsi_series: list,
    lookback: int = 90,
    rsi_period: int = 14,
) -> dict:
    """
    Detect RSI divergence from pre-computed OHLC + RSI arrays.

    Args:
        closes:     List of daily close prices (plain floats, aligned with highs/lows/rsi).
        highs:      List of daily high prices.
        lows:       List of daily low prices.
        rsi_series: Pre-computed RSI values (None/NaN for warm-up bars is OK).
        lookback:   How many trailing bars to analyse (default 90).
        rsi_period: The RSI period used (stored for reproducibility, not recomputed here).

    Returns:
        dict with keys: divergence_type, confidence, bars_ago, rsi_period,
                        price_pivot_value, rsi_pivot_value, raw_payload.

    Raises:
        InsufficientDataError: if fewer than 60 bars are provided.
        ValueError: if input arrays are not the same length.
    """
    MIN_BARS = 60
    SWING_WINDOW = 5
    _CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}

    total = len(closes)
    if total < MIN_BARS:
        raise InsufficientDataError(f"Need ≥{MIN_BARS} bars, got {total}")
    if not (len(highs) == len(lows) == len(rsi_series) == total):
        raise ValueError(
            f"Input arrays must be same length: closes={total}, highs={len(highs)}, "
            f"lows={len(lows)}, rsi={len(rsi_series)}"
        )

    # Slice to lookback window
    closes = closes[-lookback:]
    highs = highs[-lookback:]
    lows = lows[-lookback:]
    rsi_series = rsi_series[-lookback:]
    n = len(closes)

    low_indices = _find_swing_lows(lows, SWING_WINDOW)
    high_indices = _find_swing_highs(highs, SWING_WINDOW)

    raw_payload = {
        "lookback_bars": n,
        "swing_window": SWING_WINDOW,
        "rsi_period": rsi_period,
        "price_swing_lows": [
            {"index": i, "price": float(lows[i]), "rsi": float(rsi_series[i]) if _is_valid(rsi_series[i]) else None}
            for i in low_indices
        ],
        "price_swing_highs": [
            {"index": i, "price": float(highs[i]), "rsi": float(rsi_series[i]) if _is_valid(rsi_series[i]) else None}
            for i in high_indices
        ],
        "closes_tail": [float(c) for c in closes[-30:]],
        "rsi_series_tail": [
            float(r) if _is_valid(r) else None for r in rsi_series[-30:]
        ],
    }

    low_result = _check_low_divergence(lows, rsi_series, low_indices, n)
    high_result = _check_high_divergence(highs, rsi_series, high_indices, n)

    candidates = [r for r in [low_result, high_result] if r is not None]

    if not candidates:
        return {
            "divergence_type": "none",
            "confidence": None,
            "bars_ago": None,
            "rsi_period": rsi_period,
            "price_pivot_value": None,
            "rsi_pivot_value": None,
            "raw_payload": raw_payload,
        }

    # Pick highest confidence; on tie prefer smaller bars_ago (more recent)
    best = max(
        candidates,
        key=lambda c: (_CONFIDENCE_RANK.get(c["confidence"], 0), -(c["bars_ago"] or 0)),
    )
    return {
        "divergence_type": best["divergence_type"],
        "confidence": best["confidence"],
        "bars_ago": best["bars_ago"],
        "rsi_period": rsi_period,
        "price_pivot_value": best["price_pivot_value"],
        "rsi_pivot_value": best["rsi_pivot_value"],
        "raw_payload": raw_payload,
    }
