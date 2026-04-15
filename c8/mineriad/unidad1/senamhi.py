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


def _get_html_selenium(url, wait=6, headless=True):
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
        opts.add_argument(f"user-agent={HEADERS['User-Agent']}")

        drv = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=opts
        )
        drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        })
        drv.get(url)
        time.sleep(wait)
        html = drv.page_source
        drv.quit()
        return html, None
    except Exception as e:
        return None, str(e)


# ── Obtener TODAS las estaciones del mapa global ────────────────

_ALL_STATIONS_CACHE = None   # caché en memoria

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
                "type":      cate,
                "type_full": STATION_TYPES.get(cate, cate),
                "lat":       str(lat),
                "lon":       str(lon),
                "estado":    st.get("estado", ""),
                "dept":      REGIONS.get(region_code, region_code),
                "link":      (
                    f"{SENAMHI_BASE}/main.php?dp={region_code}"
                    f"&p=estaciones&cod={code}"
                    if code else ""
                ),
                "region":    region_code,
            })

    return filtered, None


# ── Descargar datos históricos de UNA estación ─────────────────

def get_station_data(station):
    """
    Intenta descargar los datos de la estación.
    Retorna (rows: list[list], headers: list, error: str|None)
    """
    link = station.get("link", "")

    # 1) Si hay link directo, intentar scrape de tabla
    if link:
        html, err = _get_html_requests(link)
        if not html:
            html, err = _get_html_selenium(link, wait=8)

        if html:
            soup = BeautifulSoup(html, "lxml")
            for tbl in soup.find_all("table"):
                rows = tbl.find_all("tr")
                if len(rows) < 3:
                    continue
                headers = [th.get_text(strip=True)
                           for th in (rows[0].find_all(["th", "td"]))]
                data_rows = []
                for tr in rows[1:]:
                    row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if row and any(c for c in row):
                        data_rows.append(row)
                if data_rows:
                    return data_rows, headers, None

    # 2) Intentar endpoint genérico de descarga de datos históricos
    # SENAMHI tiene un portal de datos con parámetros GET
    code = station.get("code", "")
    region = station.get("region", "")
    if code:
        candidate_urls = [
            f"{SENAMHI_BASE}/main.php?dp={region}&p=estaciones&est={code}",
            f"{SENAMHI_BASE}/?p=data-historica&est={code}",
        ]
        for url in candidate_urls:
            html, _ = _get_html_requests(url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                for tbl in soup.find_all("table"):
                    rows = tbl.find_all("tr")
                    if len(rows) < 3:
                        continue
                    headers = [th.get_text(strip=True)
                               for th in rows[0].find_all(["th", "td"])]
                    data_rows = [
                        [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                        for tr in rows[1:]
                        if tr.find_all(["td", "th"])
                    ]
                    if data_rows:
                        return data_rows, headers, None

    return [], [], "No se encontraron datos para esta estación."


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
                    rows, headers, err = get_station_data(st)
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
