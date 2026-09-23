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

# Координаты городов СНГ, РК и РФ
CITY_COORDINATES = {
    # Казахстан
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
    "темиртау": (50.0544, 72.9575),
    "жезказган": (47.7833, 67.7667),

    # Россия
    "москва": (55.7558, 37.6173),
    "санкт-петербург": (59.9343, 30.3351),
    "питер": (59.9343, 30.3351),
    "екатеринбург": (56.8389, 60.6057),
    "новосибирск": (55.0084, 82.9357),
    "челябинск": (55.1644, 61.4368),
    "самара": (53.1959, 50.1002),
    "омск": (54.9885, 73.3242),
    "уфа": (54.7388, 55.9721),
    "казань": (55.8304, 49.0661),
    "тюмень": (57.1522, 65.5272),
    "курган": (55.4411, 65.3411),
    "оренбург": (51.7727, 55.0988),
    "магнитогорск": (53.4186, 58.9759),
    "барнаул": (53.3548, 83.7698),
    "красноярск": (56.0153, 92.8932),
    "пермь": (58.0105, 56.2502),
    "нижний новгород": (56.2965, 43.9361),
    "волгоград": (48.7080, 44.5133),
    "ростов-на-дону": (47.2357, 39.7015),
    "краснодар": (45.0355, 38.9753),
    "воронеж": (51.6755, 39.2089),
    "саратов": (51.5406, 46.0086),

    # Узбекистан / Кыргызстан
    "ташкент": (41.2995, 69.2401),
    "самарканд": (39.6542, 66.9597),
    "бишкек": (42.8746, 74.5698),
    "ош": (40.5140, 72.8161)
}

def clean_city_name(city_str):
    if not city_str:
        return ""
    c = city_str.lower().strip()
    c = c.replace("г.", "").replace("город", "").strip()
    return c

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
    r = 6371.0
    straight_dist = r * c

    # Дорожный коэффициент
    road_km = int(round(straight_dist * 1.25))
    return max(road_km, 50)

def estimate_rate_by_distance(distance_km):
    if distance_km <= 350:
        rate_km = 680
    elif distance_km <= 750:
        rate_km = 600
    elif distance_km <= 1500:
        rate_km = 550
    elif distance_km <= 2500:
        rate_km = 580
    else:
        rate_km = 600

    avg_p = int(round((distance_km * rate_km) / 10000.0) * 10000)
    min_p = int(round((avg_p * 0.85) / 10000.0) * 10000)
    max_p = int(round((avg_p * 1.15) / 10000.0) * 10000)
    return min_p, avg_p, max_p

def parse_fafa_live_rates(from_city, to_city):
    rates_kzt = []
    urls = [
        f"https://fa-fa.kz/search_cargo/?from_city={requests.utils.quote(from_city)}&to_city={requests.utils.quote(to_city)}",
        f"https://fa-fa.kz/gruzy/?from={requests.utils.quote(from_city)}&to={requests.utils.quote(to_city)}"
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9"
    }

    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=6)
            if not res.ok:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            price_nodes = soup.find_all(class_=re.compile(r"price|cost|rate|cargo-item__price", re.I))

            for node in price_nodes:
                raw_text = node.get_text().strip().lower()
                if "договор" in raw_text or "дог." in raw_text:
                    continue
                clean_digits = re.sub(r"[^\d]", "", raw_text)
                if not clean_digits:
                    continue
                val = int(clean_digits)

                # Перевод из рублей в тенге
                if "руб" in raw_text or "rub" in raw_text or "₽" in raw_text or (val < 600000 and ("москв" in from_city.lower() or "росси" in from_city.lower())):
                    val_kzt = int(val * RUB_TO_KZT_RATE)
                else:
                    val_kzt = val

                if 150000 <= val_kzt <= 8000000:
                    rates_kzt.append(val_kzt)

            if rates_kzt:
                break
        except Exception as e:
            print("FA-FA fetch error:", e)

    return rates_kzt

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"error": "Укажите from и to"}), 400

    # 1. Поиск прямых заявок на бирже
    live_rates = parse_fafa_live_rates(from_city, to_city)
    if live_rates:
        min_p = int(round(min(live_rates) / 1000.0) * 1000)
        max_p = int(round(max(live_rates) / 1000.0) * 1000)
        avg_p = int(round((sum(live_rates) / len(live_rates)) / 1000.0) * 1000)
        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "count": len(live_rates),
            "source": f"Живые торги FA-FA (заявок: {len(live_rates)})"
        })

    # 2. Если прямых ставок нет — точный расчет по расстоянию
    dist = calculate_distance_km(from_city, to_city)
    if dist:
        min_p, avg_p, max_p = estimate_rate_by_distance(dist)
        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "distance_km": dist,
            "source": f"Рыночный срез по расстоянию ({dist} км)"
        })

    # 3. Базовый срез для неизвестных точек
    return jsonify({
        "found": True,
        "min_price": 450000,
        "avg_price": 550000,
        "max_price": 650000,
        "source": "Индикатив (уточните у диспетчера)"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
