import requests
from datetime import datetime
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def get_candle_lighting_datetime(city="Jerusalem", country="IL"):
    """
    Fetch the candle lighting time for a given city using the Hebcal API.
    Returns a timezone-aware datetime object or None if not found.
    """
    
    url = "https://www.hebcal.com/shabbat"
    params = {
        "cfg": "json",
        "city": city,
        "country": country,
        "c": "on"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()

    # Search for the candle lighting event in the returned items
    for item in data.get("items", []):
        title = item.get("title", "").lower()

        if "candle lighting" in title:
            date_str = item.get("date")
            if not date_str:
                return None

            dt = datetime.fromisoformat(date_str)
            # Ensure datetime is in Israel timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ISRAEL_TZ)
            else:
                dt = dt.astimezone(ISRAEL_TZ)

            return dt

    return None


def is_valid_city(city="Jerusalem", country="IL"):
    try:
        candle_time = get_candle_lighting_datetime(city, country)
        return candle_time is not None
    except requests.RequestException:
        return False