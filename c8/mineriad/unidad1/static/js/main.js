/* ===== WebScraper Pro v2 — main.js ===== */

let currentPdfFilename = null;
let currentArticleUrl  = null;
let scrapedData        = null;   // guarda los resultados del último scraping
let exportTaskId       = null;
let exportPollInterval = null;
let currentZipFilename = null;

// ─────────────────────────────────────────────
//  UTILIDADES
// ─────────────────────────────────────────────
function show(id) { document.getElementById(id).classList.remove('d-none'); }
function hide(id) { document.getElementById(id).classList.add('d-none'); }

function setUrl(url) {
  document.getElementById('urlInput').value = url;
  document.getElementById('urlInput').focus();
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function showToast(msg, type = 'success') {
  const el = document.getElementById('toastMsg');
  el.classList.remove('bg-success','bg-danger','bg-warning','bg-info');
  el.classList.add(type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : type === 'warning' ? 'bg-warning' : 'bg-info');
  document.getElementById('toastText').textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 3800 }).show();
}

function resetResults() {
  ['resultsSection','errorSection','loadingSection'].forEach(hide);
  ['newsGrid','videosGrid','tablasList','filesList','imagesGrid'].forEach(id => {
    document.getElementById(id).innerHTML = '';
  });
  ['noNewsMsg','noVideosMsg','noTablasMsg','noFilesMsg','noImagesMsg'].forEach(hide);
  currentPdfFilename = null;
}

// ─────────────────────────────────────────────
//  FILTRO POR CATEGORÍA
// ─────────────────────────────────────────────
function filterCategory(cat, btn) {
  document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.news-item').forEach(item => {
    item.style.display = (cat === 'Todas' || item.dataset.category === cat) ? '' : 'none';
  });
}

// ─────────────────────────────────────────────
//  CATEGORÍAS CONFIG
// ─────────────────────────────────────────────
const CAT_CONFIG = {
  'Regional':   { badge:'badge-Regional',  icon:'fa-map-marker-alt' },
  'Educación':  { badge:'badge-Educación', icon:'fa-graduation-cap' },
  'Salud':      { badge:'badge-Salud',     icon:'fa-heart-pulse' },
  'Deporte':    { badge:'badge-Deporte',   icon:'fa-futbol' },
  'Otros':      { badge:'badge-Otros',     icon:'fa-ellipsis' },
};
function catCfg(cat) { return CAT_CONFIG[cat] || CAT_CONFIG['Otros']; }

// ─────────────────────────────────────────────
//  RENDER NOTICIAS
// ─────────────────────────────────────────────
function renderNews(newsArray) {
  const grid = document.getElementById('newsGrid');
  if (!newsArray.length) { hide('newsGrid'); show('noNewsMsg'); return; }
  hide('noNewsMsg');

  newsArray.forEach(item => {
    const cfg = catCfg(item.category);
    const imgHtml = item.image
      ? `<img class="news-card-img" src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}"
              loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'news-card-img-placeholder\\'><i class=\\'fas fa-newspaper\\'></i></div>'" />`
      : `<div class="news-card-img-placeholder"><i class="fas fa-newspaper"></i></div>`;

    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-lg-4 col-xl-3 news-item';
    col.dataset.category = item.category;
    col.innerHTML = `
      <div class="news-card" onclick="openArticle('${escapeHtml(item.link)}','${escapeHtml(item.title)}')">
        ${imgHtml}
        <div class="news-card-body">
          <span class="news-category-badge ${cfg.badge}">
            <i class="fas ${cfg.icon} me-1"></i>${item.category}
          </span>
          <div class="news-card-title">${escapeHtml(item.title)}</div>
          <div class="news-card-actions">
            <button class="btn-read" onclick="event.stopPropagation();openArticle('${escapeHtml(item.link)}','${escapeHtml(item.title)}')">
              <i class="fas fa-book-open me-1"></i>Leer artículo
            </button>
            <a href="${escapeHtml(item.link)}" target="_blank" rel="noopener"
               class="btn-visit" onclick="event.stopPropagation()">
              <i class="fas fa-external-link-alt"></i>
            </a>
          </div>
        </div>
      </div>`;
    grid.appendChild(col);
  });
}

