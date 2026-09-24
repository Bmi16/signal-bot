"""Machine-learning filter: predicts P(TP1 is hit before SL) for a rule-based candidate.

Honest validation is the core of this file:
  * labels use the triple-barrier method on future candles (SL wins if both are touched in one bar)
  * a final 25% of the timeline is held out and never used for training or threshold choice
  * results are simulated the way the live bot behaves (one open trade per pair at a time)
  * a model is only "approved" if it beats break-even AND the unfiltered rules on the holdout
"""
import datetime
import json
import math
import os

import ml_config as mc
from features import FEATURE_NAMES, build_features, candidate_signal

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_CACHE = {}


# ---------------------------------------------------------------- labelling
def label_outcome(direction, entry, sl_dist, tp_ratio, future):
    """Returns (y, k). y: 1 = TP1 first, 0 = SL first, None = neither within the horizon. k = bars used."""
    buy = direction == "BUY"
    sl = entry - sl_dist if buy else entry + sl_dist
    tp = entry + sl_dist * tp_ratio if buy else entry - sl_dist * tp_ratio
    for k, c in enumerate(future[: mc.HORIZON_BARS], start=1):
        hit_sl = c["low"] <= sl if buy else c["high"] >= sl
        hit_tp = c["high"] >= tp if buy else c["low"] <= tp
        if hit_sl:               # conservative: if both are touched in the same bar, count the loss
            return 0, k
        if hit_tp:
            return 1, k
    return None, mc.HORIZON_BARS


def build_dataset(cfg, history):
    """history: {pair: closed candles oldest->newest}. One row per rule-based candidate bar."""
    rows = []
    for pair, candles in history.items():
        n = len(candles)
        for i in range(mc.WARMUP_BARS, n - mc.HORIZON_BARS - 1):
            window = candles[max(0, i - mc.WINDOW_BARS + 1): i + 1]
            cand = candidate_signal(window, cfg)
            if cand is None:
                continue
            y, k = label_outcome(cand["direction"], cand["entry"], cand["atr"] * cfg["sl_mult"],
                                 cfg["tp_ratios"][0], candles[i + 1: i + 1 + mc.HORIZON_BARS])
            feats = build_features(window, cand["direction"], cfg)
            rows.append({"pair": pair, "i": i, "t": candles[i]["dt"], "k": k, "y": y,
                         "x": [feats[name] for name in FEATURE_NAMES]})
    rows.sort(key=lambda r: r["t"])
    return rows


# ---------------------------------------------------------------- simulation / stats
def wilson_lower(wins, n, z=1.96):
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / denom


def simulate(rows, probs, threshold, cfg):
    """Replays candidates like the live bot: one open trade per pair, skip if prob < threshold."""
    tp_r = cfg["tp_ratios"][0]
    order = sorted(range(len(rows)), key=lambda j: (rows[j]["pair"], rows[j]["i"]))
    free_from, wins, losses, timeouts, total = {}, 0, 0, 0, 0.0
    for j in order:
        r = rows[j]
        if r["i"] < free_from.get(r["pair"], -1):
            continue
        if probs is not None and probs[j] < threshold:
            continue
        free_from[r["pair"]] = r["i"] + r["k"] + 1
        if r["y"] == 1:
            wins += 1
            total += tp_r - mc.COST_R
        elif r["y"] == 0:
            losses += 1
            total -= 1 + mc.COST_R
        else:
            timeouts += 1
            total -= mc.COST_R
    n = wins + losses + timeouts
    decided = wins + losses
    return {
        "trades": n, "wins": wins, "losses": losses, "timeouts": timeouts,
        "win_rate": round(wins / decided, 4) if decided else None,
        "wilson_lower": round(wilson_lower(wins, decided), 4) if decided else None,
        "expectancy_r": round(total / n, 4) if n else None,
        "breakeven_win_rate": round((1 + mc.COST_R) / (tp_r + 1), 4),
    }


# ---------------------------------------------------------------- model
def _new_model():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
        l2_regularization=1.0, random_state=42)


def _fit(rows, extra=None):
    import numpy as np
    lab = [r for r in rows if r["y"] is not None]
    X = [r["x"] for r in lab]
    y = [r["y"] for r in lab]
    w = [1.0] * len(lab)
    if extra:
        for x_, y_ in extra:
            X.append(x_); y.append(y_); w.append(mc.LIVE_SAMPLE_WEIGHT)
    if len(set(y)) < 2 or len(y) < 100:
        return None
    m = _new_model()
    m.fit(np.array(X), np.array(y), sample_weight=np.array(w))
    return m


def _predict(model, rows):
    import numpy as np
    if not rows:
        return []
    return model.predict_proba(np.array([r["x"] for r in rows]))[:, 1].tolist()


def _walk_forward(rows):
    """Expanding-window walk-forward with an embargo. Returns out-of-sample (rows, probs)."""
    if len(rows) < 400:
        return [], []
    n = len(rows)
    bounds = [int(n * q) for q in (0, 0.25, 0.5, 0.75, 1.0)]
    oos_rows, oos_probs = [], []
    embargo = datetime.timedelta(hours=mc.HORIZON_BARS)
    for f in range(3):
        test = rows[bounds[f + 1]: bounds[f + 2]]
        if not test:
            continue
        cutoff = test[0]["t"] - embargo
        train = [r for r in rows[: bounds[f + 1]] if r["t"] <= cutoff]
        model = _fit(train)
        if model is None:
            continue
        oos_rows += test
        oos_probs += _predict(model, test)
    return oos_rows, oos_probs


