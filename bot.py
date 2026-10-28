import json, os, sys, time, requests

KEY = os.environ.get("KEEPA_KEY")
TOPIC = os.environ.get("NTFY_TOPIC")

DOMINIO = 9                  # 9 = amazon.es
TIPOS_PRECIO = [0, 1]        # 0 = vendido por Amazon, 1 = nuevo de otros vendedores
PAGINAS = 2                  # 150 ofertas por pagina
MIN_DESCUENTO = 50           # % minimo para aparecer en la lista
ERROR_PRECIO = 70            # % desde el que se marca como posible error de precio
PRECIO_MIN, PRECIO_MAX = 2000, 600000   # en centimos: de 20 EUR a 6.000 EUR
PRECIO_ANTES_MIN = 3000      # ignora productos cuyo precio normal sea menor de 30 EUR
SOLO_CATEGORIAS = True       # pon False para vigilar todas las categorias
CATEGORIAS = ["electr", "inform", "hogar", "cocina", "videojuego", "foto",
              "camara", "c\u00e1mara", "electrodom", "bricolaje"]

NIVEL = 0   # consulta usada: 0 = completa, 1 = intermedia, 2 = minima

def consulta(tipo, pag, nivel):
    base = {"page": pag, "domainId": DOMINIO, "priceTypes": [tipo], "dateRange": 0}
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
    return base

def pedir(tipo, pag):
    global NIVEL
    while NIVEL <= 2:
        try:
            r = requests.post("https://api.keepa.com/deal", params={"key": KEY},
                              json=consulta(tipo, pag, NIVEL), timeout=60)
        except Exception as e:
            print("Aviso red", e); return None
        if r.status_code == 400 and NIVEL < 2:
            print("Consulta nivel", NIVEL, "rechazada (400); pruebo una mas sencilla")
            NIVEL += 1
            continue
        if r.status_code != 200:
            print("Aviso Keepa", tipo, pag, r.status_code, r.text[:300]); return None
        d = r.json()
        print("nivel", NIVEL, "| tokens restantes:", d.get("tokensLeft"))
        return d.get("deals") or {}
    return None

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
    if not KEY:
        print("Falta el secreto KEEPA_KEY"); sys.exit(1)
    previos = set()
    if os.path.exists("deals.json"):
        previos = {c["asin"] for c in json.load(open("deals.json", encoding="utf-8")).get("chollos", [])}
    vistos, cats_vistas, ok = {}, {}, False
    for tipo in TIPOS_PRECIO:
        for pag in range(PAGINAS):
            deals = pedir(tipo, pag)
            if deals is None: break
            ok = True
            nombres = dict(zip(deals.get("categoryIds", []), deals.get("categoryNames", [])))
            dr = deals.get("dr", [])
            for dl in dr:
                try:
                    cur, avg = dl["current"][tipo], dl["avg"][0][tipo]
                except (KeyError, IndexError, TypeError):
                    continue
                if cur < PRECIO_MIN or cur > PRECIO_MAX or avg < PRECIO_ANTES_MIN or cur >= avg: continue
                d = round((1 - cur / avg) * 100)
                if d < MIN_DESCUENTO: continue
                cat = nombres.get(dl.get("rootCat"), "?")
                cats_vistas[cat] = cats_vistas.get(cat, 0) + 1
                if SOLO_CATEGORIAS and not any(c in cat.lower() for c in CATEGORIAS): continue
                asin = dl["asin"]
                if asin in vistos and vistos[asin]["descuento"] >= d: continue
                vistos[asin] = {"asin": asin, "titulo": (dl.get("title") or "")[:110],
                    "precio": cur / 100, "antes": avg / 100, "descuento": d,
                    "error": d >= ERROR_PRECIO, "categoria": cat,
                    "url": f"https://www.amazon.es/dp/{asin}"}
            if len(dr) < 150: break
            time.sleep(1)
    if not ok:
        print("Keepa no respondio; se conserva la lista anterior"); sys.exit(1)
    print("categorias vistas:", cats_vistas)
    lista = sorted(vistos.values(), key=lambda x: (not x["error"], -x["descuento"]))
    for x in lista:
        if x["error"] and x["asin"] not in previos: avisar(x)
    json.dump({"actualizado": time.strftime("%d/%m/%Y %H:%M UTC", time.gmtime()), "chollos": lista},
              open("deals.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(lista), "chollos")

main()