// ─────────────────────────────────────────────
//  ARTÍCULO COMPLETO
// ─────────────────────────────────────────────
async function openArticle(url, title) {
  currentArticleUrl = url;
  currentPdfFilename = null;

  const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('articleModal'));
  document.getElementById('articleModalTitle').textContent = title || 'Artículo';
  document.getElementById('articleModalUrl').href = url;
  document.getElementById('articleModalUrlText').textContent = url;
  document.getElementById('articleModalLink').href = url;
  document.getElementById('articleModalContent').classList.add('d-none');
  document.getElementById('articleModalContent').innerHTML = '';
  hide('btnDownloadPDF');
  show('articleModalSpinner');
  modal.show();

  try {
    const res  = await fetch('/article', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, title }),
    });
    const data = await res.json();
    hide('articleModalSpinner');

    if (data.content) {
      const body = document.getElementById('articleModalContent');
      body.innerHTML = data.content
        .split('\n')
        .map(p => p.trim() ? `<p>${escapeHtml(p)}</p>` : '')
        .join('');
      body.classList.remove('d-none');
    }

    if (data.pdf_filename) {
      currentPdfFilename = data.pdf_filename;
      show('btnDownloadPDF');
    }
  } catch (err) {
    hide('articleModalSpinner');
    document.getElementById('articleModalContent').innerHTML =
      `<div class="alert alert-warning">Error al cargar el artículo: ${err.message}</div>`;
    document.getElementById('articleModalContent').classList.remove('d-none');
  }
}

function downloadArticlePDF() {
  if (!currentPdfFilename) return;
  const a = document.createElement('a');
  a.href = `/download-file/${encodeURIComponent(currentPdfFilename)}`;
  a.download = currentPdfFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast('PDF descargado correctamente.', 'success');
}

// ─────────────────────────────────────────────
//  RENDER VIDEOS
// ─────────────────────────────────────────────
function renderVideos(videos) {
  const grid = document.getElementById('videosGrid');
  if (!videos.length) { show('noVideosMsg'); return; }
  hide('noVideosMsg');

  videos.forEach((v, i) => {
    const thumb = v.thumbnail
      ? `<img class="video-thumb" src="${escapeHtml(v.thumbnail)}" alt="${escapeHtml(v.title)}" loading="lazy"
              onerror="this.parentElement.innerHTML+='<div class=\\'video-thumb-placeholder\\'><i class=\\'fas fa-film\\'></i></div>';this.remove()" />`
      : `<div class="video-thumb-placeholder"><i class="fas fa-film"></i></div>`;

    const typeLabel = v.type === 'youtube' ? 'YouTube' : v.type === 'vimeo' ? 'Vimeo' : 'Video';

    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-lg-4';
    col.innerHTML = `
      <div class="video-card" onclick="openVideo('${escapeHtml(v.embed)}','${escapeHtml(v.title)}')">
        ${thumb}
        <span class="video-type-badge">${typeLabel}</span>
        <div class="video-play-overlay"><i class="fas fa-play ms-1"></i></div>
        <div class="video-title">${escapeHtml(v.title)}</div>
      </div>`;
    grid.appendChild(col);
  });
}

function openVideo(embedUrl, title) {
  document.getElementById('videoModalTitle').textContent = title;
  document.getElementById('videoModalFrame').src = embedUrl;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('videoModal')).show();
}
function stopVideo() {
  document.getElementById('videoModalFrame').src = '';
}
document.getElementById('videoModal')?.addEventListener('hidden.bs.modal', stopVideo);

