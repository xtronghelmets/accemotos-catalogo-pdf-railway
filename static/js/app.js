/* app.js — lógica de la interfaz del generador de catálogos */

const MARCAS = {
  xtrong: { color: '#005654', acento: '#B6FF00' },
  xecuro: { color: '#303830', acento: '#FFAD40' },
};

let marcaActual    = 'xtrong';
let categoriasCats = {};   // marca → [nombres]
let selCats        = {};   // marca → Set de seleccionadas
let toggles        = { precios: true, stock: true, accesorios: false };
let jobActual      = null;
let pollInterval   = null;

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('input[name="marca"]').forEach(r => {
    r.addEventListener('change', e => seleccionarMarca(e.target.value));
  });

  document.querySelectorAll('.tog').forEach(t => {
    t.addEventListener('click', () => toggleSwitch(t));
  });

  document.getElementById('btn-gen').addEventListener('click', iniciarGeneracion);

  cargarCategorias('xtrong');
  cargarCategorias('xecuro');
  actualizarTheme();
  renderPreview();
});

// ── Marca ─────────────────────────────────────────────────────────────────

function seleccionarMarca(marca) {
  marcaActual = marca;

  ['xtrong', 'xecuro'].forEach(m => {
    const opt = document.getElementById(`opt-${m}`);
    const rc  = document.getElementById(`rc-${m}`);
    const bn  = document.getElementById(`bn-${m}`);
    const sel = m === marca;

    opt.className = `brand-option${sel ? ` selected-${m}` : ''}`;
    rc.className  = `radio-circle${sel ? ` checked-${m}` : ''}`;
    bn.className  = `brand-name${sel ? ` ${m}` : ''}`;
  });

  actualizarTheme();
  renderCategorias();
  renderPreview();
}

function actualizarTheme() {
  const cfg = MARCAS[marcaActual];
  document.documentElement.style.setProperty('--marca-color',  cfg.color);
  document.documentElement.style.setProperty('--marca-acento', cfg.acento);
}

// ── Categorías ────────────────────────────────────────────────────────────

async function cargarCategorias(marca) {
  try {
    const r = await fetch(`/api/categorias/${marca}`);
    const d = await r.json();
    if (d.categorias) {
      categoriasCats[marca] = d.categorias;
      selCats[marca] = new Set(d.categorias); // todas seleccionadas por defecto
      const sub = document.getElementById(`bs-${marca}`);
      const url = marca === 'xtrong' ? 'xtronghelmets.com' : 'xecurohelmets.com';
      sub.textContent = `${url} · ${d.categorias.length} categ.`;
    }
  } catch (e) {
    console.warn(`Error cargando categorías ${marca}:`, e);
  }
  if (marca === marcaActual) renderCategorias();
}

function renderCategorias() {
  const grid = document.getElementById('cat-grid');
  const cats = categoriasCats[marcaActual] || [];
  const sel  = selCats[marcaActual] || new Set();

  if (!cats.length) {
    grid.innerHTML = '<div class="cat-loading">Cargando categorías...</div>';
    return;
  }

  grid.innerHTML = cats.map(cat => {
    const on  = sel.has(cat);
    const cls = on ? `on-${marcaActual}` : '';
    const chk = on ? `<svg viewBox="0 0 9 7" fill="none"><path d="M1 3.5l2.5 2.5 4.5-5" stroke="#fff" stroke-width="1.4" stroke-linecap="round"/></svg>` : '';
    return `
      <div class="cat-chip ${cls}" data-cat="${esc(cat)}" onclick="toggleCat('${esc(cat)}')">
        <div class="chip-check ${cls}">${chk}</div>
        <span class="chip-label ${cls}">${cat}</span>
      </div>`;
  }).join('');
}

function toggleCat(cat) {
  const sel = selCats[marcaActual];
  if (!sel) return;
  if (sel.has(cat)) sel.delete(cat);
  else sel.add(cat);
  renderCategorias();
}

