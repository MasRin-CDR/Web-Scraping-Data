'use strict';

/* ============================================================
   CONFIG
   ============================================================ */
const API_CANDIDATES = [
  window.MAHKAMAH_API_BASE,
  window.location.protocol === 'file:' ? null : `${window.location.origin}/api`,
  'http://127.0.0.1:8000/api',
  'http://localhost:8000/api',
].filter(Boolean).map(url => url.replace(/\/$/, ''));

let API_BASE = API_CANDIDATES[0] || 'http://127.0.0.1:8000/api';
let backendReady = false;

/* ============================================================
   DATA
   ============================================================ */
const LOKASI_LIST = [
  'Mahkamah Agung RI, Jakarta',
  'PN Jakarta Pusat','PN Jakarta Selatan','PN Jakarta Utara','PN Jakarta Barat','PN Jakarta Timur',
  'PN Bandung','PN Bekasi','PN Depok','PN Bogor','PN Tangerang','PN Tangerang Selatan',
  'PN Surabaya','PN Malang','PN Sidoarjo','PN Gresik','PN Pasuruan',
  'PN Semarang','PN Yogyakarta','PN Klaten','PN Solo',
  'PN Medan','PN Deli Serdang','PN Binjai','PN Pematangsiantar',
  'PN Makassar','PN Gowa','PN Maros',
  'PN Palembang','PN Prabumulih',
  'PN Pekanbaru','PN Dumai',
  'PN Banjarmasin','PN Banjarbaru',
  'PN Balikpapan','PN Samarinda','PN Kutai Kartanegara',
  'PN Manado','PN Bitung',
  'PN Denpasar','PN Badung','PN Gianyar',
  'PN Padang','PN Bukittinggi',
  'PN Pontianak','PN Singkawang',
  'PN Jambi','PN Muara Bungo',
  'PN Kupang','PN Ende',
  'PN Mataram','PN Selong',
  'PN Ambon','PN Ternate',
  'PN Jayapura','PN Sorong','PN Merauke',
  'PN Bengkulu','PN Kepahiang',
  'PN Serang','PN Cilegon',
  'PN Gorontalo','PN Limboto',
  'PN Kendari','PN Baubau',
  'PN Palu','PN Poso',
  'PN Mamuju','PN Polewali',
  'PN Tanjungpinang','PN Batam',
  'PA Jakarta Pusat','PA Jakarta Selatan','PA Bandung','PA Surabaya','PA Makassar',
  'PTUN Jakarta','PTUN Bandung','PTUN Surabaya','PTUN Medan','PTUN Makassar',
  'Dilmil I-02 Medan','Dilmil II-08 Jakarta','Dilmil II-09 Bandung','Dilmil III-14 Makassar',
];
const JENIS_LIST = ['Mahkamah Agung','Peradilan Umum','Peradilan Agama','Peradilan Tata Usaha Negara','Peradilan Militer'];

/* ============================================================
   STATE
   ============================================================ */
const state = {
  results: [], filtered: [], sortCol: null, sortDir: 'asc',
  page: 1, perPage: 10, totalFromApi: 0, totalPages: 0,
  selectedLokasi: '', selectedJenis: '', keyword: '',
  darkMode: false, currentModalData: null, loading: false,
};

/* ============================================================
   DOM
   ============================================================ */
