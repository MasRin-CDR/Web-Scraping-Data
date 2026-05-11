/* ═══════════════════════════════════════════════════
   DIREKTORI PUTUSAN — Mahkamah Agung RI
   app.js — Frontend Logic & API Integration
   ═══════════════════════════════════════════════════ */

'use strict';

/* ══════════════════════════════════════════════
   CONFIG — sesuaikan dengan URL backend
══════════════════════════════════════════════ */
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : ''; // jika frontend di-serve dari backend langsung

/* ══════════════════════════════════════════════
   STATE
══════════════════════════════════════════════ */
const state = {
  results: [],          // data hasil scraping
  filtered: [],         // hasil setelah filter tabel
  currentPage: 1,
  perPage: 20,
  sortCol: -1,
  sortAsc: true,
  warmupVerified: false,
  currentDetailUrl: '',
};

/* ══════════════════════════════════════════════
   DAFTAR LOKASI PENGADILAN
══════════════════════════════════════════════ */
const LOKASI_LIST = [
  'Mahkamah Agung RI',
  'Pengadilan Negeri Jakarta Pusat',
  'Pengadilan Negeri Jakarta Selatan',
  'Pengadilan Negeri Jakarta Barat',
  'Pengadilan Negeri Jakarta Timur',
  'Pengadilan Negeri Jakarta Utara',
  'Pengadilan Tinggi DKI Jakarta',
  'Pengadilan Negeri Bandung',
  'Pengadilan Tinggi Bandung',
  'Pengadilan Negeri Surabaya',
  'Pengadilan Tinggi Surabaya',
  'Pengadilan Negeri Medan',
  'Pengadilan Tinggi Medan',
  'Pengadilan Negeri Semarang',
  'Pengadilan Tinggi Semarang',
  'Pengadilan Negeri Makassar',
  'Pengadilan Tinggi Makassar',
  'Pengadilan Negeri Yogyakarta',
  'Pengadilan Negeri Denpasar',
  'Pengadilan Tinggi Denpasar',
  'Pengadilan Negeri Palembang',
  'Pengadilan Tinggi Palembang',
  'Pengadilan Negeri Padang',
  'Pengadilan Tinggi Padang',
  'Pengadilan Negeri Pekanbaru',
  'Pengadilan Negeri Banjarmasin',
  'Pengadilan Tinggi Banjarmasin',
  'Pengadilan Negeri Balikpapan',
  'Pengadilan Negeri Samarinda',
  'Pengadilan Tinggi Kalimantan Timur',
  'Pengadilan Negeri Manado',
  'Pengadilan Negeri Ambon',
  'Pengadilan Negeri Jayapura',
  'Pengadilan Tinggi Papua',
  'Pengadilan Negeri Kupang',
  'Pengadilan Negeri Mataram',
  'Pengadilan Negeri Pontianak',
  'Pengadilan Negeri Bengkulu',
  'Pengadilan Negeri Jambi',
  'Pengadilan Negeri Banda Aceh',
  'Pengadilan Tinggi Banda Aceh',
  'Pengadilan Agama Jakarta Pusat',
  'Pengadilan Agama Jakarta Selatan',
  'Pengadilan Agama Jakarta Barat',
  'Pengadilan Agama Bandung',
  'Pengadilan Agama Surabaya',
  'Pengadilan Agama Medan',
  'Pengadilan Tata Usaha Negara Jakarta',
  'Pengadilan Tata Usaha Negara Surabaya',
  'Pengadilan Tata Usaha Negara Bandung',
  'Pengadilan Tata Usaha Negara Medan',
  'Pengadilan Militer I-02 Jakarta',
  'Pengadilan Militer I-03 Padang',
  'Pengadilan Militer II-08 Jakarta',
  'Pengadilan Militer Tinggi II Jakarta',
];

