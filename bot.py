import json
from pathlib import Path
from datetime import time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from shabbat_times import get_candle_lighting

TOKEN = ״YOUR_TELEGRAM_BOT_TOKEN_HERE״
USERS_FILE = Path("users.json")


def load_user_cities():
    if not USERS_FILE.exists():
        return {}

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # JSON שומר מפתחות כמחרוזות, ואנחנו רוצים chat_id כ-int
        return {int(chat_id): city for chat_id, city in data.items()}

    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(f"Failed to load users.json: {e}")
        return {}


def save_user_cities(user_cities):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(user_cities, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"Failed to save users.json: {e}")


user_cities = load_user_cities()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Use /setcity CITY_NAME"
    )


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot works!")


async def setcity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /setcity CITY_NAME")
        return

    city = " ".join(context.args).strip()
    chat_id = update.effective_chat.id

    user_cities[chat_id] = city
    save_user_cities(user_cities)

    print(f"Saved city for chat_id={chat_id}: {city}")
    print("user_cities =", user_cities)

    await update.message.reply_text(f"City set to {city}")


async def when(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    city = user_cities.get(chat_id, "Jerusalem")

    try:
        shabbat_time = get_candle_lighting(city)

        if shabbat_time is None:
            await update.message.reply_text(
                f"Could not get Shabbat time for {city}"
            )
            return

        await update.message.reply_text(
            f"Shabbat enters in {city} at {shabbat_time}"
        )

    except Exception as e:
        print("ERROR in /when:", e)
        await update.message.reply_text("Error while getting Shabbat time.")


async def send_reminder_to_chat(bot, chat_id, city):
    shabbat_time = get_candle_lighting(city)

    if shabbat_time is None:
        print(f"Could not get Shabbat time for {city}")
        return

    await bot.send_message(
        chat_id=chat_id,
        text=f"🕯 Shabbat enters in {city} at {shabbat_time}"
    )

    print(f"Reminder sent to {chat_id} for {city}")


async def sendnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    city = user_cities.get(chat_id, "Jerusalem")

    print(f"/sendnow called by chat_id={chat_id}, city={city}")

    try:
        await send_reminder_to_chat(context.bot, chat_id, city)
        await update.message.reply_text("Manual reminder sent.")
    except Exception as e:
        print("ERROR in /sendnow:", e)
        await update.message.reply_text(f"Failed to send manual reminder: {e}")


async def shabbat_reminder(context: ContextTypes.DEFAULT_TYPE):
    print("Scheduled reminder is running")
    print("user_cities =", user_cities)

    for chat_id, city in user_cities.items():
        try:
            await send_reminder_to_chat(context.bot, chat_id, city)
        except Exception as e:
            print(f"ERROR sending scheduled reminder to {chat_id}: {e}")


async def remindin10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    job_queue = context.job_queue

    if job_queue is None:
        await update.message.reply_text("JobQueue is not available.")
        return

    job_queue.run_once(shabbat_reminder, when=10)
    await update.message.reply_text("Okay, I will try to send a reminder in 10 seconds.")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("setcity", setcity))
    app.add_handler(CommandHandler("when", when))
    app.add_handler(CommandHandler("sendnow", sendnow))
    app.add_handler(CommandHandler("remindin10", remindin10))

    reminder_time = time(hour=16, minute=0, tzinfo=ZoneInfo("Asia/Jerusalem"))

    job_queue = app.job_queue
    if job_queue is not None:
        job_queue.run_daily(
            shabbat_reminder,
            time=reminder_time,
            days=(4,),
        )
        print("Daily Friday reminder scheduled for 16:00 Asia/Jerusalem")
    else:
        print("JobQueue is not available")

    print("Loaded users:", user_cities)
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()