const $ = id => document.getElementById(id);
const DOM = {
  themeToggle:$('themeToggle'), searchBtn:$('searchBtn'), resetBtn:$('resetBtn'),
  lokasiInput:$('lokasiInput'), lokasiDropdown:$('lokasiDropdown'), lokasiWrapper:$('lokasiWrapper'),
  jenisInput:$('jenisInput'), jenisDropdown:$('jenisDropdown'), jenisWrapper:$('jenisWrapper'),
  keywordInput:$('keywordInput'), clearKeyword:$('clearKeyword'),
  resultsHeader:$('resultsHeader'), tableWrapper:$('tableWrapper'), tableBody:$('tableBody'),
  skeletonWrapper:$('skeletonWrapper'), emptyState:$('emptyState'), initialState:$('initialState'),
  paginationWrapper:$('paginationWrapper'), pagination:$('pagination'),
  paginationInfo:$('paginationInfo'), resultsTotal:$('resultsTotal'),
  filterSummary:$('filterSummary'), realtimeSearch:$('realtimeSearch'),
  downloadAllBtn:$('downloadAllBtn'),
  detailModal:$('detailModal'), modalClose:$('modalClose'), modalCloseBtn:$('modalCloseBtn'),
  modalDownloadBtn:$('modalDownloadBtn'), modalTitle:$('modalTitle'), modalBody:$('modalBody'),
  // Warmup
  warmupBanner:$('warmupBanner'), warmupBtn:$('warmupBtn'),
  warmupIcon:$('warmupIcon'), warmupTitle:$('warmupTitle'), warmupDesc:$('warmupDesc'),
};

/* ============================================================
   API HELPERS
   ============================================================ */
async function apiPost(endpoint, body) {
  await ensureBackend();
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  if (!isJsonResponse(res)) throw new Error('Backend FastAPI tidak ditemukan');
  return res.json();
}

function isJsonResponse(res) {
  return (res.headers.get('content-type') || '').includes('application/json');
}

async function fetchJson(endpoint, options) {
  const res = await fetch(`${API_BASE}${endpoint}`, options);
  if (!res.ok || !isJsonResponse(res)) throw new Error(`API unavailable at ${API_BASE}`);
  return res.json();
}

async function detectBackend() {
  for (const base of API_CANDIDATES) {
    try {
      const res = await fetch(`${base}/health`, { cache: 'no-store' });
      if (res.ok && isJsonResponse(res)) {
        API_BASE = base;
        backendReady = true;
        return true;
      }
    } catch (_) { /* try next candidate */ }
  }
  backendReady = false;
  return false;
}

async function ensureBackend() {
  if (backendReady) return true;
  const ok = await detectBackend();
  if (!ok) throw new Error('Backend FastAPI belum aktif. Jalankan server di localhost:8000.');
  return true;
}

/* ============================================================
   THEME
   ============================================================ */
function initTheme() {
  setTheme(localStorage.getItem('theme') || 'light');
  DOM.themeToggle.addEventListener('click', () => {
    setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });
}
function setTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('theme', t);
}

/* ============================================================
   DROPDOWNS
   ============================================================ */
function buildDropdown(items, dropdownEl, inputEl, wrapperEl, onSelect) {
  function render(filter='') {
    const q = filter.toLowerCase().trim();
    const f = q ? items.filter(i => i.toLowerCase().includes(q)) : items;
    dropdownEl.innerHTML = '';
    if (!f.length) { dropdownEl.innerHTML = '<div class="dropdown-no-result">Tidak ditemukan</div>'; return; }
    f.forEach(item => {
      const div = document.createElement('div');
      div.className = 'dropdown-item' + (item === inputEl._selected ? ' selected' : '');
      div.setAttribute('role','option'); div.textContent = item;
      div.addEventListener('mousedown', e => {
        e.preventDefault(); inputEl._selected = item; inputEl.value = item;
        close(); onSelect(item);
      });
      dropdownEl.appendChild(div);
    });
  }
  function open() { wrapperEl.classList.add('open'); render(inputEl.value); if(inputEl.readOnly){inputEl.value='';inputEl.readOnly=false;} }
  function close() { wrapperEl.classList.remove('open'); if(!inputEl._selected) inputEl.value = inputEl._selected || ''; }
  inputEl.addEventListener('focus', open);
  inputEl.addEventListener('input', () => render(inputEl.value));
  inputEl.addEventListener('blur', () => setTimeout(close, 150));
  inputEl._selected = '';
  if (inputEl.readOnly) inputEl.addEventListener('click', open);
}
function initDropdowns() {
  buildDropdown(LOKASI_LIST, DOM.lokasiDropdown, DOM.lokasiInput, DOM.lokasiWrapper, v => { state.selectedLokasi = v; });
  buildDropdown(JENIS_LIST, DOM.jenisDropdown, DOM.jenisInput, DOM.jenisWrapper, v => { state.selectedJenis = v; DOM.jenisInput.readOnly = true; });
  DOM.jenisInput.addEventListener('click', () => {
    DOM.jenisWrapper.classList.toggle('open');
    if (DOM.jenisWrapper.classList.contains('open')) DOM.jenisDropdown.style.display = 'block';
  });
}

