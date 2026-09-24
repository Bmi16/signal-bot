import os

CRYPTO_BOT_TOKEN = os.environ.get("CRYPTO_BOT_TOKEN", "ضع_توكن_بوت_الكريبتو")
CRYPTO_CHANNEL_ID = os.environ.get("CRYPTO_CHANNEL_ID", "@اسم_قناة_الكريبتو")
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "ضع_مفتاح_API_هنا")

CRYPTO_PAIRS = ["BTC/USD", "ETH/USD", "BNB/USD", "SOL/USD", "XRP/USD"]
INTERVAL = "1h"

TP1_RATIO = 1.0
TP2_RATIO = 2.0
TP3_RATIO = 3.0

SL_ATR_MULTIPLIER = 1.5
