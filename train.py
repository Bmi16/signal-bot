"""Train / retrain the ML filter.   Usage:  python train.py forex   |   python train.py crypto"""
import sys
import time

import data
import markets
import ml
import ml_config as mc
import state_store


def fetch_history(cfg):
    history = {}
    for pair in cfg["pairs"]:
        try:
            raw = data.fetch_candles(pair, cfg["interval"], mc.HISTORY_BARS)
            history[pair] = data.drop_forming(raw, cfg["interval"])
            print(f"  {pair}: {len(history[pair])} candles")
        except Exception as e:
            print(f"  {pair}: FAILED ({e})")
        time.sleep(8)  # stay under the free-plan per-minute limit
    return history


def main():
    market = sys.argv[1] if len(sys.argv) > 1 else "forex"
    cfg = markets.get(market)
    print(f"Training {market} model...")
    history = fetch_history(cfg)
    live = state_store.load_performance_log(market)
    report = ml.train_market(market, cfg, history, live)
    report["live_report"] = ml.live_report(live, report.get("threshold"))
    ml.save_metrics(market, report)

    print(f"candidates={report['candidates']} labeled={report['labeled']} approved={report['approved']} "
          f"threshold={report['threshold']}")
    print("holdout, rules only :", report.get("holdout_baseline_rules_only"))
    print("holdout, with ML    :", report.get("holdout_with_ml"))
    if report.get("note"):
        print("note:", report["note"])


if __name__ == "__main__":
    main()
