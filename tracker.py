"""Follows an open signal candle by candle (uses highs/lows, so wicks between polls are not missed)."""
import datetime

import ml_config as mc
from markets import fmt_price


def evaluate(sig, candles, cfg, now):
    """Mutates `sig` and returns a list of events: {"type": TP1|TP2|TP3|SL|BE|EXPIRED|TIMEOUT, "level": price|None}.

    Conservative rule: if a candle touches both the stop and a target, the stop wins.
    """
    events = []
    buy = sig["direction"] == "BUY"
    created = datetime.datetime.fromisoformat(sig["created_at"])
    sl_level = sig.get("sl_active", sig["stop_loss"])

    for c in candles:
        if c["dt"] < created:      # only bars that opened after the signal was created
            continue
        hi, lo = c["high"], c["low"]
        if (lo <= sl_level) if buy else (hi >= sl_level):
            if sig.get("tp1_hit"):
                ev = "BE" if cfg["breakeven_after_tp1"] else "SL"
            else:
                ev = "SL"
            events.append({"type": ev, "level": sl_level})
            sig["status"] = "closed"
            sig["closed_by"] = ev
            break
        for key in ("tp1", "tp2", "tp3"):
            if sig.get(f"{key}_hit"):
                continue
            if (hi >= sig[key]) if buy else (lo <= sig[key]):
                sig[f"{key}_hit"] = True
                events.append({"type": key.upper(), "level": sig[key]})
                if key == "tp1" and cfg["breakeven_after_tp1"]:
                    sl_level = sig["entry"]
                    sig["sl_active"] = sig["entry"]
        if sig.get(f"{cfg['final_tp']}_hit"):
            sig["status"] = "closed"
            sig["closed_by"] = cfg["final_tp"].upper()
            break

    if sig["status"] == "open":
        age = now - created
        if not sig.get("tp1_hit") and age > datetime.timedelta(hours=mc.HORIZON_BARS):
            events.append({"type": "EXPIRED", "level": None})
            sig["status"] = "closed"
            sig["closed_by"] = "EXPIRED"
        elif sig.get("tp1_hit") and age > datetime.timedelta(hours=mc.HORIZON_BARS * 3):
            events.append({"type": "TIMEOUT", "level": None})   # closed silently
            sig["status"] = "closed"
            sig["closed_by"] = "TIMEOUT"
    return events


def performance_outcome(sig, event):
    """The first decisive event of a signal is what the model learns from: TP1 / SL / EXPIRED."""
    if sig.get("logged"):
        return None
    mapping = {"TP1": "TP", "SL": "SL", "EXPIRED": "EXPIRED"}
    return mapping.get(event["type"])


def format_event(market, sig, event):
    p = lambda x: fmt_price(market, sig["pair"], x)
    head = f"`#{sig['id']}` — `{sig['pair']}`"
    t = event["type"]
    if t in ("TP1", "TP2", "TP3"):
        extra = "\n↪️ تم نقل وقف الخسارة إلى سعر الدخول" if (t == "TP1" and sig.get("sl_active")) else ""
        return f"✅ *تحقق الهدف ({t})* {head}\n🎯 السعر: `{p(event['level'])}`{extra}"
    if t == "SL":
        return f"🛑 *تم ضرب وقف الخسارة (SL)* {head}\n📉 السعر: `{p(event['level'])}`"
    if t == "BE":
        return f"➖ *أُغلقت الصفقة عند نقطة التعادل* {head}\n(تحقق TP1 ثم عاد السعر إلى الدخول)"
    if t == "EXPIRED":
        return f"⌛ *انتهت صلاحية الإشارة* {head}\nلم يتحقق الهدف ولا وقف الخسارة خلال {mc.HORIZON_BARS} ساعة"
    return None
