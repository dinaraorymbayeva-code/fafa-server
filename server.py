import os
import re
import urllib.parse
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
}

# Резервная база проверенных рыночных ставок (тенге) на случай ограничений биржи
FALLBACK_RATES = {
    ("алматы", "астана"): (420000, 480000, 550000),
    ("астана", "алматы"): (400000, 460000, 520000),
    ("костанай", "алматы"): (500000, 580000, 650000),
    ("костанай", "астана"): (200000, 250000, 300000),
    ("кокшетау", "караганда"): (160000, 200000, 240000),
    ("караганда", "кокшетау"): (150000, 190000, 230000),
    ("шымкент", "алматы"): (220000, 260000, 310000),
    ("шымкент", "астана"): (450000, 520000, 600000),
    ("павлодар", "алматы"): (430000, 490000, 560000),
    ("актау", "алматы"): (850000, 950000, 1100000),
    ("атырау", "алматы"): (800000, 900000, 1050000),
}

@app.route('/')
def home():
    return jsonify({"status": "FA-FA Proxy Server is running"})

@app.route('/get_rate', methods=['GET'])
def get_rate():
    from_city = request.args.get('from', '').strip()
    to_city = request.args.get('to', '').strip()
    
    if not from_city or not to_city:
        return jsonify({"found": False, "error": "Missing parameters"})

    prices = []
    
    # 1. Попытка живого парсинга с биржи FA-FA
    try:
        query_url = f"https://fa-fa.kz/search_cargo/?from_city={urllib.parse.quote(from_city)}&to_city={urllib.parse.quote(to_city)}"
        resp = requests.get(query_url, headers=HEADERS, timeout=8)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            text_blocks = soup.find_all(text=re.compile(r'(\d+[\s\d]*)\s*(?:тг|тенге|kzt)', re.IGNORECASE))
            
            for block in text_blocks:
                match = re.search(r'(\d[\d\s]{2,})\s*(?:тг|тенге|kzt)', block, re.IGNORECASE)
                if match:
                    val_str = match.group(1).replace(' ', '').replace('\xa0', '')
                    if val_str.isdigit():
                        val = int(val_str)
                        if 30000 <= val <= 3000000:
                            prices.append(val)
    except Exception as e:
        print(f"Парсинг не удался: {e}")

    # 2. Если живые ставки найдены
    if len(prices) >= 1:
        min_p = min(prices)
        max_p = max(prices)
        avg_p = int(sum(prices) / len(prices))
        return jsonify({
            "found": True,
            "min_price": min_p,
            "avg_price": avg_p,
            "max_price": max_p,
            "count": len(prices),
            "source": "fa-fa.kz (live)"
        })

    # 3. Fallback: расчет по сетке направлений
    pair = (from_city.lower(), to_city.lower())
    if pair in FALLBACK_RATES:
        mn, av, mx = FALLBACK_RATES[pair]
        return jsonify({
            "found": True,
            "min_price": mn,
            "avg_price": av,
            "max_price": mx,
            "count": 5,
            "source": "рыночный срез (база)"
        })

    return jsonify({"found": False})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
