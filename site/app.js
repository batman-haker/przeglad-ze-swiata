/* ============================================================
   Tablica Świat — app.js
   ============================================================ */

const SPOTLIGHT_WATEK = 'iran-2025';
const SPOTLIGHT_LABEL = 'Konflikt Iran / Ormuz';

let allEvents = [];
let activeFilter = 'all';
let searchQuery  = '';

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement('script');
    s.src = src; s.onload = resolve; s.onerror = reject;
    document.head.appendChild(s);
  });
}
function loadCSS(href) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const l = document.createElement('link');
  l.rel = 'stylesheet'; l.href = href;
  document.head.appendChild(l);
}

// Charts & map state
let chartsInit   = false;
let mapInit      = false;
let leafletMap   = null;

// ============================================================
// Init
// ============================================================

async function init() {
  try {
    const resp = await fetch('events.json?v=' + Date.now());
    if (!resp.ok) throw new Error('Brak events.json');
    allEvents = (await resp.json()).slice(0, 300);
  } catch (e) {
    document.getElementById('timeline').innerHTML =
      `<div class="no-results">Nie można załadować danych.<br><small>${e.message}</small></div>`;
    return;
  }

  setupViewNav();
  setupFilters();
  setupSearch();
  renderTimeline();
  updateMeta();
  setupEntityModal();
}

// ============================================================
// View navigation
// ============================================================

function setupViewNav() {
  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;

      document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

      btn.classList.add('active');
      document.getElementById('view-' + view).classList.add('active');

      if (view === 'analiza') { renderAnaliza(); }
      if (view === 'market')  { renderMarketAnalysis(); }
      if (view === 'iran')    { renderIran(); }
      if (view === 'makro')   { renderMakro(); }
      if (view === 'rynki')    { renderRynki(); }
      if (view === 'heatmapa') { renderHeatmapa(); }
    });
  });
}

// ============================================================
// Meta
// ============================================================

function updateMeta() {
  document.getElementById('event-count').textContent = allEvents.length;
  if (!allEvents.length) return;
  const d = new Date(allEvents[0].datetime);
  document.getElementById('last-update').textContent =
    d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
}

// ============================================================
// Spotlight
// ============================================================

function renderSpotlight() {
  const items = allEvents.filter(e => e.watek === SPOTLIGHT_WATEK).slice(0, 8);
  if (!items.length) return;

  document.getElementById('spotlight').removeAttribute('hidden');
  document.getElementById('spotlight-title').textContent = SPOTLIGHT_LABEL;

  const container = document.getElementById('spotlight-events');
  container.innerHTML = '';
  items.forEach(e => {
    const chip = document.createElement('div');
    chip.className = 'spotlight-chip';
    chip.textContent = e.haslo;
    chip.title = e.haslo;
    chip.addEventListener('click', () => {
      // switch to timeline view
      document.querySelectorAll('.view-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.view === 'timeline');
      });
      document.querySelectorAll('.view').forEach(v => {
        v.classList.toggle('active', v.id === 'view-timeline');
      });
      activeFilter = 'all';
      searchQuery  = e.haslo.split(' ').slice(0, 3).join(' ');
      document.getElementById('search').value = searchQuery;
      updateFilterButtons();
      renderTimeline();
      document.getElementById('timeline').scrollIntoView({ behavior: 'smooth' });
    });
    container.appendChild(chip);
  });
}

// ============================================================
// Filters & search
// ============================================================

function setupFilters() {
  document.getElementById('filters').addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    activeFilter = btn.dataset.filter;
    updateFilterButtons();
    renderTimeline();
  });
}

function updateFilterButtons() {
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === activeFilter);
  });
}

function setupSearch() {
  const input = document.getElementById('search');
  let timer;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      searchQuery = input.value.trim().toLowerCase();
      renderTimeline();
    }, 220);
  });
}

const EDITORIAL_RE = /zobacz\s+skr[oó]t|zapraszam\s+(do|na)|skr[oó]ty?\s+(nocn|porann|wieczorn|numer\s*\d|nr\s*\d)|nocne\s+numer|poranne\s+numer|to\s+ju[zż]\s+wszystko|kr[oó]tkie\s+info\s+nr|skr[oó]t\s+info\s+nr|(info|skr[oó]t)\s+nr\s*\d.*godzin/i;

