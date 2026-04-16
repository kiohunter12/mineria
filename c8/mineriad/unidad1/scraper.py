"""
scraper.py — Motor principal de extracción para WebScraper Pro
Funciona con CUALQUIER URL: noticias, videos, tablas, documentos, imágenes.
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os, re, time, zipfile, threading, uuid, json
from pathlib import Path
from datetime import datetime

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

TASKS        = {}   # exportaciones ZIP en background
PDF_TASKS    = {}   # compilaciones de noticias en PDF
DOC_ZIP_TASKS = {}  # ZIP de documentos en background

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

CATEGORIES = {
    "Regional":  ["regional","local","ciudad","municipio","provincia","barrio",
                  "comunidad","alcaldía","gobernación","canton","parroquia",
                  "loreto","lima","cusco","arequipa","iquitos","trujillo",
                  "piura","chiclayo","huancayo","puno","tacna"],
    "Educación": ["educación","escuela","universidad","estudiante","colegio",
                  "maestro","académico","educativo","profesor","clase",
                  "docente","alumno","instituto","beca","graduación","minedu"],
    "Salud":     ["salud","médico","hospital","enfermedad","vacuna","medicina",
                  "clínica","paciente","covid","virus","tratamiento","minsa",
                  "emergencia","cirugía","farmacia","epidemia","pandemia"],
    "Deporte":   ["deporte","fútbol","baloncesto","liga","torneo","atleta",
                  "campeonato","partido","equipo","gol","estadio","selección",
                  "olimpiada","maraton","natacion","ciclismo","voley"],
}

FILE_EXTENSIONS = [
    ".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",
    ".zip",".rar",".7z",".txt",".csv",".json",".xml",".geojson",
    ".mp4",".avi",".mkv",".mov",".mp3",".wav",".ogg",".m4a",".aac",
    ".epub",".kml",".shp",".dwg",".sql",
]

EMBED_PLATFORMS = [
    ("youtube",    [r"youtube\.com/embed/", r"youtu\.be/"]),
    ("vimeo",      [r"vimeo\.com/video/", r"player\.vimeo\.com"]),
    ("twitter",    [r"platform\.twitter\.com", r"twitframe\.com", r"x\.com/", r"twitter\.com/widgets"]),
    ("instagram",  [r"instagram\.com/embed", r"instagram\.com/p/"]),
    ("tiktok",     [r"tiktok\.com/embed", r"vm\.tiktok\.com"]),
    ("facebook",   [r"facebook\.com/plugins", r"fb\.com/"]),
    ("maps",       [r"maps\.google\.com", r"google\.com/maps/embed"]),
    ("spotify",    [r"open\.spotify\.com/embed"]),
    ("dailymotion",[r"dailymotion\.com/embed"]),
    ("twitch",     [r"player\.twitch\.tv"]),
    ("soundcloud", [r"w\.soundcloud\.com/player"]),
]

PAGE_TYPE_SIGNALS = {
    "Noticias":  ["article","noticia","news","redaccion","editorial","breaking",
                  "headline","periodico","diario","reportaje","journalist"],
    "Blog":      ["blog","post","author","entry","permalink","comments",
                  "disqus","wordpress","blogger","tag"],
    "Gobierno":  ["gob.pe","gob.ar","gov.","ministerio","gobierno","municipalidad",
                  "alcaldia","decreto","resolucion","transparencia","licitacion"],
    "Académico": ["universidad","repositorio","doi.org","scholar","investigacion",
                  "tesis","facultad","academic","scielo","redalyc","journal","paper"],
    "Wiki":      ["wiki","wikipedia","fandom","mediawiki","editar","historial","discusion"],
    "Comercio":  ["tienda","shop","store","carrito","comprar","precio","producto",
                  "checkout","cart","oferta","descuento","envio gratis","amazon"],
    "Red Social":["facebook","twitter","instagram","tiktok","reddit","linkedin",
                  "perfil","seguir","timeline","like","repost"],
    "Portal":    ["portal","inicio","bienvenido","directorio","categorias","secciones"],
}

SKIP_IMG = ["icon","logo","pixel","tracking","1x1","spacer",
            "blank","transparent","sprite","avatar","badge","button"]

# Señales de que la página está renderizada por JavaScript
JS_SIGNALS = [
    "__NEXT_DATA__","__NUXT__","ng-version","data-reactroot",
    "window.__INITIAL_STATE__","ember-application",
    "gatsby-focus-wrapper","svelte","_app","__vue"
]


# ─────────────────────────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────────────────────────

def categorize_text(text):
    if not text:
        return "Otros"
    tl = text.lower()
    for cat, kws in CATEGORIES.items():
        if any(kw in tl for kw in kws):
            return cat
    return "Otros"


def abs_url(base, url):
    if not url: return None
    url = url.strip()
    if url.startswith(("data:","javascript:","#","mailto:")): return None
    if url.startswith("//"): return "https:" + url
    return urljoin(base, url)


def best_img(tag, base):
    if not tag: return None
    img = tag.find("img")
    if not img: return None
    src = (img.get("src") or img.get("data-src") or
           img.get("data-lazy-src") or img.get("data-original") or
           img.get("data-lazysrc") or img.get("data-srcset","").split()[0])
    return abs_url(base, src)


def yt_id(url):
    for p in [r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
              r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
              r"youtu\.be/([a-zA-Z0-9_-]{11})"]:
        m = re.search(p, url)
        if m: return m.group(1)
    return None


def is_js_page(html):
    """Detecta si la página devolvió HTML vacío / solo shell JS."""
    if not html or len(html) < 2000:
        return True
    # Señales fuertes de SPA sin contenido
    for sig in JS_SIGNALS:
        if sig in html:
            return True
    soup = BeautifulSoup(html[:80000], "lxml")
    body = soup.body
    if not body:
        return True
    body_text = body.get_text(separator=" ", strip=True)
    # Texto muy corto Y pocas etiquetas de contenido = SPA shell
    content_tags = len(body.find_all(["article","p","h1","h2","h3","li","td"]))
    return len(body_text) < 300 and content_tags < 5


# ─────────────────────────────────────────────────────────────────
#  EXTRACTORES
# ─────────────────────────────────────────────────────────────────

def extract_news(soup, base):
    news, seen = [], set()

    # Estrategia 1 — etiquetas <article>
    for art in soup.find_all("article", limit=25):
        h = art.find(["h1","h2","h3","h4"])
        a = art.find("a", href=True)
        title = h.get_text(strip=True) if h else ""
        if not title or len(title) < 8 or title in seen: continue
        link = abs_url(base, a["href"]) if a else base
        seen.add(title)
        news.append({"title": title, "link": link or base,
                     "image": best_img(art, base),
                     "category": categorize_text(title)})

    # Estrategia 2 — h2/h3 con enlace
    if len(news) < 8:
        for tag in ["h2","h3"]:
            for h in soup.find_all(tag, limit=40):
                title = h.get_text(strip=True)
                if not title or len(title) < 10 or title in seen: continue
                a = h.find("a", href=True) or h.find_parent("a", href=True)
                link = abs_url(base, a["href"]) if a and a.get("href") else base
                parent = h.find_parent(["div","li","section","figure"])
                image = best_img(parent, base) if parent else None
                seen.add(title)
                news.append({"title": title, "link": link or base,
                             "image": image, "category": categorize_text(title)})

    # Estrategia 3 — contenedores con clase tipo "card","item","entry","post"
    if len(news) < 8:
        card_re = re.compile(r"\b(card|item|entry|post|story|news|article|noticia)\b", re.I)
        for div in soup.find_all(["div","li"], class_=card_re, limit=30):
            h = div.find(["h1","h2","h3","h4","a"])
            if not h: continue
            title = h.get_text(strip=True)
            if not title or len(title) < 10 or title in seen: continue
            a = div.find("a", href=True)
            link = abs_url(base, a["href"]) if a and a.get("href") else base
            seen.add(title)
            news.append({"title": title, "link": link or base,
                         "image": best_img(div, base),
                         "category": categorize_text(title)})

    # Estrategia 4 — <li> con links largos (menús de noticias)
    if len(news) < 6:
        for li in soup.find_all("li", limit=50):
            a = li.find("a", href=True)
            if not a: continue
            title = a.get_text(strip=True)
            if not title or len(title) < 15 or title in seen: continue
            link = abs_url(base, a["href"]) or base
            seen.add(title)
            news.append({"title": title, "link": link,
                         "image": best_img(li, base),
                         "category": categorize_text(title)})

    return news[:30]


def extract_videos(soup, base):
    videos, seen = [], set()

    # iframes (YouTube, Vimeo, etc.)
    for ifr in soup.find_all("iframe"):
        src = (ifr.get("src") or ifr.get("data-src") or "").strip()
        if not src: continue
        full = abs_url(base, src) or src
        sl = full.lower()
        if full in seen: continue
        seen.add(full)

        if "youtube" in sl or "youtu.be" in sl:
            vid = yt_id(full)
            embed = f"https://www.youtube.com/embed/{vid}" if vid else full
            thumb = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None
            videos.append({"type":"youtube","embed":embed,
                           "thumbnail":thumb,"title":ifr.get("title","Video YouTube")})
        elif "vimeo" in sl:
            videos.append({"type":"vimeo","embed":full,
                           "thumbnail":None,"title":ifr.get("title","Video Vimeo")})
        elif any(x in sl for x in [".mp4",".webm","player","video","dailymotion","twitch"]):
            videos.append({"type":"iframe","embed":full,
                           "thumbnail":None,"title":ifr.get("title","Video")})

    # <video> HTML5
    for vid in soup.find_all("video"):
        src = vid.get("src","")
        if not src:
            s = vid.find("source")
            src = s.get("src","") if s else ""
        if src and src not in seen:
            fu = abs_url(base, src)
            if fu:
                seen.add(fu)
                poster = abs_url(base, vid.get("poster",""))
                videos.append({"type":"html5","embed":fu,
                               "thumbnail":poster,"title":vid.get("title","Video")})

    # Links directos a videos
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(ext in href for ext in [".mp4",".webm",".avi",".mov"]):
            fu = abs_url(base, a["href"])
            if fu and fu not in seen:
                seen.add(fu)
                videos.append({"type":"direct","embed":fu,
                               "thumbnail":None,"title":a.get_text(strip=True) or "Video"})

    return videos[:20]


def extract_tables(soup):
    tables = []
    for i, tbl in enumerate(soup.find_all("table", limit=20)):
        rows = tbl.find_all("tr")
        if len(rows) < 2: continue

        # Headers
        thead = tbl.find("thead")
        if thead:
            fr = thead.find("tr")
            headers = [c.get_text(strip=True) for c in fr.find_all(["th","td"])] if fr else []
        else:
            headers = [c.get_text(strip=True) for c in rows[0].find_all(["th","td"])]

        # Filas
        start = 1 if headers else 0
        data_rows = []
        for tr in rows[start:]:
            row = [c.get_text(strip=True) for c in tr.find_all(["td","th"])]
            if row and any(c for c in row):
                data_rows.append(row)

        if not data_rows: continue

        caption = tbl.find("caption")
        title = caption.get_text(strip=True) if caption else f"Tabla {i+1}"
        tables.append({"id":i,"title":title,"headers":headers,
                       "rows":data_rows[:200],"total_rows":len(data_rows)})

    return tables


def extract_files(soup, base):
    files, seen = [], set()
    for a in soup.find_all("a", href=True):
        fu = abs_url(base, a["href"])
        if not fu or fu in seen: continue
        path_l = urlparse(fu).path.lower()
        ext = next((e for e in FILE_EXTENSIONS if path_l.endswith(e)), None)
        if ext:
            seen.add(fu)
            name = a.get_text(strip=True) or os.path.basename(urlparse(fu).path) or "Archivo"
            fname = os.path.basename(urlparse(fu).path) or f"archivo{ext}"
            files.append({"name":name[:120],"url":fu,
                          "type":ext[1:].upper(),"filename":fname,"size":None})
    return files[:200]


def _best_from_srcset(srcset_str):
    """Del valor srcset elige la URL de mayor resolución (último candidato por ancho)."""
    if not srcset_str:
        return ""
    candidates = []
    for part in srcset_str.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if tokens:
            url = tokens[0]
            # descriptor puede ser "800w" o "2x"; extraer número
            w = 0
            if len(tokens) > 1:
                desc = tokens[1].lower()
                try:
                    w = float(re.sub(r"[^\d.]", "", desc))
                    if desc.endswith("x"):
                        w *= 1000   # convertir densidad a "pseudo-ancho"
                except ValueError:
                    pass
            candidates.append((w, url))
    if not candidates:
        return ""
    # elegir la de mayor ancho/densidad
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# Todos los atributos lazy-load conocidos (orden de preferencia)
IMG_SRC_ATTRS = [
    "src", "data-src", "data-lazy-src", "data-original",
    "data-img-src", "data-image", "data-lazy", "data-echo",
    "data-srcset", "srcset", "data-src-desktop", "data-src-mobile",
    "data-hi-res-src", "data-retina-src", "data-full-src",
    "data-bg", "data-background", "data-cover",
    "data-thumb", "data-photo",
]


def extract_images_from_raw(html, base):
    """Extrae URLs de imagen del HTML crudo (captura URLs en JS inline, JSON, etc.)."""
    images, seen = [], set()
    pattern = re.compile(
        r'https?://[^\s"\'<>{}\[\]\\]+?'
        r'\.(?:jpg|jpeg|png|webp|gif|bmp|tiff|avif|svg)'
        r'(?:\?[^\s"\'<>]*)?',
        re.IGNORECASE
    )
    for url in pattern.findall(html):
        url = url.rstrip(".,);'\"")
        if url in seen:
            continue
        fu = abs_url(base, url) or url
        fu_lower = fu.lower()
        if any(p in fu_lower for p in SKIP_IMG):
            continue
        fname = os.path.basename(urlparse(fu).path) or "imagen.jpg"
        seen.add(url)
        images.append({"url": fu, "alt": "", "filename": fname, "source": "raw-html"})
    return images, seen


def extract_images(soup, base):
    """Extrae TODAS las imágenes: <img>, <picture><source>, srcset completo, lazy-load."""
    images, seen = [], set()

    def add_img(url_raw, alt="", source="img"):
        if not url_raw:
            return
        fu = abs_url(base, url_raw.strip())
        if not fu or fu in seen:
            return
        fu_lower = fu.lower()
        if any(p in fu_lower for p in SKIP_IMG):
            return
        # Ignorar GIFs de 1px y SVGs de UI
        path = urlparse(fu).path.lower()
        if path.endswith(".gif") and any(x in fu_lower for x in ["tracker","pixel","beacon"]):
            return
        ext = os.path.splitext(path)[1]
        if not ext:
            ext = ".jpg"
        fname = os.path.basename(path) or f"imagen{ext}"
        seen.add(fu)
        images.append({"url": fu, "alt": alt.strip(), "filename": fname, "source": source})

    # ── 1. Etiquetas <img> con todos los atributos posibles ──
    for img in soup.find_all("img"):
        alt = img.get("alt", "")
        chosen = None
        # Intentar srcset primero (mejor calidad)
        for attr in ("srcset", "data-srcset"):
            val = img.get(attr, "").strip()
            if val:
                chosen = _best_from_srcset(val)
                break
        # Luego atributos simples
        if not chosen:
            for attr in IMG_SRC_ATTRS:
                if attr in ("srcset", "data-srcset"):
                    continue
                val = img.get(attr, "").strip()
                if val and not val.startswith("data:"):
                    chosen = val
                    break
        add_img(chosen, alt, "img")

    # ── 2. <picture><source srcset> ──
    for picture in soup.find_all("picture"):
        alt = ""
        img_tag = picture.find("img")
        if img_tag:
            alt = img_tag.get("alt", "")
        for source in picture.find_all("source"):
            for attr in ("srcset", "data-srcset"):
                val = source.get(attr, "").strip()
                if val:
                    best = _best_from_srcset(val)
                    if best:
                        add_img(best, alt, "picture")
                    break

    # ── 3. Atributos style con background-image ──
    for tag in soup.find_all(style=True):
        m = re.search(r'background(?:-image)?\s*:\s*url\(["\']?([^"\')\s]+)["\']?\)', tag["style"])
        if m:
            add_img(m.group(1), tag.get("alt",""), "bg-style")

    # ── 4. data-bg / data-background en cualquier elemento ──
    for tag in soup.find_all(attrs={"data-bg": True}):
        add_img(tag["data-bg"], "", "data-bg")
    for tag in soup.find_all(attrs={"data-background": True}):
        add_img(tag["data-background"], "", "data-background")

    # ── 5. Open Graph image (si no está ya) ──
    for meta in soup.find_all("meta", attrs={"property": re.compile(r"og:image", re.I)}):
        add_img(meta.get("content",""), "og:image", "og")
    for meta in soup.find_all("meta", attrs={"name": re.compile(r"twitter:image", re.I)}):
        add_img(meta.get("content",""), "twitter:image", "og")

    return images   # SIN límite — devolver todas


# ─────────────────────────────────────────────────────────────────
#  CAPAS DE FETCH — del más ligero al más potente
# ─────────────────────────────────────────────────────────────────

# UA pool para rotación
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

def _random_ua():
    try:
        from fake_useragent import UserAgent
        return UserAgent().chrome
    except Exception:
        import random
        return random.choice(_UA_POOL)

def _build_headers(url=""):
    """Cabeceras completas tipo navegador real."""
    ua = _random_ua()
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
    h = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }
    if origin:
        h["Referer"] = origin + "/"
    return h


# ── Tier 1: requests estándar con headers robustos ────────────────
def _fetch_requests(url):
    sess = requests.Session()
    sess.headers.update(_build_headers(url))
    resp = sess.get(url, timeout=20, allow_redirects=True)
    resp.raise_for_status()
    return resp.text, resp.url


# ── Tier 2: curl_cffi — TLS fingerprint como Chrome real ─────────
def _fetch_curl(url):
    from curl_cffi import requests as creq
    resp = creq.get(
        url, impersonate="chrome124",
        headers=_build_headers(url),
        timeout=25, allow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text, resp.url


# ── Tier 3: cloudscraper — bypass Cloudflare JS Challenge ─────────
def _fetch_cloudscraper(url):
    import cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    scraper.headers.update(_build_headers(url))
    resp = scraper.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    return resp.text, resp.url


# ── Tier 4: Reddit API JSON ───────────────────────────────────────
def _is_reddit(url):
    return re.search(r"(reddit\.com|redd\.it)", url, re.I)

def _fetch_reddit(url):
    """Usa la API JSON de Reddit para extraer posts."""
    parsed = urlparse(url)
    # Normalizar: extraer solo el host reddit.com y el path
    path = parsed.path.rstrip("/") or ""
    # Construir JSON endpoint: https://www.reddit.com/<path>.json
    if path:
        json_url = f"https://www.reddit.com{path}.json?limit=50&raw_json=1"
    else:
        json_url = "https://www.reddit.com/.json?limit=50&raw_json=1"
    headers = {**_build_headers(url), "Accept": "application/json"}
    resp = requests.get(json_url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json(), json_url

def _reddit_json_to_html(data, base_url):
    """Convierte la respuesta JSON de Reddit a HTML parseable."""
    try:
        # Puede ser lista [listing, comments] o un solo listing
        listing = data[0] if isinstance(data, list) else data
        posts = listing.get("data", {}).get("children", [])
        parts = [f'<html><head><title>Reddit</title></head><body>']
        for child in posts:
            d = child.get("data", {})
            title   = d.get("title", "")
            link    = d.get("url", "")
            selfurl = f"https://www.reddit.com{d.get('permalink','')}"
            thumb   = d.get("thumbnail", "")
            score   = d.get("score", 0)
            sub     = d.get("subreddit_name_prefixed", "")
            preview_img = ""
            try:
                preview_img = d["preview"]["images"][0]["source"]["url"].replace("&amp;","&")
            except Exception:
                pass
            img_tag = f'<img src="{preview_img or thumb}" />' if (preview_img or thumb) not in ("self","default","","nsfw") else ""
            parts.append(
                f'<article>'
                f'{img_tag}'
                f'<h2><a href="{selfurl}">{title}</a></h2>'
                f'<p class="reddit-meta">{sub} · {score} pts</p>'
                f'</article>'
            )
        parts.append("</body></html>")
        return "\n".join(parts), base_url
    except Exception as e:
        return f"<html><body><p>Error parsing Reddit JSON: {e}</p></body></html>", base_url


# ── Tier 5: undetected-chromedriver (stealth headless) ────────────
def _fetch_undetected(url, headless=True, wait=8):
    try:
        import undetected_chromedriver as uc
        opts = uc.ChromeOptions()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument(f"--user-agent={_random_ua()}")
        if headless:
            opts.add_argument("--headless=new")
        drv = uc.Chrome(options=opts, use_subprocess=True)
        drv.set_page_load_timeout(45)
        try:
            drv.get(url)
            time.sleep(wait)
            # scroll para activar lazy-load
            drv.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(2)
            drv.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            html = drv.page_source
            final = drv.current_url
        finally:
            try: drv.quit()
            except Exception: pass
        return html, final, None
    except ImportError:
        return None, url, "undetected-chromedriver no disponible."
    except Exception as e:
        return None, url, f"[uc] {e}"


# ── Tier 6: Selenium estándar con máximo stealth ──────────────────
def _fetch_selenium(url, headless=True, wait=7):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager

        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--window-size=1280,900")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(f"--user-agent={_random_ua()}")

        drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        drv.set_page_load_timeout(45)
        drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": (
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
                "Object.defineProperty(navigator,'languages',{get:()=>['es-ES','es','en']});"
            )
        })
        try:
            drv.get(url)
            time.sleep(wait)
            if not headless:
                print("[Selenium] Resuelve el CAPTCHA si aparece...")
                time.sleep(15)
            drv.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(2)
            html      = drv.page_source
            final_url = drv.current_url
        finally:
            try: drv.quit()
            except Exception: pass
        return html, final_url, None
    except ImportError:
        return None, url, "Selenium no instalado."
    except Exception as e:
        return None, url, str(e)


# ── Legado — nombre que ya usan otros módulos ─────────────────────
def scrape_with_browser(url, headless=True, wait=7):
    html, final, err = _fetch_undetected(url, headless=headless, wait=wait)
    if html and len(html) > 500:
        return html, final, err
    return _fetch_selenium(url, headless=headless, wait=wait)


# ─────────────────────────────────────────────────────────────────
#  ARTÍCULO COMPLETO → PDF
# ─────────────────────────────────────────────────────────────────

def scrape_full_article(url):
    try:
        try:
            import trafilatura
            dl = trafilatura.fetch_url(url)
            if dl:
                txt = trafilatura.extract(dl, include_comments=False,
                                          include_tables=True, favor_recall=True)
                if txt and len(txt) > 200:
                    return txt
        except Exception:
            pass

        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup.find_all(["script","style","nav","footer","header","aside","form"]):
            tag.decompose()
        content = (soup.find("article") or
                   soup.find(class_=re.compile(r"(article|content|post|entry|body|nota)", re.I)) or
                   soup.find("main") or soup.find("body"))
        if content:
            paras = content.find_all(["p","h1","h2","h3","h4","li"])
            txt = "\n\n".join(p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 20)
            if txt:
                return txt
        return "No se pudo extraer el contenido del artículo."
    except Exception as e:
        return f"Error: {e}"


def article_to_pdf(title, content, url, filename):
    try:
        from fpdf import FPDF

        class PDF(FPDF):
            def footer(self):
                self.set_y(-12)
                self.set_font("Helvetica","I",8)
                self.set_text_color(150,150,150)
                self.cell(0,10,f"Pagina {self.page_no()} | WebScraper Pro",align="C")

        pdf = PDF()
        pdf.set_margins(20,20,20)
        pdf.add_page()
        pdf.set_auto_page_break(True, 20)

        # Título
        pdf.set_font("Helvetica","B",17)
        pdf.set_text_color(30,58,138)
        t = (title or "Articulo").encode("latin-1","replace").decode("latin-1")
        pdf.multi_cell(0, 9, t)
        pdf.ln(3)

        # Fuente
        pdf.set_font("Helvetica","",9)
        pdf.set_text_color(100,116,139)
        pdf.multi_cell(0, 5, f"Fuente: {url.encode('latin-1','replace').decode('latin-1')}")
        pdf.ln(4)

        pdf.set_draw_color(200,210,230)
        pdf.set_line_width(0.5)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(5)

        pdf.set_font("Helvetica","",11)
        pdf.set_text_color(30,41,59)
        for para in content.split("\n"):
            para = para.strip()
            if not para: continue
            p = para.encode("latin-1","replace").decode("latin-1")
            if len(para) < 80 and para.isupper():
                pdf.set_font("Helvetica","B",12)
                pdf.set_text_color(30,58,138)
                pdf.multi_cell(0,7,p)
                pdf.set_font("Helvetica","",11)
                pdf.set_text_color(30,41,59)
            else:
                pdf.multi_cell(0,7,p)
            pdf.ln(2)

        safe = re.sub(r"[^\w\-_]","_", filename)
        if not safe.endswith(".pdf"): safe += ".pdf"
        fp = DOWNLOAD_DIR / safe
        pdf.output(str(fp))
        return str(fp), safe
    except Exception as e:
        return None, f"Error al generar PDF: {e}"


# ─────────────────────────────────────────────────────────────────
#  NUEVOS EXTRACTORES — análisis profundo
# ─────────────────────────────────────────────────────────────────

def extract_metadata(soup, base_url):
    """Extrae metadatos Open Graph, Twitter Cards, JSON-LD y meta tags."""
    def og(prop):
        t = soup.find("meta", attrs={"property": prop})
        return t["content"].strip() if t and t.get("content") else None

    def meta_name(name):
        t = soup.find("meta", attrs={"name": name})
        return t["content"].strip() if t and t.get("content") else None

    title       = og("og:title") or (soup.find("title").get_text(strip=True) if soup.find("title") else None)
    og_image    = og("og:image")
    og_type     = og("og:type")
    site_name   = og("og:site_name")
    description = og("og:description") or meta_name("description")
    author      = og("article:author") or meta_name("author")
    keywords    = meta_name("keywords")

    if not og_image:
        t = soup.find("meta", attrs={"name": "twitter:image"})
        og_image = t["content"].strip() if t and t.get("content") else None
    if not author:
        t = soup.find("meta", attrs={"name": "twitter:creator"})
        author = t["content"].strip() if t and t.get("content") else None

    # Fecha publicación: <time>, article:published_time, JSON-LD
    published_date = None
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        published_date = time_tag["datetime"][:10]
    if not published_date:
        t = soup.find("meta", attrs={"property": "article:published_time"})
        if t and t.get("content"):
            published_date = t["content"][:10]
    if not published_date:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = script.string or ""
                d   = json.loads(raw)
                items = d if isinstance(d, list) else [d]
                for item in items:
                    if item.get("datePublished"):
                        published_date = item["datePublished"][:10]
                        if not author and item.get("author"):
                            a = item["author"]
                            author = a.get("name") if isinstance(a, dict) else str(a)
                        break
                if published_date:
                    break
            except Exception:
                pass

    language = ""
    html_tag = soup.find("html")
    if html_tag:
        language = html_tag.get("lang", "")

    if og_image:
        og_image = abs_url(base_url, og_image) or og_image

    return {
        "title": title, "description": description, "og_image": og_image,
        "og_type": og_type, "site_name": site_name, "author": author,
        "published_date": published_date, "keywords": keywords,
        "language": language,
    }


def extract_embeds(soup, base):
    """Detecta iframes de plataformas conocidas: YouTube, Vimeo, Twitter, etc."""
    embeds, seen = [], set()
    for ifr in soup.find_all("iframe"):
        src = (ifr.get("src") or ifr.get("data-src") or "").strip()
        if not src: continue
        full = abs_url(base, src) or src
        if full in seen: continue
        src_lower = full.lower()

        etype = None
        for name, patterns in EMBED_PLATFORMS:
            if any(re.search(p, src_lower) for p in patterns):
                etype = name
                break
        if not etype:
            continue
        seen.add(full)

        thumbnail = None
        if etype == "youtube":
            vid = yt_id(full)
            if vid:
                thumbnail = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                full = f"https://www.youtube.com/embed/{vid}"

        embeds.append({
            "type":      etype,
            "title":     ifr.get("title") or etype.capitalize(),
            "url":       full,
            "thumbnail": thumbnail,
        })
    return embeds[:20]


def extract_audio(soup, base):
    """Detecta audio HTML5, mp3/wav directos, RSS podcast y SoundCloud."""
    audio_list, seen = [], set()
    AUDIO_EXT = [".mp3",".ogg",".wav",".m4a",".aac",".flac"]

    for tag in soup.find_all("audio"):
        src = tag.get("src","")
        if not src:
            s = tag.find("source")
            src = s.get("src","") if s else ""
        if src:
            fu = abs_url(base, src)
            if fu and fu not in seen:
                seen.add(fu)
                audio_list.append({
                    "url": fu,
                    "title": tag.get("title") or os.path.basename(urlparse(fu).path) or "Audio",
                    "type": "html5",
                })

    for a in soup.find_all("a", href=True):
        href_l = a["href"].lower()
        if any(ext in href_l for ext in AUDIO_EXT):
            fu = abs_url(base, a["href"])
            if fu and fu not in seen:
                seen.add(fu)
                audio_list.append({
                    "url": fu,
                    "title": a.get_text(strip=True) or os.path.basename(urlparse(fu).path) or "Audio",
                    "type": "direct",
                })

    for link in soup.find_all("link"):
        ltype = link.get("type","")
        if re.search(r"rss|atom|podcast", ltype, re.I):
            href = link.get("href","")
            if href:
                fu = abs_url(base, href)
                if fu and fu not in seen:
                    seen.add(fu)
                    audio_list.append({
                        "url": fu,
                        "title": link.get("title","Feed RSS/Podcast"),
                        "type": "rss",
                    })

    return audio_list[:20]


def detect_page_type(html_str, base_url):
    """Clasifica el tipo de página usando señales del HTML y la URL."""
    sample = (html_str[:30000] + " " + base_url).lower()
    scores = {}
    for ptype, keywords in PAGE_TYPE_SIGNALS.items():
        scores[ptype] = sum(1 for kw in keywords if kw in sample)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Otro"


def extract_all_links(soup, base_url):
    """Inventario completo de enlaces: internos vs externos y top dominios."""
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower().replace("www.","")
    internal_count = 0
    external_count = 0
    domain_counts  = {}

    for a in soup.find_all("a", href=True):
        fu = abs_url(base_url, a["href"])
        if not fu: continue
        domain = urlparse(fu).netloc.lower().replace("www.","")
        if domain == base_domain or not domain:
            internal_count += 1
        else:
            external_count += 1
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

    top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "internal":    internal_count,
        "external":    external_count,
        "total":       internal_count + external_count,
        "top_domains": [{"domain": d, "count": c} for d, c in top_domains],
    }


# ─────────────────────────────────────────────────────────────────
#  FUNCIÓN PRINCIPAL — scrape_url
# ─────────────────────────────────────────────────────────────────

def scrape_url(url, use_browser=False, headless=True):
    """
    Estrategia de 6 capas:
      L1 → requests (headers robustos)
      L2 → curl_cffi (TLS fingerprint Chrome)
      L3 → cloudscraper (bypass Cloudflare)
      L4 → Reddit JSON API  (solo reddit.com)
      L5 → undetected-chromedriver (stealth headless)
      L6 → Selenium clásico como último recurso
    """
    html, final_url, browser_err = None, url, None
    fetch_method  = "requests"
    needs_js      = False
    site_specific = False   # si usamos handler especializado, no intentar capas genéricas

    # ── L0 especial: Reddit API JSON ──────────────────────────────
    if _is_reddit(url):
        try:
            rdata, final_url = _fetch_reddit(url)
            html, final_url  = _reddit_json_to_html(rdata, final_url)
            fetch_method     = "reddit-api"
            site_specific    = True
        except Exception as e:
            browser_err = f"Reddit API falló ({e}), intentando otras capas…"

    if not site_specific:
        # ── L1: requests con headers robustos ─────────────────────
        try:
            html, final_url = _fetch_requests(url)
            fetch_method = "requests"
        except requests.exceptions.ConnectionError:
            return {"error": "No se pudo conectar. Verifica la URL."}
        except requests.exceptions.Timeout:
            pass
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 404:
                return {"error": "Página no encontrada (404). Verifica la URL."}
        except Exception:
            pass

        # ── L2: curl_cffi — TLS fingerprint Chrome ────────────────
        if not html or is_js_page(html):
            try:
                html_c, url_c = _fetch_curl(url)
                if html_c and len(html_c) > (len(html) if html else 0):
                    html, final_url, fetch_method = html_c, url_c, "curl_cffi"
            except Exception:
                pass

        # ── L3: cloudscraper — Cloudflare JS Challenge ────────────
        if not html or is_js_page(html):
            try:
                html_cs, url_cs = _fetch_cloudscraper(url)
                if html_cs and len(html_cs) > (len(html) if html else 0):
                    html, final_url, fetch_method = html_cs, url_cs, "cloudscraper"
            except Exception:
                pass

        # ── L4/L5: browser (si el usuario lo pide O sigue siendo SPA) ──
        needs_js = not html or is_js_page(html)
        if use_browser or needs_js:
            html_b, url_b, err_b = _fetch_undetected(url, headless=headless, wait=8)
            if html_b and len(html_b) > (len(html) if html else 0):
                html, final_url, fetch_method = html_b, url_b, "undetected-chrome"
                browser_err = err_b
            if not html or (is_js_page(html) and not use_browser):
                # Último recurso: Selenium clásico
                html_b2, url_b2, err_b2 = _fetch_selenium(url, headless=headless, wait=7)
                if html_b2 and len(html_b2) > (len(html) if html else 0):
                    html, final_url, fetch_method = html_b2, url_b2, "selenium"
                    browser_err = err_b2

    if not html:
        return {"error": "No se pudo obtener el contenido de la página. "
                         "Activa el Modo Avanzado o verifica la URL."}

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # ── Extraer metadata y tipo ANTES de limpiar scripts (necesitan JSON-LD)
    metadata  = extract_metadata(soup, final_url)
    page_type = detect_page_type(html, final_url)
    embeds    = extract_embeds(soup, final_url)
    audio     = extract_audio(soup, final_url)
    all_links = extract_all_links(soup, final_url)

    # Limpiar scripts/styles para el resto de extractores
    for tag in soup.find_all(["script","style"]):
        tag.decompose()

    title_tag  = soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else (metadata.get("title") or "Sin título")

    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = (meta_desc["content"].strip()
                   if meta_desc and meta_desc.get("content")
                   else metadata.get("description") or "")

    news   = extract_news(soup, final_url)
    videos = extract_videos(soup, final_url)
    tables = extract_tables(soup)
    files  = extract_files(soup, final_url)

    # Imágenes: combinar extracción DOM + regex sobre HTML crudo
    images_dom  = extract_images(soup, final_url)
    images_raw, raw_seen = extract_images_from_raw(html, final_url)
    # Fusionar: las del DOM van primero (tienen alt text), las del raw agregan las que faltan
    dom_urls = {img["url"] for img in images_dom}
    for img in images_raw:
        if img["url"] not in dom_urls:
            images_dom.append(img)
    images = images_dom

    result = {
        "title":        page_title,
        "description":  description,
        "url":          final_url,
        "page_type":    page_type,
        "metadata":     metadata,
        "news":         news,
        "videos":       videos,
        "embeds":       embeds,
        "tables":       tables,
        "files":        files,
        "images":       images,
        "audio":        audio,
        "all_links":    all_links,
        "needed_js":    needs_js,
        "fetch_method": fetch_method,   # qué capa funcionó
        "stats": {
            "news_count":    len(news),
            "videos_count":  len(videos),
            "embeds_count":  len(embeds),
            "tables_count":  len(tables),
            "files_count":   len(files),
            "images_count":  len(images),
            "audio_count":   len(audio),
            "links_total":   all_links["total"],
        }
    }
    if browser_err:
        result["browser_warning"] = browser_err
    return result


# ─────────────────────────────────────────────────────────────────
#  DESCARGA DE ARCHIVOS
# ─────────────────────────────────────────────────────────────────

def download_file(file_url, filename):
    try:
        resp = requests.get(file_url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        safe = re.sub(r"[^\w\-_\.]","_", filename) or "archivo"
        fp = DOWNLOAD_DIR / safe
        with open(fp, "wb") as f:
            for chunk in resp.iter_content(8192):
                if chunk: f.write(chunk)
        return str(fp), safe
    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────────────────────────
#  EXPORTACIÓN TOTAL → ZIP (background)
# ─────────────────────────────────────────────────────────────────

def _safe(text, n=50):
    return re.sub(r"[^\w\s\-]","", text or "").strip().replace(" ","_")[:n] or "archivo"


def run_export_task(task_id, news, files, images, page_title):
    task = TASKS[task_id]
    try:
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        zip_name = f"export_{_safe(page_title,30)}_{date_str}.zip"
        zip_path = DOWNLOAD_DIR / zip_name

        news_lim  = min(len(news),   12)
        files_lim = min(len(files),  15)
        imgs_lim  = min(len(images), 25)
        total     = (news_lim + files_lim + imgs_lim) or 1
        done      = 0

        def upd(msg):
            task["msg"]      = msg
            task["progress"] = min(int(done / total * 95), 95)

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:

            # Noticias → PDFs
            for i, item in enumerate(news[:news_lim]):
                try:
                    upd(f"Artículo {i+1}/{news_lim}: {item['title'][:45]}...")
                    content = scrape_full_article(item["link"])
                    fname   = f"noticia_{i+1:02d}_{_safe(item['title'])}"
                    pp, pn  = article_to_pdf(item["title"], content, item["link"], fname)
                    if pp: zf.write(pp, f"noticias/{pn}")
                except Exception:
                    pass
                done += 1
                task["progress"] = min(int(done / total * 95), 95)

            # Documentos
            for i, f in enumerate(files[:files_lim]):
                try:
                    upd(f"Documento {i+1}/{files_lim}: {f['filename']}")
                    fp, fn = download_file(f["url"], f["filename"])
                    if fp: zf.write(fp, f"documentos/{fn}")
                except Exception:
                    pass
                done += 1
                task["progress"] = min(int(done / total * 95), 95)

            # Imágenes
            img_ok = 0
            for i, img in enumerate(images[:imgs_lim]):
                try:
                    upd(f"Imagen {i+1}/{imgs_lim}")
                    resp = requests.get(img["url"], headers=HEADERS, timeout=12, stream=True)
                    resp.raise_for_status()
                    ct = resp.headers.get("Content-Type","")
                    if not any(t in ct for t in ["image","jpeg","png","gif","webp"]):
                        done += 1; continue
                    ext  = os.path.splitext(urlparse(img["url"]).path)[1] or ".jpg"
                    fname = f"imagen_{img_ok+1:02d}{ext}"
                    zf.writestr(f"imagenes/{fname}", resp.content)
                    img_ok += 1
                except Exception:
                    pass
                done += 1
                task["progress"] = min(int(done / total * 95), 95)

            # Índice
            try:
                idx = [
                    f"EXPORTACIÓN: {page_title}",
                    f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                    "="*60,
                    f"\nNOTICIAS ({news_lim}):",
                ]
                for j, n in enumerate(news[:news_lim],1):
                    idx += [f"  {j:02d}. {n['title']}", f"      {n['link']}"]
                idx.append(f"\nDOCUMENTOS ({files_lim}):")
                for j, ff in enumerate(files[:files_lim],1):
                    idx += [f"  {j:02d}. {ff['name']} ({ff['type']})", f"      {ff['url']}"]
                idx.append(f"\nIMAGENES: {img_ok} descargadas")
                zf.writestr("INDICE.txt", "\n".join(idx))
            except Exception:
                pass

        task["progress"] = 100
        task["status"]   = "done"
        task["filename"] = zip_name
        task["msg"]      = f"¡ZIP listo! {news_lim} noticias · {files_lim} docs · {img_ok} imágenes"

    except Exception as e:
        task["status"] = "error"
        task["msg"]    = str(e)


def start_export(news, files, images, page_title):
    tid = uuid.uuid4().hex[:12]
    TASKS[tid] = {"progress":0,"status":"working",
                  "msg":"Iniciando exportación...","filename":None}
    threading.Thread(target=run_export_task,
                     args=(tid, news, files, images, page_title),
                     daemon=True).start()
    return tid


# ─────────────────────────────────────────────────────────────────
#  COMPILAR TODAS LAS NOTICIAS → UN SOLO PDF ORGANIZADO
# ─────────────────────────────────────────────────────────────────

def _enc(text):
    """Codifica texto a Latin-1 sin errores (reemplaza caracteres no soportados)."""
    return (text or "").encode("latin-1", "replace").decode("latin-1")


def run_compile_pdf_task(task_id, news_list, page_title):
    task = PDF_TASKS[task_id]
    try:
        from fpdf import FPDF

        date_str  = datetime.now().strftime("%Y%m%d_%H%M")
        pdf_name  = f"noticias_{_safe(page_title, 30)}_{date_str}.pdf"
        pdf_path  = DOWNLOAD_DIR / pdf_name
        total     = len(news_list) or 1

        _title = page_title  # closure

        class CompilePDF(FPDF):
            def header(self):
                if self.page_no() == 1:
                    return
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 8, _enc(_title)[:70], align="L")
                self.set_draw_color(220, 220, 220)
                self.set_line_width(0.3)
                self.line(15, self.get_y() + 2, 195, self.get_y() + 2)
                self.ln(5)

            def footer(self):
                self.set_y(-13)
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 8, f"Pagina {self.page_no()} | WebScraper Pro", align="C")

        pdf = CompilePDF()
        pdf.set_margins(15, 20, 15)
        pdf.set_auto_page_break(True, 18)

        # ── PORTADA ──
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 26)
        pdf.set_text_color(30, 58, 138)
        pdf.ln(18)
        pdf.multi_cell(0, 13, _enc(page_title), align="C")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 8, f"Recopilacion de {len(news_list)} noticias", align="C", ln=True)
        pdf.cell(0, 8, datetime.now().strftime("Generado el %d/%m/%Y a las %H:%M"),
                 align="C", ln=True)
        pdf.ln(8)
        pdf.set_draw_color(30, 58, 138)
        pdf.set_line_width(1.2)
        pdf.line(25, pdf.get_y(), 185, pdf.get_y())
        pdf.ln(10)

        # Índice agrupado por categoría
        CAT_ORDER = ["Regional", "Educacion", "Salud", "Deporte", "Otros"]
        cat_map = {}
        for item in news_list:
            cat = item.get("category", "Otros")
            cat_key = cat.replace("ó","o").replace("é","e").replace("á","a").replace("í","i").replace("ú","u")
            cat_map.setdefault(cat_key, []).append(item)

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 7, "INDICE:", ln=True)
        pdf.ln(1)
        num = 1
        for cat_key in CAT_ORDER + [k for k in cat_map if k not in CAT_ORDER]:
            items = cat_map.get(cat_key, [])
            if not items:
                continue
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(0, 6, f"  {cat_key.upper()} ({len(items)})", ln=True)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(71, 85, 105)
            for item in items:
                t = _enc(item["title"])[:100]
                pdf.cell(0, 5, f"    {num:02d}. {t}", ln=True)
                num += 1
        pdf.ln(4)

        # ── ARTÍCULOS ordenados por categoría ──
        CAT_COLORS = {
            "Regional":  (37,  99,  235),
            "Educacion": (124, 58,  237),
            "Salud":     (22,  163, 74),
            "Deporte":   (234, 88,  12),
            "Otros":     (100, 116, 139),
        }

        article_num = 1
        for cat_key in CAT_ORDER + [k for k in cat_map if k not in CAT_ORDER]:
            items = cat_map.get(cat_key, [])
            if not items:
                continue
            for item in items:
                pct = min(int(article_num / total * 92), 92)
                task["progress"] = pct
                task["msg"] = f"Artículo {article_num}/{len(news_list)}: {item['title'][:50]}..."

                try:
                    content = scrape_full_article(item.get("link",""))
                except Exception:
                    content = "No se pudo extraer el contenido."
                if not content or len(content) < 20:
                    content = "Contenido no disponible para este artículo."

                pdf.add_page()
                rgb = CAT_COLORS.get(cat_key, CAT_COLORS["Otros"])

                # Badge categoría
                pdf.set_fill_color(*rgb)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 8)
                badge_txt = f"  {cat_key.upper()}  — N° {article_num:02d}  "
                pdf.cell(0, 7, _enc(badge_txt), fill=True, ln=True)
                pdf.ln(2)

                # Título
                pdf.set_font("Helvetica", "B", 15)
                pdf.set_text_color(30, 58, 138)
                pdf.multi_cell(0, 8, _enc(item["title"]))
                pdf.ln(2)

                # URL fuente
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(100, 116, 139)
                pdf.multi_cell(0, 5, f"Fuente: {_enc(item.get('link',''))}")
                pdf.ln(3)

                # Línea separadora
                pdf.set_draw_color(200, 210, 230)
                pdf.set_line_width(0.4)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(4)

                # Contenido
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(30, 41, 59)
                for para in content.split("\n"):
                    para = para.strip()
                    if not para:
                        pdf.ln(2)
                        continue
                    p = _enc(para)
                    if len(para) < 80 and para.isupper():
                        pdf.set_font("Helvetica", "B", 10)
                        pdf.set_text_color(*rgb)
                        pdf.multi_cell(0, 6, p)
                        pdf.set_font("Helvetica", "", 10)
                        pdf.set_text_color(30, 41, 59)
                    else:
                        pdf.multi_cell(0, 6, p)
                    pdf.ln(1)

                article_num += 1

        pdf.output(str(pdf_path))
        task["status"]   = "done"
        task["progress"] = 100
        task["filename"] = pdf_name
        task["msg"]      = f"PDF listo — {len(news_list)} noticias compiladas"

    except Exception as e:
        task["status"] = "error"
        task["msg"]    = str(e)


def start_compile_news(news_list, page_title):
    tid = uuid.uuid4().hex[:12]
    PDF_TASKS[tid] = {
        "progress": 0, "status": "working",
        "msg": "Iniciando compilación...", "filename": None,
    }
    threading.Thread(
        target=run_compile_pdf_task,
        args=(tid, news_list, page_title),
        daemon=True,
    ).start()
    return tid


# ─────────────────────────────────────────────────────────────────
#  DESCARGAR TODOS LOS DOCUMENTOS → ZIP
# ─────────────────────────────────────────────────────────────────

def run_docs_zip_task(task_id, files_list, page_title):
    task = DOC_ZIP_TASKS[task_id]
    try:
        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        zip_name = f"documentos_{_safe(page_title, 30)}_{date_str}.zip"
        zip_path = DOWNLOAD_DIR / zip_name
        total    = len(files_list) or 1
        ok       = 0

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for i, f in enumerate(files_list):
                task["msg"]      = f"Descargando {i+1}/{len(files_list)}: {f['filename']}"
                task["progress"] = min(int(i / total * 94), 94)
                try:
                    fp, fn = download_file(f["url"], f["filename"])
                    if fp:
                        zf.write(fp, fn)
                        ok += 1
                except Exception:
                    pass

            # Índice
            idx = [
                f"DOCUMENTOS — {page_title}",
                f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                "=" * 60,
            ]
            for j, ff in enumerate(files_list, 1):
                idx.append(f"  {j:02d}. [{ff['type']}] {ff['name']}")
                idx.append(f"       {ff['url']}")
            zf.writestr("LISTA_DOCUMENTOS.txt", "\n".join(idx))

        task["status"]   = "done"
        task["progress"] = 100
        task["filename"] = zip_name
        task["msg"]      = f"ZIP listo — {ok}/{len(files_list)} documentos descargados"

    except Exception as e:
        task["status"] = "error"
        task["msg"]    = str(e)


def start_docs_zip(files_list, page_title):
    tid = uuid.uuid4().hex[:12]
    DOC_ZIP_TASKS[tid] = {
        "progress": 0, "status": "working",
        "msg": "Iniciando descarga de documentos...", "filename": None,
    }
    threading.Thread(
        target=run_docs_zip_task,
        args=(tid, files_list, page_title),
        daemon=True,
    ).start()
    return tid
