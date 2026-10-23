import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS
import urllib.parse

app = Flask(__name__)
CORS(app)

RUB_TO_KZT = 5.2

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Укажите города"}), 400

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Referer": "https://fa-fa.kz/"
    })

    # Сначала инициируем сессию на главной FA-FA для получения рабочих cookies
    try:
        session.get("https://fa-fa.kz/", timeout=7)
    except Exception:
        pass

    rates = []
    f_stem = from_city.lower()[:4]
    t_stem = to_city.lower()[:4]

    # Список целевых точек поиска биржи
    search_urls = [
        f"https://fa-fa.kz/search_cargo/?from_city={urllib.parse.quote(from_city)}&to_city={urllib.parse.quote(to_city)}",
        f"https://fa-fa.kz/search_cargo/?city_from={urllib.parse.quote(from_city)}&city_to={urllib.parse.quote(to_city)}",
        "https://fa-fa.kz/search_cargo/"
    ]

    for target_url in search_urls:
        try:
            resp = session.get(target_url, timeout=10)
            if resp.status_code != 200 or not resp.text:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.find_all(["tr", "div", "li"], class_=re.compile(r"(cargo|item|row|search|load)", re.I))

            for r in rows:
                txt = r.get_text(" ", strip=True).lower()
                # Проверяем вхождение обоих городов в блок заявки
                if f_stem in txt and t_stem in txt:
                    # Поиск сумм в тенге
                    kzt_matches = re.findall(r"(\d[\d\s]{3,7})\s*(?:тг|тенге|₸|kzt)", txt)
                    for m in kzt_matches:
                        num = int(re.sub(r"\D", "", m))
                        if 30000 <= num <= 4500000:
                            rates.append(num)

                    # Поиск сумм в рублях (конвертируем в тенге)
                    rub_matches = re.findall(r"(\d[\d\s]{3,6})\s*(?:руб|р\b|₽|rub)", txt)
                    for m in rub_matches:
                        num = int(re.sub(r"\D", "", m))
                        if 5000 <= num <= 700000:
                            rates.append(int(num * RUB_TO_KZT))

            if len(rates) >= 1:
                break
        except Exception as e:
            print(f"Fetch error: {e}")
            continue

    if rates:
        rates.sort()
        # Исключаем явные выбросы, если ставок много
        valid_rates = rates[1:-1] if len(rates) >= 4 else rates
        avg_val = int(round(sum(valid_rates) / len(valid_rates) / 1000) * 1000)

        return jsonify({
            "found": True,
            "min_price": min(valid_rates),
            "avg_price": avg_val,
            "max_price": max(valid_rates),
            "count": len(rates),
            "source": f"FA-FA.kz (Найдено заявок: {len(rates)})"
        })

    # Если заявок с открытой ставкой нет, возвращаем честный ответ без выдуманных цифр
    return jsonify({
        "found": False,
        "message": f"На FA-FA нет открытых ставок по направлению {from_city} — {to_city}"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
