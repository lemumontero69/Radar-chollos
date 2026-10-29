import re, requests

PAGINAS = {
    "MediaMarkt ofertas": "https://www.mediamarkt.es/es/campaign/ofertas",
    "MediaMarkt portatiles": "https://www.mediamarkt.es/es/category/_portatiles-701421.html",
    "El Corte Ingles electronica": "https://www.elcorteingles.es/electronica/",
    "El Corte Ingles ofertas": "https://www.elcorteingles.es/ofertas/",
}
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"}
BLOQUEO = ["captcha", "access denied", "robot", "unusual traffic", "px-captcha", "akamai", "forbidden"]

for nombre, url in PAGINAS.items():
    try:
        r = requests.get(url, headers=HEAD, timeout=25)
    except Exception as e:
        print(f"[{nombre}] ERROR de red: {e}"); continue
    t = r.text.lower()
    precios = len(re.findall(r"\d+[.,]\d{2}\s*(?:€|&euro;|eur)", t))
    json_ld = t.count("application/ld+json")
    marcas = [b for b in BLOQUEO if b in t]
    print(f"[{nombre}] codigo={r.status_code} bytes={len(r.text)} precios_en_html={precios} json_ld={json_ld} bloqueo={marcas}")