// ─────────────────────────────────────────────
//  RENDER TABLAS + DESCARGA CSV (cliente)
// ─────────────────────────────────────────────
function renderTables(tables) {
  const list = document.getElementById('tablasList');
  if (!tables.length) { show('noTablasMsg'); return; }
  hide('noTablasMsg');

  tables.forEach((tbl, idx) => {
    const previewRows = tbl.rows.slice(0, 6);
    const thHtml = tbl.headers.length
      ? '<tr>' + tbl.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('') + '</tr>'
      : '';
    const tdHtml = previewRows.map(row =>
      '<tr>' + row.map(c => `<td>${escapeHtml(c)}</td>`).join('') + '</tr>'
    ).join('');

    const card = document.createElement('div');
    card.className = 'table-card';
    card.innerHTML = `
      <div class="table-card-header">
        <i class="fas fa-table"></i>
        <span class="table-card-title">${escapeHtml(tbl.title)}</span>
        <span class="table-rows-label">${tbl.total_rows} filas × ${tbl.headers.length || '?'} columnas</span>
      </div>
      <div class="table-preview" id="tablePreview_${idx}">
        <table><thead>${thHtml}</thead><tbody>${tdHtml}</tbody></table>
      </div>
      <div class="table-card-footer">
        <button class="btn-csv" onclick="downloadCSV(${idx})">
          <i class="fas fa-file-csv me-1"></i>Descargar CSV completo
        </button>
        ${tbl.total_rows > 6 ? `<button class="table-expand-btn" onclick="expandTable(${idx})">
          <i class="fas fa-expand-alt me-1"></i>Ver todas las filas (${tbl.total_rows})
        </button>` : ''}
      </div>`;
    list.appendChild(card);

    // Guardar datos en dataset para CSV
    card.dataset.tableJson = JSON.stringify({ headers: tbl.headers, rows: tbl.rows, title: tbl.title });
  });
}

function downloadCSV(idx) {
  const card  = document.querySelectorAll('.table-card')[idx];
  const data  = JSON.parse(card.dataset.tableJson);
  const lines = [];

  if (data.headers.length) {
    lines.push(data.headers.map(h => `"${String(h).replace(/"/g,'""')}"`).join(','));
  }
  data.rows.forEach(row => {
    lines.push(row.map(c => `"${String(c).replace(/"/g,'""')}"`).join(','));
  });

  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href  = URL.createObjectURL(blob);
  a.download = (data.title || `tabla_${idx+1}`).replace(/[^\w\s]/g,'').trim().replace(/\s+/g,'_') + '.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast(`CSV "${a.download}" descargado.`, 'success');
}

function expandTable(idx) {
  const card = document.querySelectorAll('.table-card')[idx];
  const data = JSON.parse(card.dataset.tableJson);
  const thHtml = data.headers.length
    ? '<tr>' + data.headers.map(h => `<th>${escapeHtml(h)}</th>`).join('') + '</tr>'
    : '';
  const tdHtml = data.rows.map(row =>
    '<tr>' + row.map(c => `<td>${escapeHtml(c)}</td>`).join('') + '</tr>'
  ).join('');
  const preview = card.querySelector('.table-preview');
  preview.innerHTML = `<table><thead>${thHtml}</thead><tbody>${tdHtml}</tbody></table>`;
  preview.style.maxHeight = '500px';
  card.querySelector('.table-expand-btn')?.remove();
}

// ─────────────────────────────────────────────
//  RENDER ARCHIVOS
// ─────────────────────────────────────────────
const FILE_ICON_CLASS = {
  PDF:'fi-pdf', DOC:'fi-doc', DOCX:'fi-doc', XLS:'fi-xls', XLSX:'fi-xls',
  PPT:'fi-ppt', PPTX:'fi-pptx', ZIP:'fi-zip', RAR:'fi-rar',
  CSV:'fi-csv', JSON:'fi-json',
};

