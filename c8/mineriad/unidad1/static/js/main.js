/* ===== WebScraper Pro v2 — main.js ===== */

let currentPdfFilename = null;
let currentArticleUrl  = null;
let scrapedData        = null;   // guarda los resultados del último scraping
let exportTaskId       = null;
let exportPollInterval = null;
let currentZipFilename = null;

// ── Compilar PDF de noticias ──
let compilePdfTaskId   = null;
let compilePdfInterval = null;
let compilePdfFilename = null;

// ── ZIP de documentos ──
let docsZipTaskId      = null;
let docsZipInterval    = null;
let docsZipFilename    = null;

// ── News sort/data ──
let _newsData     = [];
let _newsSortMode = 'cat';

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
  ['newsGrid','videosGrid','embedsGrid','tablasList','filesList','imagesGrid','audioList',
   'linksSummaryStats','topDomainsWrap'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
  });
  ['noNewsMsg','noVideosMsg','noTablasMsg','noFilesMsg','noImagesMsg','noAudioMsg'].forEach(hide);
  ['embedsSection','allLinksSection','pageSummaryRow'].forEach(id => {
    document.getElementById(id)?.classList.add('d-none');
  });
  document.getElementById('ogImage')?.classList.add('d-none');
  currentPdfFilename = null;
  // Reset news state
  _newsData     = [];
  _newsSortMode = 'cat';
  document.getElementById('sortBtnCat')?.classList.add('active');
  document.getElementById('sortBtnRel')?.classList.remove('active');
  // Reset filter count badges
  ['Todas','Regional','Educación','Salud','Deporte','Otros'].forEach(c => {
    const el = document.getElementById(`cnt-${c}`);
    if (el) el.textContent = '';
  });
  // Reset filter buttons
  document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
  document.querySelector('.btn-filter[data-cat="Todas"]')?.classList.add('active');
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
function _domainFromUrl(url) {
  try { return new URL(url).hostname.replace(/^www\./,''); } catch { return ''; }
}

function renderNews(newsArray) {
  _newsData = newsArray || [];
  _doRenderNews();
}