/* ══════════════════════════════════════════════
   INIT
══════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initLokasiDropdown();
  checkWarmupStatus();
  // Close dropdown on outside click
  document.addEventListener('click', (e) => {
    if (!document.getElementById('lokasiWrapper').contains(e.target)) {
      closeLokasiDropdown();
    }
    if (!document.getElementById('jenisWrapper').contains(e.target)) {
      const dd = document.getElementById('jenisDropdown');
      if (dd) dd.classList.remove('open');
    }
  });
});

/* ══════════════════════════════════════════════
   THEME
══════════════════════════════════════════════ */
function initTheme() {
  const saved = localStorage.getItem('theme') || 'light';
  applyTheme(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem('theme', next);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  // icon dikontrol via CSS class di data-theme attribute
}

/* ══════════════════════════════════════════════
   LOKASI SEARCHABLE DROPDOWN
══════════════════════════════════════════════ */
function initLokasiDropdown() {
  renderLokasiDropdown(LOKASI_LIST);
}

function renderLokasiDropdown(list) {
  const dd = document.getElementById('lokasiDropdown');
  if (!list.length) {
    dd.innerHTML = '<div class="dropdown-empty">Tidak ditemukan</div>';
    return;
  }
  dd.innerHTML = list.map(item =>
    `<div class="dropdown-item" onclick="selectLokasi('${item.replace(/'/g, "\\'")}')">${item}</div>`
  ).join('');
}

function filterLokasi(query) {
  const filtered = LOKASI_LIST.filter(l => l.toLowerCase().includes(query.toLowerCase()));
  renderLokasiDropdown(filtered);
  openLokasiDropdown();
  if (!query) document.getElementById('lokasiInput').value = '';
}

function openLokasiDropdown() {
  document.getElementById('lokasiDropdown').classList.add('open');
}

function closeLokasiDropdown() {
  document.getElementById('lokasiDropdown').classList.remove('open');
}


/* ══════════════════════════════════════════════
   JENIS PERADILAN DROPDOWN
══════════════════════════════════════════════ */
const JENIS_LIST = [
  'Perdata',
  'Pidana',
  'Agama',
  'Tata Usaha Negara',
  'Militer',
  'Mahkamah Agung',
];

function toggleJenisDropdown() {
  const dd = document.getElementById('jenisDropdown');
  if (dd.classList.contains('open')) {
    dd.classList.remove('open');
  } else {
    renderJenisDropdown();
    dd.classList.add('open');
  }
}

function renderJenisDropdown() {
  const dd = document.getElementById('jenisDropdown');
  dd.innerHTML = ['', ...JENIS_LIST].map(item =>
    `<div class="dropdown-item" onclick="selectJenisItem('${item}')">${item || '— Semua Jenis —'}</div>`
  ).join('');
}

function selectJenisItem(value) {
  document.getElementById('jenisInput').value = value;
  document.getElementById('jenisDropdown').classList.remove('open');
}

function selectLokasi(value) {
  document.getElementById('lokasiInput').value = value;
  closeLokasiDropdown();
}

/* ══════════════════════════════════════════════
   WARMUP — Verifikasi Cloudflare
══════════════════════════════════════════════ */
async function checkWarmupStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) {
      showWarmupBar('Backend tidak dapat dijangkau');
      return;
    }
    const data = await res.json();
    if (data.cf_clearance) {
      setWarmupVerified();
    } else {
      // Tampilkan banner warmup jika belum verified
      document.getElementById('warmupBar').style.display = 'block';
      document.getElementById('warmupLabel').textContent = 'Verifikasi Cloudflare diperlukan';
    }
  } catch (_) {
    // Backend belum jalan — sembunyikan banner saja
  }
}

async function startWarmup() {
  if (state.warmupVerified) return;
  showWarmupBar('Memulai proses verifikasi Cloudflare...');
  try {
    const res = await fetch(`${API_BASE}/api/warmup`, { method: 'POST' });
    if (!res.ok) throw new Error('Warmup gagal');
    toast('Verifikasi dimulai. Selesaikan Turnstile di browser.', 'info');
    pollWarmupStatus();
  } catch (err) {
    toast('Gagal memulai verifikasi: ' + err.message, 'error');
    closeWarmupBar();
  }
}

