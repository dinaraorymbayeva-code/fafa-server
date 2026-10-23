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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Referer": "https://fa-fa.kz/"
    })

    search_url = f"https://fa-fa.kz/search_cargo/?from_city={urllib.parse.quote(from_city)}&to_city={urllib.parse.quote(to_city)}"
    
    try:
        resp = session.get(search_url, timeout=12)
        status = resp.status_code
        html = resp.text
    except Exception as e:
        return jsonify({"found": False, "debug_error": str(e), "message": "Сбой соединения с FA-FA"})

    # Диагностика: если FA-FA вернул блокировку или пустую страницу
    if status != 200:
        return jsonify({"found": False, "status_code": status, "message": f"FA-FA вернул код ошибки {status}"})

    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.string.strip() if soup.title else "Без заголовка"
    
    # Ищем любые упоминания цен в тексте всей страницы
    all_text = soup.get_text(" ", strip=True)
    kzt_all = re.findall(r"(\d[\d\s]{3,7})\s*(?:тг|тенге|₸)", all_text, re.IGNORECASE)
    
    prices = []
    for m in kzt_all:
        val = int(re.sub(r"\D", "", m))
        if 40000 <= val <= 3500000:
            prices.append(val)

    if prices:
        prices.sort()
        valid = prices[1:-1] if len(prices) >= 4 else prices
        avg_val = int(round(sum(valid) / len(valid) / 1000) * 1000)
        return jsonify({
            "found": True,
            "min_price": min(valid),
            "avg_price": avg_val,
            "max_price": max(valid),
            "count": len(prices),
            "source": f"FA-FA.kz live ({len(prices)} заявок)"
        })

    # Возвращаем точную причину, что именно ответила биржа FA-FA
    return jsonify({
        "found": False,
        "title": page_title,
        "html_length": len(html),
        "sample": html[:300].strip(),
        "message": f"Биржа открылась ({page_title}), но активных цен не обнаружено"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
