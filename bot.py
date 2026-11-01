import json, os, sys, time, requests

KEY = os.environ.get("KEEPA_KEY")
TOPIC = os.environ.get("NTFY_TOPIC")
PO_TOKEN = os.environ.get("PUSHOVER_TOKEN")
PO_USER = os.environ.get("PUSHOVER_USER")
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID")

# mercado: (dominio Amazon, codigo, tipos de precio, paginas). Gasta tokens: no abuses.
MERCADOS = [("www.amazon.es", "ES", 9, [0, 1], 2),
            ("www.amazon.de", "DE", 3, [0], 1),
            ("www.amazon.fr", "FR", 4, [0], 1),
            ("www.amazon.it", "IT", 8, [0], 1)]
# tipo de precio: 0 = vendido por Amazon, 1 = nuevo de otros vendedores
MIN_DESCUENTO = 80           # % minimo para aparecer en la lista
MAX_DESCUENTO = 99           # por encima se considera dato roto
ERROR_PRECIO = 80            # % desde el que se marca como posible error de precio
PRECIO_MIN, PRECIO_MAX = 100, 600000    # en centimos: de 1 EUR a 6.000 EUR
PRECIO_ANTES_MIN = 10000     # ignora productos cuyo precio normal sea menor de 100 EUR
SOLO_CATEGORIAS = True       # pon False para vigilar todas las categorias
STOCK_MIN = 2                # unidades minimas: si Keepa confirma menos, se descarta
STOCK_DESCONOCIDO_AVISAR = True   # True: avisa aunque Keepa no sepa el stock (lo marca "sin confirmar")
RECHEQUEO_STOCK = 3600       # segundos hasta volver a mirar el stock de un chollo ya visto
EXIGIR_MES = True            # descarta productos sin al menos un mes de historial de precios
CATEGORIAS = [  # trozos del nombre de categoria en espanol, aleman, frances e italiano
    "electr", "inform", "videojuego", "foto", "camara", "c\u00e1mara", "hogar", "cocina",
    "electrodom", "coche", "moto", "bricolaje", "herramientas",
    "computer", "k\u00fcche", "haushalt", "baumarkt", "auto", "kamera", "games",
    "high-tech", "informatique", "cuisine", "maison", "bricolage", "jeux vid", "appareil",
    "elettronica", "informatica", "casa e cucina", "fai da te", "videogiochi", "fotocamera",
    # grandes electrodomesticos (lavadoras, frigorificos...): "electr" no los cubre en DE/FR/IT
    "elektro", "lectro", "elettro", "großger", "gros électro", "grandi",
    # ropa, zapatos y relojes (solo pasan las marcas de MARCAS)
    "ropa", "zapato", "reloj", "bekleidung", "schuhe", "uhren", "vêtement", "chaussures",
    "montres", "abbigliamento", "scarpe", "orologi"]
CATEGORIAS_MARCA = [   # en estas categorias solo se avisa si el titulo contiene una marca de MARCAS
    "ropa", "zapato", "reloj", "bekleidung", "schuhe", "uhren", "vêtement", "chaussures",
    "montres", "abbigliamento", "scarpe", "orologi"]
MARCAS = [   # marcas caras que te interesan: anade o quita las que quieras (en minusculas)
    "gucci", "prada", "louis vuitton", "moncler", "versace", "burberry", "armani", "dolce",
    "balenciaga", "valentino", "givenchy", "ralph lauren", "lacoste", "tommy hilfiger",
    "calvin klein", "hugo boss", "north face", "carhartt", "levi's", "levis", "stone island",
    "canada goose", "patagonia", "diesel", "guess", "michael kors", "barbour", "napapijri",
    "timberland", "superdry", "fossil", "seiko", "citizen", "tissot", "hamilton", "tag heuer",
    "omega", "rolex", "breitling", "casio", "g-shock", "garmin", "swatch", "longines",
    "daniel wellington", "emporio armani", "bulova", "festina", "maurice lacroix"]
EXCLUIR_TITULO = [
    "funda", "cubierta", "cubre", "lona", "toldo", "parasol", "alfombrilla", "limpia",
    "ambientador", "protector", "pegatina", "adhesivo", "vinilo", "cera ", "pulid", "aceite",
    "aditivo", "cable", "soporte", "organizador", "brocas", "puntas", "juego de puntas",
    "abdeckung", "schutzh", "plane", "autoabdeck", "kabel", "halterung", "reiniger",
    "housse", "b\u00e2che", "pare-soleil", "c\u00e2ble", "support", "nettoyant",
    "copriauto", "telo", "cavo", "supporto", "detergente", "custodia",
    "correa de", "correa para", "armband", "ersatzarmband", "uhrenarmband", "cinturino per",
    "bracelet de rechange", "recambio"]
CATS = []    # ids de categorias del mercado actual (se descubren en cada ejecucion)

NIVEL = 0   # consulta usada: 0 = completa, 1 = intermedia, 2 = minima

