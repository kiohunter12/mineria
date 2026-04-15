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

TASKS = {}   # exportaciones en background

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
    ".zip",".rar",".7z",".txt",".csv",".json",".xml",".geojson"
]

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
    """Detecta si la página necesita JS para mostrar contenido."""
    if len(html) < 4000:
        return True
    for sig in JS_SIGNALS:
        if sig in html:
            return True
    soup = BeautifulSoup(html, "lxml")
    body_text = soup.get_text(separator=" ", strip=True)
    return len(body_text) < 400


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
                          "type":ext[1:].upper(),"filename":fname})
    return files[:25]


def extract_images(soup, base):
    images, seen = [], set()
    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or
               img.get("data-lazy-src") or img.get("data-original") or
               img.get("data-srcset","").split()[0])
        if not src: continue
        fu = abs_url(base, src)
        if not fu or fu in seen: continue
        if any(p in fu.lower() for p in SKIP_IMG): continue
        alt = img.get("alt","").strip()
        fname = os.path.basename(urlparse(fu).path) or "imagen.jpg"
        seen.add(fu)
        images.append({"url":fu,"alt":alt,"filename":fname})
    return images[:40]


# ─────────────────────────────────────────────────────────────────
#  SELENIUM (páginas con JS / CAPTCHA)
# ─────────────────────────────────────────────────────────────────

def scrape_with_browser(url, headless=True, wait=6):
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
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(f"user-agent={HEADERS['User-Agent']}")

        drv = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=opts
        )
        drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        })
        drv.get(url)
        time.sleep(wait)
        if not headless:
            print("[Selenium] Navegador abierto. Resuelve el CAPTCHA si aparece...")
            time.sleep(15)
        html = drv.page_source
        final_url = drv.current_url
        drv.quit()
        return html, final_url, None
    except ImportError:
        return None, url, "Selenium no instalado."
    except Exception as e:
        return None, url, str(e)


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
#  FUNCIÓN PRINCIPAL — scrape_url
# ─────────────────────────────────────────────────────────────────

def scrape_url(url, use_browser=False, headless=True):
    html, final_url, browser_err = None, url, None
    needs_js = False

    # 1) Intentar con requests primero
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        final_url = resp.url
    except requests.exceptions.ConnectionError:
        return {"error": "No se pudo conectar. Verifica que la URL sea correcta."}
    except requests.exceptions.Timeout:
        return {"error": "La página tardó demasiado (timeout). Intenta con Modo Avanzado."}
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code
        if code == 403:
            return {"error": f"Acceso denegado (403). Activa el Modo Avanzado (Selenium)."}
        if code == 404:
            return {"error": "Página no encontrada (404). Verifica la URL."}
        return {"error": f"Error HTTP {code}."}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    # 2) Detectar si necesita JS
    needs_js = is_js_page(html)

    # 3) Si el usuario pidió Selenium O la página necesita JS → usar browser
    if use_browser or needs_js:
        html_b, final_url_b, browser_err = scrape_with_browser(
            url, headless=headless, wait=7
        )
        if html_b and len(html_b) > len(html):
            html = html_b
            final_url = final_url_b

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["script","style"]):
        tag.decompose()

    title_tag = soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else "Sin título"

    meta = soup.find("meta", attrs={"name": "description"})
    description = (meta["content"].strip() if meta and meta.get("content") else "")

    news   = extract_news(soup, final_url)
    videos = extract_videos(soup, final_url)
    tables = extract_tables(soup)
    files  = extract_files(soup, final_url)
    images = extract_images(soup, final_url)

    result = {
        "title": page_title, "description": description, "url": final_url,
        "news": news, "videos": videos, "tables": tables,
        "files": files, "images": images,
        "needed_js": needs_js,
        "stats": {
            "news_count":   len(news),
            "videos_count": len(videos),
            "tables_count": len(tables),
            "files_count":  len(files),
            "images_count": len(images),
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