function isEditorial(e) {
  const txt = (e.raw_fragment || e.haslo || '');
  if (EDITORIAL_RE.test(txt)) return true;
  if (txt.length < 35 && /skr[oó]t/i.test(txt)) return true;
  return false;
}

function filtered() {
  return allEvents.filter(e => {
    if (isEditorial(e)) return false;
    if (activeFilter !== 'all' && e.kategoria !== activeFilter) return false;
    if (searchQuery) {
      const hay = [e.haslo, e.rozwiniecie, ...(e.podmioty || [])].join(' ').toLowerCase();
      if (!hay.includes(searchQuery)) return false;
    }
    return true;
  });
}

// ============================================================
// Timeline view
// ============================================================

function renderTimeline() {
  const events = filtered();
  const timeline = document.getElementById('timeline');
  timeline.innerHTML = '';

  if (!events.length) {
    timeline.innerHTML = '<div class="no-results">Brak wyników.</div>';
    return;
  }

  const groups = new Map();
  events.forEach(e => {
    const day = e.datetime.slice(0, 10);
    if (!groups.has(day)) groups.set(day, []);
    groups.get(day).push(e);
  });

  groups.forEach((dayEvents, day) => {
    const group = document.createElement('div');
    group.className = 'date-group';
    group.innerHTML = `
      <div class="date-header">
        <span class="date-label">${formatDay(day)}</span>
        <div class="date-line"></div>
        <span class="date-label" style="opacity:.5">${dayEvents.length}</span>
      </div>`;
    dayEvents.forEach(e => group.appendChild(buildCard(e)));
    timeline.appendChild(group);
  });
}

function formatDay(isoDate) {
  const d = new Date(isoDate + 'T12:00:00Z');
  return d.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long' });
}

function buildCard(event) {
  const card = document.createElement('div');
  card.className = 'event-card';
  card.dataset.id = event.id;

  const time     = event.datetime.slice(11, 16);
  const podmiotyChips = (event.podmioty || []).slice(0, 3)
    .map(p => `<span class="tag-podmioty" data-entity="${esc(p)}">${esc(p)}</span>`)
    .join('');
  const katClass = `kat-${event.kategoria}`;

  const punktyHtml = (event.punkty && event.punkty.length)
    ? `<ul class="detail-punkty">${event.punkty.map(p => `<li>${esc(p)}</li>`).join('')}</ul>`
    : '';

  card.innerHTML = `
    <div class="card-main">
      <div class="card-waga waga-${event.waga}"></div>
      <div class="card-body">
        <div class="card-haslo">${esc(event.haslo)}</div>
        <div class="card-tags">
          <span class="tag-kat ${katClass}">${event.kategoria}</span>
          ${event.watek ? `<span class="tag-watek">${event.watek}</span>` : ''}
          ${podmiotyChips}
        </div>
      </div>
      <span class="card-time">${time}</span>
      <span class="card-arrow">▾</span>
    </div>
    <div class="card-detail">
      <div class="detail-rozw">${esc(event.rozwiniecie)}</div>
      ${punktyHtml}
      <div class="detail-meta">
        <span><b>Waga:</b> ${event.waga}</span>
        <span><b>Typ:</b> ${event.typ}</span>
        ${event.region ? `<span><b>Region:</b> ${esc(event.region)}</span>` : ''}
      </div>
      <div class="detail-source">
        <a href="${event.post_url}" target="_blank" rel="noopener">Zrodlo na X</a>
      </div>
    </div>`;

  card.querySelector('.card-main').addEventListener('click', () => {
    card.classList.toggle('expanded');
  });

  return card;
}

// ============================================================
// Dashboard — Chart.js
// ============================================================

const CAT_COLORS = {
  geopolityka: '#ef4444',
  gospodarka:  '#f59e0b',
  rynki:       '#10b981',
  energia:     '#f97316',
  technologia: '#8b5cf6',
  polska:      '#e11d48',
};

const WAGA_COLORS = {
  high:   '#ef4444',
  medium: '#f59e0b',
  low:    '#64748b',
};

function count(arr, key) {
  return arr.reduce((acc, e) => {
    acc[e[key]] = (acc[e[key]] || 0) + 1;
    return acc;
  }, {});
}