/* ============================================================
   KEYWORD INPUT
   ============================================================ */
function initKeyword() {
  DOM.keywordInput.addEventListener('input', () => {
    DOM.clearKeyword.style.display = DOM.keywordInput.value ? 'inline-flex' : 'none';
  });
  DOM.clearKeyword.addEventListener('click', () => {
    DOM.keywordInput.value = ''; DOM.clearKeyword.style.display = 'none'; DOM.keywordInput.focus();
  });
  DOM.keywordInput.addEventListener('keydown', e => { if (e.key === 'Enter') triggerSearch(); });
}

/* ============================================================
   SEARCH — calls real API
   ============================================================ */
async function triggerSearch(pageNum) {
  if (state.loading) return;
  state.selectedLokasi = DOM.lokasiInput._selected || DOM.lokasiInput.value;
  state.selectedJenis  = DOM.jenisInput._selected  || DOM.jenisInput.value;
  state.keyword        = DOM.keywordInput.value.trim();
  state.page = pageNum || 1;
  state.sortCol = null; state.sortDir = 'asc';
  DOM.realtimeSearch.value = '';
  showSkeleton();

  try {
    const resp = await apiPost('/search', {
      keyword: state.keyword,
      lokasi: state.selectedLokasi,
      jenis_peradilan: state.selectedJenis,
      page: state.page,
      per_page: 100,
    });
    if (resp.success) {
      state.results = resp.data || [];
      state.filtered = [...state.results];
      state.totalFromApi = resp.total || state.results.length;
      state.totalPages = resp.total_pages || Math.ceil(state.totalFromApi / state.perPage);
      showToast(`${resp.total} hasil ditemukan (${resp.source})`, 'success');
    } else {
      state.results = []; state.filtered = [];
      showToast(resp.message || 'Pencarian gagal', 'error');
    }
  } catch (err) {
    console.error(err);
    state.results = []; state.filtered = [];
    showToast('Gagal menghubungi server: ' + err.message, 'error');
  }
  hideSkeleton();
  state.page = 1;
  renderResults();
}

function resetFilter() {
  DOM.lokasiInput.value=''; DOM.lokasiInput._selected='';
  DOM.jenisInput.value=''; DOM.jenisInput._selected=''; DOM.jenisInput.readOnly=true;
  DOM.keywordInput.value=''; DOM.clearKeyword.style.display='none'; DOM.realtimeSearch.value='';
  state.selectedLokasi=''; state.selectedJenis=''; state.keyword='';
  state.results=[]; state.filtered=[]; state.page=1; state.sortCol=null;
  DOM.resultsHeader.style.display='none'; DOM.tableWrapper.style.display='none';
  DOM.emptyState.style.display='none'; DOM.initialState.style.display='';
  DOM.paginationWrapper.style.display='none';
  showToast('Filter berhasil direset','success');
}

/* ============================================================
   LOADING
   ============================================================ */
function showSkeleton() {
  state.loading = true;
  const btn = DOM.searchBtn;
  btn.querySelector('.btn-text').style.display='none';
  btn.querySelector('.btn-loader').style.display='inline-flex'; btn.disabled=true;
  DOM.resultsHeader.style.display='none'; DOM.tableWrapper.style.display='none';
  DOM.emptyState.style.display='none'; DOM.initialState.style.display='none';
  DOM.paginationWrapper.style.display='none'; DOM.skeletonWrapper.style.display='';
}
function hideSkeleton() {
  state.loading = false;
  DOM.skeletonWrapper.style.display='none';
  const btn = DOM.searchBtn;
  btn.querySelector('.btn-text').style.display='';
  btn.querySelector('.btn-loader').style.display='none'; btn.disabled=false;
}

