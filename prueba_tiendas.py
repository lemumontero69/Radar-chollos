import re, time, requests

# Cada web se prueba una sola vez, con una peticion normal. Solo lectura.
PAGINAS = {
    "Coolmod inicio": "https://www.coolmod.com/",
    "Coolmod ofertas": "https://www.coolmod.com/ofertas/",
    "Game inicio": "https://www.game.es/",
    "Game ofertas": "https://www.game.es/ofertas",
    "IKEA ofertas": "https://www.ikea.com/es/es/offers/",
    "IKEA ultimas unidades": "https://www.ikea.com/es/es/campaigns/",
    "Zalando ofertas": "https://www.zalando.es/ofertas/",
    "AliExpress inicio": "https://es.aliexpress.com/",
    "Neobyte ofertas": "https://www.neobyte.es/ofertas",
    "Xtremmedia ofertas": "https://www.xtremmedia.com/ofertas",
}
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"}
BLOQUEO = ["captcha", "access denied", "unusual traffic", "px-captcha", "forbidden",
           "just a moment", "enable javascript", "cf-chl", "are you a robot", "perimeterx"]

for nombre, url in PAGINAS.items():
    try:
        r = requests.get(url, headers=HEAD, timeout=25)
    except Exception as e:
        print(f"[{nombre}] ERROR de red: {str(e)[:80]}"); continue
    t = r.text.lower()
    precios = len(re.findall(r"\d+[.,]\d{2}\s*(?:€|&euro;|eur)", t))
    json_ld = t.count("application/ld+json")
    gtin = t.count("gtin") + t.count('"ean"') + t.count("itemprop=\"gtin")
    marcas = [b for b in BLOQUEO if b in t]
    print(f"[{nombre}] codigo={r.status_code} bytes={len(r.text)} precios={precios} "
          f"json_ld={json_ld} gtin_ean={gtin} bloqueo={marcas}")
    time.sleep(2)
