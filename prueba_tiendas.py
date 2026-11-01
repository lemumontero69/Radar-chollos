import json, re, time, requests

# Prueba de lectura (solo mira, no compra ni guarda nada): Game y Neobyte
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"}

def bajar(url):
    try:
        r = requests.get(url, headers=HEAD, timeout=30)
        return r.status_code, r.text
    except Exception as e:
        return 0, ""

def recorrer(o):
    yield o
    if isinstance(o, dict):
        for v in o.values():
            yield from recorrer(v)
    elif isinstance(o, list):
        for v in o:
            yield from recorrer(v)

def jsonld(html):
    out = []
    for b in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, flags=re.S | re.I):
        try:
            out.append(json.loads(b.strip()))
        except Exception:
            pass
    return out

def productos(html):
    res = []
    for blk in jsonld(html):
        for n in recorrer(blk):
            if isinstance(n, dict) and "Product" in str(n.get("@type")):
                res.append(n)
    return res

def resumen(p):
    of = p.get("offers")
    if isinstance(of, list) and of:
        of = of[0]
    of = of if isinstance(of, dict) else {}
    codigos = {k: p[k] for k in p if k.lower().startswith("gtin") or k.lower() in ("sku", "mpn", "productid")}
    return (f"nombre={str(p.get('name'))[:45]!r} precio={of.get('price')} "
            f"stock={str(of.get('availability'))[-12:]} codigos={codigos}")

def probar(nombre, url, enlaces_re, n_enlaces=2):
    cod, html = bajar(url)
    tipos = set()
    for blk in jsonld(html):
        for n in recorrer(blk):
            if isinstance(n, dict) and n.get("@type"):
                tipos.add(str(n["@type"]))
    prods = productos(html)
    print(f"[{nombre}] codigo={cod} bytes={len(html)} tipos_jsonld={sorted(tipos)[:6]} productos={len(prods)}")
    for p in prods[:2]:
        print("   ", resumen(p))
    links = []
    for blk in jsonld(html):
        for n in recorrer(blk):
            if isinstance(n, dict) and n.get("@type") == "ListItem":
                u = n.get("url") or (n.get("item") or {}).get("url") if isinstance(n.get("item"), dict) else n.get("url")
                if u:
                    links.append(u)
    links += re.findall(enlaces_re, html)
    vistos = []
    for u in links:
        if u.startswith("/"):
            u = url.split("/", 3)[0] + "//" + url.split("/")[2] + u
        if u not in vistos:
            vistos.append(u)
    return vistos[:n_enlaces + 6]

# Game: lista de ofertas y dos fichas de producto
enl = probar("Game ofertas", "https://www.game.es/ofertas", r'href="((?:https://www\.game\.es)?/[^"]+/\d{5,}[^"]*)"')
print("   enlaces ejemplo:", [e[-60:] for e in enl[:3]])
for u in enl[:2]:
    time.sleep(2)
    probar("Game ficha", u, r"$^", 0)

# Neobyte: portada y enlaces de categoria
time.sleep(2)
enl = probar("Neobyte portada", "https://www.neobyte.es/", r'href="(https://www\.neobyte\.es/[a-z0-9\-]+)"', 8)
print("   enlaces ejemplo:", [e[-40:] for e in enl[:8]])
for u in enl[:1]:
    time.sleep(2)
    enl2 = probar("Neobyte categoria", u, r'href="(https://www\.neobyte\.es/[a-z0-9\-/]+\.html)"', 2)
    for v in enl2[:2]:
        time.sleep(2)
        probar("Neobyte ficha", v, r"$^", 0)
