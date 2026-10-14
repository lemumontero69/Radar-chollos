import json, os, re, time, random, requests
TOPIC = os.environ.get('NTFY_TOPIC')
from bs4 import BeautifulSoup

BUSQUEDAS = ["televisor 4k", "televisor oled", "smartphone", "iphone", "samsung galaxy",
             "xiaomi", "lavadora", "frigorifico", "lavavajillas", "horno", "robot aspirador",
             "portatil", "monitor", "tablet", "auriculares bluetooth", "consola", "camara"]
PAGINAS = 2            # paginas de resultados por busqueda
MIN_DESCUENTO = 50     # % minimo para aparecer en la lista
ERROR_PRECIO = 70      # % desde el que se marca como posible error de precio
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"}

def num(txt):
    m = re.search(r"[\d.]+,\d{2}|\d+", txt.replace("\xa0", ""))
    return float(m.group().replace(".", "").replace(",", ".")) if m else None

def buscar(q, pag):
    r = requests.get("https://www.amazon.es/s", params={"k": q, "page": pag}, headers=HEAD, timeout=20)
    if r.status_code != 200:
        print("Aviso", q, pag, r.status_code); return []
    out = []
    for it in BeautifulSoup(r.text, "html.parser").select('div[data-component-type="s-search-result"]'):
        asin = it.get("data-asin")
        ahora = it.select_one("span.a-price:not(.a-text-price) span.a-offscreen")
        antes = it.select_one("span.a-price.a-text-price span.a-offscreen")
        t = it.select_one("h2")
        if not (asin and ahora and t): continue
        p = num(ahora.text)
        o = num(antes.text) if antes else None
        if p: out.append((asin, t.get_text(strip=True)[:110], p, o))
    return out

def avisar(x):
    if not TOPIC: return
    try:
        requests.post(f"https://ntfy.sh/{TOPIC}",
            data=f"{x['titulo']}\n{x['precio']:.2f} EUR (antes {x['antes']:.2f} EUR)".encode("utf-8"),
            headers={"Title": f"Posible error de precio -{x['descuento']}%", "Click": x["url"],
                     "Priority": "high", "Tags": "rotating_light"}, timeout=15)
    except Exception as e:
        print("ntfy fallo", e)

def main():
    previos = set()
    if os.path.exists("deals.json"):
        previos = {c["asin"] for c in json.load(open("deals.json", encoding="utf-8")).get("chollos", [])}
    hist = json.load(open("prices.json")) if os.path.exists("prices.json") else {}
    vistos = {}
    for q in BUSQUEDAS:
        for pag in range(1, PAGINAS + 1):
            for asin, titulo, p, o in buscar(q, pag):
                h = hist.get(asin, {"max": p})
                h["max"] = max(h.get("max", p), p); h["ult"] = p
                hist[asin] = h
                d_lista = round((1 - p / o) * 100) if o and o > p else 0
                d_hist = round((1 - p / h["max"]) * 100) if h["max"] > p else 0
                d = max(d_lista, d_hist)
                if d >= MIN_DESCUENTO:
                    vistos[asin] = {"asin": asin, "titulo": titulo, "precio": p,
                        "antes": o if d_lista >= d_hist else h["max"], "descuento": d,
                        "error": d >= ERROR_PRECIO,
                        "motivo": "histórico" if d_hist > d_lista else "precio tachado",
                        "url": f"https://www.amazon.es/dp/{asin}"}
            time.sleep(random.uniform(3, 7))
    lista = sorted(vistos.values(), key=lambda x: (not x["error"], -x["descuento"]))
    for x in lista:
        if x["error"] and x["asin"] not in previos: avisar(x)
    json.dump({"actualizado": time.strftime("%d/%m/%Y %H:%M UTC", time.gmtime()), "chollos": lista},
              open("deals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(hist, open("prices.json", "w"))
    print(len(lista), "chollos")

main()
