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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://fa-fa.kz/"
}

RUB_KZT_RATE = 5.2

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Города не указаны"}), 400

    prices = []
    
    search_params = {
        "from_city": from_city,
        "to_city": to_city
    }
    query_str = urllib.parse.urlencode(search_params)
    
    urls_to_try = [
        f"https://fa-fa.kz/search_cargo/?{query_str}",
        f"https://fa-fa.kz/search_cargo/?from_city={urllib.parse.quote(from_city)}",
        f"https://m.fa-fa.kz/search_cargo/?{query_str}"
    ]

    for url in urls_to_try:
        try:
            res = requests.get(url, headers=HEADERS, timeout=12)
            if res.status_code != 200 or not res.text:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.select(".cargo_item, .load_item, tr, .search_result_item, .list_item")
            
            for row in rows:
                text = row.get_text(" ", strip=True)
                lower_text = text.lower()

                if to_city.lower() not in lower_text and len(urls_to_try) > 1:
                    continue

                kzt_matches = re.findall(r"(\d[\d\s]{3,8})\s*(?:тг|тенге|₸)", text, re.IGNORECASE)
                for m in kzt_matches:
                    val = int(re.sub(r"\D", "", m))
                    if 40000 <= val <= 5000000:
                        prices.append(val)

                rub_matches = re.findall(r"(\d[\d\s]{3,7})\s*(?:руб|р\b|₽)", text, re.IGNORECASE)
                for m in rub_matches:
                    val = int(re.sub(r"\D", "", m))
                    if 5000 <= val <= 800000:
                        prices.append(int(val * RUB_KZT_RATE))

            if prices:
                break
        except Exception as e:
            print(f"Ошибка запроса к {url}: {e}")
            continue

    if prices:
        prices.sort()
        valid_prices = prices
        if len(prices) >= 4:
            valid_prices = prices[1:-1]

        min_p = min(valid_prices)
        max_p = max(valid_prices)
        avg_p = int(round(sum(valid_prices) / len(valid_prices) / 1000) * 1000)

        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "count": len(prices),
            "source": f"Биржа FA-FA.kz (активных заявок: {len(prices)})"
        })

    return jsonify({
        "found": False,
        "source": "FA-FA: нет опубликованных открытых ставок по направлению"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