async function renderDashboard() {
  if (!allEvents.length) return;
  await loadScript('https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js');

  const chartDefaults = {
    animation: false,
    plugins: { legend: { labels: { color: '#8892a4' } } },
    scales: {},
  };

  // 1. Kategorie — doughnut
  const katCounts = count(allEvents, 'kategoria');
  new Chart(document.getElementById('chart-kategorie'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(katCounts),
      datasets: [{
        data: Object.values(katCounts),
        backgroundColor: Object.keys(katCounts).map(k => CAT_COLORS[k] || '#4b5563'),
        borderColor: '#1e2333',
        borderWidth: 2,
      }],
    },
    options: { ...chartDefaults },
  });

  // 2. Waga — bar horizontal
  const wagaCounts = count(allEvents, 'waga');
  const wagaOrder  = ['high', 'medium', 'low'];
  new Chart(document.getElementById('chart-waga'), {
    type: 'bar',
    data: {
      labels: wagaOrder.map(w => ({ high: 'Wysoka', medium: 'Srednia', low: 'Niska' }[w])),
      datasets: [{
        data: wagaOrder.map(w => wagaCounts[w] || 0),
        backgroundColor: wagaOrder.map(w => WAGA_COLORS[w]),
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4' }, grid: { color: '#2a2f42' } },
        y: { ticks: { color: '#8892a4' }, grid: { display: false } },
      },
    },
  });

  // 3. Aktywnosc per dzien — line
  const dayCounts = {};
  allEvents.forEach(e => {
    const d = e.datetime.slice(0, 10);
    dayCounts[d] = (dayCounts[d] || 0) + 1;
  });
  const days = Object.keys(dayCounts).sort();
  new Chart(document.getElementById('chart-aktywnosc'), {
    type: 'line',
    data: {
      labels: days,
      datasets: [{
        label: 'Wydarzen',
        data: days.map(d => dayCounts[d]),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,.15)',
        fill: true,
        tension: .3,
        pointRadius: 2,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4', maxTicksLimit: 10 }, grid: { color: '#2a2f42' } },
        y: { ticks: { color: '#8892a4' }, grid: { color: '#2a2f42' } },
      },
    },
  });

  // 4. Top 10 podmiotow — bar
  const podmiotyCounts = {};
  allEvents.forEach(e => {
    (e.podmioty || []).forEach(p => {
      podmiotyCounts[p] = (podmiotyCounts[p] || 0) + 1;
    });
  });
  const topPodmioty = Object.entries(podmiotyCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);
  new Chart(document.getElementById('chart-podmioty'), {
    type: 'bar',
    data: {
      labels: topPodmioty.map(([p]) => p),
      datasets: [{
        data: topPodmioty.map(([, n]) => n),
        backgroundColor: '#3b82f6',
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4' }, grid: { color: '#2a2f42' } },
        y: { ticks: { color: '#8892a4', font: { size: 11 } }, grid: { display: false } },
      },
    },
  });

  // 5. Typy wydarzen — doughnut
  const typCounts = count(allEvents, 'typ');
  const typEntries = Object.entries(typCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const palette = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#f97316','#e11d48','#64748b'];
  new Chart(document.getElementById('chart-typy'), {
    type: 'doughnut',
    data: {
      labels: typEntries.map(([t]) => t),
      datasets: [{
        data: typEntries.map(([, n]) => n),
        backgroundColor: palette,
        borderColor: '#1e2333',
        borderWidth: 2,
      }],
    },
    options: { ...chartDefaults },
  });
}

// ============================================================
// Mapa — Leaflet
// ============================================================

const REGION_COORDS = {
  'USA':               [38, -97],
  'Stany Zjednoczone': [38, -97],
  'UE':                [50, 10],
  'Europa':            [50, 15],
  'Niemcy':            [51, 10],
  'Polska':            [52, 20],
  'Rosja':             [60, 90],
  'Ukraina':           [49, 32],
  'Chiny':             [35, 105],
  'Izrael':            [31.5, 35],
  'Iran':              [32, 53],
  'Arabia Saudyjska':  [24, 45],
  'Turcja':            [39, 35],
  'Francja':           [46, 2],
  'UK':                [52, -1],
  'Wielka Brytania':   [52, -1],
  'Japonia':           [36, 138],
  'Korea Poludniowa':  [36, 128],
  'India':             [20, 77],
  'Indie':             [20, 77],
  'Brazylia':          [-15, -53],
  'Australia':         [-25, 133],
  'Bliski Wschód':     [27, 45],
  'Azja':              [34, 100],
  'Afryka':            [0, 25],
  'Ameryka Lacinska':  [-15, -60],
  'Kanada':            [60, -96],
  'Meksyk':            [23, -102],
  'Hiszpania':         [40, -3],
  'Wlochy':            [42, 12],
  'Holandia':          [52, 5],
  'Szwecja':           [62, 15],
  'Norwegia':          [64, 15],
  'Finlandia':         [64, 26],
  'Serbia':            [44, 21],
  'Wegry':             [47, 19],
  'Syria':             [35, 38],
  'Irak':              [33, 44],
  'Jemen':             [15, 48],
  'Pakistan':          [30, 70],
  'Afganistan':        [33, 65],
  'Tajwan':            [23.5, 121],
  'Wietnam':           [16, 108],
  'Tajlandia':         [15, 101],
  'Mjanma':            [17, 96],
  'Nigeria':           [9, 8],
  'Egipt':             [26, 30],
  'RPA':               [-29, 25],
  'Maroko':            [32, -6],
  'Algieria':          [28, 3],
  'Libia':             [27, 17],
  'Sudan':             [15, 30],
  'Etiopia':           [9, 40],
  'Kenia':             [0, 38],
  'Wenezuela':         [8, -66],
  'Kolumbia':          [4, -74],
  'Argentyna':         [-34, -64],
  'Chile':             [-30, -71],
  'Peru':              [-10, -76],
  'Globalnie':         [20, 0],
  'Swiat':             [20, 0],
};

function getCoords(event) {
  if (!event.region) return null;
  const r = event.region;
  if (REGION_COORDS[r]) return REGION_COORDS[r];
  // try partial match
  for (const key of Object.keys(REGION_COORDS)) {
    if (r.includes(key) || key.includes(r)) return REGION_COORDS[key];
  }
  return null;
}

async function renderMap() {
  loadCSS('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css');
  await loadScript('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js');
  if (!leafletMap) {
    leafletMap = L.map('leaflet-map', { zoomControl: true }).setView([20, 10], 2);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(leafletMap);
    mapInit = true;
  } else {
    // clear old markers
    leafletMap.eachLayer(layer => {
      if (layer instanceof L.CircleMarker) leafletMap.removeLayer(layer);
    });
  }

  // build legend
  const legend = document.getElementById('map-legend');
  legend.innerHTML = Object.entries(CAT_COLORS)
    .map(([k, c]) => `<div class="legend-item"><div class="legend-dot" style="background:${c}"></div>${k}</div>`)
    .join('');

  // bucket events by coords
  const buckets = new Map();
  allEvents.forEach(e => {
    const coords = getCoords(e);
    if (!coords) return;
    const key = coords.join(',');
    if (!buckets.has(key)) buckets.set(key, { coords, events: [] });
    buckets.get(key).events.push(e);
  });

  buckets.forEach(({ coords, events: evs }) => {
    const topKat = evs.reduce((acc, e) => {
      acc[e.kategoria] = (acc[e.kategoria] || 0) + 1;
      return acc;
    }, {});
    const dominant = Object.entries(topKat).sort((a, b) => b[1] - a[1])[0][0];
    const color = CAT_COLORS[dominant] || '#3b82f6';
    const r = Math.min(5 + evs.length * 1.5, 22);

    const circle = L.circleMarker(coords, {
      radius: r,
      fillColor: color,
      color: '#0f1117',
      weight: 1.5,
      fillOpacity: 0.75,
    }).addTo(leafletMap);

    const topEvents = evs.slice(0, 5);
    const popupHtml = `
      <div style="font-size:12px;max-width:220px">
        <b style="color:${color}">${evs[0].region}</b> — ${evs.length} wydarzen<br><br>
        ${topEvents.map(e => `<div style="margin-bottom:4px">• ${esc(e.haslo)}</div>`).join('')}
      </div>`;
    circle.bindPopup(popupHtml);
  });

  // force map resize after display
  setTimeout(() => leafletMap.invalidateSize(), 100);
}

// ============================================================
// Analiza dnia — AI-powered (analyses.json)
// ============================================================

// ============================================================
// Analiza rynkowa AI
// ============================================================

let marketAnalysisInit = false;
async function renderMarketAnalysis() {
  if (marketAnalysisInit) return;
  marketAnalysisInit = true;

  const container = document.getElementById('mkt-container');

  let data;
  try {
    const resp = await fetch('market_analysis.json?v=' + Date.now());
    if (!resp.ok) throw new Error('Brak danych');
    data = await resp.json();
  } catch (e) {
    container.innerHTML = `<div class="no-results">Brak analizy rynkowej.<br><small>${e.message}</small></div>`;
    return;
  }

  const { market, analysis, generated_at, events_count } = data;
  const genDt = new Date(generated_at).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' });

  // — Nagłówek —
  let html = `
    <div class="mkt-header">
      <div class="mkt-headline">${esc(analysis.naglowek || '')}</div>
      <div class="mkt-meta">Analiza z ${genDt} · na podstawie ${events_count} newsów z 72h</div>
    </div>`;

  // — Tabela instrumentów pogrupowana —
  const groups = { indeksy: 'Indeksy', surowce: 'Surowce', crypto: 'Crypto', waluty: 'Waluty', akcje: 'Akcje' };
  html += `<div class="mkt-instruments">`;
  for (const [gKey, gLabel] of Object.entries(groups)) {
    const items = Object.values(market).filter(m => m.group === gKey);
    if (!items.length) continue;
    html += `<div class="mkt-group"><div class="mkt-group-title">${gLabel}</div><div class="mkt-group-items">`;
    for (const m of items) {
      const c1 = m.change_1d >= 0 ? 'pos' : 'neg';
      const c3 = m.change_3d >= 0 ? 'pos' : 'neg';
      const c5 = m.change_5d >= 0 ? 'pos' : 'neg';
      html += `
        <div class="mkt-item">
          <div class="mkt-item-name">${esc(m.name)}</div>
          <div class="mkt-item-price">${m.price.toLocaleString('pl-PL')}</div>
          <div class="mkt-item-changes">
            <span class="chg ${c1}">${m.change_1d >= 0 ? '+' : ''}${m.change_1d}%<small>1D</small></span>
            <span class="chg ${c3}">${m.change_3d >= 0 ? '+' : ''}${m.change_3d}%<small>3D</small></span>
            <span class="chg ${c5}">${m.change_5d >= 0 ? '+' : ''}${m.change_5d}%<small>5D</small></span>
          </div>
        </div>`;
    }
    html += `</div></div>`;
  }
  html += `</div>`;

  // — Sekcje analizy —
  const sections = [
    { key: 'trendy',     icon: '📊', label: 'Trendy rynkowe' },
    { key: 'korelacje',  icon: '🔗', label: 'Korelacje news ↔ rynek' },
    { key: 'sygnaly',    icon: '🎯', label: 'Sygnały dla tradera' },
  ];

  html += `<div class="mkt-sections">`;
  for (const { key, icon, label } of sections) {
    const items = analysis[key] || [];
    if (!items.length) continue;
    html += `<div class="mkt-section">
      <div class="mkt-section-title">${icon} ${label}</div>
      <ul class="mkt-list">
        ${items.map(t => `<li>${esc(t)}</li>`).join('')}
      </ul>
    </div>`;
  }

  if (analysis.uwaga) {
    html += `<div class="mkt-section mkt-uwaga">
      <div class="mkt-section-title">⚠️ Szum vs sygnał</div>
      <p>${esc(analysis.uwaga)}</p>
    </div>`;
  }
  html += `</div>`;

  container.innerHTML = html;
}

async function renderAnaliza() {
  const container = document.getElementById('analiza-container');
  container.innerHTML = '<div class="no-results">Ładowanie analizy…</div>';

  let analyses = [];
  try {
    const resp = await fetch('analyses.json?v=' + Date.now());
    if (resp.ok) analyses = await resp.json();
  } catch (e) {}

  container.innerHTML = '';

  if (!analyses.length) {
    container.innerHTML = '<div class="no-results">Brak analiz AI. Uruchom <code>python scripts/analyze.py</code> na serwerze.</div>';
    return;
  }

  analyses.forEach(a => {
    const dayEl = document.createElement('div');
    dayEl.className = 'analiza-day';

    // Header
    const header = document.createElement('div');
    header.className = 'analiza-day-header';
    header.innerHTML = `
      <span class="analiza-day-date">${esc(a.date_pl)}</span>
      <span class="analiza-day-count">${a.events_count} wydarzeń</span>`;
    dayEl.appendChild(header);

    // Nagłówek AI
    if (a.naglowek) {
      const nagl = document.createElement('div');
      nagl.className = 'analiza-naglowek';
      nagl.textContent = a.naglowek;
      dayEl.appendChild(nagl);
    }

    // Synteza
    if (a.synteza) {
      const sec = document.createElement('div');
      sec.className = 'analiza-section';
      sec.innerHTML = `
        <div class="analiza-section-label">Synteza</div>
        <div class="analiza-section-text">${esc(a.synteza)}</div>`;
      dayEl.appendChild(sec);
    }

    // Kontekst globalny + Perspektywa
    const twoCols = document.createElement('div');
    twoCols.className = 'analiza-two-col';
    if (a.kontekst_globalny) {
      const sec = document.createElement('div');
      sec.className = 'analiza-section';
      sec.innerHTML = `
        <div class="analiza-section-label">🌍 Kontekst globalny</div>
        <div class="analiza-section-text">${esc(a.kontekst_globalny)}</div>`;
      twoCols.appendChild(sec);
    }
    if (a.perspektywa) {
      const sec = document.createElement('div');
      sec.className = 'analiza-section';
      sec.innerHTML = `
        <div class="analiza-section-label">🔮 Perspektywa</div>
        <div class="analiza-section-text">${esc(a.perspektywa)}</div>`;
      twoCols.appendChild(sec);
    }
    if (twoCols.children.length) dayEl.appendChild(twoCols);

    // Kluczowe napięcia
    const tensions = a['kluczowe_napięcia'] || a['kluczowe_napiecia'] || [];
    if (tensions.length) {
      const tenSec = document.createElement('div');
      tenSec.className = 'analiza-tensions';
      tenSec.innerHTML = `<div class="analiza-section-label">⚡ Kluczowe napięcia</div>`;
      tensions.forEach(t => {
        const chip = document.createElement('span');
        chip.className = 'analiza-tension-chip';
        chip.textContent = t;
        tenSec.appendChild(chip);
      });
      dayEl.appendChild(tenSec);
    }

    container.appendChild(dayEl);
  });
}

// ============================================================
// Modal: Podmiot
// ============================================================

let entityChart = null;

function setupEntityModal() {
  document.getElementById('entity-modal-close')
    ?.addEventListener('click', closeEntityModal);
  document.querySelector('.entity-modal-backdrop')
    ?.addEventListener('click', closeEntityModal);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeEntityModal();
  });
  // Delegacja kliknięć na tagi podmiotów
  document.addEventListener('click', e => {
    const tag = e.target.closest('[data-entity]');
    if (tag) { e.stopPropagation(); openEntityView(tag.dataset.entity); }
  });
}