/* ============================================================
   RENDER RESULTS
   ============================================================ */
function renderResults() {
  const { filtered, page, perPage } = state;
  const total = filtered.length;
  DOM.resultsTotal.textContent = `${total.toLocaleString('id-ID')} hasil ditemukan`;
  const parts = [];
  if (state.selectedLokasi) parts.push(state.selectedLokasi);
  if (state.selectedJenis)  parts.push(state.selectedJenis);
  if (state.keyword)        parts.push(`"${state.keyword}"`);
  DOM.filterSummary.textContent = parts.length ? '· '+parts.join(' · ') : '';

  if (!total) {
    DOM.resultsHeader.style.display='flex'; DOM.tableWrapper.style.display='none';
    DOM.emptyState.style.display=''; DOM.paginationWrapper.style.display='none'; return;
  }
  DOM.resultsHeader.style.display='flex'; DOM.tableWrapper.style.display='';
  DOM.emptyState.style.display='none'; DOM.initialState.style.display='none';

  const totalPages = Math.ceil(total / perPage);
  const start = (page-1)*perPage;
  const pageData = filtered.slice(start, start+perPage);

  DOM.tableBody.innerHTML = pageData.map(d => `
    <tr data-url="${escHtml(d.url_detail||'')}" class="result-row" tabindex="0">
      <td><div class="cell-nomor"><span>${escHtml(d.nomor_perkara)}</span>
        <button class="copy-btn" data-copy="${escHtml(d.nomor_perkara)}" title="Salin">⎘</button></div></td>
      <td>${escHtml(d.tahun||'')}</td>
      <td style="white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis;" title="${escHtml(d.lokasi)}">${escHtml(d.lokasi)}</td>
      <td><span class="badge ${jenisBadge(d.jenis_peradilan)}">${escHtml(d.jenis_peradilan)}</span></td>
      <td class="cell-judul" title="${escHtml(d.judul)}">${escHtml(d.judul)}</td>
      <td><div class="action-group">
        <button class="action-btn action-btn-detail" data-url="${escHtml(d.url_detail||'')}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> Detail</button>
        <button class="action-btn action-btn-pdf" data-pdf="${escHtml(d.url_pdf||'')}" title="Unduh PDF" ${d.url_pdf?'':'disabled'}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></button>
      </div></td>
    </tr>`).join('');

  renderPagination(total, totalPages);
  DOM.paginationWrapper.style.display='flex';
  DOM.paginationInfo.textContent = `Menampilkan ${start+1}–${Math.min(start+perPage,total)} dari ${total}`;

  // Event delegation
  DOM.tableBody.querySelectorAll('.result-row').forEach(row => {
    row.addEventListener('click', e => {
      if (e.target.closest('.copy-btn')||e.target.closest('.action-btn-pdf')) return;
      openModal(row.dataset.url);
    });
  });
  DOM.tableBody.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      navigator.clipboard.writeText(btn.dataset.copy).then(() => showToast('Nomor disalin!','success'));
    });
  });
  DOM.tableBody.querySelectorAll('.action-btn-pdf').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      if (btn.dataset.pdf) downloadPdf(btn.dataset.pdf);
      else showToast('PDF tidak tersedia','warning');
    });
  });
  DOM.tableBody.querySelectorAll('.action-btn-detail').forEach(btn => {
    btn.addEventListener('click', e => { e.stopPropagation(); openModal(btn.dataset.url); });
  });
}

