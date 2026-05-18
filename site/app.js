/* ============================================================
   Tablica Świat — app.js
   ============================================================ */

const SPOTLIGHT_WATEK = 'iran-2025';
const SPOTLIGHT_LABEL = 'Konflikt Iran / Ormuz';

let allEvents = [];
let activeFilter = 'all';
let searchQuery  = '';

// Charts & map state
let chartsInit   = false;
let mapInit      = false;
let graphInit    = false;
let leafletMap   = null;

// ============================================================
// Init
// ============================================================

async function init() {
  try {
    const resp = await fetch('events.json');
    if (!resp.ok) throw new Error('Brak events.json');
    allEvents = await resp.json();
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
  renderSpotlight();
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

      if (view === 'dashboard' && !chartsInit) { renderDashboard(); chartsInit = true; }
      if (view === 'map')       { renderMap(); }
      if (view === 'graph' && !graphInit) { renderGraph(); graphInit = true; }
      if (view === 'iran')      { renderIran(); }
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

function filtered() {
  return allEvents.filter(e => {
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
  const podmioty = (event.podmioty || []).slice(0, 3).join(', ');
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
          ${podmioty ? `<span class="tag-podmioty">${esc(podmioty)}</span>` : ''}
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

function renderDashboard() {
  if (!allEvents.length) return;

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

function renderMap() {
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
// Graf powiazań — D3
// ============================================================

function renderGraph() {
  const svg = document.getElementById('graph-svg');
  const W = svg.clientWidth || 900;
  const H = svg.clientHeight || 600;

  // build nodes & edges
  const nodeMap = new Map();
  const edgeMap = new Map();

  allEvents.forEach(e => {
    const ps = (e.podmioty || []).filter(Boolean);
    ps.forEach(p => {
      if (!nodeMap.has(p)) nodeMap.set(p, { id: p, count: 0, kat: e.kategoria });
      nodeMap.get(p).count++;
    });
    for (let i = 0; i < ps.length; i++) {
      for (let j = i + 1; j < ps.length; j++) {
        const key = [ps[i], ps[j]].sort().join('|||');
        edgeMap.set(key, (edgeMap.get(key) || 0) + 1);
      }
    }
  });

  // filter to top 60 nodes
  const nodes = [...nodeMap.values()]
    .sort((a, b) => b.count - a.count)
    .slice(0, 60);
  const nodeIds = new Set(nodes.map(n => n.id));

  const links = [...edgeMap.entries()]
    .map(([key, w]) => {
      const [s, t] = key.split('|||');
      return { source: s, target: t, weight: w };
    })
    .filter(l => nodeIds.has(l.source) && nodeIds.has(l.target) && l.weight >= 2);

  if (!nodes.length) return;

  const d3svg = d3.select('#graph-svg')
    .attr('viewBox', `0 0 ${W} ${H}`);
  d3svg.selectAll('*').remove();

  const g = d3svg.append('g');

  // zoom
  d3svg.call(d3.zoom().scaleExtent([.3, 4]).on('zoom', e => g.attr('transform', e.transform)));

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(80).strength(0.4))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide(d => rScale(d.count) + 3));

  const maxCount = d3.max(nodes, d => d.count) || 1;
  const rScale = count => 4 + (count / maxCount) * 18;

  const tooltip = document.getElementById('graph-tooltip');

  const link = g.append('g').selectAll('line')
    .data(links).join('line')
    .attr('stroke', '#2a2f42')
    .attr('stroke-width', d => Math.min(d.weight, 5))
    .attr('stroke-opacity', 0.6);

  const node = g.append('g').selectAll('circle')
    .data(nodes).join('circle')
    .attr('r', d => rScale(d.count))
    .attr('fill', d => CAT_COLORS[d.kat] || '#3b82f6')
    .attr('fill-opacity', 0.8)
    .attr('stroke', '#0f1117')
    .attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('mouseover', (event, d) => {
      tooltip.style.opacity = '1';
      tooltip.innerHTML = `<b>${d.id}</b><br>${d.count} wydarzen`;
    })
    .on('mousemove', event => {
      tooltip.style.left = (event.clientX + 12) + 'px';
      tooltip.style.top  = (event.clientY - 28) + 'px';
    })
    .on('mouseout', () => { tooltip.style.opacity = '0'; })
    .call(d3.drag()
      .on('start', (event, d) => { if (!event.active) sim.alphaTarget(.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on('end',   (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
    );

  const label = g.append('g').selectAll('text')
    .data(nodes.filter(d => d.count >= 3)).join('text')
    .text(d => d.id)
    .attr('fill', '#cbd5e1')
    .attr('font-size', d => Math.min(11, 7 + rScale(d.count) * 0.4))
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .style('pointer-events', 'none');

  sim.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('cx', d => d.x).attr('cy', d => d.y);
    label.attr('x', d => d.x).attr('y', d => d.y + rScale(d.count) + 10);
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
