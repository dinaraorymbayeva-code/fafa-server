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

# Базовые ID ключевых городов Казахстана на бирже FA-FA
CITY_IDS = {
    "костанай": "10",
    "астана": "2",
    "алматы": "1",
    "шымкент": "3",
    "караганда": "4",
    "актобе": "5",
    "павлодар": "6",
    "усть-каменогорск": "7",
    "семей": "8",
    "атырау": "9",
    "актау": "11",
    "тараз": "12",
    "петропавловск": "13",
    "уральск": "14",
    "кызылорда": "15"
}

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Города не указаны"}), 400

    f_lower = from_city.lower()
    t_lower = to_city.lower()

    # Очищенные корни для надежного совпадения в тексте строки
    f_stem = f_lower[:4]
    t_stem = t_lower[:4]

    session = requests.Session()
    session.headers.update(HEADERS)

    # 1. Формируем прямой поисковый POST/GET запрос в раздел search_load
    id_from = ""
    id_to = ""
    for k, v in CITY_IDS.items():
        if k in f_lower:
            id_from = v
        if k in t_lower:
            id_to = v

    urls_to_query = [
        f"https://fa-fa.kz/search_load/?from_city={urllib.parse.quote(from_city)}&to_city={urllib.parse.quote(to_city)}",
        f"https://fa-fa.kz/search_load/?city_from={id_from}&city_to={id_to}" if id_from and id_to else None,
        "https://fa-fa.kz/search_load/"
    ]

    prices = []

    for url in urls_to_query:
        if not url:
            continue
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code != 200 or not resp.text:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Поиск строк в таблице выдачи FA-FA
            rows = soup.find_all(["tr", "div", "li"])
            
            for row in rows:
                row_text = row.get_text(" ", strip=True).lower()
                
                # Если в строке фигурируют оба города
                if f_stem in row_text and t_stem in row_text:
                    # Регулярка под реальный формат цен на FA-FA: 110.000 тнг, 140 000 тг, 150000 ₸
                    matches = re.findall(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{4,7})\s*(?:тнг|тг|тенге|₸)", row_text)
                    for m in matches:
                        clean_num = int(re.sub(r"\D", "", m))
                        # Отсекаем догрузы дешевле 35 000 и нереальные аномалии выше 4 000 000
                        if 35000 <= clean_num <= 4000000:
                            prices.append(clean_num)

            if len(prices) >= 2:
                break
        except Exception as e:
            print(f"Fetch error: {e}")
            continue

    if prices:
        prices.sort()
        # Отсекаем разовые заниженные/завышенные выбросы, если ставок много
        clean_prices = prices[1:-1] if len(prices) >= 4 else prices
        avg_price = int(round(sum(clean_prices) / len(clean_prices) / 1000) * 1000)

        return jsonify({
            "found": True,
            "min_price": min(clean_prices),
            "avg_price": avg_price,
            "max_price": max(clean_prices),
            "count": len(prices),
            "source": f"FA-FA.kz (Найдено заявок: {len(prices)})"
        })

    return jsonify({
        "found": False,
        "source": f"На FA-FA нет ставок с открытой ценой по направлению {from_city} — {to_city}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
