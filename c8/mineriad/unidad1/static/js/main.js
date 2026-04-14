/* ===== WebScraper Pro - main.js ===== */

let allNews = [];

// ---- Utilidades ----

function showToast(message, type = 'success') {
  const toast = document.getElementById('toastMsg');
  const toastText = document.getElementById('toastText');
  toast.classList.remove('bg-success', 'bg-danger', 'bg-warning');
  toast.classList.add(type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-warning');
  toastText.textContent = message;
  bootstrap.Toast.getOrCreateInstance(toast, { delay: 3500 }).show();
}

function setUrl(url) {
  document.getElementById('urlInput').value = url;
  document.getElementById('urlInput').focus();
}

function show(id) { document.getElementById(id).classList.remove('d-none'); }
function hide(id) { document.getElementById(id).classList.add('d-none'); }

function resetResults() {
  hide('resultsSection');
  hide('errorSection');
  hide('loadingSection');
  document.getElementById('newsGrid').innerHTML = '';
  document.getElementById('filesList').innerHTML = '';
  document.getElementById('imagesGrid').innerHTML = '';
  allNews = [];
}

// ---- Categoría → color y clase ----
const CATEGORY_CONFIG = {
  'Regional':   { badge: 'badge-Regional',  icon: 'fa-map-marker-alt' },
  'Educación':  { badge: 'badge-Educación', icon: 'fa-graduation-cap' },
  'Salud':      { badge: 'badge-Salud',     icon: 'fa-heart-pulse' },
  'Deporte':    { badge: 'badge-Deporte',   icon: 'fa-futbol' },
  'Otros':      { badge: 'badge-Otros',     icon: 'fa-ellipsis' },
};

function getCatConfig(cat) {
  return CATEGORY_CONFIG[cat] || CATEGORY_CONFIG['Otros'];
}

// ---- Icono para archivos ----
function getFileIcon(type) {
  const map = {
    PDF: 'PDF', DOC: 'DOC', DOCX: 'DOC',
    XLS: 'XLS', XLSX: 'XLS', PPT: 'PPT', PPTX: 'PPT',
    ZIP: 'ZIP', RAR: 'ZIP',
  };
  const css = {
    PDF: 'file-icon-pdf', DOC: 'file-icon-doc', DOCX: 'file-icon-docx',
    XLS: 'file-icon-xls', XLSX: 'file-icon-xlsx',
    PPT: 'file-icon-ppt', PPTX: 'file-icon-pptx',
    ZIP: 'file-icon-zip', RAR: 'file-icon-rar',
  };
  const label = map[type] || type;
  const cls = css[type] || 'file-icon-default';
  return `<div class="file-icon ${cls}">${label}</div>`;
}

// ---- Render noticias ----
function renderNews(newsArray) {
  const grid = document.getElementById('newsGrid');
  grid.innerHTML = '';

  if (!newsArray.length) {
    hide('newsGrid');
    show('noNewsMsg');
    return;
  }

  hide('noNewsMsg');
  show('newsGrid');

  newsArray.forEach(item => {
    const catCfg = getCatConfig(item.category);
    const imgHtml = item.image
      ? `<img class="news-card-img" src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}"
              onerror="this.parentElement.innerHTML='<div class=\\'news-card-img-placeholder\\'><i class=\\'fas fa-newspaper\\'></i></div>'" />`
      : `<div class="news-card-img-placeholder"><i class="fas fa-newspaper"></i></div>`;

    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-lg-4 news-item';
    col.dataset.category = item.category;
    col.innerHTML = `
      <div class="news-card">
        ${imgHtml}
        <div class="news-card-body">
          <span class="news-category-badge ${catCfg.badge}">
            <i class="fas ${catCfg.icon} me-1"></i>${item.category}
          </span>
          <div class="news-card-title">${escapeHtml(item.title)}</div>
          <a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer" class="news-card-link">
            Ver noticia <i class="fas fa-arrow-right"></i>
          </a>
        </div>
      </div>`;
    grid.appendChild(col);
  });
}

// ---- Render archivos ----
function renderFiles(files) {
  const list = document.getElementById('filesList');
  list.innerHTML = '';

  if (!files.length) {
    show('noFilesMsg');
    return;
  }

  hide('noFilesMsg');

  files.forEach(file => {
    const div = document.createElement('div');
    div.className = 'file-item';
    div.innerHTML = `
      ${getFileIcon(file.type)}
      <div class="file-info">
        <div class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</div>
        <div class="file-type-label">
          <i class="fas fa-tag me-1"></i>${file.type}
          &nbsp;·&nbsp;
          <a href="${escapeHtml(file.url)}" target="_blank" rel="noopener noreferrer" class="text-muted text-decoration-none small">
            <i class="fas fa-external-link-alt me-1"></i>Ver enlace
          </a>
        </div>
      </div>
      <button class="btn-download" onclick="downloadFile('${escapeHtml(file.url)}', '${escapeHtml(file.filename)}', this)">
        <i class="fas fa-download me-1"></i>Descargar
      </button>`;
    list.appendChild(div);
  });
}

// ---- Render imágenes ----
function renderImages(images) {
  const grid = document.getElementById('imagesGrid');
  grid.innerHTML = '';

  if (!images.length) {
    show('noImagesMsg');
    return;
  }

  hide('noImagesMsg');

  images.forEach(img => {
    const col = document.createElement('div');
    col.className = 'col-6 col-sm-4 col-md-3';
    col.innerHTML = `
      <div class="img-card" onclick="openImageModal('${escapeHtml(img.url)}', '${escapeHtml(img.alt || img.filename)}')">
        <img src="${escapeHtml(img.url)}" alt="${escapeHtml(img.alt || img.filename)}"
             onerror="this.closest('.col-6, .col-sm-4, .col-md-3').remove()" loading="lazy" />
        <div class="img-card-caption">${escapeHtml(img.alt || img.filename)}</div>
      </div>`;
    grid.appendChild(col);
  });
}

// ---- Filtro de categorías ----
function filterCategory(cat, btn) {
  document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  document.querySelectorAll('.news-item').forEach(item => {
    if (cat === 'Todas' || item.dataset.category === cat) {
      item.style.display = '';
    } else {
      item.style.display = 'none';
    }
  });
}

// ---- Modal imagen ----
function openImageModal(url, alt) {
  document.getElementById('imgModalSrc').src = url;
  document.getElementById('imgModalAlt').textContent = alt;
  document.getElementById('imgModalDownload').href = url;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('imgModal')).show();
}