function jenisBadge(j) {
  if (!j) return 'badge-kasasi';
  if (j.includes('Agama')) return 'badge-inkracht';
  if (j.includes('Tata')) return 'badge-kasasi';
  if (j.includes('Militer')) return 'badge-banding';
  if (j.includes('Mahkamah')) return 'badge-proses';
  return 'badge-kasasi';
}
function escHtml(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

/* ============================================================
   SORTING
   ============================================================ */
function initSorting() {
  document.querySelectorAll('.th-sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = Number(th.dataset.col);
      if (state.sortCol===col) state.sortDir = state.sortDir==='asc'?'desc':'asc';
      else { state.sortCol=col; state.sortDir='asc'; }
      document.querySelectorAll('.th-sortable').forEach(t=>t.classList.remove('sorted-asc','sorted-desc'));
      th.classList.add(state.sortDir==='asc'?'sorted-asc':'sorted-desc');
      const keys=['nomor_perkara','tahun','lokasi','jenis_peradilan','judul'];
      const key=keys[col];
      state.filtered.sort((a,b) => {
        const av=String(a[key]||'').toLowerCase(), bv=String(b[key]||'').toLowerCase();
        return state.sortDir==='asc'?av.localeCompare(bv,'id'):bv.localeCompare(av,'id');
      });
      state.page=1; renderResults();
    });
  });
}

/* ============================================================
   REALTIME FILTER
   ============================================================ */
function initRealtimeSearch() {
  DOM.realtimeSearch.addEventListener('input', () => {
    const q = DOM.realtimeSearch.value.trim().toLowerCase();
    state.filtered = !q ? [...state.results] : state.results.filter(d =>
      [d.nomor_perkara,d.judul,d.lokasi,d.jenis_peradilan,d.tahun].join(' ').toLowerCase().includes(q)
    );
    state.page=1; renderResults();
  });
}

/* ============================================================
   PAGINATION
   ============================================================ */
function renderPagination(total, totalPages) {
  const { page } = state;
  DOM.pagination.innerHTML = '';
  const mk = (label, pg, dis=false, active=false) => {
    const b = document.createElement('button');
    b.className='page-btn'+(active?' active':''); b.innerHTML=label; b.disabled=dis;
    b.addEventListener('click', () => { state.page=pg; renderResults(); window.scrollTo({top:DOM.resultsHeader.offsetTop-80,behavior:'smooth'}); });
    return b;
  };
  DOM.pagination.appendChild(mk('‹ Prev',page-1,page===1));
  const delta=2; let pages=[];
  for(let i=1;i<=totalPages;i++) if(i===1||i===totalPages||(i>=page-delta&&i<=page+delta)) pages.push(i);
  let prev=0;
  pages.forEach(p => {
    if(prev&&p-prev>1){const d=document.createElement('span');d.className='page-dots';d.textContent='…';DOM.pagination.appendChild(d);}
    DOM.pagination.appendChild(mk(p,p,false,p===page)); prev=p;
  });
  DOM.pagination.appendChild(mk('Next ›',page+1,page===totalPages));
}

/* ============================================================
   MODAL — calls /api/detail
   ============================================================ */
async function openModal(url) {
  if (!url) { showToast('URL detail tidak tersedia','warning'); return; }
  DOM.modalTitle.textContent = 'Memuat...';
  DOM.modalBody.innerHTML = '<div style="text-align:center;padding:40px"><span class="spinner"></span><p style="margin-top:12px;color:var(--text-muted)">Mengambil detail putusan…</p></div>';
  DOM.detailModal.classList.add('open'); document.body.style.overflow='hidden';

  try {
    const resp = await apiPost('/detail', { url });
    if (resp.success && resp.data) {
      const d = resp.data; state.currentModalData = d;
      DOM.modalTitle.textContent = d.nomor_perkara || 'Detail Putusan';
      DOM.modalBody.innerHTML = `<div class="modal-detail-grid">
        ${detailField('Nomor Perkara', d.nomor_perkara, 'font-family:monospace;color:var(--accent)')}
        ${detailField('Tahun', d.tahun)}
        ${detailField('Tanggal Putusan', d.tanggal_putusan)}
        ${detailField('Tanggal Register', d.tanggal_register)}
        ${detailField('Lokasi Pengadilan', d.lokasi)}
        ${detailField('Jenis Peradilan', d.jenis_peradilan)}
        ${detailField('Klasifikasi', d.klasifikasi)}
        ${detailField('Tingkat Proses', d.tingkat_proses)}
        ${detailField('Hakim', d.hakim)}
        ${detailField('Panitera', d.panitera)}
        ${detailField('Para Pihak', d.para_pihak, '', true)}
        ${detailField('Judul Perkara', d.judul, '', true)}
        ${detailField('Amar Putusan', d.amar_putusan, 'line-height:1.7;color:var(--text-secondary)', true)}
      </div>`;
    } else {
      DOM.modalTitle.textContent = 'Error';
      DOM.modalBody.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:40px">${escHtml(resp.message||'Gagal memuat detail')}</p>`;
    }
  } catch(err) {
    DOM.modalTitle.textContent = 'Error';
    DOM.modalBody.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:40px">Gagal: ${escHtml(err.message)}</p>`;
  }
}
function detailField(label, value, style, full) {
  if (!value) return '';
  return `<div class="modal-detail-item${full?' full':''}"><span class="detail-label">${escHtml(label)}</span><span class="detail-value"${style?' style="'+style+'"':''}>${escHtml(value)}</span></div>`;
}
function closeModal() { DOM.detailModal.classList.remove('open'); document.body.style.overflow=''; state.currentModalData=null; }

