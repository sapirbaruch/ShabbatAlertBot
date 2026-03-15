import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from shabbat_times import get_candle_lighting_datetime, is_valid_city

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env")

USERS_FILE = Path("users.json")
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def load_user_cities():
    if not USERS_FILE.exists():
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        normalized_data = {}

        for chat_id, value in data.items():
            chat_id = int(chat_id)

            # פורמט ישן: "123456789": "Ashkelon"
            if isinstance(value, str):
                normalized_data[chat_id] = {
                    "city": value,
                    "last_sent": None
                }

            # פורמט חדש: "123456789": {"city": "...", "last_sent": "..."}
            elif isinstance(value, dict):
                normalized_data[chat_id] = {
                    "city": value.get("city", "Jerusalem"),
                    "last_sent": value.get("last_sent")
                }

        return normalized_data

    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(f"Failed to load users.json: {e}")
        return {}


def save_user_cities(user_cities):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(user_cities, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"Failed to save users.json: {e}")


# {
#   123456789: {
#       "city": "Ashkelon",
#       "last_sent": "2026-03-20"
#   }
# }
user_cities = load_user_cities()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome!\n"
        "Use /setcity CITY_NAME\n"
        "Then use /when to see the next Shabbat time."
    )


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot works!")


async def setcity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /setcity CITY_NAME")
        return

    city = " ".join(context.args).strip()
    chat_id = update.effective_chat.id

    try:
        candle_time = get_candle_lighting_datetime(city)

        if candle_time is None:
            await update.message.reply_text(
                f"I couldn't find Shabbat times for '{city}'. Please try another city name."
            )
            return

    except Exception as e:
        print("ERROR in /setcity:", e)
        await update.message.reply_text(
            "There was a problem checking that city. Please try again."
        )
        return

    existing_data = user_cities.get(chat_id, {})
    last_sent = existing_data.get("last_sent")

    user_cities[chat_id] = {
        "city": city,
        "last_sent": last_sent
    }

    save_user_cities(user_cities)

    await update.message.reply_text(
        f"City set to {city}. Shabbat enters at {candle_time.strftime('%H:%M')}."
    )


async def when(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data = user_cities.get(chat_id, {})
    city = user_data.get("city", "Jerusalem")

    try:
        candle_time = get_candle_lighting_datetime(city)

        if candle_time is None:
            await update.message.reply_text(
                f"Could not get Shabbat time for {city}"
            )
            return

        await update.message.reply_text(
            f"Shabbat enters in {city} at {candle_time.strftime('%H:%M')}"
        )

    except Exception as e:
        print("ERROR in /when:", e)
        await update.message.reply_text("Error while getting Shabbat time.")


def should_send_reminder(now, candle_time, last_sent_date):
    reminder_time = candle_time - timedelta(minutes=30)

    # חלון של 2 דקות כדי לא לפספס
    diff_seconds = abs((now - reminder_time).total_seconds())

    if diff_seconds > 120:
        return False

    shabbat_date = candle_time.date().isoformat()

    if last_sent_date == shabbat_date:
        return False

    return True


async def send_reminder_to_chat(bot, chat_id, city, candle_time):
    await bot.send_message(
        chat_id=chat_id,
        text=f"🕯 Shabbat enters in {city} at {candle_time.strftime('%H:%M')}"
    )

    print(f"Reminder sent to {chat_id} for {city}")


async def sendnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data = user_cities.get(chat_id, {})
    city = user_data.get("city", "Jerusalem")

    print(f"/sendnow called by chat_id={chat_id}, city={city}")

    try:
        candle_time = get_candle_lighting_datetime(city)

        if candle_time is None:
            await update.message.reply_text(
                f"Could not get Shabbat time for {city}"
            )
            return

        await send_reminder_to_chat(context.bot, chat_id, city, candle_time)
        await update.message.reply_text("Manual reminder sent.")

    except Exception as e:
        print("ERROR in /sendnow:", e)
        await update.message.reply_text(f"Failed to send manual reminder: {e}")


async def shabbat_reminder(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(ISRAEL_TZ)

    print("Scheduled reminder is running")
    print("Now:", now.strftime("%Y-%m-%d %H:%M:%S"))
    print("user_cities =", user_cities)

    for chat_id, user_data in user_cities.items():
        try:
            city = user_data.get("city", "Jerusalem")
            last_sent = user_data.get("last_sent")

            candle_time = get_candle_lighting_datetime(city)

            if candle_time is None:
                print(f"Could not get Shabbat time for {city}")
                continue

            if should_send_reminder(now, candle_time, last_sent):
                await send_reminder_to_chat(context.bot, chat_id, city, candle_time)

                user_cities[chat_id]["last_sent"] = candle_time.date().isoformat()
                save_user_cities(user_cities)

        except Exception as e:
            print(f"ERROR sending scheduled reminder to {chat_id}: {e}")


async def remindin10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job_queue = context.job_queue

    if job_queue is None:
        await update.message.reply_text("JobQueue is not available.")
        return

    job_queue.run_once(shabbat_reminder, when=10)
    await update.message.reply_text(
        "Okay, I will try to send a reminder in 10 seconds."
    )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("setcity", setcity))
    app.add_handler(CommandHandler("when", when))
    app.add_handler(CommandHandler("sendnow", sendnow))
    app.add_handler(CommandHandler("remindin10", remindin10))

    job_queue = app.job_queue

    if job_queue is not None:
        job_queue.run_repeating(
            shabbat_reminder,
            interval=60,
            first=10,
        )
        print("Repeating Shabbat reminder check scheduled.")
    else:
        print("JobQueue is not available")

    print("Loaded users:", user_cities)
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()