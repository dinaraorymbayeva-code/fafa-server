import os
import math
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

RUB_TO_KZT_RATE = 5.2  # Текущий рыночный курс конвертации рубля в тенге

def parse_fafa_live_rates(from_city, to_city):
    """Парсинг живых ставок с FA-FA с поддержкой KZT и RUB"""
    rates_kzt = []
    
    # Варианты поисковых ссылок FA-FA
    urls = [
        f"https://fa-fa.kz/search_cargo/?from_city={requests.utils.quote(from_city)}&to_city={requests.utils.quote(to_city)}",
        f"https://fa-fa.kz/gruzy/?from={requests.utils.quote(from_city)}&to={requests.utils.quote(to_city)}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
    }

    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=7)
            if not res.ok:
                continue
                
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Поиск блоков с ценами и карточек грузов
            price_nodes = soup.find_all(class_=re.compile(r"price|cost|rate|cargo-item__price", re.I))
            
            for node in price_nodes:
                raw_text = node.get_text().strip().lower()
                
                # Пропускаем договорные ставки без указания цифр
                if "договор" in raw_text or "дог." in raw_text:
                    continue
                
                # Извлекаем только цифры
                clean_num_str = re.sub(r"[^\d]", "", raw_text)
                if not clean_num_str:
                    continue
                
                val = int(clean_num_str)
                
                # Если цена указана в рублях
                if "руб" in raw_text or "rub" in raw_text or "₽" in raw_text or (val < 500000 and "москв" in from_city.lower()):
                    val_kzt = int(val * RUB_TO_KZT_RATE)
                else:
                    val_kzt = val

                # Фильтр реального коридора фуры (от 150 000 до 6 000 000 ₸)
                if 150000 <= val_kzt <= 6000000:
                    rates_kzt.append(val_kzt)
                    
            if rates_kzt:
                break
        except Exception as e:
            print("Ошибка запроса к FA-FA:", e)

    return rates_kzt

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"error": "Укажите from и to"}), 400

    # 1. Запрос живых ставок на бирже
    live_rates = parse_fafa_live_rates(from_city, to_city)

    if live_rates:
        min_p = min(live_rates)
        max_p = max(live_rates)
        avg_p = int(sum(live_rates) / len(live_rates))
        
        # Округление до тысяч для чистоты расчета
        avg_p = int(round(avg_p / 1000.0) * 1000)
        min_p = int(round(min_p / 1000.0) * 1000)
        max_p = int(round(max_p / 1000.0) * 1000)

        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "count": len(live_rates),
            "source": f"Живые торги FA-FA (активных заявок: {len(live_rates)})"
        })

    # 2. Если на бирже нет открытых цен — расчет по километражу
    dist = calculate_distance_km(from_city, to_city)
    if dist:
        min_p, avg_p, max_p = estimate_rate_by_distance(dist)
        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "distance_km": dist,
            "source": f"Рыночный срез по маршруту ({dist} км)"
        })

    return jsonify({
        "found": False,
        "error": "Ставки не найдены"
    })
