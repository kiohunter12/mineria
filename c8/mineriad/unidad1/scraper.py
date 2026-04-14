import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import re
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}

CATEGORIES = {
    'Regional': [
        'regional', 'local', 'ciudad', 'municipio', 'provincia',
        'barrio', 'comunidad', 'alcaldía', 'gobernación', 'canton',
        'parroquia', 'distrito'
    ],
    'Educación': [
        'educación', 'escuela', 'universidad', 'estudiante', 'colegio',
        'maestro', 'académico', 'educativo', 'profesor', 'clase',
        'aula', 'docente', 'alumno', 'institución', 'instituto'
    ],
    'Salud': [
        'salud', 'médico', 'hospital', 'enfermedad', 'vacuna',
        'medicina', 'clínica', 'sanitario', 'paciente', 'covid',
        'virus', 'tratamiento', 'cirugía', 'farmacia', 'emergencia'
    ],
    'Deporte': [
        'deporte', 'fútbol', 'baloncesto', 'liga', 'torneo',
        'atleta', 'competencia', 'campeonato', 'partido', 'equipo',
        'gol', 'cancha', 'estadio', 'natación', 'atletismo'
    ],
}

FILE_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.ppt', '.pptx', '.zip', '.rar', '.txt', '.csv'
]

SKIP_URL_PATTERNS = [
    'icon', 'logo', 'pixel', 'tracking', '1x1',
    'spacer', 'blank', 'transparent', 'sprite'
]


def categorize_text(text):
    if not text:
        return 'Otros'
    text_lower = text.lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text_lower:
                return cat
    return 'Otros'


def get_absolute_url(base_url, url):
    if not url:
        return None
    url = url.strip()
    if url.startswith('data:') or url.startswith('javascript:'):
        return None
    return urljoin(base_url, url)


def extract_best_image(tag, base_url):
    img = tag.find('img')
    if not img:
        return None
    src = (
        img.get('src') or
        img.get('data-src') or
        img.get('data-lazy-src') or
        img.get('data-original')
    )
    return get_absolute_url(base_url, src)


def extract_news(soup, base_url):
    news = []
    seen_titles = set()

    # --- Estrategia 1: etiquetas <article> ---
    for article in soup.find_all('article', limit=25):
        title_tag = article.find(['h1', 'h2', 'h3', 'h4'])
        link_tag = article.find('a', href=True)
        image = extract_best_image(article, base_url)

        title = title_tag.get_text(strip=True) if title_tag else ''
        if not title or len(title) < 8 or title in seen_titles:
            continue

        link = base_url
        if link_tag and link_tag.get('href'):
            link = get_absolute_url(base_url, link_tag['href']) or base_url

        seen_titles.add(title)
        news.append({
            'title': title,
            'link': link,
            'image': image,
            'category': categorize_text(title)
        })

    # --- Estrategia 2: encabezados con enlace ---
    if len(news) < 6:
        for tag_name in ['h2', 'h3']:
            for h in soup.find_all(tag_name, limit=30):
                title = h.get_text(strip=True)
                if not title or len(title) < 10 or title in seen_titles:
                    continue

                link_tag = (
                    h.find('a', href=True) or
                    h.find_parent('a', href=True)
                )
                link = base_url
                if link_tag and link_tag.get('href'):
                    link = get_absolute_url(base_url, link_tag['href']) or base_url

                # Buscar imagen cercana
                image = None
                parent = h.find_parent(['div', 'li', 'section'])
                if parent:
                    image = extract_best_image(parent, base_url)

                seen_titles.add(title)
                news.append({
                    'title': title,
                    'link': link,
                    'image': image,
                    'category': categorize_text(title)
                })

    # --- Estrategia 3: elementos de lista con enlace ---
    if len(news) < 6:
        for li in soup.find_all('li', limit=40):
            a = li.find('a', href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 15 or title in seen_titles:
                continue

            link = get_absolute_url(base_url, a['href']) or base_url
            image = extract_best_image(li, base_url)

            seen_titles.add(title)
            news.append({
                'title': title,
                'link': link,
                'image': image,
                'category': categorize_text(title)
            })

    return news[:30]


def extract_files(soup, base_url):
    files = []
    seen_urls = set()

    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href:
            continue

        full_url = get_absolute_url(base_url, href)
        if not full_url or full_url in seen_urls:
            continue

        parsed = urlparse(full_url)
        path_lower = parsed.path.lower()
        ext = next((fe for fe in FILE_EXTENSIONS if path_lower.endswith(fe)), None)

        if ext:
            seen_urls.add(full_url)
            name = a.get_text(strip=True) or os.path.basename(parsed.path) or 'Archivo'
            filename = os.path.basename(parsed.path) or f'archivo{ext}'
            files.append({
                'name': name[:120],
                'url': full_url,
                'type': ext[1:].upper(),
                'filename': filename
            })

    return files[:25]


def extract_images(soup, base_url):
    images = []
    seen_urls = set()

    for img in soup.find_all('img'):
        src = (
            img.get('src') or
            img.get('data-src') or
            img.get('data-lazy-src') or
            img.get('data-original')
        )
        if not src:
            continue

        full_url = get_absolute_url(base_url, src)
        if not full_url or full_url in seen_urls:
            continue

        if any(p in full_url.lower() for p in SKIP_URL_PATTERNS):
            continue

        alt = img.get('alt', '').strip()
        filename = os.path.basename(urlparse(full_url).path) or 'imagen.jpg'

        seen_urls.add(full_url)
        images.append({
            'url': full_url,
            'alt': alt,
            'filename': filename
        })

    return images[:40]


def scrape_url(url):
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=15, allow_redirects=True
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        return {'error': 'No se pudo conectar a la URL. Verifica que sea válida.'}
    except requests.exceptions.Timeout:
        return {'error': 'La página tardó demasiado en responder (timeout).'}
    except requests.exceptions.HTTPError as e:
        return {'error': f'Error HTTP {e.response.status_code}: {str(e)}'}
    except requests.exceptions.RequestException as e:
        return {'error': f'Error al acceder a la URL: {str(e)}'}

    try:
        soup = BeautifulSoup(response.text, 'lxml')
    except Exception:
        soup = BeautifulSoup(response.text, 'html.parser')

    # Limpiar tags que no aportan contenido
    for tag in soup.find_all(['script', 'style']):
        tag.decompose()

    title_tag = soup.find('title')
    page_title = title_tag.get_text(strip=True) if title_tag else 'Sin título'

    meta_desc = soup.find('meta', attrs={'name': 'description'})
    description = ''
    if meta_desc and meta_desc.get('content'):
        description = meta_desc['content'].strip()

    news = extract_news(soup, url)
    files = extract_files(soup, url)
    images = extract_images(soup, url)

    return {
        'title': page_title,
        'description': description,
        'url': url,
        'news': news,
        'files': files,
        'images': images,
        'stats': {
            'news_count': len(news),
            'files_count': len(files),
            'images_count': len(images)
        }
    }


def download_file(file_url, filename):
    try:
        response = requests.get(
            file_url, headers=HEADERS, timeout=30, stream=True
        )
        response.raise_for_status()

        safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
        if not safe_filename:
            safe_filename = 'archivo_descargado'

        filepath = DOWNLOAD_DIR / safe_filename

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return str(filepath), safe_filename

    except requests.exceptions.RequestException as e:
        return None, f'Error de red: {str(e)}'
    except OSError as e:
        return None, f'Error al guardar archivo: {str(e)}'