async function pollWarmupStatus() {
  let attempts = 0;
  const max = 60; // 5 menit
  const interval = setInterval(async () => {
    attempts++;
    if (attempts > max) {
      clearInterval(interval);
      toast('Timeout verifikasi. Coba lagi.', 'warning');
      closeWarmupBar();
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/warmup-status`);
      const data = await res.json();
      if (data.status === 'solved' || data.cf_clearance) {
        clearInterval(interval);
        setWarmupVerified();
        setWarmupBarSuccess('Verifikasi berhasil! Siap untuk pencarian.');
        setTimeout(closeWarmupBar, 3000);
      }
    } catch (_) {}
  }, 5000);
}

function setWarmupVerified() {
  state.warmupVerified = true;
  const btn = document.getElementById('btnWarmup');
  if (btn) btn.classList.add('verified');
  const dot = document.getElementById('warmupDot');
  if (dot) dot.classList.add('verified');
  const label = document.getElementById('warmupLabel');
  if (label) label.textContent = 'Akses Terverifikasi';
}

function showWarmupBar(msg) {
  const bar = document.getElementById('warmupBar');
  bar.style.display = 'block';
  bar.className = 'warmup-bar';
  document.getElementById('warmupBarMsg').textContent = msg;
}

function setWarmupBarSuccess(msg) {
  const bar = document.getElementById('warmupBar');
  bar.className = 'warmup-bar success';
  document.getElementById('warmupBarMsg').textContent = msg;
}

function closeWarmupBar() {
  document.getElementById('warmupBar').style.display = 'none';
}

/* ══════════════════════════════════════════════
   SEARCH
══════════════════════════════════════════════ */
async function doSearch() {
  const lokasi   = document.getElementById('lokasiInput').value.trim();
  const jenis    = document.getElementById('jenisInput').value;
  const keyword  = document.getElementById('keywordInput').value.trim();

  if (!keyword && !lokasi && !jenis) {
    toast('Masukkan minimal satu filter pencarian', 'warning');
    return;
  }

  showSkeleton();
  showResultsSection();
  state.currentPage = 1;

  try {
    const payload = { keyword, lokasi, jenis_peradilan: jenis, page: 1, per_page: state.perPage };
    const res = await fetch(`${API_BASE}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    state.results = data.results || data.data || [];
    state.filtered = [...state.results];

    hideSkeleton();
    renderTable();
    renderPagination();

    const total = data.total || state.results.length;
    document.getElementById('resultsTotal').innerHTML =
      `Ditemukan <strong>${total.toLocaleString('id-ID')}</strong> putusan`;
    document.getElementById('resultsHeader').style.display = 'flex';
    document.getElementById('tableWrapper').style.display = 'block';
    document.getElementById('initialState').style.display = 'none';
    document.getElementById('paginationWrapper').style.display = 'flex';

    if (!state.results.length) {
      showEmptyState();
    } else {
      toast(`${state.results.length} hasil ditemukan`, 'success');
    }

  } catch (err) {
    hideSkeleton();
    showEmptyState();
    toast('Pencarian gagal: ' + err.message, 'error');
    console.error('[Search Error]', err);
  }
}

function resetForm() {
  document.getElementById('lokasiInput').value = '';
  document.getElementById('jenisInput').value = '';
  document.getElementById('keywordInput').value = '';
  const rt = document.getElementById('realtimeSearch');
  if (rt) rt.value = '';
  document.getElementById('clearKeyword').style.display = 'none';
  document.getElementById('resultsHeader').style.display = 'none';
  document.getElementById('tableWrapper').style.display = 'none';
  document.getElementById('paginationWrapper').style.display = 'none';
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('initialState').style.display = 'block';
  document.getElementById('tableBody').innerHTML = '';
  state.results = [];
  state.filtered = [];
}

/* ══════════════════════════════════════════════
   TABLE RENDER
══════════════════════════════════════════════ */
function renderTable() {
  const tbody = document.getElementById('tableBody');
  const start = (state.currentPage - 1) * state.perPage;
  const end   = start + state.perPage;
  const pageData = state.filtered.slice(start, end);

  if (!pageData.length) {
    showEmptyState();
    tbody.innerHTML = '';
    return;
  }

  hideEmptyState();

  tbody.innerHTML = pageData.map((item, idx) => {
    const rowNum = start + idx + 1;
    const badgeClass = getBadgeClass(item.jenis_peradilan || '');
    const judul = escHtml(item.judul || item.title || '-');
    const nomor = escHtml(item.nomor_perkara || item.nomor || '-');
    const tahun = escHtml(String(item.tahun || item.year || '-'));
    const lokasi = escHtml(item.lokasi || item.pengadilan || '-');
    const jenis = escHtml(item.jenis_peradilan || item.jenis || '-');
    const detailUrl = item.url || item.detail_url || '';

    return `
      <tr onclick="openDetail('${escAttr(detailUrl)}', '${escAttr(nomor)}')">
        <td class="row-num">${rowNum}</td>
        <td>
          <div class="perkara-num">
            ${nomor}
            <button class="copy-btn" onclick="event.stopPropagation(); copyText('${escAttr(nomor)}')" title="Salin">⎘</button>
          </div>
        </td>
        <td>${tahun}</td>
        <td style="color:var(--text-2)">${lokasi}</td>
        <td><span class="badge ${badgeClass}">${jenis}</span></td>
        <td class="judul-cell" title="${escAttr(judul)}">${judul}</td>
        <td>
          <div class="aksi-cell">
            <button class="btn-icon" onclick="event.stopPropagation(); openDetail('${escAttr(detailUrl)}', '${escAttr(nomor)}')" title="Detail">🔍</button>
            ${detailUrl ? `<button class="btn-icon" onclick="event.stopPropagation(); downloadPDF('${escAttr(detailUrl)}')" title="Download PDF">⬇</button>` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function getBadgeClass(jenis) {
  const j = jenis.toLowerCase();
  if (j.includes('agama'))   return 'badge-agama';
  if (j.includes('tata') || j.includes('ptun')) return 'badge-ptun';
  if (j.includes('militer')) return 'badge-militer';
  if (j.includes('mahkamah agung') || j.includes(' ma')) return 'badge-ma';
  return 'badge-umum';
}

/* ══════════════════════════════════════════════
   FILTER TABLE (realtime)
══════════════════════════════════════════════ */
function filterTable(query) {
  const q = query.toLowerCase();
  state.filtered = state.results.filter(item =>
    Object.values(item).some(v => String(v).toLowerCase().includes(q))
  );
  state.currentPage = 1;
  renderTable();
  renderPagination();
}

/* ══════════════════════════════════════════════
   SORT TABLE
══════════════════════════════════════════════ */
const SORT_KEYS = ['', 'nomor_perkara', 'tahun', 'lokasi', 'jenis_peradilan'];

function sortTable(col) {
  if (col === 0 || col === 6) return; // no, aksi — not sortable
  const key = SORT_KEYS[col];
  if (!key) return;

  if (state.sortCol === col) {
    state.sortAsc = !state.sortAsc;
  } else {
    state.sortCol = col;
    state.sortAsc = true;
  }

  state.filtered.sort((a, b) => {
    const va = String(a[key] || '').toLowerCase();
    const vb = String(b[key] || '').toLowerCase();
    return state.sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  });

  // Update header icons
  document.querySelectorAll('.results-table th').forEach((th, i) => {
    th.classList.remove('sorted');
    const icon = th.querySelector('.sort-icon');
    if (icon) icon.textContent = '↕';
  });

  const ths = document.querySelectorAll('.results-table th');
  ths[col].classList.add('sorted');
  const icon = ths[col].querySelector('.sort-icon');
  if (icon) icon.textContent = state.sortAsc ? '↑' : '↓';

  state.currentPage = 1;
  renderTable();
}

/* ══════════════════════════════════════════════
   PAGINATION
══════════════════════════════════════════════ */
function renderPagination() {
  const total = state.filtered.length;
  const pages = Math.ceil(total / state.perPage);
  const pag = document.getElementById('pagination');

  if (pages <= 1) { pag.innerHTML = ''; return; }

  const cur = state.currentPage;
  let html = '';

  html += `<button class="page-btn" onclick="goPage(${cur-1})" ${cur===1?'disabled':''}>‹</button>`;

  const range = getPageRange(cur, pages);
  range.forEach(p => {
    if (p === '...') {
      html += `<span class="page-btn" style="pointer-events:none;opacity:.4">…</span>`;
    } else {
      html += `<button class="page-btn ${p===cur?'active':''}" onclick="goPage(${p})">${p}</button>`;
    }
  });

  html += `<button class="page-btn" onclick="goPage(${cur+1})" ${cur===pages?'disabled':''}>›</button>`;
  pag.innerHTML = html;
}

function getPageRange(cur, total) {
  if (total <= 7) return Array.from({length: total}, (_, i) => i+1);
  const range = [1];
  if (cur > 3) range.push('...');
  for (let i = Math.max(2, cur-1); i <= Math.min(total-1, cur+1); i++) range.push(i);
  if (cur < total-2) range.push('...');
  range.push(total);
  return range;
}

function goPage(page) {
  const pages = Math.ceil(state.filtered.length / state.perPage);
  if (page < 1 || page > pages) return;
  state.currentPage = page;
  renderTable();
  renderPagination();
  document.querySelector('.results-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ══════════════════════════════════════════════
   DETAIL MODAL
══════════════════════════════════════════════ */
async function openDetail(url, nomor) {
  if (!url) {
    toast('URL detail tidak tersedia', 'warning');
    return;
  }

  state.currentDetailUrl = url;
  document.getElementById('modalTitle').textContent = nomor || 'Detail Putusan';
  document.getElementById('modalBody').innerHTML = `
    <div class="modal-skeleton">
      <div class="sk-line" style="width:60%"></div>
      <div class="sk-line" style="width:40%"></div>
      <div class="sk-line" style="width:80%"></div>
      <div class="sk-line" style="width:55%"></div>
      <div class="sk-line" style="width:70%"></div>
    </div>
  `;
  document.getElementById('detailModal').classList.add('open');
  document.body.style.overflow = 'hidden';

  try {
    const res = await fetch(`${API_BASE}/api/detail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderDetailModal(data);
  } catch (err) {
    document.getElementById('modalBody').innerHTML =
      `<p style="color:var(--danger);font-size:13px">Gagal memuat detail: ${err.message}</p>`;
    toast('Gagal memuat detail', 'error');
  }
}

function renderDetailModal(data) {
  const fields = [
    ['Nomor Perkara',    data.nomor_perkara || data.nomor || '-'],
    ['Judul',            data.judul || data.title || '-'],
    ['Tahun',            data.tahun || '-'],
    ['Pengadilan',       data.lokasi || data.pengadilan || '-'],
    ['Jenis Peradilan',  data.jenis_peradilan || data.jenis || '-'],
    ['Tanggal Putusan',  data.tanggal_putusan || data.tanggal || '-'],
    ['Hakim',            data.hakim || '-'],
    ['Amar Putusan',     data.amar || data.amar_putusan || '-'],
    ['Klasifikasi',      data.klasifikasi || '-'],
    ['Link PDF',         data.pdf_url ? `<a href="${escHtml(data.pdf_url)}" target="_blank" style="color:var(--accent)">Buka PDF ↗</a>` : '-'],
  ];

  document.getElementById('modalBody').innerHTML = `
    <div class="detail-grid">
      ${fields.map(([label, value]) => `
        <div class="detail-row">
          <div class="detail-label">${label}</div>
          <div class="detail-value">${value}</div>
        </div>
      `).join('')}
    </div>
  `;

  // Show/hide PDF button
  const pdfBtn = document.getElementById('modalDownloadBtn');
  if (data.pdf_url) {
    pdfBtn.style.display = '';
    state.currentDetailUrl = data.pdf_url;
  } else {
    pdfBtn.style.display = 'none';
  }
}

function closeModal() {
  document.getElementById('detailModal').classList.remove('open');
  document.body.style.overflow = '';
  state.currentDetailUrl = '';
}

// Close with Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

/* ══════════════════════════════════════════════
   DOWNLOAD PDF
══════════════════════════════════════════════ */
async function downloadPDF(url) {
  if (!url) { toast('URL PDF tidak tersedia', 'warning'); return; }
  toast('Memulai download PDF...', 'info');

  try {
    const proxyUrl = `${API_BASE}/api/download-pdf?url=${encodeURIComponent(url)}`;
    const a = document.createElement('a');
    a.href = proxyUrl;
    a.download = 'putusan.pdf';
    a.target = '_blank';
    a.click();
    toast('Download berhasil dimulai', 'success');
  } catch (err) {
    toast('Download gagal: ' + err.message, 'error');
  }
}

// Expose to global for modal button
window.downloadPDF = downloadPDF;
window.currentDetailUrl = () => state.currentDetailUrl;

/* ══════════════════════════════════════════════
   EXPORT CSV
══════════════════════════════════════════════ */
function exportCSV() {
  if (!state.filtered.length) { toast('Tidak ada data untuk diekspor', 'warning'); return; }

  const headers = ['Nomor Perkara', 'Tahun', 'Lokasi', 'Jenis Peradilan', 'Judul'];
  const keys    = ['nomor_perkara', 'tahun', 'lokasi', 'jenis_peradilan', 'judul'];

  const rows = [
    headers.join(','),
    ...state.filtered.map(row =>
      keys.map(k => `"${String(row[k] || '').replace(/"/g, '""')}"`).join(',')
    )
  ];

  const blob = new Blob(['\uFEFF' + rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `putusan_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  toast('CSV berhasil diekspor', 'success');
}

/* ══════════════════════════════════════════════
   COPY TEXT
══════════════════════════════════════════════ */
function copyText(text) {
  navigator.clipboard.writeText(text)
    .then(() => toast('Disalin: ' + text, 'success'))
    .catch(() => toast('Gagal menyalin', 'error'));
}

/* ══════════════════════════════════════════════
   UI HELPERS
══════════════════════════════════════════════ */
function showResultsSection() {
  const sec = document.getElementById('resultsSection');
  sec.style.display = 'block';
}

function showSkeleton() {
  document.getElementById('skeletonWrapper').style.display = 'block';
  document.getElementById('tableBody').innerHTML = '';
  hideEmptyState();
}

function hideSkeleton() {
  document.getElementById('skeletonWrapper').style.display = 'none';
}

function showEmptyState() {
  document.getElementById('emptyState').style.display = 'block';
}

function hideEmptyState() {
  document.getElementById('emptyState').style.display = 'none';
}

/* ══════════════════════════════════════════════
   TOAST NOTIFICATIONS
══════════════════════════════════════════════ */
function toast(msg, type = 'info') {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${icons[type]}</span><span>${escHtml(msg)}</span>`;
  container.appendChild(el);

  setTimeout(() => {
    el.style.transition = 'opacity .3s, transform .3s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(20px)';
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

/* ══════════════════════════════════════════════
   SECURITY HELPERS
══════════════════════════════════════════════ */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escAttr(str) {
  return String(str).replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}
// Expose state ke global untuk onclick inline
window.state = state;