def consulta(dom, tipo, pag, nivel):
    base = {"page": pag, "domainId": dom, "priceTypes": [tipo], "dateRange": 0}
    if nivel == 2:
        return base
    base.update({"isRangeEnabled": True, "deltaPercentRange": [MIN_DESCUENTO, 100], "sortType": 4})
    if nivel == 1:
        return base
    base.update({"currentRange": [PRECIO_MIN, PRECIO_MAX], "deltaRange": [0, 1000000],
                 "deltaLastRange": None, "salesRankRange": None, "titleSearch": None,
                 "excludeCategories": [], "includeCategories": [], "minRating": -1,
                 "isLowest": False, "isLowestOffer": False, "isOutOfStock": False,
                 "isFilterEnabled": False, "filterErotic": True, "hasReviews": False,
                 "singleVariation": False})
    if CATS:
        base["isFilterEnabled"] = True
        base["includeCategories"] = CATS
    return base

def pedir(dom, tipo, pag):
    global NIVEL
    while NIVEL <= 2:
        try:
            r = requests.post("https://api.keepa.com/deal", params={"key": KEY},
                              json=consulta(dom, tipo, pag, NIVEL), timeout=60)
        except Exception as e:
            print("Aviso red", e); return None
        if r.status_code == 400 and NIVEL < 2:
            print("Consulta nivel", NIVEL, "rechazada (400); pruebo una mas sencilla")
            NIVEL += 1
            continue
        if r.status_code != 200:
            print("Aviso Keepa", dom, tipo, pag, r.status_code, r.text[:300]); return None
        d = r.json()
        print("nivel", NIVEL, "| tokens restantes:", d.get("tokensLeft"))
        return d.get("deals") or {}
    return None

def consultar_stock(dom, asins):
    """Devuelve {asin: unidades} solo de los productos cuyo stock conoce Keepa (~3 tokens por producto)."""
    res = {}
    for i in range(0, len(asins), 40):
        lote = asins[i:i + 40]
        try:
            r = requests.get("https://api.keepa.com/product", params={
                "key": KEY, "domain": dom, "asin": ",".join(lote), "stats": 1, "stock": 1}, timeout=90)
        except Exception as e:
            print("Aviso stock (red)", e); continue
        if r.status_code != 200:
            print("Aviso stock", r.status_code, r.text[:200]); continue
        d = r.json()
        print("stock | tokens restantes:", d.get("tokensLeft"))
        for p in d.get("products") or []:
            st = p.get("stats") or {}
            a, b = st.get("stockAmazon"), st.get("stockBuyBox")
            print("stock", p.get("asin"), "amazon:", a, "buybox:", b)
            vals = [v for v in (a, b) if isinstance(v, (int, float)) and v >= 0]
            if vals: res[p["asin"]] = int(max(vals))
        time.sleep(1)
    return res

def avisar(x):
    s = x.get("stock")
    uds = f"Unidades: {s}" if s is not None else "Unidades: sin confirmar"
    texto = f"{x['titulo']}\n{x['precio']:.2f} EUR (antes {x['antes']:.2f} EUR)\n{uds}"
    titulo = f"Posible error de precio -{x['descuento']}%"
    if TG_TOKEN and TG_CHAT:
        try:
            r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={
                "chat_id": TG_CHAT, "text": f"\U0001F6A8 {titulo}\n{texto}\n{x['url']}",
                "reply_markup": {"inline_keyboard": [[{"text": "Abrir en Amazon", "url": x["url"]}]]}},
                timeout=15)
            if r.status_code != 200:
                print("telegram fallo", r.status_code, r.text[:200])
        except Exception as e:
            print("telegram fallo", e)
    if TOPIC:
        try:
            requests.post(f"https://ntfy.sh/{TOPIC}", data=texto.encode("utf-8"),
                headers={"Title": titulo, "Click": x["url"], "Priority": "urgent",
                         "Tags": "rotating_light"}, timeout=15)
        except Exception as e:
            print("ntfy fallo", e)
    if PO_TOKEN and PO_USER:   # alarma que suena aunque el movil este en silencio
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": PO_TOKEN, "user": PO_USER, "title": titulo, "message": texto,
                "url": x["url"], "url_title": "Abrir en Amazon", "priority": 2,
                "retry": 60, "expire": 1800, "sound": "siren"}, timeout=15)
        except Exception as e:
            print("pushover fallo", e)

