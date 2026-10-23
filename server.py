import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

FAFA_COOKIES = {
    "_ym_uid": "1674474011683190655",
    "bbuserid": "129703",
    "bbpassword": "a1ddf0774cc53568b323cab51517c172",
    "PHPSESSID": "vnlqf7kb3q7hhm4grfa64vosa3",
    "c_uid": "129703"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://fa-fa.kz/search_load/",
    "Origin": "https://fa-fa.kz"
}

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Города не указаны"}), 400

    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(FAFA_COOKIES)

    # 1. Отправляем реальные параметры поиска FA-FA
    payload = {
        "city_from": from_city,
        "city_to": to_city,
        "weight_from": "0",
        "weight_to": "22",
        "volume_from": "0",
        "volume_to": "130",
        "search": "1"
    }

    try:
        resp = session.post("https://fa-fa.kz/search_load/", data=payload, timeout=12, allow_redirects=True)
        html = resp.text
        url_now = resp.url
    except Exception as e:
        return jsonify({"found": False, "error": str(e)}), 500

    # Поиск всех цен в тенге на полученной странице
    prices = []
    matches = re.findall(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{4,7})\s*(?:тнг|тг|тенге|₸)", html, re.IGNORECASE)
    for m in matches:
        val = int(re.sub(r"\D", "", m))
        if 40000 <= val <= 3500000:
            prices.append(val)

    # Если нашли цены
    if prices:
        prices.sort()
        clean = prices[1:-1] if len(prices) >= 4 else prices
        avg_val = int(round(sum(clean) / len(clean) / 1000) * 1000)

        return jsonify({
            "found": True,
            "min_price": min(clean),
            "avg_price": avg_val,
            "max_price": max(clean),
            "count": len(prices),
            "source": f"FA-FA.kz (заявок: {len(prices)})"
        })

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title else "Нет title"
    snippet = soup.get_text(" ", strip=True)[:350]

    return jsonify({
        "found": False,
        "final_url": url_now,
        "page_title": title,
        "html_preview": snippet
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
