import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://fa-fa.kz/"
}

RUB_KZT_RATE = 5.2

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Города не указаны"}), 400

    f_clean = from_city.lower()
    t_clean = to_city.lower()

    f_stem = f_clean[:5] if len(f_clean) >= 5 else f_clean
    t_stem = t_clean[:5] if len(t_clean) >= 5 else t_clean

    prices = []
    
    urls_to_try = [
        f"https://fa-fa.kz/search_cargo/?city_from={urllib.parse.quote(from_city)}&city_to={urllib.parse.quote(to_city)}",
        f"https://fa-fa.kz/search_cargo/?from_city={urllib.parse.quote(from_city)}&to_city={urllib.parse.quote(to_city)}",
        f"https://fa-fa.kz/ru/cargo/",
        f"https://fa-fa.kz/search_cargo/"
    ]

    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code != 200 or not res.text:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.select("tr, .cargo-item, .item, .search_item, div[class*='cargo'], div[class*='load']")
            
            for item in items:
                text = item.get_text(" ", strip=True).lower()
                
                if f_stem in text and t_stem in text:
                    kzt = re.findall(r"(\d[\d\s]{3,7})\s*(?:тг|тенге|₸)", text, re.IGNORECASE)
                    for m in kzt:
                        val = int(re.sub(r"\D", "", m))
                        if 30000 <= val <= 4500000:
                            prices.append(val)

                    rub = re.findall(r"(\d[\d\s]{3,6})\s*(?:руб|р\b|₽)", text, re.IGNORECASE)
                    for m in rub:
                        val = int(re.sub(r"\D", "", m))
                        if 5000 <= val <= 700000:
                            prices.append(int(val * RUB_KZT_RATE))

            if len(prices) >= 2:
                break
        except Exception as e:
            print(f"Log error for {url}: {e}")
            continue

    if prices:
        prices.sort()
        valid = prices
        if len(prices) >= 4:
            valid = prices[1:-1]

        min_p = min(valid)
        max_p = max(valid)
        avg_p = int(round(sum(valid) / len(valid) / 1000) * 1000)

        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "count": len(prices),
            "source": f"FA-FA.kz (Найдено заявок: {len(prices)})"
        })

    return jsonify({
        "found": False,
        "source": f"На FA-FA нет активных ставок по направлению {from_city} — {to_city}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
