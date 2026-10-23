import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Авторизованные cookies сессии FA-FA
FAFA_COOKIES = (
    "_ym_uid=1674474011683190655; bbuserid=129703; "
    "_ymab_param=cifDjj0VEQgQ8SI0Pkf5D2vG05MdGpYoDGpy9ZLFq9JAeXH3yIcPR-M1nlsexCib58c_mER79E1oTECBSnnmsHexGJA; "
    "__upin=gwQWVZ9Lagb1gb6SWoTLZQ; gnezdo_uid=XV9mawducdFDF19Ub8/KAg--; "
    "bbpassword=a1ddf0774cc53568b323cab51517c172; __ai_fp_uuid=c9aeed7841c1bdae3a4; "
    "PHPSESSID=vnlqf7kb3q7hhm4grfa64vosa3; _ac_oid=7acf7cd1430305b92b430195314fdc27%3A1775214800777; "
    "c_uid=129703; puid=c1c8280ddf7cfa9ea8d62a8f018d9f7f; _ym_d=1786473088; "
    "__eoi=ID=ef415c5c71fd86ea:T=1786459108:RT=1788341390:S=AA-AfjzNNwkrknEsR1vo-bmfnJZE"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://fa-fa.kz/search_load/",
    "Cookie": FAFA_COOKIES
}

@app.route("/get_rate", methods=["GET"])
def get_rate():
    from_city = request.args.get("from", "").strip()
    to_city = request.args.get("to", "").strip()

    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Города не указаны"}), 400

    f_stem = from_city.lower()[:4]
    t_stem = to_city.lower()[:4]

    session = requests.Session()
    session.headers.update(HEADERS)

    search_url = f"https://fa-fa.kz/search_load/?from_city={urllib.parse.quote(from_city)}&to_city={urllib.parse.quote(to_city)}"

    try:
        resp = session.get(search_url, timeout=12)
        if resp.status_code != 200:
            return jsonify({"found": False, "status": resp.status_code, "message": "FA-FA вернул ошибку"}), 502

        soup = BeautifulSoup(resp.text, "html.parser")
        prices = []

        for row in soup.find_all(["tr", "div", "li"]):
            text = row.get_text(" ", strip=True).lower()
            if f_stem in text and t_stem in text:
                matches = re.findall(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{4,7})\s*(?:тнг|тг|тенге|₸)", text)
                for m in matches:
                    val = int(re.sub(r"\D", "", m))
                    if 35000 <= val <= 4000000:
                        prices.append(val)

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
                "source": f"FA-FA.kz (активных заявок: {len(prices)})"
            })

        return jsonify({
            "found": False,
            "message": f"На FA-FA нет активных ставок с открытой ценой по направлению {from_city} — {to_city}"
        })

    except Exception as e:
        return jsonify({"found": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
