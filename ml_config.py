"""Settings for the machine-learning layer (shared by forex and crypto)."""

HORIZON_BARS = 24          # a signal is "resolved" if TP1/SL is hit within this many bars, else it expires
COST_R = 0.05              # assumed spread + slippage per trade, as a fraction of the risk (1R)
MIN_TRADES = 30            # minimum simulated trades before a result is trusted
MIN_TRAIN_SAMPLES = 400    # below this, no model is trained
MIN_EDGE_OVER_BREAKEVEN = 0.03  # holdout win rate must beat break-even by at least 3 points
THRESHOLD_GRID = [0.50, 0.52, 0.54, 0.56, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70]

HISTORY_BARS = 5000        # candles downloaded per pair for training
WARMUP_BARS = 130          # candles needed before the first feature/signal can be computed
WINDOW_BARS = 200          # candles passed to the feature builder
LIVE_SAMPLE_WEIGHT = 3.0   # real (live) outcomes count 3x more than historical ones when retraining

# False -> a model that FAILED validation only runs in "shadow" mode (logs its probability, blocks nothing).
# True  -> if a model exists but failed validation, no signals are published at all.
REQUIRE_APPROVED = False

MIN_CLOSED_FOR_STATS = 30  # the win rate is only shown in messages after this many closed signals