function closeEntityModal() {
  document.getElementById('entity-modal').classList.add('hidden');
}

function openEntityView(name) {
  const evs = allEvents
    .filter(e => (e.podmioty || []).includes(name))
    .slice()
    .sort((a, b) => b.datetime.localeCompare(a.datetime));

  if (!evs.length) return;

  document.getElementById('entity-modal-name').textContent = name;

  // Meta
  const dateFirst = evs[evs.length - 1].datetime.slice(0, 10);
  const dateLast  = evs[0].datetime.slice(0, 10);
  const katCount  = {};
  evs.forEach(e => { katCount[e.kategoria] = (katCount[e.kategoria] || 0) + 1; });
  const topKats = Object.entries(katCount).sort((a, b) => b[1] - a[1]);
  document.getElementById('entity-modal-meta').textContent =
    `${evs.length} wydarzeń · ${dateFirst} — ${dateLast}`;

  // Body
  const body = document.getElementById('entity-modal-body');
  body.innerHTML = '';

  // Kategorie
  const catsEl = document.createElement('div');
  catsEl.className = 'entity-cats';
  topKats.forEach(([k, n]) => {
    const pill = document.createElement('span');
    pill.className = `entity-cat-pill tag-kat kat-${k}`;
    pill.textContent = `${k} · ${n}`;
    catsEl.appendChild(pill);
  });
  body.appendChild(catsEl);

  // Lista wydarzeń
  evs.forEach(e => {
    const item = document.createElement('div');
    item.className = 'entity-event-item';
    const time = e.datetime.slice(0, 16).replace('T', ' ');
    const otherPodmioty = (e.podmioty || [])
      .filter(p => p !== name).slice(0, 2)
      .map(p => `<span class="tag-podmioty" data-entity="${esc(p)}">${esc(p)}</span>`)
      .join('');
    item.innerHTML = `
      <div class="entity-event-time">${time}</div>
      <div class="entity-event-content">
        <div class="entity-event-haslo">${esc(e.haslo)}</div>
        <div class="entity-event-rozw">${esc(e.rozwiniecie)}</div>
        <div class="entity-event-tags">
          <span class="tag-kat kat-${e.kategoria}">${e.kategoria}</span>
          <span class="entity-waga-dot ${e.waga}"></span>
          ${otherPodmioty}
        </div>
      </div>`;
    body.appendChild(item);
  });

  document.getElementById('entity-modal').classList.remove('hidden');
  body.scrollTop = 0;

  // Wykres aktywności
  const canvas = document.getElementById('entity-chart');
  if (entityChart) { entityChart.destroy(); entityChart = null; }

  const dayCounts = {};
  evs.forEach(e => {
    const d = e.datetime.slice(0, 10);
    dayCounts[d] = (dayCounts[d] || 0) + 1;
  });
  const days = Object.keys(dayCounts).sort();

  entityChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: days,
      datasets: [{
        data: days.map(d => dayCounts[d]),
        backgroundColor: 'rgba(59,130,246,.55)',
        borderColor: 'rgba(59,130,246,.9)',
        borderWidth: 1,
        borderRadius: 3,
      }],
    },
    options: {
      animation: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: {
        title: items => items[0].label,
        label:  item  => `${item.raw} wydarzeń`,
      }}},
      scales: {
        x: { ticks: { color: '#8892a4', font: { size: 10 }, maxTicksLimit: 10 }, grid: { color: '#2a2f42' } },
        y: { ticks: { color: '#8892a4', precision: 0 }, grid: { color: '#2a2f42' } },
      },
    },
  });
}

