/* app.js — generador de catálogos v3 (catalogo_id fijo, ya no categorías Woo) */

const MARCAS = {
  xtrong: { color: '#005654', acento: '#B6FF00' },
  xecuro: { color: '#303830', acento: '#FFAD40' },
};

// Se llena al cargar la página con GET /api/catalogos:
// { xtrong: [{key, nombre, disponible}, ...], xecuro: [{key, nombre, disponible}, ...] }
let CATALOGOS_POR_MARCA = null;

const NOMBRE_MARCA = { xtrong: 'XTRONG', xecuro: 'XECURO' };

let marcaActual  = 'xtrong';
let tipoActual   = null;
let jobActual    = null;
let pollInterval = null;

// Modo de generación: 'tipo' (por tipo de catálogo) o 'referencia' (por SKU/modelo).
let modoActual = 'tipo';
let referenciaActual = null;

// Se llena bajo demanda con GET /api/referencias?marca=...:
// { xtrong: [{value, label, catalogo_id}, ...] | null, xecuro: [...] | null }
// null = todavía no se cargó para esa marca.
let REFERENCIAS_POR_MARCA = { xtrong: null, xecuro: null };

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  document.querySelectorAll('input[name="marca"]').forEach(r => {
    r.addEventListener('change', e => seleccionarMarca(e.target.value));
  });
  document.getElementById('btn-gen').addEventListener('click', iniciarGeneracion);
  document.getElementById('select-referencia').addEventListener('change', e => {
    referenciaActual = e.target.value || null;
  });

  // Checkboxes de precio — ambos independientes, ambos desmarcados por defecto
  ['mayor', 'detal'].forEach(tipo => {
    const input = document.getElementById(`chk-precio-${tipo}`);
    const opt   = document.getElementById(`opt-precio-${tipo}`);
    input.addEventListener('change', () => {
      opt.classList.toggle('checked', input.checked);
    });
  });

  await cargarCatalogos();

  // Aplicar selección visual de XTRONG al cargar
  seleccionarMarca('xtrong');
});

async function cargarCatalogos() {
  const lista = document.getElementById('cat-tipo-list');
  try {
    const r = await fetch('/api/catalogos');
    const d = await r.json();
    CATALOGOS_POR_MARCA = { xtrong: [], xecuro: [] };
    (d.catalogos || []).forEach(c => {
      CATALOGOS_POR_MARCA[c.marca].push({
        key:        c.id,
        nombre:     c.nombre,
        disponible: c.disponible !== false,
      });
    });
  } catch (e) {
    CATALOGOS_POR_MARCA = { xtrong: [], xecuro: [] };
    lista.innerHTML = '<div class="cat-loading">No se pudo cargar la lista de catálogos. Recarga la página.</div>';
  }
}

// ── Marca ─────────────────────────────────────────────────────────────────

function seleccionarMarca(marca) {
  marcaActual = marca;
  tipoActual  = null;

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
  renderTipos();

  if (modoActual === 'referencia') cargarReferencias(marcaActual);
}

function actualizarTheme() {
  const cfg = MARCAS[marcaActual];
  document.documentElement.style.setProperty('--marca-color',  cfg.color);
  document.documentElement.style.setProperty('--marca-acento', cfg.acento);
}

// ── Tipos de catálogo ─────────────────────────────────────────────────────

function renderTipos() {
  const lista = document.getElementById('cat-tipo-list');
  const tipos = CATALOGOS_POR_MARCA ? CATALOGOS_POR_MARCA[marcaActual] : null;

  if (!tipos) {
    lista.innerHTML = '<div class="cat-loading">Cargando catálogos...</div>';
    return;
  }
  if (tipos.length === 0) {
    lista.innerHTML = '<div class="cat-loading">No hay catálogos configurados para esta marca.</div>';
    return;
  }

  // Seleccionar primero disponible por defecto
  if (!tipoActual || !tipos.find(t => t.key === tipoActual && t.disponible)) {
    const primeroDisponible = tipos.find(t => t.disponible);
    tipoActual = primeroDisponible ? primeroDisponible.key : null;
  }

  lista.innerHTML = tipos.map(t => {
    const sel = t.key === tipoActual && t.disponible;
    const cls = [
      sel ? `selected-${marcaActual}` : '',
      t.disponible ? '' : 'disabled',
    ].filter(Boolean).join(' ');
    const rCls = sel ? `checked-${marcaActual}` : '';
    const click = t.disponible ? `onclick="seleccionarTipo('${t.key}')"` : '';
    const msg = t.disponible
      ? ''
      : `<div class="cat-tipo-msg">No hay inventario de repuestos para ${NOMBRE_MARCA[marcaActual]}</div>`;
    return `
      <div class="cat-tipo-item ${cls}" data-key="${t.key}" ${click}>
        <div class="cat-tipo-radio ${rCls}"><div class="radio-dot"></div></div>
        <div class="cat-tipo-info">
          <div class="cat-tipo-nombre">${t.nombre}</div>
          ${msg}
        </div>
      </div>`;
  }).join('');
}