/* ============================================================
   PDF DOWNLOAD — via /api/download-pdf
   ============================================================ */
function downloadPdf(url) {
  if (!url) { showToast('URL PDF tidak tersedia','warning'); return; }
  showToast('Mengunduh PDF...','info');
  const a = document.createElement('a');
  a.href = `${API_BASE}/download-pdf?url=${encodeURIComponent(url)}`;
  a.target = '_blank'; a.download = ''; a.click();
}

/* ============================================================
   TOAST
   ============================================================ */
function showToast(msg, type='info') {
  const icons={success:'✓',error:'✕',warning:'⚠',info:'ℹ'};
  const c=$('toast-container'), t=document.createElement('div');
  t.className=`toast ${type}`;
  t.innerHTML=`<span class="toast-icon">${icons[type]||'ℹ'}</span><span>${escHtml(msg)}</span>`;
  c.appendChild(t);
  setTimeout(()=>{t.classList.add('hiding');setTimeout(()=>t.remove(),350);},3000);
}

/* ============================================================
   CSV EXPORT
   ============================================================ */
function exportCSV() {
  if (!state.filtered.length) { showToast('Tidak ada data','warning'); return; }
  const h=['Nomor Perkara','Tahun','Lokasi','Jenis Peradilan','Judul','Tanggal Putusan'];
  const rows=state.filtered.map(d=>[d.nomor_perkara,d.tahun,d.lokasi,d.jenis_peradilan,d.judul,d.tanggal_putusan].map(v=>`"${String(v||'').replace(/"/g,'""')}"`).join(','));
  const csv=[h.join(','),...rows].join('\n');
  const blob=new Blob(['\uFEFF'+csv],{type:'text/csv;charset=utf-8;'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download=`putusan-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(a.href);
  showToast(`${state.filtered.length} data diekspor`,'success');
}

/* ============================================================
   WARMUP — Cloudflare Bypass
   ============================================================ */
let warmupPollTimer = null;

async function startWarmup() {
  const btn = DOM.warmupBtn;
  btn.querySelector('.warmup-btn-text').style.display='none';
  btn.querySelector('.warmup-btn-loader').style.display='inline-flex';
  btn.disabled = true;
  try {
    await ensureBackend();
    const data = await fetchJson('/warmup', {method:'POST'});
    updateWarmupUI(data.status);
    if (data.status === 'challenge') {
      showToast('Selesaikan verifikasi di jendela Chromium yang muncul!','warning');
      startWarmupPolling();
    } else if (data.status === 'solved' || data.direct_access) {
      showToast('Verifikasi berhasil!','success');
    }
  } catch(err) {
    updateWarmupUI('demo');
    showToast(err.message,'error');
  }
  btn.querySelector('.warmup-btn-text').style.display='';
  btn.querySelector('.warmup-btn-loader').style.display='none';
  btn.disabled = false;
}

function startWarmupPolling() {
  if (warmupPollTimer) clearInterval(warmupPollTimer);
  warmupPollTimer = setInterval(async () => {
    try {
      const data = await fetchJson('/warmup-status');
      updateWarmupUI(data.status);
      if (data.status === 'solved') {
        clearInterval(warmupPollTimer);
        warmupPollTimer = null;
        showToast('Verifikasi Cloudflare berhasil! Siap mencari.','success');
      }
    } catch(e) { /* silent */ }
  }, 3000);
}

function updateWarmupUI(status) {
  const b = DOM.warmupBanner;
  const btn = DOM.warmupBtn;
  b.className = 'warmup-banner ' + status;
  const cfg = {
    idle:      {icon:'🔒', title:'Verifikasi Diperlukan',              desc:'Klik tombol untuk memulai verifikasi Cloudflare.',        btnText:'Mulai Verifikasi', btnClass:''},
    warming:   {icon:'⏳', title:'Sedang Memverifikasi…',              desc:'Membuka halaman target, harap tunggu.',                    btnText:'Memproses…',       btnClass:''},
    challenge: {icon:'⚠️', title:'Selesaikan Verifikasi Cloudflare',   desc:'Buka jendela Chromium yang muncul dan klik checkbox verifikasi.', btnText:'Menunggu…', btnClass:''},
    solved:    {icon:'✅', title:'Verifikasi Berhasil',                 desc:'Anda sudah terverifikasi. Silakan mulai pencarian.',        btnText:'Terverifikasi',    btnClass:'solved-btn'},
    failed:    {icon:'❌', title:'Verifikasi Gagal',                    desc:'Terjadi kesalahan. Silakan coba lagi.',                    btnText:'Coba Lagi',        btnClass:''},
    demo:      {icon:'🌐', title:'Backend Belum Terhubung',            desc:'Jalankan backend FastAPI di localhost:8000, lalu muat ulang halaman untuk pencarian live.', btnText:'Cek Lagi', btnClass:''},
  };
  const c = cfg[status] || cfg.idle;
  DOM.warmupIcon.textContent = c.icon;
  DOM.warmupTitle.textContent = c.title;
  DOM.warmupDesc.textContent = c.desc;
  btn.querySelector('.warmup-btn-text').textContent = c.btnText;
  btn.className = 'btn btn-warmup ' + c.btnClass;
  btn.disabled = (status === 'warming' || status === 'challenge');
}

async function checkInitialWarmup() {
  const detected = await detectBackend();
  if (!detected) {
    updateWarmupUI('demo');
    return;
  }
  try {
    const data = await fetchJson('/warmup-status');
    updateWarmupUI(data.cf_clearance ? 'solved' : data.status);
    if (data.status === 'challenge') startWarmupPolling();
  } catch(e) { updateWarmupUI('idle'); }
}

/* ============================================================
   INIT
   ============================================================ */
function init() {
  initTheme(); initDropdowns(); initKeyword(); initSorting(); initRealtimeSearch();
  DOM.searchBtn.addEventListener('click', () => {
    triggerSearch();
  });
  DOM.resetBtn.addEventListener('click', resetFilter);
  DOM.downloadAllBtn.addEventListener('click', exportCSV);
  DOM.warmupBtn.addEventListener('click', () => {
    startWarmup();
  });
  DOM.modalClose.addEventListener('click', closeModal);
  DOM.modalCloseBtn.addEventListener('click', closeModal);
  DOM.detailModal.addEventListener('click', e => { if(e.target===DOM.detailModal) closeModal(); });
  DOM.modalDownloadBtn.addEventListener('click', () => {
    if (state.currentModalData?.url_pdf) downloadPdf(state.currentModalData.url_pdf);
    else showToast('PDF tidak tersedia','warning');
  });
  document.addEventListener('keydown', e => { if(e.key==='Escape') closeModal(); });
  DOM.initialState.style.display=''; DOM.skeletonWrapper.style.display='none';
  checkInitialWarmup();
  showToast('Selamat datang di Direktori Putusan Pengadilan','success');
}
document.addEventListener('DOMContentLoaded', init);