function renderFiles(files) {
  const list = document.getElementById('filesList');
  if (!files.length) { show('noFilesMsg'); return; }
  hide('noFilesMsg');

  files.forEach(file => {
    const iconCls = FILE_ICON_CLASS[file.type] || 'fi-default';
    const div = document.createElement('div');
    div.className = 'file-item';
    div.innerHTML = `
      <div class="file-icon ${iconCls}">${file.type}</div>
      <div class="file-info">
        <div class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</div>
        <div class="file-type-label">
          <i class="fas fa-tag me-1"></i>${file.type}
          &nbsp;·&nbsp;
          <a href="${escapeHtml(file.url)}" target="_blank" rel="noopener" class="text-muted text-decoration-none">
            <i class="fas fa-external-link-alt me-1"></i>Ver enlace
          </a>
        </div>
      </div>
      <button class="btn-download" onclick="downloadFile('${escapeHtml(file.url)}','${escapeHtml(file.filename)}',this)">
        <i class="fas fa-download me-1"></i>Descargar
      </button>`;
    list.appendChild(div);
  });
}

async function downloadFile(url, filename, btn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Descargando...';
  try {
    const res  = await fetch('/download', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ url, filename }),
    });
    const data = await res.json();
    if (data.success) {
      const a = document.createElement('a');
      a.href = `/download-file/${encodeURIComponent(data.filename)}`;
      a.download = data.filename;
      document.body.appendChild(a); a.click(); a.remove();
      btn.innerHTML = '<i class="fas fa-check me-1"></i>Listo';
      btn.style.background = 'linear-gradient(135deg,#64748b,#475569)';
      showToast(`"${data.filename}" descargado.`, 'success');
    } else throw new Error(data.error);
  } catch (err) {
    btn.disabled = false; btn.innerHTML = orig;
    showToast(`Error: ${err.message}`, 'error');
  }
}

// ─────────────────────────────────────────────
//  RENDER IMÁGENES
// ─────────────────────────────────────────────
function renderImages(images) {
  const grid = document.getElementById('imagesGrid');
  if (!images.length) { show('noImagesMsg'); return; }
  hide('noImagesMsg');

  images.forEach(img => {
    const col = document.createElement('div');
    col.className = 'col-6 col-sm-4 col-md-3 col-xl-2';
    col.innerHTML = `
      <div class="img-card" onclick="openImageModal('${escapeHtml(img.url)}','${escapeHtml(img.alt||img.filename)}')">
        <img src="${escapeHtml(img.url)}" alt="${escapeHtml(img.alt||img.filename)}"
             loading="lazy" onerror="this.closest('[class^=col]').remove()" />
        <div class="img-card-caption">${escapeHtml(img.alt||img.filename)}</div>
      </div>`;
    grid.appendChild(col);
  });
}

function openImageModal(url, alt) {
  document.getElementById('imgModalSrc').src = url;
  document.getElementById('imgModalAlt').textContent = alt;
  document.getElementById('imgModalDownload').href = url;
  document.getElementById('imgModalDL').href = url;
  document.getElementById('imgModalDL').download = alt || 'imagen';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('imgModal')).show();
}

