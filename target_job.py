"""Check every open signal against the latest candles and announce TP / SL / expiry."""
import time

import data
import markets
import state_store
import tracker


def _publisher(market):
    if market == "crypto":
        import crypto_publisher as pub
    else:
        import telegram_publisher as pub
    return pub


def run(market):
    cfg = markets.get(market)
    signals = state_store.load_signals(market)
    open_signals = [s for s in signals if s.get("status") == "open"]
    if not open_signals:
        print("No open signals.")
        return

    pub = _publisher(market)
    now = data.utc_now()
    cache = {}
    for i, sig in enumerate(open_signals):
        try:
            if sig["pair"] not in cache:
                if cache:
                    time.sleep(1)
                cache[sig["pair"]] = data.fetch_candles(sig["pair"], cfg["interval"], output_size=60)
            events = tracker.evaluate(sig, cache[sig["pair"]], cfg, now)
        except Exception as e:
            print(f"{sig.get('id')}: check failed - {e}")
            continue

        for ev in events:
            outcome = tracker.performance_outcome(sig, ev)
            if outcome:
                sig["logged"] = True
                state_store.append_performance_entry({
                    "id": sig["id"], "market": market, "pair": sig["pair"], "direction": sig["direction"],
                    "entry": sig["entry"], "outcome": outcome,
                    "created_at": sig["created_at"], "closed_at": now.isoformat(timespec="seconds"),
                    "features": sig.get("features"), "ml_prob": sig.get("ml_prob"), "ml_mode": sig.get("ml_mode"),
                }, market)
            text = tracker.format_event(market, sig, ev)
            if text:
                try:
                    pub.send_to_telegram(text)
                except Exception as e:
                    print(f"{sig['id']}: telegram failed - {e}")
        state_store.save_signals(signals, market)
        print(f"{sig['id']}: {sig['status']} ({[e['type'] for e in events]})")
