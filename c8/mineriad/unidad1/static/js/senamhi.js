/* ===== SENAMHI — senamhi.js ===== */

let allStations   = [];
let currentTaskId = null;
let pollInterval  = null;
let currentZip    = null;
let singleCsvData = null;   // { headers, rows, name }

// ── Utilidades ──────────────────────────────────────────────────
function show(id) { document.getElementById(id).classList.remove('d-none'); }
function hide(id) { document.getElementById(id).classList.add('d-none'); }

function showToast(msg, type = 'success') {
  const el = document.getElementById('toastMsg');
  el.classList.remove('bg-success','bg-danger','bg-warning','bg-info');
  el.classList.add(type === 'success' ? 'bg-success'
                 : type === 'error'   ? 'bg-danger'
                 : type === 'warning' ? 'bg-warning' : 'bg-info');
  document.getElementById('toastText').textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 3500 }).show();
}

function escHtml(s) {
  return String(s || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function typeBadge(type) {
  const t = (type || '').toLowerCase();
  if (t.includes('conv'))  return `<span class="type-badge type-conv">${escHtml(type)}</span>`;
  if (t.includes('auto'))  return `<span class="type-badge type-auto">${escHtml(type)}</span>`;
  return type ? `<span class="type-badge type-other">${escHtml(type)}</span>` : '—';
}

// ── Buscar estaciones ───────────────────────────────────────────
async function buscarEstaciones() {
  const region = document.getElementById('selRegion').value;
  const useSelenium = document.getElementById('chkSelenium').checked;

  if (!region) { showToast('Selecciona una región primero.', 'warning'); return; }

  hide('resultsSection');
  hide('errorSection');
  show('loadingSection');
  document.getElementById('loadingMsg').textContent =
    useSelenium ? 'Abriendo navegador para cargar estaciones...' : 'Buscando estaciones...';

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);

  try {
    const res  = await fetch('/senamhi/stations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ region, use_selenium: useSelenium }),
      signal: controller.signal,
    });
    clearTimeout(timer);
    const data = await res.json();
    hide('loadingSection');

    if (data.error && !data.stations?.length) {
      document.getElementById('errorMsg').textContent = data.error;
      show('errorSection');
      return;
    }

    allStations = data.stations || [];
    renderStations(allStations);

    document.getElementById('regionTitle').textContent = data.region_name || region;
    document.getElementById('totalCount').textContent  = allStations.length;
    document.getElementById('selectedCount').textContent = 0;

    show('resultsSection');
    document.getElementById('resultsSection').scrollIntoView({ behavior:'smooth' });

    if (data.warning) showToast('Aviso: ' + data.warning, 'warning');
    if (!allStations.length) showToast('No se encontraron estaciones. Prueba activando Selenium.', 'warning');

  } catch (err) {
    clearTimeout(timer);
    hide('loadingSection');
    const msg = err.name === 'AbortError'
      ? 'Tiempo agotado. Activa el modo Selenium e intenta de nuevo.'
      : 'Error de conexión. Verifica que el servidor esté corriendo (python app.py).';
    document.getElementById('errorMsg').textContent = msg;
    show('errorSection');
  }
}

// ── Renderizar tabla ────────────────────────────────────────────
function renderStations(list) {
  const tbody = document.getElementById('stationsBody');
  tbody.innerHTML = '';

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">
      <i class="fas fa-satellite-dish fs-2 d-block mb-2"></i>
      No se encontraron estaciones para esta región.
    </td></tr>`;
    return;
  }

  list.forEach((st, i) => {
    const tr = document.createElement('tr');
    tr.dataset.idx = i;
    tr.innerHTML = `
      <td>
        <input type="checkbox" class="form-check-input station-chk"
               onchange="updateSelectedCount()" data-idx="${i}"/>
      </td>
      <td class="fw-semibold">${escHtml(st.name)}</td>
      <td><code class="text-primary">${escHtml(st.code) || '—'}</code></td>
      <td>${typeBadge(st.type)}</td>
      <td>${escHtml(st.dept) || '—'}</td>
      <td>${escHtml(st.alt)  || '—'}</td>
      <td>
        <button class="btn-view-data" onclick="verDatos(${i})">
          <i class="fas fa-table me-1"></i>Ver datos
        </button>
      </td>`;
    tbody.appendChild(tr);
  });
}

// ── Filtro ──────────────────────────────────────────────────────
function filterStations(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('#stationsBody tr[data-idx]').forEach(tr => {
    const name = tr.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || '';
    const code = tr.querySelector('td:nth-child(3)')?.textContent.toLowerCase() || '';
    tr.style.display = (name.includes(q) || code.includes(q)) ? '' : 'none';
  });
}

// ── Selección ───────────────────────────────────────────────────
function toggleAll(checked) {
  document.querySelectorAll('.station-chk').forEach(chk => {
    chk.checked = checked;
    chk.closest('tr').classList.toggle('selected-row', checked);
  });
  document.getElementById('chkAll').checked = checked;
  updateSelectedCount();
}

function updateSelectedCount() {
  const selected = document.querySelectorAll('.station-chk:checked').length;
  document.getElementById('selectedCount').textContent = selected;
  document.querySelectorAll('.station-chk').forEach(chk => {
    chk.closest('tr').classList.toggle('selected-row', chk.checked);
  });
}

// ── Ver datos de UNA estación ───────────────────────────────────
async function verDatos(idx) {
  const st = allStations[idx];
  if (!st) return;

  singleCsvData = null;
  document.getElementById('stationDataTitle').textContent = st.name;
  document.getElementById('stationDataContent').classList.add('d-none');
  document.getElementById('stationDataEmpty').classList.add('d-none');
  document.getElementById('btnDownloadSingle').classList.add('d-none');
  show('stationDataSpinner');

  bootstrap.Modal.getOrCreateInstance(document.getElementById('stationDataModal')).show();

  // Usar la ruta de scrape normal con la URL de la estación
  try {
    const url = st.link || `https://www.senamhi.gob.pe/main.php?dp=${st.region}&p=estaciones`;
    const res  = await fetch('/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, use_browser: false }),
    });
    const data = await res.json();
    hide('stationDataSpinner');

    if (data.tables && data.tables.length > 0) {
      const tbl = data.tables[0];
      singleCsvData = { headers: tbl.headers, rows: tbl.rows, name: st.name };

      // Renderizar tabla
      const thHtml = tbl.headers.length
        ? '<tr>' + tbl.headers.map(h => `<th class="bg-light">${escHtml(h)}</th>`).join('') + '</tr>'
        : '';
      const tdHtml = tbl.rows.slice(0, 100).map(row =>
        '<tr>' + row.map(c => `<td>${escHtml(c)}</td>`).join('') + '</tr>'
      ).join('');

      document.getElementById('stationDataTable').innerHTML = `
        <p class="text-muted small mb-2">
          Mostrando ${Math.min(tbl.rows.length, 100)} de ${tbl.total_rows} registros
        </p>
        <table class="table table-sm table-bordered table-hover" style="font-size:.82rem;">
          <thead>${thHtml}</thead>
          <tbody>${tdHtml}</tbody>
        </table>`;

      show('stationDataContent');
      document.getElementById('btnDownloadSingle').classList.remove('d-none');
    } else {
      show('stationDataEmpty');
    }
  } catch (err) {
    hide('stationDataSpinner');
    show('stationDataEmpty');
  }
}

