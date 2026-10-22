import os
import math
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

RUB_TO_KZT_RATE = 5.2

def parse_fafa_direct(from_city, to_city):
    """Прямой сбор реальных ставок через сессию формы поиска FA-FA"""
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://fa-fa.kz/search_load/",
        "Accept-Language": "ru-RU,ru;q=0.9"
    }
    
    rates = []
    try:
        # Шаг 1: инициализация страницы поиска
        init_res = session.get("https://fa-fa.kz/search_load/", headers=headers, timeout=6)
        
        # Шаг 2: отправка фильтра по городам (20 тонн)
        post_data = {
            "from_name": from_city,
            "to_name": to_city,
            "weight_to": "22",
            "volume_to": "92"
        }
        search_res = session.post("https://fa-fa.kz/search_load/", data=post_data, headers=headers, timeout=6)
        
        soup = BeautifulSoup(search_res.text, "html.parser")
        
        # Извлекаем все строки таблицы, где указана цена
        rows = soup.find_all(text=re.compile(r"(?:тнг|тг|₸|руб|\bтенге\b)", re.I))
        for item in rows:
            text = item.strip().lower()
            if "договор" in text or "дог" in text:
                continue
            digits = re.sub(r"[^\d]", "", text)
            if not digits:
                continue
            val = int(digits)
            if "руб" in text or "rub" in text or "₽" in text:
                val = int(val * RUB_TO_KZT_RATE)
                
            # Реальные ставки для фуры
            if 150000 <= val <= 3500000:
                rates.append(val)
    except Exception as e:
        print("Ошибка сессии FA-FA:", e)

    return rates

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_c = request.args.get("from", "").strip()
    to_c = request.args.get("to", "").strip()

    if not from_c or not to_c:
        return jsonify({"error": "Укажите города"}), 400

    rates = parse_fafa_direct(from_c, to_c)

    if rates and len(rates) >= 2:
        rates.sort()
        # Отсекаем 10% самых крайних выбросов
        mid_rates = rates[1:-1] if len(rates) > 4 else rates
        min_p = min(mid_rates)
        max_p = max(mid_rates)
        avg_p = int(sum(mid_rates) / len(mid_rates))
        
        return jsonify({
            "found": True,
            "min_price": int(round(min_p / 1000.0) * 1000),
            "avg_price": int(round(avg_p / 1000.0) * 1000),
            "max_price": int(round(max_p / 1000.0) * 1000),
            "count": len(rates),
            "source": f"Живые торги FA-FA (найдено {len(rates)} заявок)"
        })

    # Если биржа вернула 0 заявок (нет грузов по фильтру)
    return jsonify({
        "found": False,
        "source": "На FA-FA нет активных заявок. Укажите ставку вручную"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
