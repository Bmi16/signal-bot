import requests
import crypto_config as config
from markets import fmt_price


def format_signal_message(signal: dict, ref_id: str) -> str:
    direction_ar = "شراء 🟢" if signal["direction"] == "BUY" else "بيع 🔴"

    def fmt(x):
        return fmt_price("crypto", signal["pair"], x)

    ml_line = ""
    if signal.get("ml_mode") == "active" and signal.get("ml_prob") is not None:
        ml_line = f"\n\n🤖 ثقة النموذج: {round(signal['ml_prob'] * 100)}%"

    msg = (
        f"🪙 *إشارة كريبتو جديدة* `#{ref_id}`\n\n"
        f"💱 العملة: `{signal['pair']}`\n"
        f"📈 الاتجاه: *{direction_ar}*\n\n"
        f"🎯 سعر الدخول (Entry): `{fmt(signal['entry'])}`\n"
        f"🛑 وقف الخسارة (SL): `{fmt(signal['stop_loss'])}`\n\n"
        f"✅ الهدف الأول (TP1): `{fmt(signal['tp1'])}`\n"
        f"✅ الهدف الثاني (TP2): `{fmt(signal['tp2'])}`\n"
        f"✅ الهدف الثالث (TP3): `{fmt(signal['tp3'])}`"
        f"{ml_line}"
    )
    return msg


def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{config.CRYPTO_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.CRYPTO_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()
