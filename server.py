import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Разрешает калькулятору обращаться к серверу без блокировок

CITY_SLUGS = {
    "костанай": "kostanaj",
    "астана": "astana",
    "алматы": "almaty",
    "шымкент": "shymkent",
    "караганда": "karaganda",
    "актобе": "aktobe",
    "павлодар": "pavlodar"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9"
}

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Города не указаны"}), 400

    f_slug = CITY_SLUGS.get(from_city.lower(), from_city.lower())
    
    urls_to_try = [
        f"https://fa-fa.kz/search_load/gruzy-{f_slug}/",
        f"https://fa-fa.kz/gruzy/?from_city={from_city}&to_city={to_city}",
        f"https://m.fa-fa.kz/search_load/gruzy-{f_slug}/"
    ]

    prices = []

    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.find_all(["div", "tr", "li", "article"])

            for card in cards:
                card_text = card.get_text(" ", strip=True)
                if to_city.lower() in card_text.lower():
                    matches = re.findall(r"([\d\s]{4,9})\s*(?:тг|тенге|₸)", card_text, re.IGNORECASE)
                    for m in matches:
                        clean = int(re.sub(r"\s+", "", m))
                        if 40000 <= clean <= 3500000:
                            prices.append(clean)

            if prices:
                break
        except Exception:
            pass

    if prices:
        min_p = min(prices)
        max_p = max(prices)
        avg_p = int(round(sum(prices) / len(prices) / 1000) * 1000)
        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "count": len(prices)
        })
    else:
        return jsonify({"found": False})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)