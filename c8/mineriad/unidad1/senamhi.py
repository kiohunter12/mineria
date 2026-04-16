"""
senamhi.py — Módulo dedicado para scraping de SENAMHI Perú
Extrae estaciones por región y descarga datos históricos en CSV.
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re, os, time, zipfile, threading, uuid, csv, io, json
from pathlib import Path
from datetime import datetime

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

SENAMHI_BASE    = "https://www.senamhi.gob.pe"
SENAMHI_MAP_URL = "https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/"
SENAMHI_DATA_URL = "https://www.senamhi.gob.pe/?p=data-historica"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-PE,es;q=0.9",
    "Referer": "https://www.senamhi.gob.pe/",
}

# ── Todas las regiones de Perú ──────────────────────────────────
# Límites geográficos (lat_min, lat_max, lon_min, lon_max) por región de Perú
REGION_BOUNDS = {
    "amazonas":      (-6.5,  -2.0,  -78.5, -76.5),
    "ancash":        (-10.5, -8.0,  -78.5, -76.5),
    "apurimac":      (-14.5, -12.5, -73.5, -71.5),
    "arequipa":      (-17.5, -14.0, -73.5, -70.0),
    "ayacucho":      (-15.0, -11.5, -75.5, -73.0),
    "cajamarca":     (-8.0,  -4.5,  -79.5, -77.5),
    "callao":        (-12.1, -11.8, -77.2, -77.0),
    "cusco":         (-15.5, -11.0, -73.5, -70.0),
    "huancavelica":  (-14.0, -11.5, -75.5, -74.0),
    "huanuco":       (-10.5, -8.0,  -77.0, -74.5),
    "ica":           (-15.5, -13.0, -76.0, -74.5),
    "junin":         (-12.5, -10.0, -76.0, -73.5),
    "la-libertad":   (-9.0,  -6.5,  -79.5, -77.0),
    "lambayeque":    (-7.5,  -5.5,  -80.5, -79.0),
    "lima":          (-12.8, -10.0, -77.5, -75.5),
    "loreto":        (-8.0,  -0.5,  -76.5, -70.0),
    "madre-de-dios": (-13.5, -9.5,  -72.5, -68.5),
    "moquegua":      (-17.5, -15.5, -72.0, -69.5),
    "pasco":         (-11.5, -9.5,  -76.5, -74.5),
    "piura":         (-6.5,  -3.5,  -81.5, -79.0),
    "puno":          (-16.5, -13.0, -71.5, -68.5),
    "san-martin":    (-9.0,  -5.0,  -78.0, -75.5),
    "tacna":         (-18.5, -16.5, -71.0, -69.0),
    "tumbes":        (-4.5,  -3.0,  -81.0, -79.5),
    "ucayali":       (-11.5, -7.0,  -75.5, -72.0),
}

# Categorías de estaciones
STATION_TYPES = {
    "CO":  "Meteorológica Convencional",
    "CP":  "Climatológica Principal",
    "CS":  "Climatológica Secundaria",
    "PLU": "Pluviométrica",
    "HLG": "Hidrológica",
    "HLM": "Hidrológica Meteorológica",
    "ALT": "Automática",
}

REGIONS = {
    "amazonas":     "Amazonas",
    "ancash":       "Áncash",
    "apurimac":     "Apurímac",
    "arequipa":     "Arequipa",
    "ayacucho":     "Ayacucho",
    "cajamarca":    "Cajamarca",
    "callao":       "Callao",
    "cusco":        "Cusco",
    "huancavelica": "Huancavelica",
    "huanuco":      "Huánuco",
    "ica":          "Ica",
    "junin":        "Junín",
    "la-libertad":  "La Libertad",
    "lambayeque":   "Lambayeque",
    "lima":         "Lima",
    "loreto":       "Loreto",
    "madre-de-dios":"Madre de Dios",
    "moquegua":     "Moquegua",
    "pasco":        "Pasco",
    "piura":        "Piura",
    "puno":         "Puno",
    "san-martin":   "San Martín",
    "tacna":        "Tacna",
    "tumbes":       "Tumbes",
    "ucayali":      "Ucayali",
}

# Almacén de tareas SENAMHI
SENAMHI_TASKS = {}


# ── Helpers ─────────────────────────────────────────────────────

def _safe(text, n=60):
    return re.sub(r"[^\w\s\-]", "", text or "").strip().replace(" ", "_")[:n] or "archivo"


def _get_html_requests(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        return r.text, None
    except Exception as e:
        return None, str(e)


def _get_html_curl(url):
    """curl_cffi — TLS fingerprint Chrome."""
    try:
        from curl_cffi import requests as creq
        r = creq.get(url, impersonate="chrome124", headers=HEADERS, timeout=25)
        r.raise_for_status()
        return r.text, None
    except Exception as e:
        return None, str(e)


def _get_html_cloudscraper(url):
    """Cloudflare bypass."""
    try:
        import cloudscraper
        sc = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        sc.headers.update(HEADERS)
        r = sc.get(url, timeout=30)
        r.raise_for_status()
        return r.text, None
    except Exception as e:
        return None, str(e)


def _get_html_undetected(url, wait=10, headless=True):
    """undetected-chromedriver stealth — mejor contra anti-bots."""
    try:
        import undetected_chromedriver as uc
        opts = uc.ChromeOptions()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument(f"--user-agent={HEADERS['User-Agent']}")
        if headless:
            opts.add_argument("--headless=new")
        drv = uc.Chrome(options=opts, use_subprocess=True)
        drv.set_page_load_timeout(45)
        try:
            drv.get(url)
            time.sleep(wait)
            # scroll para activar carga de datos
            drv.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(2)
            drv.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            html = drv.page_source
        finally:
            try: drv.quit()
            except Exception: pass
        return html, None
    except Exception as e:
        return None, str(e)


def _get_html_selenium(url, wait=8, headless=True):
    """Selenium clásico como último recurso."""
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
        drv.set_page_load_timeout(45)
        drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        })
        try:
            drv.get(url)
            time.sleep(wait)
            drv.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            html = drv.page_source
        finally:
            try: drv.quit()
            except Exception: pass
        return html, None
    except Exception as e:
        return None, str(e)


def _fetch_senamhi_html(url):
    """
    Intenta obtener el HTML de una página SENAMHI probando en cascada:
    requests → curl_cffi → cloudscraper → undetected-chrome → selenium
    Devuelve el HTML más largo/completo que encuentre.
    """
    best_html, best_len = None, 0

    for fn in [_get_html_requests, _get_html_curl, _get_html_cloudscraper]:
        html, _ = fn(url)
        if html and len(html) > best_len:
            best_html, best_len = html, len(html)
        if best_html and _has_data_table(best_html):
            return best_html   # ya tiene datos, no necesitamos browser

    # Si no encontramos tabla, usar browser headless
    if not best_html or not _has_data_table(best_html):
        html, _ = _get_html_undetected(url, wait=10)
        if html and len(html) > best_len:
            best_html = html

    # Último recurso: Selenium
    if not best_html or not _has_data_table(best_html):
        html, _ = _get_html_selenium(url, wait=8)
        if html and html:
            best_html = html

    return best_html


def _has_data_table(html):
    """¿El HTML tiene una tabla con más de 3 filas de datos?"""
    if not html:
        return False
    soup = BeautifulSoup(html[:200000], "lxml")
    for tbl in soup.find_all("table"):
        if len(tbl.find_all("tr")) >= 4:
            return True
    return False


# ── Obtener TODAS las estaciones del mapa global ────────────────

_ALL_STATIONS_CACHE = None   # caché en memoria (se invalida al reiniciar)

def _load_all_stations():
    """Descarga el mapa global y extrae las 900+ estaciones."""
    global _ALL_STATIONS_CACHE
    if _ALL_STATIONS_CACHE is not None:
        return _ALL_STATIONS_CACHE, None

    html, err = _get_html_requests(SENAMHI_MAP_URL)
    if not html:
        return [], err

    # El array JSON está en: var PruebaTest = [{...},{...},...];
    m = re.search(r"var\s+PruebaTest\s*=\s*(\[.*?\]);", html, re.DOTALL)
    if not m:
        return [], "No se encontró el array de estaciones en el mapa."

    raw = m.group(1)
    objects = re.findall(r"\{[^}]+\}", raw)
    stations = []
    for obj in objects:
        try:
            d = json.loads(obj)
            stations.append(d)
        except Exception:
            pass

    _ALL_STATIONS_CACHE = stations
    return stations, None


# ── Filtrar estaciones por región (coordenadas) ─────────────────

def get_stations(region_code, use_selenium=False):
    """
    Devuelve las estaciones de la región dada, filtrando por límites geográficos.
    Claves del dict: name, code, type, type_full, lat, lon, estado, link, region
    """
    all_st, err = _load_all_stations()
    if err and not all_st:
        return [], f"Error cargando mapa de estaciones: {err}"

    bounds = REGION_BOUNDS.get(region_code)
    if not bounds:
        return [], f"Región '{region_code}' no tiene límites configurados."

    lat_min, lat_max, lon_min, lon_max = bounds

    filtered = []
    for st in all_st:
        lat = st.get("lat")
        lon = st.get("lon")
        if lat is None or lon is None:
            continue
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            code = st.get("cod", "")
            cate = st.get("cate", "")
            filtered.append({
                "name":      st.get("nom", "Sin nombre"),
                "code":      code,
                "cod_old":   st.get("cod_old", code),
                "type":      cate,
                "type_full": STATION_TYPES.get(cate, cate),
                "ico":       st.get("ico", "M"),
                "lat":       str(lat),
                "lon":       str(lon),
                "estado":    st.get("estado", "DIFERIDO"),
                "dept":      REGIONS.get(region_code, region_code),
                "link":      (
                    f"{SENAMHI_BASE}/mapas/mapa-estaciones-2/map_red_graf.php"
                    f"?cod={code}&estado={st.get('estado','DIFERIDO')}"
                    f"&tipo_esta={st.get('ico','M')}&cate={cate}"
                    f"&cod_old={st.get('cod_old', code)}"
                    if code else ""
                ),
                "region":    region_code,
            })

    return filtered, None


# ── Descargar datos históricos de UNA estación ─────────────────

def _extract_tables_from_html(html):
    """Devuelve lista de (headers, data_rows) para todas las tablas con datos."""
    results = []
    if not html:
        return results
    soup = BeautifulSoup(html, "lxml")
    for tbl in soup.find_all("table"):
        rows_el = tbl.find_all("tr")
        if len(rows_el) < 3:
            continue
        headers = [c.get_text(strip=True) for c in rows_el[0].find_all(["th", "td"])]
        data_rows = []
        for tr in rows_el[1:]:
            row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if row and any(c for c in row):
                data_rows.append(row)
        if len(data_rows) >= 2:
            results.append((headers, data_rows))
    return results


def _extract_highcharts_data(html):
    """
    Extrae datos del gráfico Highcharts embebido en el HTML de SENAMHI.
    Devuelve (headers, rows) con fechas + variables meteorológicas.
    """
    if not html:
        return None, None

    # Extraer categorías (fechas)
    dates_m = re.search(r"categories\s*:\s*\[([^\]]+)\]", html)
    if not dates_m:
        return None, None
    dates = re.findall(r"'([^']+)'|\"([^\"]+)\"", dates_m.group(1))
    dates = [d[0] or d[1] for d in dates]
    if not dates:
        return None, None

    # Extraer series de datos
    series_raw = re.findall(
        r'console\.log\s*\(\s*"Data\d+\s*\(([^"]+)\)"\s*,\s*\[([^\]]+)\]',
        html
    )
    if not series_raw:
        # Intentar formato alternativo: data: [1.2, 3.4, ...]
        series_raw2 = re.findall(
            r'name\s*:\s*["\']([^"\']+)["\'].*?data\s*:\s*\[([^\]]+)\]',
            html, re.DOTALL
        )
        series_raw = [(n, d) for n, d in series_raw2]

    if not series_raw:
        return None, None

    # Construir tabla
    headers = ["Fecha"]
    series_data = []
    for name, data_str in series_raw:
        values = []
        for v in data_str.split(","):
            v = v.strip()
            try:
                values.append(str(round(float(v), 1)) if v not in ("", "null", "None") else "—")
            except Exception:
                values.append("—")
        series_data.append(values)
        headers.append(name.strip())

    rows = []
    for i, date in enumerate(dates):
        row = [date]
        for vals in series_data:
            row.append(vals[i] if i < len(vals) else "—")
        rows.append(row)

    return headers, rows


def _build_station_url(station):
    """Construye la URL del popup de SENAMHI para una estación."""
    cod     = station.get("code", "")
    cod_old = station.get("cod_old", cod)
    estado  = station.get("estado", "DIFERIDO")
    ico     = station.get("ico", "M")
    cate    = station.get("type", "CO")
    if not cod:
        return ""
    return (
        f"{SENAMHI_BASE}/mapas/mapa-estaciones-2/map_red_graf.php"
        f"?cod={cod}&estado={estado}&tipo_esta={ico}&cate={cate}&cod_old={cod_old}"
    )


def get_station_data(station):
    """
    Descarga datos de la estación desde SENAMHI.
    1) Usa map_red_graf.php (endpoint real del mapa interactivo)
    2) Extrae datos del gráfico Highcharts embebido
    3) Si no hay gráfico, intenta parsear tablas HTML
    Retorna (rows, headers, error, source_url)
    """
    # Construir URL correcta del popup
    url = _build_station_url(station)
    if not url and station.get("link"):
        url = station["link"]

    if not url:
        return [], [], "No hay URL disponible para esta estación.", ""

    try:
        html, err = _get_html_requests(url)
        if not html:
            html, err = _get_html_curl(url)
        if not html:
            return [], [], f"No se pudo obtener la página: {err}", url

        # 1) Intentar extraer datos del gráfico Highcharts (fuente más rica)
        headers, rows = _extract_highcharts_data(html)
        if rows and len(rows) >= 5:
            return rows, headers, None, url

        # 2) Intentar tablas HTML normales
        tables = _extract_tables_from_html(html)
        if tables:
            headers, rows = max(tables, key=lambda t: len(t[1]))
            if len(rows) >= 2:
                return rows, headers, None, url

        # 3) Intentar con browser si el HTML no tiene datos
        html_b, _ = _get_html_undetected(url, wait=8)
        if html_b:
            headers, rows = _extract_highcharts_data(html_b)
            if rows and len(rows) >= 2:
                return rows, headers, None, url
            tables = _extract_tables_from_html(html_b)
            if tables:
                headers, rows = max(tables, key=lambda t: len(t[1]))
                if len(rows) >= 2:
                    return rows, headers, None, url

        return [], [], "Datos protegidos por CAPTCHA o no disponibles públicamente.", url

    except Exception as e:
        return [], [], str(e), url


def station_data_to_csv(rows, headers, station_name):
    """Convierte los datos de la estación a CSV y lo guarda."""
    fname = f"senamhi_{_safe(station_name)}.csv"
    fpath = DOWNLOAD_DIR / fname
    with open(fpath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if headers:
            w.writerow(headers)
        w.writerows(rows)
    return str(fpath), fname


# ── Tarea en background: descargar TODAS las estaciones ─────────

def run_senamhi_task(task_id, stations, region_name):
    task = SENAMHI_TASKS[task_id]
    try:
        date_str  = datetime.now().strftime("%Y%m%d_%H%M")
        zip_name  = f"senamhi_{_safe(region_name)}_{date_str}.zip"
        zip_path  = DOWNLOAD_DIR / zip_name

        total = len(stations) or 1
        done  = 0

        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            # Índice de estaciones
            index_lines = [
                f"SENAMHI — Región: {region_name}",
                f"Descarga: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                "=" * 50,
                f"Total estaciones seleccionadas: {len(stations)}",
                "",
            ]

            for i, st in enumerate(stations):
                task["msg"]      = f"Estación {i+1}/{total}: {st['name']}"
                task["progress"] = int(done / total * 95)

                try:
                    rows, headers, err, _src = get_station_data(st)
                    if rows:
                        _, csv_name = station_data_to_csv(rows, headers, st["name"])
                        zf.write(DOWNLOAD_DIR / csv_name, f"datos/{csv_name}")
                        index_lines.append(
                            f"✓ {st['name']} ({st['code']}) — {len(rows)} registros"
                        )
                    else:
                        index_lines.append(
                            f"✗ {st['name']} ({st['code']}) — sin datos: {err}"
                        )
                except Exception as ex:
                    index_lines.append(f"✗ {st['name']} — error: {ex}")

                done += 1
                task["progress"] = int(done / total * 95)

            zf.writestr("INDICE.txt", "\n".join(index_lines))

        task["status"]   = "done"
        task["progress"] = 100
        task["filename"] = zip_name
        task["msg"]      = f"¡ZIP listo! {total} estaciones procesadas."

    except Exception as e:
        task["status"] = "error"
        task["msg"]    = str(e)


def start_senamhi_task(stations, region_name):
    task_id = uuid.uuid4().hex[:12]
    SENAMHI_TASKS[task_id] = {
        "progress": 0, "status": "working",
        "msg": "Iniciando descarga...", "filename": None,
    }
    t = threading.Thread(
        target=run_senamhi_task,
        args=(task_id, stations, region_name),
        daemon=True,
    )
    t.start()
    return task_id
