"""Market data access (Twelve Data) shared by every job."""
import datetime
import time

import requests

import config

BASE_URL = "https://api.twelvedata.com/time_series"
INTERVAL_MINUTES = {"1min": 1, "5min": 5, "15min": 15, "30min": 30, "1h": 60, "2h": 120, "4h": 240, "1day": 1440}


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def fetch_candles(symbol: str, interval: str = "1h", output_size: int = 200, retries: int = 2) -> list:
    """Returns candles oldest -> newest. The last one may still be forming."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": output_size,
        "order": "ASC",
        "timezone": "UTC",
        "apikey": config.TWELVE_DATA_API_KEY,
    }
    payload = {}
    for attempt in range(retries + 1):
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if "values" in payload:
            break
        if payload.get("code") == 429 and attempt < retries:
            time.sleep(20)  # per-minute credit limit: wait and retry
            continue
        raise RuntimeError(f"Twelve Data error for {symbol}: {payload.get('message', payload)}")

    candles = []
    for v in payload["values"]:
        candles.append({
            "dt": datetime.datetime.fromisoformat(v["datetime"]),
            "open": float(v["open"]),
            "high": float(v["high"]),
            "low": float(v["low"]),
            "close": float(v["close"]),
        })
    candles.sort(key=lambda c: c["dt"])
    return candles


def drop_forming(candles: list, interval: str = "1h", now=None) -> list:
    """Removes the last candle if it has not closed yet, so indicators only see finished bars."""
    if not candles:
        return candles
    now = now or utc_now()
    minutes = INTERVAL_MINUTES.get(interval, 60)
    if candles[-1]["dt"] + datetime.timedelta(minutes=minutes) > now:
        return candles[:-1]
    return candles


def is_stale(candles: list, interval: str = "1h", now=None, bars: int = 3) -> bool:
    """True if the newest candle is older than `bars` intervals (market closed / feed problem)."""
    if not candles:
        return True
    now = now or utc_now()
    minutes = INTERVAL_MINUTES.get(interval, 60)
    return now - candles[-1]["dt"] > datetime.timedelta(minutes=minutes * bars)