function esc(s) {
  return s.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ── Toggles ───────────────────────────────────────────────────────────────

function toggleSwitch(el) {
  const key = el.dataset.key;
  toggles[key] = !toggles[key];
  el.className = `tog ${toggles[key] ? 'on' : 'off'}`;
}

// ── Preview ───────────────────────────────────────────────────────────────

function renderPreview() {
  const strip  = document.getElementById('preview-strip');
  const cfg    = MARCAS[marcaActual];
  const acento = cfg.acento;
  const color  = cfg.color;
  const VISIBLE = 4;

  const makeLine = () => `<div class="p-thumb-line"></div>`;
  const makeThumb = () => `
    <div class="p-thumb">
      <div class="p-thumb-h" style="background:${color}"></div>
      <div class="p-thumb-body"><div class="p-thumb-rect"></div></div>
      <div class="p-thumb-foot">${makeLine()}${makeLine()}</div>
    </div>`;

  const cover = `
    <div class="p-thumb cover" style="background:${color}">
      <div class="p-thumb-body">
        <div style="width:24px;height:2px;background:${acento};border-radius:1px;opacity:.8;"></div>
        <div class="cover-label" style="color:${acento};">PORTADA</div>
      </div>
    </div>`;

  strip.innerHTML = cover + makeThumb().repeat(VISIBLE) + `<div class="p-more">···</div>`;
}

// ── Generación ────────────────────────────────────────────────────────────

async function iniciarGeneracion() {
  const titulo  = document.getElementById('titulo').value.trim();
  const periodo = document.getElementById('periodo').value.trim();
  const sel     = selCats[marcaActual] || new Set();

  if (sel.size === 0) {
    alert('Selecciona al menos una categoría.');
    return;
  }

  // UI: deshabilitar botón, mostrar card progreso
  const btn = document.getElementById('btn-gen');
  btn.disabled = true;
  btn.textContent = 'Generando...';
  document.getElementById('card-progreso').style.display = 'block';
  document.getElementById('card-progreso').scrollIntoView({ behavior: 'smooth' });
  document.getElementById('avisos-box').innerHTML = '';
  setNavStatus('busy', 'Generando...');

  const payload = {
    marca:           marcaActual,
    titulo:          titulo,
    periodo:         periodo,
    categorias:      [...sel],
    mostrar_precios: toggles.precios,
    solo_stock:      toggles.stock,
  };

  try {
    const r = await fetch('/api/generar', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    jobActual = d.job_id;
    iniciarPolling();
  } catch (e) {
    addAviso('❌ ' + e.message, 'err');
    resetBtn();
  }
}

function iniciarPolling() {
  if (pollInterval) clearInterval(pollInterval);
  let logCount = 0;

  pollInterval = setInterval(async () => {
    try {
      const r = await fetch(`/api/estado/${jobActual}`);
      const d = await r.json();

      // Progreso
      actualizarProgreso(d.progreso, d.logs[d.logs.length - 1] || '');

      // Nuevos logs
      const nuevos = d.logs.slice(logCount);
      nuevos.forEach(l => addAviso(l));
      logCount = d.logs.length;

      if (d.error) {
        clearInterval(pollInterval);
        addAviso('❌ ' + d.error, 'err');
        resetBtn();
        setNavStatus('error', 'Error');
      } else if (d.listo) {
        clearInterval(pollInterval);
        actualizarProgreso(100, '✅ PDF listo');
        setNavStatus('ok', 'Listo');
        // Descargar automáticamente
        window.location.href = `/api/descargar/${jobActual}`;
        resetBtn();
      }
    } catch (e) {
      console.warn('Polling error:', e);
    }
  }, 1200);
}

function actualizarProgreso(pct, label) {
  document.getElementById('prog-fill').style.width = pct + '%';
  document.getElementById('prog-pct').textContent  = pct + '%';
  if (label) document.getElementById('prog-label').textContent = label.replace(/^[^a-zA-Z0-9✅⚠️❌🔗📦🖼️📄💾]*/, '').slice(0, 60);
}

function addAviso(msg, tipo) {
  const box  = document.getElementById('avisos-box');
  const now  = new Date();
  const time = now.toTimeString().slice(0, 8);
  let cls    = '';
  if (msg.includes('✅') || msg.includes('listo') || msg.includes('Lista')) cls = 'ok';
  if (msg.includes('⚠️') || msg.includes('Sin imagen')) cls = 'warn';
  if (tipo === 'err' || msg.includes('❌')) cls = 'err';
  const line = document.createElement('div');
  line.className = 'aviso-line';
  line.innerHTML = `<span class="aviso-time">${time}</span><span class="aviso-text ${cls}">${msg}</span>`;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

function resetBtn() {
  const btn = document.getElementById('btn-gen');
  btn.disabled = false;
  btn.innerHTML = `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/>
    </svg>
    Generar y descargar catálogo`;
}

function setNavStatus(state, text) {
  const dot  = document.querySelector('.nav-dot');
  const span = document.querySelector('.nav-api-text');
  dot.className  = `nav-dot ${state === 'ok' ? '' : state}`;
  span.textContent = text;
}