function seleccionarTipo(key) {
  const tipos = CATALOGOS_POR_MARCA ? CATALOGOS_POR_MARCA[marcaActual] : null;
  const t = tipos && tipos.find(x => x.key === key);
  if (!t || !t.disponible) return;
  tipoActual = key;
  renderTipos();
}

// ── Modo de generación (tipo de catálogo vs. referencia) ────────────────────

function seleccionarModo(modo) {
  modoActual = modo;

  document.getElementById('modo-tipo').classList.toggle('selected', modo === 'tipo');
  document.getElementById('modo-referencia').classList.toggle('selected', modo === 'referencia');
  document.getElementById('card-cats').style.display       = modo === 'tipo' ? '' : 'none';
  document.getElementById('card-referencia').style.display = modo === 'referencia' ? '' : 'none';

  if (modo === 'referencia') cargarReferencias(marcaActual);
}

async function cargarReferencias(marca) {
  if (REFERENCIAS_POR_MARCA[marca] === null) {
    const select = document.getElementById('select-referencia');
    select.innerHTML = '<option value="">Cargando...</option>';
    try {
      const r = await fetch(`/api/referencias?marca=${marca}`);
      const d = await r.json();
      REFERENCIAS_POR_MARCA[marca] = d.referencias || [];
    } catch (e) {
      REFERENCIAS_POR_MARCA[marca] = [];
    }
  }
  // Puede haber cambiado la marca mientras cargaba: renderizar solo si sigue vigente.
  if (marca === marcaActual) renderReferencias();
}

function renderReferencias() {
  const select = document.getElementById('select-referencia');
  const vacio  = document.getElementById('referencia-vacio');
  const lista  = REFERENCIAS_POR_MARCA[marcaActual] || [];

  referenciaActual = null;

  if (lista.length === 0) {
    select.innerHTML = '<option value="">— sin referencias disponibles —</option>';
    vacio.style.display = 'block';
    return;
  }

  vacio.style.display = 'none';
  select.innerHTML = '<option value="">Selecciona una referencia...</option>' +
    lista.map(r =>
      `<option value="${r.value}" data-catalogo-id="${r.catalogo_id}">${r.label}</option>`
    ).join('');
}

// ── Generación ────────────────────────────────────────────────────────────

async function iniciarGeneracion() {
  const periodo = document.getElementById('periodo').value.trim();

  let catalogoId  = null;
  let referencia  = null;

  if (modoActual === 'referencia') {
    const select = document.getElementById('select-referencia');
    if (!select.value) {
      alert('Selecciona una referencia.');
      return;
    }
    referencia = select.value;
    catalogoId = select.selectedOptions[0].dataset.catalogoId;
  } else {
    if (!tipoActual) {
      alert('Selecciona un tipo de catálogo.');
      return;
    }
    catalogoId = tipoActual;
  }

  const btn = document.getElementById('btn-gen');
  btn.disabled    = true;
  btn.textContent = 'Generando...';
  document.getElementById('card-progreso').style.display = 'block';
  document.getElementById('card-progreso').scrollIntoView({ behavior: 'smooth' });
  document.getElementById('avisos-box').innerHTML = '';
  setNavStatus('busy', 'Generando...');

  const payload = {
    catalogo_id:   catalogoId,
    periodo:       periodo,
    precio_mayor:  document.getElementById('chk-precio-mayor').checked,
    precio_detal:  document.getElementById('chk-precio-detal').checked,
  };
  if (referencia) payload.referencia = referencia;

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

      actualizarProgreso(d.progreso, d.logs[d.logs.length - 1] || '');

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
  if (label) {
    const txt = label.replace(/^[\s\S]{0,3}/, '').slice(0, 60);
    document.getElementById('prog-label').textContent = label.slice(0, 70);
  }
}

function addAviso(msg, tipo) {
  const box  = document.getElementById('avisos-box');
  const now  = new Date();
  const time = now.toTimeString().slice(0, 8);
  let cls = '';
  if (msg.includes('✅') || msg.includes('listo')) cls = 'ok';
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
  dot.className    = `nav-dot ${state === 'ok' ? '' : state}`;
  span.textContent = text;
}
