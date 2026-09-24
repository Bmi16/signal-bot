"""Turns market data into a signal: rules -> ML gate -> entry / SL / TP levels."""
import datetime

import data
import markets
import ml
from features import build_features, candidate_signal


def build_signal(market, pair, candles, live_price=None):
    """Pure function (no network). `candles` must contain closed candles only."""
    cfg = markets.get(market)
    cand = candidate_signal(candles, cfg)
    if cand is None:
        return None

    feats = build_features(candles, cand["direction"], cfg)
    decision = ml.decide(market, feats)
    if not decision["allow"]:
        print(f"[ml] {pair} {cand['direction']} rejected (p={decision['prob']:.2f})")
        return None

    entry = live_price if live_price is not None else cand["entry"]
    dist = cand["atr"] * cfg["sl_mult"]
    sign = 1 if cand["direction"] == "BUY" else -1
    r1, r2, r3 = cfg["tp_ratios"]
    return {
        "pair": pair,
        "direction": cand["direction"],
        "entry": entry,
        "stop_loss": entry - sign * dist,
        "tp1": entry + sign * dist * r1,
        "tp2": entry + sign * dist * r2,
        "tp3": entry + sign * dist * r3,
        "rsi": cand["rsi"],
        "features": feats,
        "ml_prob": decision["prob"],
        "ml_mode": decision["mode"],
    }


def generate_signal(market, pair):
    cfg = markets.get(market)
    raw = data.fetch_candles(pair, cfg["interval"], output_size=200)
    if data.is_stale(raw, cfg["interval"]):
        raise RuntimeError(f"{pair}: latest candle is {raw[-1]['dt']} (stale data / market closed)")
    closed = data.drop_forming(raw, cfg["interval"])
    return build_signal(market, pair, closed, live_price=raw[-1]["close"])
