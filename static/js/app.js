/* app.js — generador de catálogos v2 */

const MARCAS = {
  xtrong: { color: '#005654', acento: '#B6FF00' },
  xecuro: { color: '#303830', acento: '#FFAD40' },
};

// Tipos de catálogo por marca con sus categorías WooCommerce asociadas
const TIPOS_CATALOGO = {
  xtrong: [
    {
      key:    'abatibles_abiertos',
      nombre: 'Cascos abatibles y abiertos',
      desc:   'Abatibles, Abiertos',
      cats:   ['Abatibles', 'Abiertos'],
    },
    {
      key:    'integrales',
      nombre: 'Cascos integrales',
      desc:   'Integrales, Carretera, Multipropósito',
      cats:   ['Integrales', 'Carretera', 'Multipropósito'],
    },
    {
      key:    'textiles_accesorios',
      nombre: 'Textiles y accesorios',
      desc:   'Chaquetas, Guantes, Impermeables y más',
      cats:   ['Chaquetas', 'Guantes', 'IMPERMEABLES', 'Tela', 'Urbanas',
               'ACCESORIOS', 'Candados', 'INTERCOMS', 'Intercomunicadores',
               'Rodilleras y Coderas', 'Body armors', 'INDUMENTARIA DE PROTECCIÓN',
               'Antiempañantes', 'Cobertores/Pijamas', 'Caña corta'],
    },
  ],
  xecuro: null, // dinámico desde API
};

let marcaActual  = 'xtrong';
let tipoActual   = 'abatibles_abiertos';
let jobActual    = null;
let pollInterval = null;

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('input[name="marca"]').forEach(r => {
    r.addEventListener('change', e => seleccionarMarca(e.target.value));
  });
  document.getElementById('btn-gen').addEventListener('click', iniciarGeneracion);

  // Aplicar selección visual de XTRONG al cargar
  seleccionarMarca('xtrong');
});

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
}

function actualizarTheme() {
  const cfg = MARCAS[marcaActual];
  document.documentElement.style.setProperty('--marca-color',  cfg.color);
  document.documentElement.style.setProperty('--marca-acento', cfg.acento);
}

// ── Tipos de catálogo ─────────────────────────────────────────────────────

function renderTipos() {
  const lista = document.getElementById('cat-tipo-list');
  const tipos = TIPOS_CATALOGO[marcaActual];

  if (!tipos) {
    lista.innerHTML = '<div class="cat-loading">Cargando tipos...</div>';
    return;
  }

  // Seleccionar primero por defecto
  if (!tipoActual || !tipos.find(t => t.key === tipoActual)) {
    tipoActual = tipos[0].key;
  }

  lista.innerHTML = tipos.map(t => {
    const sel = t.key === tipoActual;
    const cls = sel ? `selected-${marcaActual}` : '';
    const rCls = sel ? `checked-${marcaActual}` : '';
    return `
      <div class="cat-tipo-item ${cls}" data-key="${t.key}" onclick="seleccionarTipo('${t.key}')">
        <div class="cat-tipo-radio ${rCls}"><div class="radio-dot"></div></div>
        <div class="cat-tipo-info">
          <div class="cat-tipo-nombre">${t.nombre}</div>
          <div class="cat-tipo-desc">${t.desc}</div>
        </div>
      </div>`;
  }).join('');
}

function seleccionarTipo(key) {
  tipoActual = key;
  renderTipos();
}

// ── Generación ────────────────────────────────────────────────────────────

async function iniciarGeneracion() {
  const periodo = document.getElementById('periodo').value.trim();

  if (!tipoActual) {
    alert('Selecciona un tipo de catálogo.');
    return;
  }

  const tipos = TIPOS_CATALOGO[marcaActual];
  const tipo  = tipos ? tipos.find(t => t.key === tipoActual) : null;
  if (!tipo) {
    alert('Tipo de catálogo no válido.');
    return;
  }

  const btn = document.getElementById('btn-gen');
  btn.disabled    = true;
  btn.textContent = 'Generando...';
  document.getElementById('card-progreso').style.display = 'block';
  document.getElementById('card-progreso').scrollIntoView({ behavior: 'smooth' });
  document.getElementById('avisos-box').innerHTML = '';
  setNavStatus('busy', 'Generando...');

  const payload = {
    marca:           marcaActual,
    titulo:          tipo.nombre,
    tipo_catalogo:   tipo.key,
    periodo:         periodo,
    categorias:      tipo.cats,
    mostrar_precios: true,
    solo_stock:      true,
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
