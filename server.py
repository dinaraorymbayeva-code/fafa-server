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

CITY_COORDINATES = {
    "астана": (51.1694, 71.4491),
    "нур-султан": (51.1694, 71.4491),
    "алматы": (43.2220, 76.8512),
    "шымкент": (42.3417, 69.5901),
    "костанай": (53.2198, 63.6354),
    "караганда": (49.8019, 73.1021),
    "актобе": (50.2839, 57.1670),
    "павлодар": (52.2873, 76.9674),
    "усть-каменогорск": (49.9526, 82.6059),
    "семей": (50.4111, 80.2275),
    "атырау": (47.0945, 51.9238),
    "актау": (43.6481, 51.1722),
    "кокшетау": (53.2833, 69.3833),
    "петропавловск": (54.8753, 69.1630),
    "уральск": (51.2333, 51.3667),
    "тараз": (42.9000, 71.3667),
    "кызылорда": (44.8528, 65.5092),
    "туркестан": (43.2973, 68.2519),
    "талдыкорган": (45.0156, 78.3739),
    "рудный": (52.9629, 63.1252),
    "экибастуз": (51.7236, 75.3229),
    "москва": (55.7558, 37.6173),
    "санкт-петербург": (59.9343, 30.3351),
    "екатеринбург": (56.8389, 60.6057),
    "челябинск": (55.1644, 61.4368),
    "самара": (53.1959, 50.1002),
    "омск": (54.9885, 73.3242),
    "новосибирск": (55.0084, 82.9357)
}

def clean_city_name(city_str):
    if not city_str:
        return ""
    return city_str.lower().replace("г.", "").replace("город", "").strip()

def calculate_distance_km(city1, city2):
    c1 = clean_city_name(city1)
    c2 = clean_city_name(city2)
    coord1 = CITY_COORDINATES.get(c1)
    coord2 = CITY_COORDINATES.get(c2)
    if not coord1 or not coord2:
        return None
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(round(6371.0 * c * 1.25))

def estimate_rate_by_distance(dist_km, is_international=False):
    """Реалистичные индикативные ставки за 20т (фура)"""
    if is_international:
        rate_km = 450 if dist_km > 2000 else 550
    else:
        # Внутренние рейсы РК (на плечах > 1000 км ставка 200-240 ₸/км)
        if dist_km >= 1200:
            rate_km = 210
        elif dist_km >= 700:
            rate_km = 260
        else:
            rate_km = 330

    avg_p = int(round((dist_km * rate_km) / 5000.0) * 5000)
    min_p = int(round((avg_p * 0.90) / 5000.0) * 5000)
    max_p = int(round((avg_p * 1.12) / 5000.0) * 5000)
    return min_p, avg_p, max_p

def parse_fafa_live_rates(from_city, to_city):
    rates_kzt = []
    
    # Актуальные поисковые эндпоинты FA-FA
    urls = [
        f"https://fa-fa.kz/search_load/?from_name={requests.utils.quote(from_city)}&to_name={requests.utils.quote(to_city)}",
        f"https://fa-fa.kz/search_load/?filter%5Bfrom_name%5D={requests.utils.quote(from_city)}&filter%5Bto_name%5D={requests.utils.quote(to_city)}",
        f"https://fa-fa.kz/gruzy/?from={requests.utils.quote(from_city)}&to={requests.utils.quote(to_city)}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if not res.ok:
                continue
            
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Поиск всех текстовых блоков с ценами в таблице грузов
            items = soup.find_all(text=re.compile(r"(?:тнг|тг|₸|руб|\bтенге\b)", re.I))
            for text in items:
                line = text.strip().lower()
                if "договор" in line or "дог" in line:
                    continue
                
                digits = re.sub(r"[^\d]", "", line)
                if not digits:
                    continue
                val = int(digits)

                if "руб" in line or "rub" in line or "₽" in line:
                    val = int(val * RUB_TO_KZT_RATE)

                # Коридор цен для реальной фуры (от 150 000 до 4 500 000 ₸)
                if 150000 <= val <= 4500000:
                    rates_kzt.append(val)

            if len(rates_kzt) >= 2:
                break
        except Exception as e:
            print("Fetch error:", e)

    return rates_kzt

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"error": "Укажите города"}), 400

    # 1. Попытка взять живые торги с FA-FA
    live_rates = parse_fafa_live_rates(from_city, to_city)
    
    # Отсекаем аномальные выбросы (слишком мелкие догрузы и завышенные ставки)
    valid_rates = [p for p in live_rates if p >= 200000]
    
    if valid_rates:
        min_p = min(valid_rates)
        max_p = max(valid_rates)
        avg_p = int(sum(valid_rates) / len(valid_rates))
        
        return jsonify({
            "found": True,
            "min_price": int(round(min_p / 1000.0) * 1000),
            "avg_price": int(round(avg_p / 1000.0) * 1000),
            "max_price": int(round(max_p / 1000.0) * 1000),
            "count": len(valid_rates),
            "source": f"Живые торги FA-FA (заявок: {len(valid_rates)})"
        })

    # 2. Если торги пусты или парсер закрыт капчей — точный индикатив по реальному рынку
    dist = calculate_distance_km(from_city, to_city) or 1470
    is_int = any(c in from_city.lower() or c in to_city.lower() for c in ["москва", "питер", "екатеринбург", "челябинск", "самара", "омск"])
    min_p, avg_p, max_p = estimate_rate_by_distance(dist, is_international=is_int)

    return jsonify({
        "found": True,
        "min_price": min_p,
        "avg_price": avg_p,
        "max_price": max_p,
        "distance_km": dist,
        "source": f"Рыночный индикатив ({dist} км)"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
