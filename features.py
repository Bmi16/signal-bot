"""Indicators, the rule-based candidate signal and the ML feature vector.

Everything here is pure (no network) so it can be reused for live signals AND for
building the historical training set with exactly the same logic.
"""
import math

MIN_BARS = 130
EPS = 1e-12

FEATURE_NAMES = [
    "rsi_dir", "atr_pct", "atr_ratio", "trend_gap", "trend_slope", "htf_gap",
    "ret_3", "ret_12", "ret_24", "range_pos", "body", "wick_against", "wick_with",
    "room_ahead", "hour_sin", "hour_cos", "dow", "is_buy",
]


# ---------- indicators ----------
def sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains += change
        else:
            losses -= change
    avg_gain, avg_loss = gains / period, losses / period
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        c, p = candles[i], candles[i - 1]
        trs.append(max(c["high"] - c["low"], abs(c["high"] - p["close"]), abs(c["low"] - p["close"])))
    return sum(trs) / period


# ---------- support / resistance ----------
def find_support_resistance(candles, lookback=50, tolerance=0.0005):
    recent = candles[-lookback:]
    supports, resistances = [], []
    for i in range(2, len(recent) - 2):
        lo, hi = recent[i]["low"], recent[i]["high"]
        if lo < min(recent[i - 2]["low"], recent[i - 1]["low"], recent[i + 1]["low"], recent[i + 2]["low"]):
            supports.append(lo)
        if hi > max(recent[i - 2]["high"], recent[i - 1]["high"], recent[i + 1]["high"], recent[i + 2]["high"]):
            resistances.append(hi)

    def merge(levels):
        levels = sorted(levels)
        merged = []
        for lv in levels:
            if merged and abs(lv - merged[-1]) / max(merged[-1], EPS) < tolerance:
                merged[-1] = (merged[-1] + lv) / 2
            else:
                merged.append(lv)
        return merged

    return merge(supports), merge(resistances)


def _nearest_ahead(direction, entry, supports, resistances):
    if direction == "BUY":
        above = [r for r in resistances if r > entry]
        return min(above) if above else None
    below = [s for s in supports if s < entry]
    return max(below) if below else None


# ---------- rule-based candidate ----------
def candidate_signal(candles, cfg):
    """The original strategy (SMA10/30 trend + RSI limits + filters). Returns None if no setup."""
    if len(candles) < MIN_BARS:
        return None
    closes = [c["close"] for c in candles]
    fast, slow = sma(closes, 10), sma(closes, 30)
    r, a = rsi(closes, 14), atr(candles, 14)
    if fast is None or slow is None or r is None or a is None or a <= 0:
        return None
    entry = closes[-1]
    if a / entry < cfg["min_atr_pct"]:
        return None

    if fast >= slow and r < cfg["rsi_hi"]:
        direction = "BUY"
    elif fast < slow and r > cfg["rsi_lo"]:
        direction = "SELL"
    else:
        return None

    if cfg["htf_filter"]:
        h_fast, h_slow = sma(closes, 40), sma(closes, 120)
        if h_fast is None or h_slow is None:
            return None
        if (direction == "BUY") != (h_fast >= h_slow):
            return None

    if cfg["sr_filter"]:
        tp1_dist = a * cfg["sl_mult"] * cfg["tp_ratios"][0]
        tp1 = entry + tp1_dist if direction == "BUY" else entry - tp1_dist
        supports, resistances = find_support_resistance(candles)
        obstacle = _nearest_ahead(direction, entry, supports, resistances)
        if obstacle is not None:
            if direction == "BUY" and obstacle < tp1:
                return None
            if direction == "SELL" and obstacle > tp1:
                return None

    return {"direction": direction, "entry": entry, "atr": a, "rsi": r}


# ---------- ML features ----------
def build_features(candles, direction, cfg):
    """Direction-aware features (all normalised by ATR so pairs are comparable)."""
    s = 1.0 if direction == "BUY" else -1.0
    closes = [c["close"] for c in candles]
    close = closes[-1]
    a = atr(candles, 14)
    a50 = atr(candles, 50) or a
    r = rsi(closes, 14)
    fast, slow = sma(closes, 10), sma(closes, 30)
    slow_prev = sma(closes[:-5], 30)
    h_fast, h_slow = sma(closes, 40), sma(closes, 120)

    last = candles[-1]
    rng = last["high"] - last["low"] + EPS
    upper_wick = (last["high"] - max(last["open"], last["close"])) / rng
    lower_wick = (min(last["open"], last["close"]) - last["low"]) / rng

    hi20 = max(c["high"] for c in candles[-20:])
    lo20 = min(c["low"] for c in candles[-20:])
    pos = (close - lo20) / (hi20 - lo20 + EPS)

    supports, resistances = find_support_resistance(candles)
    obstacle = _nearest_ahead(direction, close, supports, resistances)
    unit = a * cfg["sl_mult"] * cfg["tp_ratios"][0]
    room = 5.0 if obstacle is None else min(5.0, abs(obstacle - close) / (unit + EPS))

    hour = last["dt"].hour
    f = {
        "rsi_dir": r if direction == "BUY" else 100 - r,
        "atr_pct": a / close * 100,
        "atr_ratio": a / (a50 + EPS),
        "trend_gap": s * (fast - slow) / a,
        "trend_slope": s * (slow - slow_prev) / a,
        "htf_gap": s * (h_fast - h_slow) / a,
        "ret_3": s * (close - closes[-4]) / a,
        "ret_12": s * (close - closes[-13]) / a,
        "ret_24": s * (close - closes[-25]) / a,
        "range_pos": pos if direction == "BUY" else 1 - pos,
        "body": s * (last["close"] - last["open"]) / rng,
        "wick_against": upper_wick if direction == "BUY" else lower_wick,
        "wick_with": lower_wick if direction == "BUY" else upper_wick,
        "room_ahead": room,
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        "dow": float(last["dt"].weekday()),
        "is_buy": 1.0 if direction == "BUY" else 0.0,
    }
    return {k: float(f[k]) for k in FEATURE_NAMES}
