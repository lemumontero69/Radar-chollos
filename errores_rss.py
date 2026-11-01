import html, json, os, re, sys, time
import xml.etree.ElementTree as ET
import requests

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID")
TOPIC = os.environ.get("NTFY_TOPIC")
PO_TOKEN = os.environ.get("PUSHOVER_TOKEN")
PO_USER = os.environ.get("PUSHOVER_USER")

FUENTES = {   # comunidades de chollos que publican RSS; el bot SOLO avisa de errores de precio
    "Chollometro": ["https://www.chollometro.com/rss/nuevos", "https://www.chollometro.com/rss"],
    "Dealabs": ["https://www.dealabs.com/rss"],
    "MyDealz": ["https://www.mydealz.de/rss"],
    "HotUKDeals": ["https://www.hotukdeals.com/rss"],
}
PALABRAS = [   # frases que usa la gente cuando encuentra un error de precio
    "error de precio", "error precio", "error en el precio", "error en precio", "fallo de precio",
    "fallo en el precio", "precio erroneo", "precio equivocado", "error de tienda", "bug de precio",
    "bug precio", "error de etiquetado",
    "erreur de prix", "erreur prix", "erreur de tarif", "bug de prix", "bug prix", "erreur tarifaire",
    "preisfehler", "preis-fehler", "preis fehler", "fehlerpreis", "preisbug", "preis bug",
    "price error", "pricing error", "price mistake", "price glitch", "pricing glitch"]
ARCHIVO = "rss_vistos.json"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"}

def limpio(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("è", "e"),
                 ("ê", "e"), ("à", "a"), ("ü", "u"), ("ä", "a"), ("ö", "o")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)

def leer(url):
    r = requests.get(url, headers=HEAD, timeout=25)
    r.raise_for_status()
    items = []
    try:
        root = ET.fromstring(r.content)
        for it in root.iter("item"):
            d = {}
            for ch in it:
                tag = ch.tag.split("}")[-1]
                if tag == "merchant":
                    d["tienda"] = ch.attrib.get("name", "")
                    d["precio"] = ch.attrib.get("price", "")
                else:
                    d.setdefault(tag, (ch.text or "").strip())
            items.append(d)
    except ET.ParseError:   # plan B: leer a mano si el XML trae algo raro
        for bloque in re.findall(r"<item[ >].*?</item>", r.text, flags=re.S):
            g = lambda t: (re.search(rf"<{t}[^>]*>(.*?)</{t}>", bloque, flags=re.S) or [None, ""])[1]
            items.append({k: re.sub(r"<!\[CDATA\[|\]\]>", "", g(k)).strip()
                          for k in ("title", "link", "guid", "description")})
    return items

def avisar(fuente, titulo, enlace, extra=""):
    texto = f"{titulo}\n{extra}".strip()
    cab = f"Posible error de precio ({fuente})"
    if TG_TOKEN and TG_CHAT:
        try:
            r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={
                "chat_id": TG_CHAT, "text": f"\U0001F6A8 {cab}\n{texto}\n{enlace}",
                "reply_markup": {"inline_keyboard": [[{"text": "Abrir chollo", "url": enlace}]]}}, timeout=15)
            if r.status_code != 200:
                print("telegram fallo", r.status_code, r.text[:200])
        except Exception as e:
            print("telegram fallo", e)
    if TOPIC:
        try:
            requests.post(f"https://ntfy.sh/{TOPIC}", data=texto.encode("utf-8"),
                          headers={"Title": cab, "Click": enlace, "Priority": "urgent",
                                   "Tags": "rotating_light"}, timeout=15)
        except Exception as e:
            print("ntfy fallo", e)
    if PO_TOKEN and PO_USER:
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": PO_TOKEN, "user": PO_USER, "title": cab, "message": texto, "url": enlace,
                "url_title": "Abrir chollo", "priority": 2, "retry": 60, "expire": 1800,
                "sound": "siren"}, timeout=15)
        except Exception as e:
            print("pushover fallo", e)

def main():
    if "--prueba" in sys.argv:
        avisar("PRUEBA", "Mensaje de prueba del detector de errores de precio",
               "https://www.chollometro.com")
        print("prueba enviada")
    primera = not os.path.exists(ARCHIVO)
    vistos = {}
    if not primera:
        try:
            vistos = json.load(open(ARCHIVO, encoding="utf-8")).get("ids", {})
        except Exception:
            vistos = {}
    ahora = int(time.time())
    vistos = {k: t for k, t in vistos.items() if ahora - t < 14 * 86400}
    nuevos, fallos, total = 0, 0, 0
    for fuente, urls in FUENTES.items():
        hechos = set()
        for url in urls:
            try:
                items = leer(url)
            except Exception as e:
                print(f"[{fuente}] fallo {url}: {str(e)[:100]}"); fallos += 1; continue
            total += 1
            coinc = 0
            for d in items:
                texto = limpio((d.get("title") or "") + " " + (d.get("description") or ""))
                if not any(p in texto for p in PALABRAS):
                    continue
                clave = d.get("guid") or d.get("link") or d.get("title")
                if not clave or clave in hechos:
                    continue
                hechos.add(clave); coinc += 1
                if clave in vistos:
                    continue
                vistos[clave] = ahora
                if primera:
                    continue   # primera vez: se anota sin avisar para no mandarte un aluvion
                nuevos += 1
                extra = " | ".join(x for x in (d.get("tienda"), d.get("precio")) if x)
                avisar(fuente, (d.get("title") or "")[:200], d.get("link") or clave, extra)
            print(f"[{fuente}] {url} items={len(items)} errores_de_precio={coinc}")
    if total == 0:
        print("Ninguna fuente respondio"); sys.exit(1)
    json.dump({"ids": vistos}, open(ARCHIVO, "w", encoding="utf-8"), indent=1)
    print("primera vez, anotados sin avisar" if primera else f"avisos nuevos: {nuevos}")

main()
