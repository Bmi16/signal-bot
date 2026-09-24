"""Scan the pairs, keep the best candidates, SAVE them, then publish them."""
import itertools
import time

import data
import markets
import state_store
import strategy


def _publisher(market):
    if market == "crypto":
        import crypto_publisher as pub
    else:
        import telegram_publisher as pub
    return pub


def _base_currency(pair):
    return pair.split("/")[0]


def _rank(sig):
    return sig["ml_prob"] if sig["ml_prob"] is not None else sig["features"]["trend_gap"]


def run(market):
    cfg = markets.get(market)
    now = data.utc_now()
    if cfg["skip_weekends"] and now.weekday() >= 5:
        print("Weekend - market closed, nothing to do.")
        return

    signals = state_store.load_signals(market)
    open_pairs = {s["pair"] for s in signals if s.get("status") in ("open", "pending")}

    candidates = []
    for pair in cfg["pairs"]:
        if pair in open_pairs:
            print(f"{pair}: already has an open signal, skipping")
            continue
        try:
            sig = strategy.generate_signal(market, pair)
        except Exception as e:
            print(f"{pair}: error - {e}")
            continue
        if sig:
            candidates.append(sig)

    candidates.sort(key=_rank, reverse=True)
    if cfg["dedupe_base"]:
        seen, unique = set(), []
        for s in candidates:
            base = _base_currency(s["pair"])
            if base not in seen:
                seen.add(base)
                unique.append(s)
        candidates = unique
    candidates = candidates[: cfg["max_signals"]]

    if not candidates:
        print("No signals this run.")
        return

    pub = _publisher(market)
    for sig in candidates:
        ref_id = f"{sig['pair'].replace('/', '')}-{now.strftime('%m%d%H%M')}"
        record = {
            "id": ref_id, "market": market, "pair": sig["pair"], "direction": sig["direction"],
            "entry": sig["entry"], "stop_loss": sig["stop_loss"],
            "tp1": sig["tp1"], "tp2": sig["tp2"], "tp3": sig["tp3"],
            "created_at": now.isoformat(timespec="seconds"),
            "status": "pending",            # saved BEFORE sending, so a crash can never orphan a signal
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False, "logged": False,
            "features": sig["features"], "ml_prob": sig["ml_prob"], "ml_mode": sig["ml_mode"],
        }
        signals.append(record)
        state_store.save_signals(signals, market)
        try:
            pub.send_to_telegram(pub.format_signal_message(sig, ref_id))
            record["status"] = "open"
            print(f"Sent: {ref_id} ({sig['direction']}, ml={sig['ml_mode']}, p={sig['ml_prob']})")
        except Exception as e:
            record["status"] = "failed"     # never published -> never counted in statistics
            print(f"Telegram send failed for {ref_id}: {e}")
        state_store.save_signals(signals, market)
        time.sleep(2)
