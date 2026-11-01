import re, time, requests

# Cada web se prueba una sola vez, con una peticion normal. Solo lectura.
PAGINAS = {
    # comunidades de chollos con RSS (los chollos los publica la gente)
    "Chollometro RSS": "https://www.chollometro.com/rss",
    "Chollometro RSS nuevos": "https://www.chollometro.com/rss/nuevos",
    "Dealabs RSS (Francia)": "https://www.dealabs.com/rss",
    "MyDealz RSS (Alemania)": "https://www.mydealz.de/rss",
    "HotUKDeals RSS (UK)": "https://www.hotukdeals.com/rss",
    # tiendas
    "PcComponentes ofertas": "https://www.pccomponentes.com/ofertas-del-dia",
    "Fnac ofertas": "https://www.fnac.es/Ofertas",
    "Worten ofertas": "https://www.worten.es/ofertas",
    "Carrefour electronica": "https://www.carrefour.es/electrodomesticos/",
    "Leroy Merlin ofertas": "https://www.leroymerlin.es/ofertas.html",
    "eBay ofertas": "https://www.ebay.es/globaldeals",
    "Idealo": "https://www.idealo.es/",
    "Miravia": "https://www.miravia.es/",
}
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"}
BLOQUEO = ["captcha", "access denied", "unusual traffic", "px-captcha", "forbidden",
           "just a moment", "enable javascript", "cf-chl", "are you a robot"]

for nombre, url in PAGINAS.items():
    try:
        r = requests.get(url, headers=HEAD, timeout=25)
    except Exception as e:
        print(f"[{nombre}] ERROR de red: {str(e)[:80]}"); continue
    t = r.text.lower()
    precios = len(re.findall(r"\d+[.,]\d{2}\s*(?:€|&euro;|eur)", t))
    items = t.count("<item>") + t.count("<item ")
    json_ld = t.count("application/ld+json")
    marcas = [b for b in BLOQUEO if b in t]
    print(f"[{nombre}] codigo={r.status_code} bytes={len(r.text)} items_rss={items} "
          f"precios={precios} json_ld={json_ld} bloqueo={marcas}")
    time.sleep(2)
