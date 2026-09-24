# ML layer - quick guide

1. Add the same secrets as before (TWELVE_DATA_API_KEY, Telegram tokens).
2. Actions -> "Train ML Models" -> Run workflow. It downloads ~5000 hourly candles per pair, trains, and commits
   `models/<market>.joblib` + `models/<market>_metrics.json`. It then re-runs automatically every Sunday and
   learns from the real outcomes stored in `data/*performance_log.json`.
3. Read `models/<market>_metrics.json`:
   - `holdout_baseline_rules_only`  = the old rules on data the model never saw
   - `holdout_with_ml`              = the same period with the ML filter
   - `approved: true` only if the ML result beats break-even AND the old rules.
4. Modes (shown in the logs / state files):
   - off     : no model yet -> original rules only
   - shadow  : model exists but was NOT approved -> it only records its probability, blocks nothing
   - active  : model approved -> signals below `threshold` are dropped, confidence % is shown in the message
5. `ml_config.py`: set `REQUIRE_APPROVED = True` to publish nothing while a model is not approved.
