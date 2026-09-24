import data
from state_store import load_performance_log
from telegram_publisher import send_to_telegram


def format_summary_message(entries: list) -> str:
    tp_count = sum(1 for e in entries if e["outcome"] == "TP")
    sl_count = sum(1 for e in entries if e["outcome"] == "SL")
    exp_count = sum(1 for e in entries if e["outcome"] == "EXPIRED")

    msg = (
        f"📅 *ملخص اليوم*\n\n"
        f"📊 عدد النتائج المسجلة: {len(entries)}\n"
        f"✅ تحقق الهدف: {tp_count}\n"
        f"🛑 ضرب وقف الخسارة: {sl_count}"
    )
    if exp_count:
        msg += f"\n⌛ انتهت صلاحيتها: {exp_count}"
    return msg


def run_summary():
    all_entries = load_performance_log("forex")
    today_str = data.utc_now().date().isoformat()
    today_entries = [e for e in all_entries if e["closed_at"].startswith(today_str)]

    if not today_entries:
        print("لا توجد نتائج مسجلة اليوم.")
        return

    send_to_telegram(format_summary_message(today_entries))
    print("تم إرسال الملخص اليومي.")


if __name__ == "__main__":
    run_summary()