function _doRenderNews() {
  const grid = document.getElementById('newsGrid');
  grid.innerHTML = '';

  if (!_newsData.length) { hide('newsGrid'); show('noNewsMsg'); return; }
  hide('noNewsMsg');

  // Conteo por categoría
  const counts = {};
  _newsData.forEach(item => {
    counts[item.category] = (counts[item.category] || 0) + 1;
  });
  counts['Todas'] = _newsData.length;

  // Actualizar badges de filtro
  Object.entries(counts).forEach(([cat, n]) => {
    const el = document.getElementById(`cnt-${cat}`);
    if (el) el.textContent = ` (${n})`;
  });

  // Ordenar
  let sorted = [..._newsData];
  if (_newsSortMode === 'cat') {
    const ORDER = { Regional:0, Educación:1, Salud:2, Deporte:3, Otros:4 };
    sorted.sort((a,b) => (ORDER[a.category] ?? 99) - (ORDER[b.category] ?? 99));
  }
  // 'rel' → original order (no sort)

  // Obtener filtro activo
  const activeCat = document.querySelector('.btn-filter.active')?.dataset?.cat || 'Todas';

  sorted.forEach(item => {
    const cfg    = catCfg(item.category);
    const domain = _domainFromUrl(item.link);
    const imgHtml = item.image
      ? `<img class="news-card-img" src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}"
              loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'news-card-img-placeholder\\'><i class=\\'fas fa-newspaper\\'></i></div>'" />`
      : `<div class="news-card-img-placeholder"><i class="fas fa-newspaper"></i></div>`;

    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-lg-4 col-xl-3 news-item';
    col.dataset.category = item.category;
    if (activeCat !== 'Todas' && item.category !== activeCat) col.style.display = 'none';

    col.innerHTML = `
      <div class="news-card" onclick="openArticle('${escapeHtml(item.link)}','${escapeHtml(item.title)}')">
        ${imgHtml}
        <div class="news-card-body">
          ${domain ? `<div class="news-domain-badge">${escapeHtml(domain)}</div>` : ''}
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

function toggleNewsSort(mode, btn) {
  _newsSortMode = mode;
  document.querySelectorAll('.btn-sort-news').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  _doRenderNews();
}

// ─────────────────────────────────────────────
//  COMPILAR NOTICIAS EN PDF
// ─────────────────────────────────────────────
async function compileNewsPDF() {
  if (!_newsData.length) { showToast('No hay noticias para compilar.', 'warning'); return; }
  compilePdfFilename = null;

  // Reset modal
  document.getElementById('compilePdfBar').style.width  = '0%';
  document.getElementById('compilePdfBar').className    = 'progress-bar progress-bar-striped progress-bar-animated bg-danger';
  document.getElementById('compilePdfPct').textContent  = '0%';
  document.getElementById('compilePdfMsg').textContent  = 'Iniciando...';
  document.getElementById('compilePdfDone').classList.add('d-none');
  document.getElementById('compilePdfError').classList.add('d-none');

  bootstrap.Modal.getOrCreateInstance(document.getElementById('compilePdfModal')).show();

  try {
    const res  = await fetch('/compile-news', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ news: _newsData, title: scrapedData?.title || 'Noticias' }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    compilePdfTaskId = data.task_id;
    compilePdfInterval = setInterval(pollCompilePdfStatus, 1500);
  } catch (err) {
    document.getElementById('compilePdfErrorMsg').textContent = 'Error al iniciar: ' + err.message;
    document.getElementById('compilePdfError').classList.remove('d-none');
  }
}

async function pollCompilePdfStatus() {
  if (!compilePdfTaskId) return;
  try {
    const res  = await fetch(`/compile-status/${compilePdfTaskId}`);
    const task = await res.json();
    const pct  = task.progress || 0;

    document.getElementById('compilePdfBar').style.width = pct + '%';
    document.getElementById('compilePdfPct').textContent = pct + '%';
    document.getElementById('compilePdfMsg').textContent = task.msg || '';

    if (task.status === 'done') {
      clearInterval(compilePdfInterval);
      compilePdfFilename = task.filename;
      document.getElementById('compilePdfBar').classList.remove('bg-danger','progress-bar-animated');
      document.getElementById('compilePdfBar').classList.add('bg-success');
      document.getElementById('compilePdfBar').style.width = '100%';
      document.getElementById('compilePdfPct').textContent = '100%';
      document.getElementById('compilePdfDoneMsg').textContent = task.msg;
      document.getElementById('compilePdfDone').classList.remove('d-none');
      showToast('¡PDF compilado listo!', 'success');
    }
    if (task.status === 'error') {
      clearInterval(compilePdfInterval);
      document.getElementById('compilePdfErrorMsg').textContent = task.msg;
      document.getElementById('compilePdfError').classList.remove('d-none');
    }
  } catch (err) {
    clearInterval(compilePdfInterval);
    document.getElementById('compilePdfErrorMsg').textContent = 'Error de conexión: ' + err.message;
    document.getElementById('compilePdfError').classList.remove('d-none');
  }
}

function downloadCompilePdf() {
  if (!compilePdfFilename) return;
  const a = document.createElement('a');
  a.href = `/download-file/${encodeURIComponent(compilePdfFilename)}`;
  a.download = compilePdfFilename;
  document.body.appendChild(a); a.click(); a.remove();
  showToast('PDF compilado descargado.', 'success');
}

// ─────────────────────────────────────────────
//  ZIP DE DOCUMENTOS
// ─────────────────────────────────────────────
async function startDocsZip() {
  if (!scrapedData?.files?.length) { showToast('No hay documentos para descargar.', 'warning'); return; }
  docsZipFilename = null;

  document.getElementById('docsZipBar').style.width  = '0%';
  document.getElementById('docsZipBar').className    = 'progress-bar progress-bar-striped progress-bar-animated bg-info';
  document.getElementById('docsZipPct').textContent  = '0%';
  document.getElementById('docsZipMsg').textContent  = 'Iniciando...';
  document.getElementById('docsZipDone').classList.add('d-none');
  document.getElementById('docsZipError').classList.add('d-none');

  bootstrap.Modal.getOrCreateInstance(document.getElementById('docsZipModal')).show();

  try {
    const res  = await fetch('/docs-zip', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ files: scrapedData.files, title: scrapedData?.title || 'Documentos' }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    docsZipTaskId = data.task_id;
    docsZipInterval = setInterval(pollDocsZipStatus, 1500);
  } catch (err) {
    document.getElementById('docsZipErrorMsg').textContent = 'Error al iniciar: ' + err.message;
    document.getElementById('docsZipError').classList.remove('d-none');
  }
}

async function pollDocsZipStatus() {
  if (!docsZipTaskId) return;
  try {
    const res  = await fetch(`/docs-zip-status/${docsZipTaskId}`);
    const task = await res.json();
    const pct  = task.progress || 0;

    document.getElementById('docsZipBar').style.width = pct + '%';
    document.getElementById('docsZipPct').textContent = pct + '%';
    document.getElementById('docsZipMsg').textContent = task.msg || '';

    if (task.status === 'done') {
      clearInterval(docsZipInterval);
      docsZipFilename = task.filename;
      document.getElementById('docsZipBar').classList.remove('bg-info','progress-bar-animated');
      document.getElementById('docsZipBar').classList.add('bg-success');
      document.getElementById('docsZipBar').style.width = '100%';
      document.getElementById('docsZipPct').textContent = '100%';
      document.getElementById('docsZipDoneMsg').textContent = task.msg;
      document.getElementById('docsZipDone').classList.remove('d-none');
      showToast('¡ZIP de documentos listo!', 'success');
    }
    if (task.status === 'error') {
      clearInterval(docsZipInterval);
      document.getElementById('docsZipErrorMsg').textContent = task.msg;
      document.getElementById('docsZipError').classList.remove('d-none');
    }
  } catch (err) {
    clearInterval(docsZipInterval);
    document.getElementById('docsZipErrorMsg').textContent = 'Error de conexión: ' + err.message;
    document.getElementById('docsZipError').classList.remove('d-none');
  }
}

function downloadDocsZip() {
  if (!docsZipFilename) return;
  const a = document.createElement('a');
  a.href = `/download-file/${encodeURIComponent(docsZipFilename)}`;
  a.download = docsZipFilename;
  document.body.appendChild(a); a.click(); a.remove();
  showToast('ZIP de documentos descargado.', 'success');
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
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 30000);
    const res  = await fetch('/article', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, title }),
      signal: ctrl.signal,
    });
    clearTimeout(t);
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
  CSV:'fi-csv', JSON:'fi-json', TXT:'fi-txt', KML:'fi-kml',
  MP4:'fi-video', AVI:'fi-video', MOV:'fi-video', MKV:'fi-video',
  MP3:'fi-audio', WAV:'fi-audio', OGG:'fi-audio',
};

function formatFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/1048576).toFixed(1) + ' MB';
}

function trackDirectDownload(url, filename) {
  showToast(`Descargando "${filename}" directamente…`, 'info');
}

function renderFiles(files) {
  const list = document.getElementById('filesList');
  if (!files.length) { show('noFilesMsg'); return; }
  hide('noFilesMsg');

  files.forEach(file => {
    const iconCls  = FILE_ICON_CLASS[file.type] || 'fi-default';
    const sizeText = file.size ? `<span class="text-muted small ms-2">${formatFileSize(file.size)}</span>` : '';
    const div = document.createElement('div');
    div.className = 'file-item';
    div.innerHTML = `
      <div class="file-icon ${iconCls}">${file.type}</div>
      <div class="file-info">
        <div class="file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}${sizeText}</div>
        <div class="file-type-label">
          <i class="fas fa-tag me-1"></i>${file.type}
          &nbsp;·&nbsp;
          <a href="${escapeHtml(file.url)}" target="_blank" rel="noopener" class="text-muted text-decoration-none">
            <i class="fas fa-external-link-alt me-1"></i>Ver enlace
          </a>
        </div>
      </div>
      <div class="d-flex gap-2 align-items-center flex-shrink-0">
        <a href="${escapeHtml(file.url)}" download="${escapeHtml(file.filename)}"
           class="btn-dl-direct" target="_blank" rel="noopener"
           onclick="trackDirectDownload('${escapeHtml(file.url)}','${escapeHtml(file.filename)}')">
          <i class="fas fa-link"></i>Directo
        </a>
        <button class="btn-download" onclick="downloadFile('${escapeHtml(file.url)}','${escapeHtml(file.filename)}',this)">
          <i class="fas fa-download me-1"></i>Proxy
        </button>
      </div>`;
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
//  RENDER IMÁGENES (con carga progresiva)
// ─────────────────────────────────────────────
let _allImages   = [];
let _imgsShown   = 0;
const IMGS_BATCH = 60;

function renderImages(images) {
  _allImages = images;
  _imgsShown = 0;
  const grid = document.getElementById('imagesGrid');
  // Eliminar botón previo si existe
  document.getElementById('loadMoreImgsBtn')?.remove();

  if (!images.length) { show('noImagesMsg'); return; }
  hide('noImagesMsg');

  // Actualizar badge con total real
  document.getElementById('statImages').textContent  = images.length;
  document.getElementById('badgeImagenes').textContent = images.length;

  _renderImageBatch(grid);
}

function _renderImageBatch(grid) {
  const batch = _allImages.slice(_imgsShown, _imgsShown + IMGS_BATCH);
  batch.forEach(img => {
    const col = document.createElement('div');
    col.className = 'col-6 col-sm-4 col-md-3 col-xl-2';
    col.innerHTML = `
      <div class="img-card" onclick="openImageModal('${escapeHtml(img.url)}','${escapeHtml(img.alt||img.filename)}')">
        <img src="${escapeHtml(img.url)}" alt="${escapeHtml(img.alt||img.filename)}"
             loading="lazy" onerror="this.closest('.col-6, .col-sm-4').remove()" />
        <div class="img-card-caption">${escapeHtml(img.alt||img.filename||'imagen')}</div>
      </div>`;
    grid.appendChild(col);
  });
  _imgsShown += batch.length;

  // Eliminar botón viejo
  document.getElementById('loadMoreImgsBtn')?.remove();

  // Añadir botón "Cargar más" si quedan imágenes
  if (_imgsShown < _allImages.length) {
    const remaining = _allImages.length - _imgsShown;
    const btn = document.createElement('div');
    btn.id = 'loadMoreImgsBtn';
    btn.className = 'col-12 text-center mt-3';
    btn.innerHTML = `
      <button class="btn btn-outline-primary px-4" onclick="_renderImageBatch(document.getElementById('imagesGrid'))">
        <i class="fas fa-images me-2"></i>Cargar ${Math.min(remaining, IMGS_BATCH)} más
        <span class="badge bg-primary ms-2">${remaining} restantes</span>
      </button>`;
    grid.appendChild(btn);
  }
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
//  BADGE DE MÉTODO DE FETCH
// ─────────────────────────────────────────────
const FETCH_METHOD_INFO = {
  'requests':          { label:'requests',           color:'#64748b', icon:'fa-bolt'         },
  'curl_cffi':         { label:'curl_cffi (TLS)',    color:'#0891b2', icon:'fa-shield-halved' },
  'cloudscraper':      { label:'cloudscraper (CF)',  color:'#d97706', icon:'fa-cloud-bolt'    },
  'reddit-api':        { label:'Reddit API',         color:'#ff4500', icon:'fa-reddit'        },
  'undetected-chrome': { label:'Chrome Stealth',     color:'#7c3aed', icon:'fa-user-secret'   },
  'selenium':          { label:'Selenium',           color:'#16a34a', icon:'fa-robot'         },
};

function renderFetchBadge(method, neededJs) {
  const info = FETCH_METHOD_INFO[method] || { label: method || '?', color:'#94a3b8', icon:'fa-circle-info' };
  // Inyectar junto al título de la página
  let badge = document.getElementById('fetchMethodBadge');
  if (!badge) {
    badge = document.createElement('span');
    badge.id = 'fetchMethodBadge';
    badge.style.cssText = 'display:inline-flex;align-items:center;gap:4px;font-size:.7rem;font-weight:600;padding:2px 9px;border-radius:20px;color:#fff;margin-left:8px;vertical-align:middle;';
    const titleEl = document.getElementById('pageTitle');
    if (titleEl) titleEl.after(badge);
  }
  badge.style.background = info.color;
  badge.innerHTML = `<i class="fas ${info.icon}"></i>${info.label}`;
  badge.title = `Extraído con: ${info.label}`;
}

// ─────────────────────────────────────────────
//  RESUMEN DE PÁGINA (tipo, autor, fecha, og)
// ─────────────────────────────────────────────
const PAGE_TYPE_COLORS = {
  'Noticias':'#2563eb','Blog':'#7c3aed','Gobierno':'#dc2626',
  'Académico':'#0891b2','Wiki':'#16a34a','Comercio':'#ea580c',
  'Red Social':'#db2777','Portal':'#64748b','Otro':'#94a3b8',
};

function renderPageSummary(data) {
  const meta  = data.metadata || {};
  const ptype = data.page_type || 'Otro';
  const row   = document.getElementById('pageSummaryRow');

  // Badge tipo de página
  const badge = document.getElementById('pageTypeBadge');
  badge.textContent = ptype;
  badge.style.background = PAGE_TYPE_COLORS[ptype] || '#94a3b8';

  // og:image
  if (meta.og_image) {
    const img = document.getElementById('ogImage');
    img.src = meta.og_image;
    img.classList.remove('d-none');
    img.onerror = () => img.classList.add('d-none');
  }

  // site_name
  const siteNameEl = document.getElementById('pageSiteName');
  siteNameEl.textContent = meta.site_name || '';

  // Autor
  if (meta.author) {
    document.getElementById('pageAuthorText').textContent = meta.author;
    document.getElementById('pageAuthor').classList.remove('d-none');
  }

  // Fecha
  if (meta.published_date) {
    document.getElementById('pagePublishedDateText').textContent = meta.published_date;
    document.getElementById('pagePublishedDate').classList.remove('d-none');
  }

  // Idioma
  if (meta.language) {
    document.getElementById('pageLanguageText').textContent = meta.language.toUpperCase();
    document.getElementById('pageLanguage').classList.remove('d-none');
  }

  row.classList.remove('d-none');
}

// ─────────────────────────────────────────────
//  EMBEDS (YouTube, Vimeo, Twitter, etc.)
// ─────────────────────────────────────────────
const EMBED_COLORS = {
  youtube:'#ff0000', vimeo:'#1ab7ea', twitter:'#1da1f2', instagram:'#e1306c',
  tiktok:'#010101', facebook:'#1877f2', maps:'#34a853', spotify:'#1db954',
  dailymotion:'#f7821b', twitch:'#9146ff', soundcloud:'#ff5500',
};

function renderEmbeds(embeds) {
  const grid    = document.getElementById('embedsGrid');
  const section = document.getElementById('embedsSection');
  const badge   = document.getElementById('badgeEmbeds');
  badge.textContent = embeds.length;
  document.getElementById('statEmbeds').textContent = embeds.length;
  if (!embeds.length) return;
  section.classList.remove('d-none');
  hide('noVideosMsg');

  embeds.forEach(e => {
    const color = EMBED_COLORS[e.type] || '#6b7280';
    const thumb = e.thumbnail
      ? `<img src="${escapeHtml(e.thumbnail)}" alt="${escapeHtml(e.title)}" class="embed-thumb"
             loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'embed-thumb-ph\\'style=\\'background:${color}22\\'><i class=\\'fas fa-play-circle\\'style=\\'color:${color}\\'></i></div>'"/>`
      : `<div class="embed-thumb-ph" style="background:${color}22"><i class="fas fa-play-circle" style="color:${color};font-size:2.5rem"></i></div>`;

    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-md-4';
    col.innerHTML = `
      <div class="embed-card" onclick="openVideo('${escapeHtml(e.url)}','${escapeHtml(e.title)}')">
        ${thumb}
        <span class="embed-type-badge" style="background:${color}">${escapeHtml(e.type)}</span>
        <div class="embed-title">${escapeHtml(e.title)}</div>
      </div>`;
    grid.appendChild(col);
  });
}

