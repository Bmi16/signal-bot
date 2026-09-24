import requests
import config
from state_store import get_historical_win_rate


def format_signal_message(signal: dict, ref_id: str) -> str:
    direction_ar = "شراء 🟢" if signal["direction"] == "BUY" else "بيع 🔴"

    if "JPY" in signal["pair"]:
        decimals = 3
    elif "XAU" in signal["pair"]:
        decimals = 2
    elif "XAG" in signal["pair"]:
        decimals = 3
    else:
        decimals = 5

    def fmt(x):
        return f"{x:.{decimals}f}"

    win_rate_info = get_historical_win_rate("forex")
    stats_line = ""
    if win_rate_info:
        rate, total = win_rate_info
        stats_line = f"\n\n📈 نسبة النجاح التاريخية: {rate}% (آخر {total} إشارة)"

    ml_line = ""
    if signal.get("ml_mode") == "active" and signal.get("ml_prob") is not None:
        ml_line = f"\n🤖 ثقة النموذج: {round(signal['ml_prob'] * 100)}%"

    msg = (
        f"📊 *إشارة تداول جديدة* `#{ref_id}`\n\n"
        f"💱 الزوج: `{signal['pair']}`\n"
        f"📈 الاتجاه: *{direction_ar}*\n\n"
        f"🎯 سعر الدخول (Entry): `{fmt(signal['entry'])}`\n"
        f"🛑 وقف الخسارة (SL): `{fmt(signal['stop_loss'])}`\n\n"
        f"✅ الهدف (TP): `{fmt(signal['tp1'])}`"
        f"{ml_line}"
        f"{stats_line}"
    )
    return msg


def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()