// ---- Descargar archivo ----
async function downloadFile(url, filename, btn) {
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Descargando...';

  try {
    const res = await fetch('/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, filename }),
    });

    const data = await res.json();

    if (data.success) {
      // Disparar descarga desde el servidor
      const a = document.createElement('a');
      a.href = `/download-file/${encodeURIComponent(data.filename)}`;
      a.download = data.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();

      btn.innerHTML = '<i class="fas fa-check me-1"></i>Descargado';
      btn.style.background = 'linear-gradient(135deg, #64748b, #475569)';
      showToast(`Archivo "${data.filename}" descargado correctamente.`, 'success');
    } else {
      throw new Error(data.error || 'Error desconocido');
    }
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
    showToast(`Error al descargar: ${err.message}`, 'error');
  }
}

// ---- Scraping principal ----
async function analyze() {
  const urlInput = document.getElementById('urlInput');
  const url = urlInput.value.trim();

  if (!url) {
    urlInput.focus();
    showToast('Ingresa una URL para analizar.', 'warning');
    return;
  }

  resetResults();
  show('loadingSection');

  try {
    const res = await fetch('/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    const data = await res.json();
    hide('loadingSection');

    if (data.error) {
      document.getElementById('errorMsg').textContent = data.error;
      show('errorSection');
      return;
    }

    // Rellenar info de la página
    document.getElementById('pageTitle').textContent = data.title || 'Sin título';
    document.getElementById('pageDesc').textContent = data.description || '';
    const urlLink = document.getElementById('pageUrl');
    urlLink.textContent = data.url;
    urlLink.href = data.url;

    // Estadísticas
    document.getElementById('statNews').textContent   = data.stats.news_count;
    document.getElementById('statFiles').textContent  = data.stats.files_count;
    document.getElementById('statImages').textContent = data.stats.images_count;
    document.getElementById('badgeNoticias').textContent = data.stats.news_count;
    document.getElementById('badgeArchivos').textContent = data.stats.files_count;
    document.getElementById('badgeImagenes').textContent = data.stats.images_count;

    allNews = data.news || [];
    renderNews(allNews);
    renderFiles(data.files || []);
    renderImages(data.images || []);

    show('resultsSection');

    // Scroll suave hacia resultados
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'start' });

  } catch (err) {
    hide('loadingSection');
    document.getElementById('errorMsg').textContent = `Error de conexión: ${err.message}`;
    show('errorSection');
  }
}

// ---- Sanitizar HTML ----
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ---- Eventos ----
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btnAnalyze').addEventListener('click', analyze);

  document.getElementById('urlInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') analyze();
  });
});
