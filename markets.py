"""One place that describes how each market (forex / crypto) behaves."""
import config as fx
import crypto_config as cr

MARKETS = {
    "forex": {
        "name": "forex",
        "pairs": fx.PAIRS,
        "interval": fx.INTERVAL,
        "sl_mult": fx.SL_ATR_MULTIPLIER,
        "tp_ratios": (fx.TP1_RATIO, fx.TP2_RATIO, fx.TP3_RATIO),
        "rsi_hi": 75, "rsi_lo": 25,
        "min_atr_pct": 0.0,
        "sr_filter": True,        # skip if a support/resistance level sits before TP1
        "htf_filter": False,
        "skip_weekends": True,
        "max_signals": 3,
        "dedupe_base": True,
        "breakeven_after_tp1": False,
        "final_tp": "tp1",        # forex signals close at TP1
    },
    "crypto": {
        "name": "crypto",
        "pairs": cr.CRYPTO_PAIRS,
        "interval": cr.INTERVAL,
        "sl_mult": cr.SL_ATR_MULTIPLIER,
        "tp_ratios": (cr.TP1_RATIO, cr.TP2_RATIO, cr.TP3_RATIO),
        "rsi_hi": 70, "rsi_lo": 30,
        "min_atr_pct": 0.0005,
        "sr_filter": False,
        "htf_filter": True,       # trend on ~4h (SMA40 vs SMA120 of 1h bars) must agree
        "skip_weekends": False,
        "max_signals": 5,
        "dedupe_base": False,
        "breakeven_after_tp1": True,   # after TP1 the stop moves to entry
        "final_tp": "tp3",
    },
}


def get(market: str) -> dict:
    if market not in MARKETS:
        raise ValueError(f"unknown market: {market}")
    return MARKETS[market]


def fmt_price(market: str, pair: str, x: float) -> str:
    if market == "crypto":
        d = 2 if x >= 100 else (3 if x >= 1 else 5)
        return f"{x:,.{d}f}"
    if "JPY" in pair:
        d = 3
    elif "XAU" in pair:
        d = 2
    elif "XAG" in pair:
        d = 3
    else:
        d = 5
    return f"{x:.{d}f}"