// ── Descargar CSV de una estación (cliente) ─────────────────────
function downloadSingleCSV() {
  if (!singleCsvData) return;
  const { headers, rows, name } = singleCsvData;
  const lines = [];
  if (headers.length) lines.push(headers.map(h => `"${String(h).replace(/"/g,'""')}"`).join(','));
  rows.forEach(r => lines.push(r.map(c => `"${String(c).replace(/"/g,'""')}"`).join(',')));
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type:'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `senamhi_${name.replace(/[^\w]/g,'_')}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  showToast('CSV descargado.', 'success');
}

// ── Descargar todas las seleccionadas (ZIP background) ──────────
async function descargarSeleccionadas() {
  const selected = [];
  document.querySelectorAll('.station-chk:checked').forEach(chk => {
    const idx = parseInt(chk.dataset.idx);
    if (!isNaN(idx) && allStations[idx]) selected.push(allStations[idx]);
  });

  if (!selected.length) {
    showToast('Selecciona al menos una estación.', 'warning'); return;
  }

  const regionName = document.getElementById('regionTitle').textContent;

  // Reset modal
  currentZip = null;
  document.getElementById('dlProgressBar').style.width  = '0%';
  document.getElementById('dlProgressBar').className    =
    'progress-bar progress-bar-striped progress-bar-animated bg-primary';
  document.getElementById('dlPercent').textContent      = '0%';
  document.getElementById('dlStatusMsg').textContent    = 'Iniciando...';
  document.getElementById('dlDoneSection').classList.add('d-none');
  document.getElementById('dlErrorSection').classList.add('d-none');
  document.getElementById('currentStationBox').classList.add('d-none');

  bootstrap.Modal.getOrCreateInstance(document.getElementById('progressModal')).show();

  try {
    const res  = await fetch('/senamhi/download-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stations: selected, region_name: regionName }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    currentTaskId = data.task_id;
    pollInterval  = setInterval(pollStatus, 1800);
  } catch (err) {
    document.getElementById('dlErrorMsg').textContent = err.message;
    show('dlErrorSection');
  }
}

// ── Polling de estado ───────────────────────────────────────────
async function pollStatus() {
  if (!currentTaskId) return;
  try {
    const res  = await fetch(`/senamhi/status/${currentTaskId}`);
    const task = await res.json();

    const pct = task.progress || 0;
    document.getElementById('dlProgressBar').style.width = pct + '%';
    document.getElementById('dlPercent').textContent     = pct + '%';
    document.getElementById('dlStatusMsg').textContent   = task.msg || '';

    if (task.msg && task.status === 'working') {
      show('currentStationBox');
      document.getElementById('currentStationName').textContent = task.msg;
    }

    if (task.status === 'done') {
      clearInterval(pollInterval);
      currentZip = task.filename;
      document.getElementById('dlProgressBar').style.width = '100%';
      document.getElementById('dlProgressBar').className   = 'progress-bar bg-success';
      document.getElementById('dlPercent').textContent     = '100%';
      hide('currentStationBox');
      document.getElementById('dlDoneMsg').textContent = task.msg;
      show('dlDoneSection');
    }

    if (task.status === 'error') {
      clearInterval(pollInterval);
      document.getElementById('dlErrorMsg').textContent = task.msg;
      show('dlErrorSection');
    }
  } catch (err) {
    clearInterval(pollInterval);
    document.getElementById('dlErrorMsg').textContent = 'Error de conexión: ' + err.message;
    show('dlErrorSection');
  }
}

// ── Descargar ZIP ───────────────────────────────────────────────
function downloadZipFile() {
  if (!currentZip) return;
  const a = document.createElement('a');
  a.href = `/download-file/${encodeURIComponent(currentZip)}`;
  a.download = currentZip;
  document.body.appendChild(a); a.click(); a.remove();
  showToast('¡ZIP descargado!', 'success');
}

// ── Enter en selector de región ─────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('selRegion').addEventListener('keydown', e => {
    if (e.key === 'Enter') buscarEstaciones();
  });
});