// ============================================================
// Iran timeline
// ============================================================

function renderIran() {
  const items = allEvents
    .filter(e => e.watek === SPOTLIGHT_WATEK)
    .slice()
    .sort((a, b) => b.datetime.localeCompare(a.datetime));

  document.getElementById('iran-count').textContent =
    `${items.length} wydarzen chronologicznie`;

  const container = document.getElementById('iran-timeline');
  container.innerHTML = '';

  if (!items.length) {
    container.innerHTML = '<div class="no-results">Brak wydarzen w watku Iran / Ormuz.</div>';
    return;
  }

  items.forEach(e => {
    const time = e.datetime.slice(5, 16).replace('T', ' ');
    const entry = document.createElement('div');
    entry.className = 'iran-entry';
    entry.innerHTML = `
      <div class="iran-time">${time}</div>
      <div class="iran-dot ${e.waga}"></div>
      <div class="iran-content">
        <div class="iran-haslo">${esc(e.haslo)}</div>
        <div class="iran-rozw">${esc(e.rozwiniecie)}</div>
        <div class="iran-meta">
          ${e.podmioty && e.podmioty.length ? esc(e.podmioty.slice(0, 3).join(' · ')) : ''}
          ${e.region ? ' &nbsp;|&nbsp; ' + esc(e.region) : ''}
        </div>
      </div>`;

    entry.querySelector('.iran-haslo').addEventListener('click', () => {
      entry.classList.toggle('open');
    });

    container.appendChild(entry);
  });
}

