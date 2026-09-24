import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ضع_التوكن_هنا")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@اسم_قناتك")
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "ضع_مفتاح_API_هنا")

PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY" , "EUR/GBP" , "XAU/USD", "XAG/USD"]
INTERVAL = "1h"

TP1_RATIO = 1.0
TP2_RATIO = 2.0
TP3_RATIO = 3.0

SL_ATR_MULTIPLIER = 1.5
