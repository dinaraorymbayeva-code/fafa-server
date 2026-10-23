import os
import re
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse

app = Flask(__name__)
CORS(app)

# Создаем scraper с эмуляцией реального браузера Chrome на Windows
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Города не указаны"}), 400

    f_stem = from_city.lower()[:4]
    t_stem = to_city.lower()[:4]

    search_url = f"https://fa-fa.kz/search_load/?from_city={urllib.parse.quote(from_city)}&to_city={urllib.parse.quote(to_city)}"

    try:
        resp = scraper.get(search_url, timeout=15)
        if resp.status_code != 200:
            return jsonify({
                "found": False,
                "message": f"Защита FA-FA отклонила запрос (код {resp.status_code})"
            })

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        
        prices = []
        
        # Находим все строки и блоки таблицы
        rows = soup.find_all(["tr", "div", "li"])
        for row in rows:
            text = row.get_text(" ", strip=True).lower()
            if f_stem in text and t_stem in text:
                # Поиск формата цен с FA-FA: 110.000 тнг, 140 000 тг, 150000 ₸
                matches = re.findall(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{4,7})\s*(?:тнг|тг|тенге|₸)", text)
                for m in matches:
                    clean_val = int(re.sub(r"\D", "", m))
                    if 40000 <= clean_val <= 4000000:
                        prices.append(clean_val)

        if prices:
            prices.sort()
            clean_prices = prices[1:-1] if len(prices) >= 4 else prices
            avg_val = int(round(sum(clean_prices) / len(clean_prices) / 1000) * 1000)

            return jsonify({
                "found": True,
                "min_price": min(clean_prices),
                "avg_price": avg_val,
                "max_price": max(clean_prices),
                "count": len(prices),
                "source": f"FA-FA.kz (Найдено заявок: {len(prices)})"
            })

        return jsonify({
            "found": False,
            "message": f"На FA-FA нет активных ставок с открытой ценой по направлению {from_city} — {to_city}"
        })

    except Exception as e:
        return jsonify({
            "found": False,
            "error": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
