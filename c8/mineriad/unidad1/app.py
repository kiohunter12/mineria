from flask import Flask, render_template, request, jsonify, send_file, abort
from scraper import (scrape_url, download_file, scrape_full_article,
                     article_to_pdf, start_export, TASKS, DOWNLOAD_DIR,
                     PDF_TASKS, start_compile_news,
                     DOC_ZIP_TASKS, start_docs_zip)
from senamhi import (get_stations, start_senamhi_task,
                     SENAMHI_TASKS, REGIONS)
from pathlib import Path
import re

app = Flask(__name__)
app.config['TIMEOUT'] = 300


# ── Página principal ─────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


# ── Página SENAMHI ───────────────────────────────────────────────
@app.route('/senamhi')
def senamhi_page():
    return render_template('senamhi.html', regions=REGIONS)


@app.route('/senamhi/stations', methods=['POST'])
def senamhi_stations():
    data = request.get_json()
    if not data or 'region' not in data:
        return jsonify({'error': 'Región requerida'}), 400
    region = data['region'].strip()
    if region not in REGIONS:
        return jsonify({'error': 'Región no válida'}), 400
    stations, err = get_stations(region, use_selenium=data.get('use_selenium', False))
    if err and not stations:
        return jsonify({'error': err}), 500
    return jsonify({'stations': stations, 'region_name': REGIONS[region], 'warning': err})


@app.route('/senamhi/download-all', methods=['POST'])
def senamhi_download_all():
    data = request.get_json()
    if not data or 'stations' not in data:
        return jsonify({'error': 'Lista de estaciones requerida'}), 400
    stations    = data['stations']
    region_name = data.get('region_name', 'Peru')
    if not stations:
        return jsonify({'error': 'No hay estaciones seleccionadas'}), 400
    task_id = start_senamhi_task(stations, region_name)
    return jsonify({'task_id': task_id})


@app.route('/senamhi/status/<task_id>')
def senamhi_status(task_id):
    task = SENAMHI_TASKS.get(task_id)
    if not task:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    return jsonify(task)


# ── Scraping general ─────────────────────────────────────────────
@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL requerida'}), 400
    url = data['url'].strip()
    if not url:
        return jsonify({'error': 'La URL no puede estar vacía'}), 400
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    use_browser = bool(data.get('use_browser', False))
    headless    = bool(data.get('headless', True))
    result = scrape_url(url, use_browser=use_browser, headless=headless)
    return jsonify(result)


@app.route('/article', methods=['POST'])
def get_article():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL requerida'}), 400
        url   = data['url'].strip()
        if not url:
            return jsonify({'error': 'URL vacía'}), 400
        title = data.get('title', 'articulo')
        content = scrape_full_article(url)
        safe_title = re.sub(r'[^\w\s]', '', title)[:50].strip().replace(' ', '_') or 'articulo'
        pdf_path, pdf_filename = article_to_pdf(title, content, url, f'noticia_{safe_title}')
        return jsonify({
            'title':        title,
            'content':      content,
            'url':          url,
            'pdf_filename': pdf_filename if pdf_path else None,
            'pdf_error':    pdf_filename if not pdf_path else None,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'content': 'Error interno al procesar el artículo.'}), 200


@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL requerida'}), 400
    filepath, result = download_file(data['url'], data.get('filename', 'archivo'))
    if filepath:
        return jsonify({'success': True, 'filename': result})
    return jsonify({'error': result}), 500


@app.route('/start-export', methods=['POST'])
def start_export_route():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos requeridos'}), 400
    task_id = start_export(
        news       = data.get('news', []),
        files      = data.get('files', []),
        images     = data.get('images', []),
        page_title = data.get('title', 'export'),
    )
    return jsonify({'task_id': task_id})


@app.route('/export-status/<task_id>')
def export_status(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    return jsonify(task)


@app.route('/compile-news', methods=['POST'])
def compile_news():
    data = request.get_json()
    if not data or not data.get('news'):
        return jsonify({'error': 'Lista de noticias requerida'}), 400
    task_id = start_compile_news(data['news'], data.get('title', 'Noticias'))
    return jsonify({'task_id': task_id})


@app.route('/compile-status/<task_id>')
def compile_status(task_id):
    task = PDF_TASKS.get(task_id)
    if not task:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    return jsonify(task)


@app.route('/docs-zip', methods=['POST'])
def docs_zip():
    data = request.get_json()
    if not data or not data.get('files'):
        return jsonify({'error': 'Lista de archivos requerida'}), 400
    task_id = start_docs_zip(data['files'], data.get('title', 'Documentos'))
    return jsonify({'task_id': task_id})


@app.route('/docs-zip-status/<task_id>')
def docs_zip_status(task_id):
    task = DOC_ZIP_TASKS.get(task_id)
    if not task:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    return jsonify(task)


@app.route('/download-file/<path:filename>')
def serve_file(filename):
    safe = Path(filename).name
    filepath = DOWNLOAD_DIR / safe
    if not filepath.exists():
        abort(404)
    return send_file(str(filepath.resolve()), as_attachment=True)


if __name__ == '__main__':
    print("=" * 55)
    print("  WebScraper Pro v2 — Servidor iniciado")
    print("  Principal : http://127.0.0.1:5000")
    print("  SENAMHI   : http://127.0.0.1:5000/senamhi")
    print("=" * 55)
    app.run(debug=True, port=5000, threaded=True)
