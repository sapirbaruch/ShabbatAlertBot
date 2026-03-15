# Shabbat Alert Bot

Telegram bot that sends a reminder 30 minutes before Shabbat candle lighting based on the user's city.

## Features
- Set city with `/setcity`
- Check Shabbat time with `/when`
- Automatic reminder before Shabbat
- City data stored locally
- Environment variables for secrets

## Setup

Install dependencies:

pip install -r requirements.txt

Create `.env`:

TELEGRAM_BOT_TOKEN=YOUR_TOKEN

Run:

python bot.py