// ─────────────────────────────────────────────
//  ANALIZAR URL — FUNCIÓN PRINCIPAL
// ─────────────────────────────────────────────
async function analyze() {
  const urlInput   = document.getElementById('urlInput');
  const useBrowser = document.getElementById('chkBrowser').checked;
  const url = urlInput.value.trim();

  if (!url) { urlInput.focus(); showToast('Ingresa una URL.', 'warning'); return; }

  resetResults();
  show('loadingSection');

  const loadingMsg = document.getElementById('loadingMsg');
  if (useBrowser) {
    loadingMsg.innerHTML = '<i class="fas fa-robot me-2"></i>Abriendo navegador Chrome... (puede tardar 20 segundos)';
  } else {
    loadingMsg.textContent = 'Analizando la página, por favor espera...';
  }

  // Contador regresivo visible para modo avanzado
  let countdownInterval = null;
  if (useBrowser) {
    let secs = 60;
    countdownInterval = setInterval(() => {
      secs--;
      loadingMsg.innerHTML = `<i class="fas fa-robot me-2"></i>Chrome abierto — esperando carga de la página... <strong>${secs}s</strong><br>
        <small class="text-warning">Si hay CAPTCHA, resuélvelo en la ventana de Chrome que se abrió.</small>`;
      if (secs <= 0) clearInterval(countdownInterval);
    }, 1000);
  }

  // Timeout de 3 minutos para selenium, 30s para modo normal
  const controller = new AbortController();
  const timeoutMs  = useBrowser ? 180000 : 30000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res  = await fetch('/scrape', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ url, use_browser: useBrowser, headless: false }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (countdownInterval) clearInterval(countdownInterval);
    const data = await res.json();
    hide('loadingSection');

    if (data.error) {
      document.getElementById('errorMsg').textContent = data.error;
      show('errorSection');
      return;
    }

    if (data.browser_warning) {
      showToast('Aviso: ' + data.browser_warning, 'warning');
    }

    // Info de la página
    document.getElementById('pageTitle').textContent = data.title || 'Sin título';
    document.getElementById('pageDesc').textContent  = data.description || '';
    document.getElementById('pageUrl').textContent   = data.url;
    document.getElementById('pageUrl').href          = data.url;

    // Stats
    document.getElementById('statNews').textContent   = data.stats.news_count;
    document.getElementById('statVideos').textContent = data.stats.videos_count;
    document.getElementById('statTables').textContent = data.stats.tables_count;
    document.getElementById('statFiles').textContent  = data.stats.files_count;
    document.getElementById('statImages').textContent = data.stats.images_count;

    document.getElementById('badgeNoticias').textContent = data.stats.news_count;
    document.getElementById('badgeVideos').textContent   = data.stats.videos_count;
    document.getElementById('badgeTablas').textContent   = data.stats.tables_count;
    document.getElementById('badgeArchivos').textContent = data.stats.files_count;
    document.getElementById('badgeImagenes').textContent = data.stats.images_count;

    scrapedData = data;   // ← guardar para export ZIP

    renderNews(data.news    || []);
    renderVideos(data.videos  || []);
    renderTables(data.tables  || []);
    renderFiles(data.files   || []);
    renderImages(data.images  || []);

    show('resultsSection');
    document.getElementById('resultsSection').scrollIntoView({ behavior:'smooth', block:'start' });

    // Resaltar tab con más contenido
    const counts = [
      { id:'tabNoticias', n: data.stats.news_count },
      { id:'tabVideos',   n: data.stats.videos_count },
      { id:'tabTablas',   n: data.stats.tables_count },
      { id:'tabArchivos', n: data.stats.files_count },
    ];
    const best = counts.reduce((a,b) => b.n > a.n ? b : a, counts[0]);
    if (best.n > 0) {
      document.querySelector(`[data-bs-target="#${best.id}"]`)?.click();
    }

  } catch (err) {
    clearTimeout(timer);
    if (countdownInterval) clearInterval(countdownInterval);
    hide('loadingSection');
    const msg = err.name === 'AbortError'
      ? 'Tiempo de espera agotado. La página tardó demasiado. Intenta sin Modo Avanzado.'
      : `Error de conexión: ${err.message}. Verifica que el servidor esté corriendo (python app.py).`;
    document.getElementById('errorMsg').textContent = msg;
    show('errorSection');
  }
}

// ─────────────────────────────────────────────
//  EXPORTACIÓN ZIP
// ─────────────────────────────────────────────

function setCheckState(id, state) {
  // state: 'waiting' | 'active' | 'done'
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'zip-check-item ' + (state === 'done' ? 'done' : state === 'active' ? 'active' : '');
  const icon = el.querySelector('i');
  if (state === 'done')   icon.className = 'fas fa-circle-check text-success me-2';
  else if (state === 'active') icon.className = 'fas fa-circle-notch fa-spin text-primary me-2';
  else                    icon.className = 'fas fa-circle text-muted me-2';
}