// ─────────────────────────────────────────────
//  AUDIO
// ─────────────────────────────────────────────
function renderAudio(audioList) {
  const list  = document.getElementById('audioList');
  const badge = document.getElementById('badgeAudio');
  badge.textContent = audioList.length;
  document.getElementById('statAudio').textContent = audioList.length;
  if (!audioList.length) { show('noAudioMsg'); return; }
  hide('noAudioMsg');

  const ICONS = { html5:'fa-volume-high', direct:'fa-file-audio', rss:'fa-rss', soundcloud:'fa-cloud' };
  audioList.forEach(item => {
    const icon = ICONS[item.type] || 'fa-music';
    const isPlayable = item.type === 'html5' || item.type === 'direct';
    const playerHtml = isPlayable
      ? `<audio controls class="w-100 mt-2" style="height:34px;" preload="none">
           <source src="${escapeHtml(item.url)}" />
         </audio>`
      : `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener"
            class="btn btn-sm btn-outline-primary mt-2">
           <i class="fas fa-external-link-alt me-1"></i>Abrir enlace
         </a>`;

    const div = document.createElement('div');
    div.className = 'audio-item';
    div.innerHTML = `
      <div class="audio-icon"><i class="fas ${icon}"></i></div>
      <div class="flex-grow-1" style="min-width:0">
        <div class="audio-title">${escapeHtml(item.title)}</div>
        <div class="audio-type text-muted">${escapeHtml(item.type.toUpperCase())}</div>
        ${playerHtml}
      </div>`;
    list.appendChild(div);
  });
}