// ============================================================
// Heatmapa — S&P500 + Nasdaq
// ============================================================

let heatmapaInit = false;
function renderHeatmapa() {
  if (heatmapaInit) return;
  heatmapaInit = true;

  function injectHeatmap(containerId, dataSource) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div></div>`;
    const s = document.createElement('script');
    s.type = 'text/javascript';
    s.src = 'https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js';
    s.async = true;
    s.textContent = JSON.stringify({
      exchanges: [],
      dataSource,
      grouping: 'sector',
      blockSize: 'market_cap_basic',
      blockColor: 'change',
      locale: 'pl',
      symbolUrl: '',
      colorTheme: 'dark',
      hasTopBar: true,
      isDataSetEnabled: false,
      isZoomEnabled: true,
      hasSymbolTooltip: true,
      isMonoSize: false,
      width: '100%',
      height: '500'
    });
    container.querySelector('.tradingview-widget-container').appendChild(s);
  }

  injectHeatmap('heatmapa-sp500', 'SPX500');
  injectHeatmap('heatmapa-nasdaq', 'NASDAQ100');
}

// ============================================================
// Rynki — Market Overview TradingView
// ============================================================

function loadTickerChart(symbol) {
  const wrap = document.getElementById('ticker-chart-wrap');
  wrap.innerHTML = `<div class="tradingview-widget-container" style="height:420px"><div class="tradingview-widget-container__widget" style="height:420px"></div></div>`;
  const s = document.createElement('script');
  s.type = 'text/javascript';
  s.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  s.async = true;
  s.textContent = JSON.stringify({
    symbol: symbol.toUpperCase(),
    interval: 'D',
    timezone: 'Europe/Warsaw',
    theme: 'dark',
    style: '1',
    locale: 'pl',
    backgroundColor: 'rgba(9,12,18,1)',
    gridColor: 'rgba(30,42,63,0.5)',
    hide_top_toolbar: false,
    hide_legend: false,
    save_image: false,
    calendar: false,
    width: '100%',
    height: '420',
  });
  wrap.querySelector('.tradingview-widget-container').appendChild(s);
}

function setupTickerSearch() {
  const input = document.getElementById('ticker-input');
  const btn   = document.getElementById('ticker-search-btn');
  if (!input) return;
  const go = () => {
    const val = input.value.trim();
    if (val) loadTickerChart(val);
  };
  btn.addEventListener('click', go);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
}

let rynkiInit = false;
function renderRynki() {
  if (rynkiInit) return;
  rynkiInit = true;
  setupTickerSearch();
  const container = document.getElementById('rynki-overview');
  container.innerHTML = `<div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div></div>`;
  const s = document.createElement('script');
  s.type = 'text/javascript';
  s.src = 'https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js';
  s.async = true;
  s.textContent = JSON.stringify({
    colorTheme: 'dark',
    dateRange: '1M',
    showChart: true,
    locale: 'pl',
    width: '100%',
    height: '660',
    largeChartUrl: '',
    isTransparent: true,
    showSymbolLogo: true,
    showFloatingTooltip: true,
    tabs: [
      {
        title: 'Indeksy',
        symbols: [
          { s: 'FOREXCOM:SPXUSD', d: 'S&P 500' },
          { s: 'FOREXCOM:NSXUSD', d: 'Nasdaq 100' },
          { s: 'XETR:DAX',        d: 'DAX' },
          { s: 'GPW:WIG20',       d: 'WIG20' },
          { s: 'INDEX:NKY',       d: 'Nikkei' },
          { s: 'SSE:000001',      d: 'Shanghai' }
        ]
      },
      {
        title: 'Surowce',
        symbols: [
          { s: 'FOREXCOM:XAUUSD', d: 'Złoto' },
          { s: 'FOREXCOM:XAGUSD', d: 'Srebro' },
          { s: 'NYMEX:CL1!',      d: 'Ropa WTI' },
          { s: 'COMEX:HG1!',      d: 'Miedź' },
          { s: 'GPW:KGH',         d: 'KGHM' }
        ]
      },
      {
        title: 'Crypto',
        symbols: [
          { s: 'COINBASE:BTCUSD', d: 'Bitcoin' },
          { s: 'COINBASE:ETHUSD', d: 'Ethereum' },
          { s: 'COINBASE:SOLUSD', d: 'Solana' }
        ]
      },
      {
        title: 'Waluty',
        symbols: [
          { s: 'FX:USDPLN', d: 'USD/PLN' },
          { s: 'FX:EURPLN', d: 'EUR/PLN' },
          { s: 'FX:EURUSD', d: 'EUR/USD' },
          { s: 'FX:USDJPY', d: 'USD/JPY' }
        ]
      }
    ]
  });
  container.querySelector('.tradingview-widget-container').appendChild(s);
}

// ============================================================
// Makro — kalendarz ekonomiczny TradingView
// ============================================================

let makroInit = false;
function renderMakro() {
  if (makroInit) return;
  makroInit = true;

  const container = document.getElementById('makro-calendar');
  container.innerHTML = `
    <div class="tradingview-widget-container" style="height:600px">
      <div class="tradingview-widget-container__widget" style="height:600px"></div>
    </div>`;
  const s = document.createElement('script');
  s.type = 'text/javascript';
  s.src = 'https://s3.tradingview.com/external-embedding/embed-widget-events.js';
  s.async = true;
  s.textContent = JSON.stringify({
    colorTheme: 'dark',
    isTransparent: true,
    width: '100%',
    height: '600',
    locale: 'pl',
    importanceFilter: '1',
    countryFilter: 'us,eu,cn,gb'
  });
  container.querySelector('.tradingview-widget-container').appendChild(s);
}

// ============================================================
// Helpers
// ============================================================

function esc(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ============================================================
// Boot
// ============================================================
init();
