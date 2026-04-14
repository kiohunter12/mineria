from flask import Flask, render_template, request, jsonify, send_file, abort
from scraper import scrape_url, download_file, DOWNLOAD_DIR
import os
from pathlib import Path

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


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

    result = scrape_url(url)
    return jsonify(result)


@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL requerida'}), 400

    file_url = data['url']
    filename = data.get('filename', 'archivo_descargado')

    filepath, result = download_file(file_url, filename)
    if filepath:
        return jsonify({'success': True, 'filename': result})
    else:
        return jsonify({'error': result}), 500


@app.route('/download-file/<filename>')
def serve_file(filename):
    safe_name = Path(filename).name  # prevenir path traversal
    filepath = DOWNLOAD_DIR / safe_name
    if not filepath.exists():
        abort(404)
    return send_file(str(filepath.resolve()), as_attachment=True)


@app.route('/downloaded-files')
def list_downloaded():
    files = []
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file():
            files.append({
                'name': f.name,
                'size': f.stat().st_size,
                'url': f'/download-file/{f.name}'
            })
    return jsonify(files)


if __name__ == '__main__':
    print("=" * 55)
    print("  WebScraper Pro - Servidor iniciado")
    print("  Abre tu navegador en: http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