async function startExport() {
  if (!scrapedData) { showToast('Primero analiza una página.', 'warning'); return; }

  currentZipFilename = null;
  exportTaskId       = null;

  // Reset modal
  document.getElementById('zipProgressBar').style.width = '0%';
  document.getElementById('zipPercent').textContent     = '0%';
  document.getElementById('zipStatusMsg').textContent   = 'Iniciando...';
  document.getElementById('zipDoneSection').classList.add('d-none');
  document.getElementById('zipErrorSection').classList.add('d-none');
  ['chk-news','chk-files','chk-images','chk-zip'].forEach(id => setCheckState(id,'waiting'));
  setCheckState('chk-news', 'active');

  bootstrap.Modal.getOrCreateInstance(document.getElementById('zipModal')).show();

  try {
    const res  = await fetch('/start-export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        news:   scrapedData.news   || [],
        files:  scrapedData.files  || [],
        images: scrapedData.images || [],
        title:  scrapedData.title  || 'export',
      }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    exportTaskId = data.task_id;
    exportPollInterval = setInterval(pollExportStatus, 1500);
  } catch (err) {
    document.getElementById('zipErrorMsg').textContent = 'Error al iniciar: ' + err.message;
    document.getElementById('zipErrorSection').classList.remove('d-none');
  }
}

async function pollExportStatus() {
  if (!exportTaskId) return;
  try {
    const res  = await fetch(`/export-status/${exportTaskId}`);
    const task = await res.json();

    // Actualizar barra
    const pct = task.progress || 0;
    document.getElementById('zipProgressBar').style.width = pct + '%';
    document.getElementById('zipPercent').textContent     = pct + '%';
    document.getElementById('zipStatusMsg').textContent   = task.msg || '';

    // Actualizar checklist según progreso
    if (pct >= 5)  setCheckState('chk-news',   pct < 60 ? 'active' : 'done');
    if (pct >= 60) setCheckState('chk-files',  pct < 80 ? 'active' : 'done');
    if (pct >= 80) setCheckState('chk-images', pct < 93 ? 'active' : 'done');
    if (pct >= 93) setCheckState('chk-zip',    pct < 100 ? 'active' : 'done');

    if (task.status === 'done') {
      clearInterval(exportPollInterval);
      currentZipFilename = task.filename;
      // Barra verde al completar
      document.getElementById('zipProgressBar').classList.remove('bg-warning','progress-bar-animated');
      document.getElementById('zipProgressBar').classList.add('bg-success');
      document.getElementById('zipProgressBar').style.width = '100%';
      document.getElementById('zipPercent').textContent = '100%';
      ['chk-news','chk-files','chk-images','chk-zip'].forEach(id => setCheckState(id,'done'));
      document.getElementById('zipDoneMsg').textContent = task.msg;
      document.getElementById('zipDoneSection').classList.remove('d-none');
    }

    if (task.status === 'error') {
      clearInterval(exportPollInterval);
      document.getElementById('zipErrorMsg').textContent = task.msg;
      document.getElementById('zipErrorSection').classList.remove('d-none');
    }

  } catch (err) {
    clearInterval(exportPollInterval);
    document.getElementById('zipErrorMsg').textContent = 'Error de conexión: ' + err.message;
    document.getElementById('zipErrorSection').classList.remove('d-none');
  }
}

function downloadZip() {
  if (!currentZipFilename) return;
  const a = document.createElement('a');
  a.href     = `/download-file/${encodeURIComponent(currentZipFilename)}`;
  a.download = currentZipFilename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast('¡ZIP descargado!', 'success');
}

// ─────────────────────────────────────────────
//  EVENTOS
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btnAnalyze').addEventListener('click', analyze);
  document.getElementById('urlInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') analyze();
  });

  // Toggle info CAPTCHA
  document.getElementById('chkBrowser').addEventListener('change', function () {
    const info = document.getElementById('captchaInfo');
    this.checked ? info.classList.remove('d-none') : info.classList.add('d-none');
  });
});