// ─────────────────────────────────────────────
//  ANÁLISIS DE ENLACES
// ─────────────────────────────────────────────
function renderAllLinks(allLinks) {
  if (!allLinks || allLinks.total === 0) return;
  const section = document.getElementById('allLinksSection');
  section.classList.remove('d-none');
  document.getElementById('statLinks').textContent = allLinks.total;
  document.getElementById('allLinksLabel').textContent =
    `Análisis de enlaces · ${allLinks.total} total`;

  const stats = document.getElementById('linksSummaryStats');
  stats.innerHTML = `
    <div class="links-stat">
      <div class="n text-primary">${allLinks.internal}</div>
      <div class="l"><i class="fas fa-house me-1"></i>Internos</div>
    </div>
    <div class="links-stat">
      <div class="n text-success">${allLinks.external}</div>
      <div class="l"><i class="fas fa-external-link-alt me-1"></i>Externos</div>
    </div>
    <div class="links-stat">
      <div class="n text-secondary">${allLinks.total}</div>
      <div class="l"><i class="fas fa-link me-1"></i>Total</div>
    </div>`;

  if (!allLinks.top_domains?.length) return;
  const rows = allLinks.top_domains.map(d =>
    `<tr><td>${escapeHtml(d.domain)}</td>
         <td class="text-end"><span class="badge bg-secondary">${d.count}</span></td></tr>`
  ).join('');
  document.getElementById('topDomainsWrap').innerHTML = `
    <p class="fw-semibold small text-muted mt-3 mb-1">Top dominios externos:</p>
    <table class="top-domains-table">
      <thead><tr><th>Dominio</th><th class="text-end">Links</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
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
    loadingMsg.innerHTML = '<i class="fas fa-user-secret me-2"></i>Modo Avanzado activado — Chrome Stealth iniciando... <span class="text-warning">(20-40 s)</span>';
  } else {
    loadingMsg.innerHTML = '<i class="fas fa-shield-halved me-2"></i>Analizando… probando capas automáticas de bypass';
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

    // Badge de método de fetch
    renderFetchBadge(data.fetch_method, data.needed_js);

    renderNews(data.news      || []);
    renderVideos(data.videos  || []);
    renderEmbeds(data.embeds  || []);
    renderTables(data.tables  || []);
    renderFiles(data.files    || []);
    renderImages(data.images  || []);
    renderAudio(data.audio    || []);
    renderAllLinks(data.all_links || {});
    renderPageSummary(data);

    // Stats nuevos
    document.getElementById('statLinks').textContent  = data.stats?.links_total  || 0;

    show('resultsSection');
    document.getElementById('resultsSection').scrollIntoView({ behavior:'smooth', block:'start' });

    // Resaltar tab con más contenido
    const counts = [
      { id:'tabNoticias', n: data.stats.news_count    || 0 },
      { id:'tabVideos',   n: (data.stats.videos_count || 0) + (data.stats.embeds_count || 0) },
      { id:'tabTablas',   n: data.stats.tables_count  || 0 },
      { id:'tabArchivos', n: data.stats.files_count   || 0 },
      { id:'tabAudio',    n: data.stats.audio_count   || 0 },
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