def main():
    if "--prueba" in sys.argv:
        avisar({"titulo": "Mensaje de prueba del radar de chollos", "precio": 19.99,
                "antes": 499.0, "descuento": 96, "stock": 5, "url": "https://www.amazon.es"})
        print("prueba enviada"); return
    if not KEY:
        print("Falta el secreto KEEPA_KEY"); sys.exit(1)
    prev = {}
    if os.path.exists("deals.json"):
        try:
            prev = json.load(open("deals.json", encoding="utf-8"))
        except Exception:
            prev = {}
    previos = {c.get("clave", "9:" + c["asin"]) for c in prev.get("chollos", [])}
    vistos, cats_vistas, ok = {}, {}, False
    global CATS
    for host, cod, dom, tipos, paginas in MERCADOS:
        CATS = []   # sin filtro al descubrir categorias (antes arrastraba las del pais anterior)
        d0 = pedir(dom, tipos[0], 0)
        if d0 is None:
            print("Aviso: mercado", cod, "sin respuesta"); continue
        if NIVEL == 0:
            CATS = [i for i, n in zip(d0.get("categoryIds", []), d0.get("categoryNames", []))
                    if any(c in n.lower() for c in CATEGORIAS)]
        print(cod, "categorias elegidas:", CATS)
        for tipo in tipos:
            for pag in range(paginas):
                deals = pedir(dom, tipo, pag)
                if deals is None: break
                ok = True
                nombres = dict(zip(deals.get("categoryIds", []), deals.get("categoryNames", [])))
                dr = deals.get("dr", [])
                for dl in dr:
                    try:
                        cur = dl["current"][tipo]
                        refs = [dl["avg"][i][tipo] for i in range(4)]   # 48h, semana, mes, 90 dias
                    except (KeyError, IndexError, TypeError):
                        continue
                    if EXIGIR_MES and (refs[2] or -1) <= 0: continue    # sin historial de un mes: no te fies
                    validos = [v for v in refs if v and v > 0]
                    if not validos: continue
                    avg = min(validos)   # precio de referencia = el mas bajo de todos los periodos
                    if cur < PRECIO_MIN or cur > PRECIO_MAX or avg < PRECIO_ANTES_MIN or cur >= avg: continue
                    d = round((1 - cur / avg) * 100)
                    if d < MIN_DESCUENTO or d > MAX_DESCUENTO: continue
                    if any(p in (dl.get("title") or "").lower() for p in EXCLUIR_TITULO): continue
                    cat = nombres.get(dl.get("rootCat"), "?")
                    cats_vistas[cod + " " + cat] = cats_vistas.get(cod + " " + cat, 0) + 1
                    if SOLO_CATEGORIAS and not any(c in cat.lower() for c in CATEGORIAS): continue
                    if (any(c in cat.lower() for c in CATEGORIAS_MARCA)
                            and not any(m in (dl.get("title") or "").lower() for m in MARCAS)): continue
                    asin = dl["asin"]; clave = f"{dom}:{asin}"
                    if clave in vistos and vistos[clave]["descuento"] >= d: continue
                    pref = "" if cod == "ES" else f"[{cod}] "
                    vistos[clave] = {"clave": clave, "asin": asin, "mercado": cod,
                        "titulo": pref + (dl.get("title") or "")[:105],
                        "precio": cur / 100, "antes": avg / 100, "descuento": d,
                        "error": d >= ERROR_PRECIO, "categoria": cat,
                        "url": f"https://{host}/dp/{asin}"}
                if len(dr) < 150: break
                time.sleep(1)
    if not ok:
        print("Keepa no respondio; se conserva la lista anterior"); sys.exit(1)
    print("categorias vistas:", cats_vistas)
    # stock: se consulta a Keepa solo en chollos nuevos (o vistos hace mas de RECHEQUEO_STOCK)
    prev_stock = {c.get("clave"): (c.get("stock"), c.get("stock_ts", 0)) for c in prev.get("chollos", [])}
    ahora = int(time.time())
    desc_prev = prev.get("descartados", {})   # chollos con poco stock: no se vuelven a consultar enseguida
    descartados = {k: t for k, t in desc_prev.items() if ahora - t < RECHEQUEO_STOCK}
    for clave in list(vistos):
        if clave in descartados: del vistos[clave]
    por_dom = {}
    for clave, x in vistos.items():
        if clave in prev_stock and ahora - prev_stock[clave][1] < RECHEQUEO_STOCK:
            x["stock"], x["stock_ts"] = prev_stock[clave]
        else:
            por_dom.setdefault(int(clave.split(":")[0]), []).append(x["asin"])
    for dom, asins in por_dom.items():
        stocks = consultar_stock(dom, asins)
        for a in asins:
            vistos[f"{dom}:{a}"]["stock"] = stocks.get(a)
            vistos[f"{dom}:{a}"]["stock_ts"] = ahora
    for clave in list(vistos):
        s = vistos[clave].get("stock")
        if s is None and not STOCK_DESCONOCIDO_AVISAR:
            del vistos[clave]
        elif s is not None and s < STOCK_MIN:
            print("descartado por poco stock:", clave, s)
            descartados[clave] = ahora
            del vistos[clave]
    lista = sorted(vistos.values(), key=lambda x: (not x["error"], -(x["antes"] - x["precio"])))
    for x in lista:
        if x["error"] and x["clave"] not in previos: avisar(x)
    firma = lambda l: [(c.get("clave", c["asin"]), c["precio"], c.get("stock")) for c in l]
    if (firma(lista) == firma(prev.get("chollos", [])) and set(descartados) == set(desc_prev)
            and time.time() - prev.get("ts", 0) < 3300):
        print(len(lista), "chollos (sin cambios, no se guarda)"); return
    json.dump({"actualizado": time.strftime("%d/%m/%Y %H:%M UTC", time.gmtime()), "ts": int(time.time()),
               "descartados": descartados, "chollos": lista}, open("deals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(lista), "chollos")

main()