def _choose_threshold(rows, probs, cfg):
    table, best = [], None
    for thr in mc.THRESHOLD_GRID:
        s = simulate(rows, probs, thr, cfg)
        table.append({"threshold": thr, **s})
        if s["trades"] >= mc.MIN_TRADES and s["expectancy_r"] is not None:
            if best is None or s["expectancy_r"] > best[1]:
                best = (thr, s["expectancy_r"])
    return (best[0] if best else None), table


def train_market(market, cfg, history, live_entries=None):
    """Full pipeline. Returns a metrics dict; saves the model to models/<market>.joblib."""
    import joblib

    rows = build_dataset(cfg, history)
    labeled = [r for r in rows if r["y"] is not None]
    report = {"market": market, "trained_at": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
              "candidates": len(rows), "labeled": len(labeled), "approved": False, "threshold": None}
    if len(labeled) < mc.MIN_TRAIN_SAMPLES:
        report["note"] = f"not enough samples ({len(labeled)} < {mc.MIN_TRAIN_SAMPLES}); no model trained"
        return report

    split = rows[int(len(rows) * 0.75)]["t"]
    train_part = [r for r in rows if r["t"] < split]
    holdout = [r for r in rows if r["t"] >= split]
    report["holdout_starts"] = split.isoformat()

    oos_rows, oos_probs = _walk_forward(train_part)
    thr, table = _choose_threshold(oos_rows, oos_probs, cfg)
    report["threshold"] = thr
    report["walk_forward_table"] = table

    embargoed = [r for r in train_part if r["t"] <= split - datetime.timedelta(hours=mc.HORIZON_BARS)]
    holdout_model = _fit(embargoed)
    baseline = simulate(holdout, None, 0.0, cfg)
    report["holdout_baseline_rules_only"] = baseline
    filtered = None
    if holdout_model is not None and thr is not None:
        filtered = simulate(holdout, _predict(holdout_model, holdout), thr, cfg)
    report["holdout_with_ml"] = filtered

    if filtered and filtered["trades"] >= mc.MIN_TRADES and filtered["win_rate"] is not None:
        edge = filtered["win_rate"] - filtered["breakeven_win_rate"]
        report["approved"] = bool(
            filtered["expectancy_r"] > 0
            and edge >= mc.MIN_EDGE_OVER_BREAKEVEN
            and filtered["expectancy_r"] > (baseline["expectancy_r"] or -9)
        )

    extra = []
    for e in live_entries or []:
        f = e.get("features")
        if f and e.get("outcome") in ("TP", "SL") and all(n in f for n in FEATURE_NAMES):
            extra.append(([f[n] for n in FEATURE_NAMES], 1 if e["outcome"] == "TP" else 0))
    report["live_samples_used"] = len(extra)

    final = _fit(rows, extra)
    if final is None:
        report["note"] = "final model could not be fitted"
        report["approved"] = False
        return report

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({"model": final, "features": FEATURE_NAMES, "threshold": thr,
                 "approved": report["approved"], "trained_at": report["trained_at"]},
                os.path.join(MODEL_DIR, f"{market}.joblib"))
    _CACHE.pop(market, None)
    return report


# ---------------------------------------------------------------- live use
def _load(market):
    if market in _CACHE:
        return _CACHE[market]
    path = os.path.join(MODEL_DIR, f"{market}.joblib")
    bundle = None
    if os.path.exists(path):
        try:
            import joblib
            bundle = joblib.load(path)
        except Exception as e:  # missing sklearn / version mismatch -> run rules-only
            print(f"[ml] could not load {path}: {e}")
    _CACHE[market] = bundle
    return bundle


def decide(market, feats):
    """mode: off (no model) | shadow (model not approved: logs prob only) | active (filters signals)."""
    bundle = _load(market)
    if bundle is None:
        return {"allow": True, "prob": None, "mode": "off"}
    try:
        prob = float(bundle["model"].predict_proba([[feats[n] for n in bundle["features"]]])[0][1])
    except Exception as e:
        print(f"[ml] prediction failed: {e}")
        return {"allow": True, "prob": None, "mode": "off"}
    if bundle["approved"] and bundle["threshold"] is not None:
        return {"allow": prob >= bundle["threshold"], "prob": prob, "mode": "active"}
    return {"allow": not mc.REQUIRE_APPROVED, "prob": prob, "mode": "shadow"}


# ---------------------------------------------------------------- learning from live mistakes
def live_report(entries, threshold=None):
    """Where does the bot lose in real trading? Win rate by pair / direction / hour / ML confidence."""
    done = [e for e in entries if e.get("outcome") in ("TP", "SL")]

    def rate(group):
        w = sum(1 for e in group if e["outcome"] == "TP")
        return {"n": len(group), "win_rate": round(w / len(group), 3)}

    def by(keyfn, min_n=5):
        buckets = {}
        for e in done:
            buckets.setdefault(keyfn(e), []).append(e)
        return {str(k): rate(v) for k, v in sorted(buckets.items(), key=lambda kv: str(kv[0])) if len(v) >= min_n}

    out = {"closed_signals": len(done)}
    if done:
        out["overall"] = rate(done)
        out["by_pair"] = by(lambda e: e.get("pair"))
        out["by_direction"] = by(lambda e: e.get("direction"))
        out["by_session"] = by(lambda e: "asia" if (e.get("features") or {}).get("hour_cos", 0) > 0.5
                               else "europe/us")
        scored = [e for e in done if e.get("ml_prob") is not None]
        if threshold is not None and scored:
            hi = [e for e in scored if e["ml_prob"] >= threshold]
            lo = [e for e in scored if e["ml_prob"] < threshold]
            out["ml_above_threshold"] = rate(hi) if hi else None
            out["ml_below_threshold"] = rate(lo) if lo else None
    return out


def save_metrics(market, report):
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, f"{market}_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
