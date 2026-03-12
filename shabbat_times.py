import requests
from datetime import datetime


def get_candle_lighting(city="Jerusalem", country="IL"):
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

    for item in data.get("items", []):
        title = item.get("title", "").lower()

        if "candle lighting" in title:
            date_str = item.get("date")
            if not date_str:
                return None

            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%H:%M")

    return None