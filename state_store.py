"""JSON persistence for open signals and the performance log (one pair of files per market)."""
import json
import os

import ml_config as mc

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FILES = {
    "forex": {"state": "signals_state.json", "log": "performance_log.json"},
    "crypto": {"state": "crypto_signals_state.json", "log": "crypto_performance_log.json"},
}


def _path(market, kind):
    return os.path.join(DATA_DIR, FILES[market][kind])


def _read(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[state] could not read {path}: {e}")
        return []


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomic: a crash can never leave half a file


def load_signals(market="forex"):
    return _read(_path(market, "state"))


def save_signals(signals, market="forex"):
    _write(_path(market, "state"), signals)


def load_performance_log(market="forex"):
    return _read(_path(market, "log"))


def append_performance_entry(entry, market="forex"):
    log = load_performance_log(market)
    log.append(entry)
    _write(_path(market, "log"), log)


def get_historical_win_rate(market="forex"):
    """(win %, number of closed signals) or None until there are enough closed signals to mean something."""
    closed = [e for e in load_performance_log(market) if e.get("outcome") in ("TP", "SL")]
    if len(closed) < mc.MIN_CLOSED_FOR_STATS:
        return None
    wins = sum(1 for e in closed if e["outcome"] == "TP")
    return round(wins / len(closed) * 100), len(closed)
